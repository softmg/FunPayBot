"use client";

import { ArrowDown, ArrowUp, ArrowUpDown, LoaderCircle, Search, ShoppingCart } from "lucide-react";
import type { FormEvent } from "react";
import { memo, useCallback, useMemo, useState } from "react";
import { formatPrice } from "@/lib/format";
import { type LotSort, type LotSortField, sortLots } from "@/lib/lot-sort";

type Lot = {
  title: string;
  url: string;
  price: string | null;
  reviews: number;
  warranty: string | null;
};

type BuyState = {
  pending: boolean;
  message: string;
  ok: boolean;
  paymentMethods?: PaymentMethod[];
};

type WarrantyState = {
  pending: boolean;
  error: string;
};

type PaymentMethod = {
  id: string;
  title: string;
  currency?: string | null;
  price?: string | null;
};

function paymentMethodLabel(method: PaymentMethod) {
  if (method.price) {
    return `${method.title} - ${method.price}`;
  }
  if (method.currency) {
    return `${method.title} (${method.currency.toUpperCase()})`;
  }
  return method.title;
}

function SortIcon({ active, direction }: { active: boolean; direction: LotSort["direction"] }) {
  if (!active) {
    return <ArrowUpDown size={16} />;
  }

  return direction === "asc" ? <ArrowUp size={16} /> : <ArrowDown size={16} />;
}

type LotRowProps = {
  lot: Lot;
  buyState: BuyState | undefined;
  warrantyState: WarrantyState | undefined;
  onBuy: (lot: Lot, paymentMethodId: string) => void;
  onLoadPaymentMethods: (lot: Lot) => void;
  onLoadWarranty: (lot: Lot) => void;
};

export function areLotRowPropsEqual(previous: LotRowProps, next: LotRowProps) {
  return (
    previous.lot === next.lot &&
    previous.buyState === next.buyState &&
    previous.warrantyState === next.warrantyState &&
    previous.onBuy === next.onBuy &&
    previous.onLoadPaymentMethods === next.onLoadPaymentMethods &&
    previous.onLoadWarranty === next.onLoadWarranty
  );
}

const LotRow = memo(function LotRow({
  lot,
  buyState,
  warrantyState,
  onBuy,
  onLoadPaymentMethods,
  onLoadWarranty
}: LotRowProps) {
  return (
    <tr>
      <td><a href={lot.url} rel="noreferrer" target="_blank">{lot.title}</a></td>
      <td>{formatPrice(lot.price)}</td>
      <td>{lot.reviews}</td>
      <td>
        {lot.warranty ? (
          lot.warranty
        ) : (
          <div className="grid">
            <span className="muted">Не найдена</span>
            <button
              className="button"
              disabled={warrantyState?.pending}
              onClick={() => onLoadWarranty(lot)}
              type="button"
            >
              {warrantyState?.pending ? <LoaderCircle className="spin" size={18} /> : <Search size={18} />}
              {warrantyState?.pending ? "Загружаем" : "Загрузить"}
            </button>
            {warrantyState?.error ? <div className="error-text">{warrantyState.error}</div> : null}
          </div>
        )}
      </td>
      <td>
        <button
          className="button"
          disabled={buyState?.pending}
          onClick={() => onLoadPaymentMethods(lot)}
          type="button"
        >
          {buyState?.pending ? <LoaderCircle className="spin" size={18} /> : <ShoppingCart size={18} />}
          {buyState?.pending ? "Загружаем" : "Купить"}
        </button>
        {buyState?.paymentMethods?.length ? (
          <form
            className="grid"
            onSubmit={(event) => {
              event.preventDefault();
              const formData = new FormData(event.currentTarget);
              const paymentMethodId = String(formData.get("payment_method_id") ?? "");
              if (paymentMethodId) {
                onBuy(lot, paymentMethodId);
              }
            }}
          >
            <select className="input" name="payment_method_id">
              {buyState.paymentMethods.map((method) => (
                <option key={method.id} value={method.id}>
                  {paymentMethodLabel(method)}
                </option>
              ))}
            </select>
            <button className="button" disabled={buyState.pending} type="submit">
              {buyState.pending ? <LoaderCircle className="spin" size={18} /> : <ShoppingCart size={18} />}
              Отправить ссылку
            </button>
          </form>
        ) : null}
        {buyState?.message ? (
          <div className={buyState.ok ? "success-text" : "error-text"}>{buyState.message}</div>
        ) : null}
      </td>
    </tr>
  );
}, areLotRowPropsEqual);

