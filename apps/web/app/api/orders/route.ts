import { NextResponse } from "next/server";
import { z } from "zod";
import { requireUser } from "@/lib/auth";
import { query } from "@/lib/db";

const schema = z.object({
  lot_url: z.string().url()
});

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

async function getPaymentNotificationRecipients() {
  const configuredIds = parseAdminTelegramIds();
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

async function notifyPaymentLink(paymentLink: string, lotUrl: string, orderId: string) {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  const recipients = await getPaymentNotificationRecipients();
  if (!token || recipients.length === 0) {
    return { notified: false, reason: "telegram_not_configured" };
  }

  const text = [
    "Новая покупка FunPay ожидает оплаты.",
    `Заказ: ${orderId}`,
    `Лот: ${lotUrl}`,
    `Оплата: ${paymentLink}`
  ].join("\n");

  const results = await Promise.all(
    recipients.map(async (chatId) => {
      const response = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          chat_id: chatId,
          text,
          disable_web_page_preview: true
        }),
        cache: "no-store"
      });
      return response.ok;
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

export async function POST(request: Request) {
  const user = await requireUser();
  const parsed = schema.safeParse(await request.json());
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid order payload" }, { status: 400 });
  }

  if (!process.env.FUNPAY_API_URL) {
    return NextResponse.json({ error: "FUNPAY_API_URL is not configured" }, { status: 503 });
  }

  const response = await fetch(`${process.env.FUNPAY_API_URL}/orders`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(parsed.data),
    cache: "no-store"
  });
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    await query(
      "INSERT INTO audit_log (actor_user_id, action, entity_type, metadata) VALUES ($1, 'order.create_failed', 'order', $2)",
      [user.id, JSON.stringify({ lot_url: parsed.data.lot_url, status: response.status, error: payload })]
    );

    return NextResponse.json(
      { error: extractError(payload, "FunPay order creation failed") },
      { status: response.status }
    );
  }

  const rows = await query<{ id: string }>(
    "INSERT INTO orders (lot_url, status, payment_link, assigned_manager_id, created_by) VALUES ($1, $2, $3, $4, $4) RETURNING id",
    [parsed.data.lot_url, payload?.payment_link ? "payment_pending" : "created", payload?.payment_link ?? null, user.id]
  );

  await query(
    "INSERT INTO audit_log (actor_user_id, action, entity_type, entity_id, metadata) VALUES ($1, 'order.create', 'order', $2, $3::jsonb)",
    [user.id, rows[0].id, JSON.stringify({ lot_url: parsed.data.lot_url, payment_link_present: Boolean(payload?.payment_link) })]
  );

  const telegram = payload?.payment_link
    ? await notifyPaymentLink(payload.payment_link, parsed.data.lot_url, rows[0].id)
    : { notified: false, reason: "payment_link_missing" };

  await query(
    "INSERT INTO audit_log (actor_user_id, action, entity_type, entity_id, metadata) VALUES ($1, 'order.payment_link_notification', 'order', $2, $3::jsonb)",
    [user.id, rows[0].id, JSON.stringify(telegram)]
  );

  return NextResponse.json({ ...payload, id: rows[0].id, telegram_notified: telegram.notified });
}
