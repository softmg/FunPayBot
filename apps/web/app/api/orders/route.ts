import { NextResponse } from "next/server";
import { z } from "zod";
import { withApiErrors } from "@/lib/api";
import { requireUserApi } from "@/lib/auth";
import { query } from "@/lib/db";
import { fetchWithTimeout, TELEGRAM_API_TIMEOUT_MS, UpstreamTimeoutError } from "@/lib/fetch-timeout";
import { funpayHeaders } from "@/lib/funpay";

const schema = z.object({
  lot_url: z.string().url(),
  payment_method_id: z.string().min(1)
});

type PaymentDetails = {
  type?: string;
  title?: string;
  address?: string;
  amount?: string;
};

type PaymentNotification = {
  paymentLink?: string | null;
  paymentDetails?: PaymentDetails | null;
};

type TelegramNotificationSettings = {
  token: string;
  adminIds: Set<string>;
};

function extractError(payload: unknown, fallback: string) {
  if (payload && typeof payload === "object" && "detail" in payload && typeof payload.detail === "string") {
    return payload.detail;
  }
  if (payload && typeof payload === "object" && "error" in payload && typeof payload.error === "string") {
    return payload.error;
  }
  return fallback;
}

function parseAdminTelegramIds() {
  return new Set(
    String(process.env.ADMIN_TELEGRAM_IDS ?? "")
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean)
  );
}

async function getTelegramNotificationSettings(): Promise<TelegramNotificationSettings> {
  const settings = new Map<string, string>();
  const rows = await query<{ key: string; value: string }>(
    "SELECT key, value FROM settings WHERE key = ANY($1::text[])",
    [["telegram_bot_token", "admin_telegram_ids"]]
  );

  for (const row of rows) {
    settings.set(row.key, row.value);
  }

  const token = settings.get("telegram_bot_token")?.trim() || process.env.TELEGRAM_BOT_TOKEN || "";
  const adminIds = parseAdminTelegramIds();
  for (const value of (settings.get("admin_telegram_ids") ?? "").split(",")) {
    const normalized = value.trim();
    if (normalized) {
      adminIds.add(normalized);
    }
  }

  return { token, adminIds };
}

async function getPaymentNotificationRecipients(configuredIds: Set<string>) {
  const rows = await query<{ telegram_user_id: string | number | null }>(
    "SELECT telegram_user_id FROM users WHERE role = 'admin' AND is_active = TRUE AND telegram_user_id IS NOT NULL",
    []
  );
  for (const row of rows) {
    if (row.telegram_user_id) {
      configuredIds.add(String(row.telegram_user_id));
    }
  }
  return [...configuredIds];
}

function formatPaymentNotification(payment: PaymentNotification, lotUrl: string, orderId: string) {
  const lines = [
    "Новая покупка FunPay ожидает оплаты.",
    `Заказ: ${orderId}`,
    `Лот: ${lotUrl}`,
  ];

  if (payment.paymentLink) {
    lines.push(`Оплата: ${payment.paymentLink}`);
    return lines.join("\n");
  }

  const details = payment.paymentDetails;
  if (details?.type === "crypto" && details.address && details.amount) {
    lines.push(
      "Оплата: крипто-реквизиты FunPay",
      details.title ? `Метод: ${details.title}` : "Метод: crypto",
      `Адрес: ${details.address}`,
      `Сумма: ${details.amount}`
    );
    return lines.join("\n");
  }

  lines.push("Оплата: не удалось получить ссылку или реквизиты");
  return lines.join("\n");
}