export default function SearchPanel() {
  const [lots, setLots] = useState<Lot[]>([]);
  const [sort, setSort] = useState<LotSort | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [buyStateByUrl, setBuyStateByUrl] = useState<Record<string, BuyState>>({});
  const [warrantyStateByUrl, setWarrantyStateByUrl] = useState<Record<string, WarrantyState>>({});
  const sortedLots = useMemo(() => sortLots(lots, sort), [lots, sort]);

  function toggleSort(field: LotSortField) {
    setSort((current) => {
      if (current?.field !== field) {
        return { field, direction: "asc" };
      }

      return { field, direction: current.direction === "asc" ? "desc" : "asc" };
    });
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    const forbidden = String(formData.get("forbidden_words") ?? "")
      .split(",")
      .map((word) => word.trim())
      .filter(Boolean);

    const response = await fetch("/api/lots/search", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        query: formData.get("query"),
        search_scope: formData.get("search_scope"),
        max_price: formData.get("max_price") || undefined,
        min_reviews: formData.get("min_reviews") || 0,
        forbidden_words: forbidden
      })
    });
    setPending(false);
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      setError(data.error ?? "Поиск не удался. Проверьте доступ к FunPay.");
      return;
    }
    const data = await response.json();
    setLots(data.results ?? []);
    setBuyStateByUrl({});
    setWarrantyStateByUrl({});
  }

  const loadPaymentMethods = useCallback(async (lot: Lot) => {
    setBuyStateByUrl((current) => ({
      ...current,
      [lot.url]: { ...current[lot.url], pending: true, message: "", ok: false }
    }));

    const response = await fetch("/api/orders/payment-methods", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ lot_url: lot.url })
    });
    const data = await response.json().catch(() => ({}));

    setBuyStateByUrl((current) => ({
      ...current,
      [lot.url]: {
        pending: false,
        message: response.ok ? "Выберите способ оплаты." : data.error ?? "Не удалось получить способы оплаты.",
        ok: response.ok,
        paymentMethods: response.ok ? data.payment_methods ?? [] : undefined
      }
    }));
  }, []);

  const buy = useCallback(async (lot: Lot, paymentMethodId: string) => {
    setBuyStateByUrl((current) => ({
      ...current,
      [lot.url]: { ...current[lot.url], pending: true, message: "", ok: false }
    }));

    const response = await fetch("/api/orders", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ lot_url: lot.url, payment_method_id: paymentMethodId })
    });
    const data = await response.json().catch(() => ({}));

    setBuyStateByUrl((current) => ({
      ...current,
      [lot.url]: {
        pending: false,
        message: response.ok
          ? data.payment_link
            ? data.telegram_notified
              ? "Ссылка оплаты отправлена в Telegram."
              : `Ссылка оплаты создана, но Telegram не уведомлен: ${data.payment_link}`
            : "Заказ создан. Ссылка оплаты пока не получена."
          : data.error ?? "Покупка не удалась.",
        ok: response.ok
      }
    }));
  }, []);

  const loadWarranty = useCallback(async (lot: Lot) => {
    setWarrantyStateByUrl((current) => ({
      ...current,
      [lot.url]: { pending: true, error: "" }
    }));

    const response = await fetch("/api/lots/warranty", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ url: lot.url, title: lot.title })
    });
    const data = await response.json().catch(() => ({}));

    if (response.ok) {
      setLots((current) =>
        current.map((item) =>
          item.url === lot.url ? { ...item, warranty: data.warranty ?? null } : item
        )
      );
    }

    setWarrantyStateByUrl((current) => ({
      ...current,
      [lot.url]: {
        pending: false,
        error: response.ok ? "" : data.error ?? "Не удалось загрузить гарантию."
      }
    }));
  }, []);

  return (
    <div className="grid">
      <form className="panel search-grid" onSubmit={submit}>
        <label className="field">
          <span className="label">Запрос</span>
          <input className="input" name="query" placeholder="steam, gmail, ..." />
        </label>
        <label className="field">
          <span className="label">Где искать</span>
          <select className="input" defaultValue="category" name="search_scope">
            <option value="category">Текущая категория</option>
            <option value="site">Весь сайт</option>
          </select>
        </label>
        <label className="field">
          <span className="label">Макс. цена</span>
          <input className="input" name="max_price" min="0" step="0.01" type="number" />
        </label>
        <label className="field">
          <span className="label">Мин. отзывов</span>
          <input className="input" defaultValue="0" min="0" name="min_reviews" type="number" />
        </label>
        <label className="field">
          <span className="label">Запрещённые слова</span>
          <input className="input" name="forbidden_words" placeholder="без гарантии, бан" />
        </label>
        <button className="button" disabled={pending} type="submit">
          {pending ? <LoaderCircle className="spin" size={18} /> : <Search size={18} />}
          {pending ? "Ищем" : "Искать"}
        </button>
      </form>

      {pending ? (
        <div aria-live="polite" className="search-status">
          <span className="search-pulse" />
          Идёт поиск лотов FunPay
        </div>
      ) : null}

      {error ? <div className="panel" style={{ color: "#b42318" }}>{error}</div> : null}

      <div className="panel">
        <table className="table">
          <thead>
            <tr>
              <th>Лот</th>
              <th>
                <button
                  aria-label={`Сортировать по цене ${
                    sort?.field === "price" && sort.direction === "asc" ? "по убыванию" : "по возрастанию"
                  }`}
                  className={`sort-button${sort?.field === "price" ? " sort-button-active" : ""}`}
                  onClick={() => toggleSort("price")}
                  type="button"
                >
                  Цена
                  <SortIcon active={sort?.field === "price"} direction={sort?.direction ?? "asc"} />
                </button>
              </th>
              <th>
                <button
                  aria-label={`Сортировать по отзывам ${
                    sort?.field === "reviews" && sort.direction === "asc" ? "по убыванию" : "по возрастанию"
                  }`}
                  className={`sort-button${sort?.field === "reviews" ? " sort-button-active" : ""}`}
                  onClick={() => toggleSort("reviews")}
                  type="button"
                >
                  Отзывы
                  <SortIcon active={sort?.field === "reviews"} direction={sort?.direction ?? "asc"} />
                </button>
              </th>
              <th>Гарантия</th>
              <th>Действие</th>
            </tr>
          </thead>
          <tbody>
            {sortedLots.map((lot) => {
              return (
                <LotRow
                  key={lot.url}
                  lot={lot}
                  buyState={buyStateByUrl[lot.url]}
                  warrantyState={warrantyStateByUrl[lot.url]}
                  onBuy={buy}
                  onLoadPaymentMethods={loadPaymentMethods}
                  onLoadWarranty={loadWarranty}
                />
              );
            })}
            {lots.length === 0 ? (
              <tr><td className="muted" colSpan={5}>Пока нет результатов.</td></tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
