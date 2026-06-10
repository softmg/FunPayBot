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
    return NextResponse.json({ error: "Invalid payment methods payload" }, { status: 400 });
  }

  if (!process.env.FUNPAY_API_URL) {
    return NextResponse.json({ error: "FUNPAY_API_URL is not configured" }, { status: 503 });
  }

  const response = await fetch(`${process.env.FUNPAY_API_URL}/orders/payment-methods`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(parsed.data),
    cache: "no-store"
  });
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    await query(
      "INSERT INTO audit_log (actor_user_id, action, entity_type, metadata) VALUES ($1, 'order.payment_methods_failed', 'order', $2)",
      [user.id, JSON.stringify({ lot_url: parsed.data.lot_url, status: response.status, error: payload })]
    );

    return NextResponse.json(
      { error: extractError(payload, "FunPay payment methods lookup failed") },
      { status: response.status }
    );
  }

  await query(
    "INSERT INTO audit_log (actor_user_id, action, entity_type, metadata) VALUES ($1, 'order.payment_methods', 'order', $2::jsonb)",
    [user.id, JSON.stringify({
      lot_url: parsed.data.lot_url,
      payment_methods_count: Array.isArray(payload?.payment_methods) ? payload.payment_methods.length : 0
    })]
  );

  return NextResponse.json(payload);
}
