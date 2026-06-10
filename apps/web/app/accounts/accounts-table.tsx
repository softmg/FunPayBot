"use client";

import { useState } from "react";
import { MessageCircle } from "lucide-react";

type AccountRow = {
  id: string;
  credentials: string;
  status: string;
  confirmed_at: string;
  confirmed_by: string | null;
  chat_url: string | null;
  seller_name: string | null;
};

const STATUSES = ["active", "blocked", "replacement_requested", "refunded"] as const;
const STATUS_LABELS: Record<(typeof STATUSES)[number], string> = {
  active: "Активен",
  blocked: "Заблокирован",
  replacement_requested: "Запрошена замена",
  refunded: "Возврат",
};

export default function AccountsTable({ initialAccounts }: { initialAccounts: AccountRow[] }) {
  const [accounts, setAccounts] = useState<AccountRow[]>(initialAccounts);
  const [contactId, setContactId] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [feedback, setFeedback] = useState("");

  async function changeStatus(accountId: string, newStatus: string) {
    setFeedback("");
    const res = await fetch(`/api/accounts/${accountId}/status`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ status: newStatus }),
    });
    if (!res.ok) {
      setFeedback("Не удалось обновить статус.");
      return;
    }
    setAccounts((prev) =>
      prev.map((a) => (a.id === accountId ? { ...a, status: newStatus } : a))
    );
  }

  async function contactSeller(accountId: string) {
    if (!message.trim()) return;
    setFeedback("");
    const res = await fetch(`/api/accounts/${accountId}/contact-seller`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message }),
    });
    if (!res.ok) {
      const data = await res.json();
      setFeedback(data.error ?? "Не удалось написать продавцу.");
      return;
    }
    setFeedback("Сообщение отправлено продавцу.");
    setContactId(null);
    setMessage("");
  }

  return (
    <div className="panel grid">
      {feedback ? <div className={feedback.includes("Не удалось") ? "error-text" : "success-text"}>{feedback}</div> : null}

      {contactId ? (
        <div className="create-form" style={{ gridTemplateColumns: "1fr auto" }}>
          <input
            className="input"
            placeholder="Сообщение продавцу (возврат или замена)"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
          />
          <div style={{ display: "flex", gap: "6px" }}>
            <button className="button" onClick={() => contactSeller(contactId)}>Отправить</button>
            <button className="button secondary" onClick={() => { setContactId(null); setMessage(""); }}>Отмена</button>
          </div>
        </div>
      ) : null}

      <table className="table">
        <thead>
          <tr>
            <th>Статус</th>
            <th>Данные</th>
            <th>Продавец</th>
            <th>Подтверждение</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          {accounts.map((account) => (
            <tr key={account.id}>
              <td>
                <select
                  className={`status status-${account.status}`}
                  value={account.status}
                  onChange={(e) => changeStatus(account.id, e.target.value)}
                  style={{ border: "none", cursor: "pointer", fontSize: "12px" }}
                >
                  {STATUSES.map((s) => (
                    <option key={s} value={s}>{STATUS_LABELS[s]}</option>
                  ))}
                </select>
              </td>
              <td>{account.credentials}</td>
              <td>
                {account.chat_url ? (
                  <a href={account.chat_url} rel="noreferrer" target="_blank">
                    {account.seller_name ?? "Чат"}
                  </a>
                ) : (
                  <span className="muted">Нет чата</span>
                )}
              </td>
              <td>
                {account.confirmed_by ?? "Неизвестно"}<br />
                <span className="muted">{new Date(account.confirmed_at).toLocaleString()}</span>
              </td>
              <td>
                {(account.status === "blocked" || account.status === "replacement_requested") && account.chat_url ? (
                  <button className="button secondary" onClick={() => setContactId(account.id)} title="Написать продавцу">
                    <MessageCircle size={14} /> Написать
                  </button>
                ) : null}
              </td>
            </tr>
          ))}
          {accounts.length === 0 ? (
            <tr><td className="muted" colSpan={5}>Подтверждённых аккаунтов пока нет.</td></tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}
