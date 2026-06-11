import { NextResponse } from "next/server";
import { z } from "zod";
import { withApiErrors } from "@/lib/api";
import { requireUserApi } from "@/lib/auth";
import { query } from "@/lib/db";

const createSchema = z.object({
  credentials: z.string().min(1),
  chat_id: z.string().uuid().optional(),
  order_id: z.string().uuid().optional()
});

const listSql = `
  SELECT
    accounts.id,
    accounts.credentials,
    accounts.status,
    accounts.confirmed_at,
    users.display_name AS confirmed_by,
    funpay_chats.chat_url,
    funpay_chats.seller_name
  FROM accounts
  LEFT JOIN users ON users.id = accounts.confirmed_by
  LEFT JOIN funpay_chats ON funpay_chats.id = accounts.chat_id
  ORDER BY accounts.created_at DESC
  LIMIT 100
`;

export const GET = withApiErrors(async () => {
  await requireUserApi();
  const accounts = await query(listSql);
  return NextResponse.json({ accounts });
});

export const POST = withApiErrors(async (request: Request) => {
  const user = await requireUserApi();
  const parsed = createSchema.safeParse(await request.json());
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid account payload" }, { status: 400 });
  }

  const rows = await query<{ id: string }>(
    "INSERT INTO accounts (credentials, chat_id, order_id, confirmed_by) VALUES ($1, $2, $3, $4) RETURNING id",
    [parsed.data.credentials, parsed.data.chat_id ?? null, parsed.data.order_id ?? null, user.id]
  );
  await query(
    "INSERT INTO audit_log (actor_user_id, action, entity_type, entity_id) VALUES ($1, 'account.confirm', 'account', $2)",
    [user.id, rows[0].id]
  );

  return NextResponse.json({ id: rows[0].id }, { status: 201 });
});