async function notifyPayment(payment: PaymentNotification, lotUrl: string, orderId: string) {
  const { token, adminIds } = await getTelegramNotificationSettings();
  const recipients = await getPaymentNotificationRecipients(adminIds);
  if (!token || recipients.length === 0) {
    return { notified: false, reason: "telegram_not_configured" };
  }

  const text = formatPaymentNotification(payment, lotUrl, orderId);

  const results = await Promise.all(
    recipients.map(async (chatId) => {
      try {
        const response = await fetchWithTimeout(
          `https://api.telegram.org/bot${token}/sendMessage`,
          {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({
              chat_id: chatId,
              text,
              disable_web_page_preview: true
            }),
            cache: "no-store"
          },
          TELEGRAM_API_TIMEOUT_MS
        );
        return response.ok;
      } catch {
        return false;
      }
    })
  );

  const delivered = results.filter(Boolean).length;
  return {
    notified: delivered > 0,
    delivered,
    recipients: recipients.length,
    reason: delivered > 0 ? undefined : "telegram_send_failed"
  };
}

export const POST = withApiErrors(async (request: Request) => {
  const user = await requireUserApi();
  const parsed = schema.safeParse(await request.json());
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid order payload" }, { status: 400 });
  }

  if (!process.env.FUNPAY_API_URL) {
    return NextResponse.json({ error: "FUNPAY_API_URL is not configured" }, { status: 503 });
  }

  let response: Response;
  try {
    response = await fetchWithTimeout(`${process.env.FUNPAY_API_URL}/orders`, {
      method: "POST",
      headers: funpayHeaders({ "content-type": "application/json" }),
      body: JSON.stringify(parsed.data),
      cache: "no-store"
    });
  } catch (error) {
    if (!(error instanceof UpstreamTimeoutError)) {
      throw error;
    }
    await query(
      "INSERT INTO audit_log (actor_user_id, action, entity_type, metadata) VALUES ($1, 'order.create_failed', 'order', $2)",
      [user.id, JSON.stringify({
        lot_url: parsed.data.lot_url,
        payment_method_id: parsed.data.payment_method_id,
        status: 504,
        error: error.message
      })]
    );
    return NextResponse.json({ error: "FunPay order creation timed out" }, { status: 504 });
  }
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    await query(
      "INSERT INTO audit_log (actor_user_id, action, entity_type, metadata) VALUES ($1, 'order.create_failed', 'order', $2)",
      [user.id, JSON.stringify({
        lot_url: parsed.data.lot_url,
        payment_method_id: parsed.data.payment_method_id,
        status: response.status,
        error: payload
      })]
    );

    return NextResponse.json(
      { error: extractError(payload, "FunPay order creation failed") },
      { status: response.status }
    );
  }

  const rows = await query<{ id: string }>(
    "INSERT INTO orders (lot_url, status, payment_link, assigned_manager_id, created_by) VALUES ($1, $2, $3, $4, $4) RETURNING id",
    [
      parsed.data.lot_url,
      payload?.payment_link || payload?.payment_details ? "payment_pending" : "created",
      payload?.payment_link ?? null,
      user.id
    ]
  );

  await query(
    "INSERT INTO audit_log (actor_user_id, action, entity_type, entity_id, metadata) VALUES ($1, 'order.create', 'order', $2, $3::jsonb)",
    [user.id, rows[0].id, JSON.stringify({
      lot_url: parsed.data.lot_url,
      payment_method_id: parsed.data.payment_method_id,
      payment_method: payload?.payment_method ?? null,
      payment_link_present: Boolean(payload?.payment_link),
      payment_details_present: Boolean(payload?.payment_details)
    })]
  );

  const telegram = payload?.payment_link || payload?.payment_details
    ? await notifyPayment(
      { paymentLink: payload.payment_link, paymentDetails: payload.payment_details },
      parsed.data.lot_url,
      rows[0].id
    )
    : { notified: false, reason: "payment_target_missing" };

  await query(
    "INSERT INTO audit_log (actor_user_id, action, entity_type, entity_id, metadata) VALUES ($1, 'order.payment_link_notification', 'order', $2, $3::jsonb)",
    [user.id, rows[0].id, JSON.stringify(telegram)]
  );

  return NextResponse.json({ ...payload, id: rows[0].id, telegram_notified: telegram.notified });
});
