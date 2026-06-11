import { NextResponse } from "next/server";
import { z } from "zod";
import { withApiErrors } from "@/lib/api";
import { requireUserApi } from "@/lib/auth";
import { query } from "@/lib/db";

const schema = z.object({
  message: z.string().min(1).max(2000),
});

type Params = { params: Promise<{ id: string }> };

export const POST = withApiErrors(async (request: Request, { params }: Params) => {
  const user = await requireUserApi();
  const { id } = await params;
  const parsed = schema.safeParse(await request.json());
  if (!parsed.success) {
    return NextResponse.json({ error: "Message is required" }, { status: 400 });
  }

  const rows = await query<{ chat_id: string | null; funpay_chat_id: string | null }>(
    `SELECT accounts.chat_id, funpay_chats.funpay_chat_id
     FROM accounts
     LEFT JOIN funpay_chats ON funpay_chats.id = accounts.chat_id
     WHERE accounts.id = $1`,
    [id]
  );

  if (rows.length === 0) {
    return NextResponse.json({ error: "Account not found" }, { status: 404 });
  }

  const funpayChatId = rows[0].funpay_chat_id;
  if (!funpayChatId) {
    return NextResponse.json({ error: "No FunPay chat linked to this account" }, { status: 400 });
  }

  const response = await fetch(`${process.env.FUNPAY_API_URL}/chats/send`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ chat_id: funpayChatId, body: parsed.data.message }),
    cache: "no-store",
  });

  if (!response.ok) {
    return NextResponse.json({ error: "Failed to send message to seller" }, { status: 502 });
  }

  await query(
    "INSERT INTO audit_log (actor_user_id, action, entity_type, entity_id, metadata) VALUES ($1, 'account.contact_seller', 'account', $2, $3::jsonb)",
    [user.id, id, JSON.stringify({ funpay_chat_id: funpayChatId, message: parsed.data.message })]
  );

  return NextResponse.json({ ok: true });
});
