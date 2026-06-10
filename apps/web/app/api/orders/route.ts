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

  return NextResponse.json({ ...payload, id: rows[0].id });
}
