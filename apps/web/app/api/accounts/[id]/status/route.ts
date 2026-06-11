import { NextResponse } from "next/server";
import { z } from "zod";
import { withApiErrors } from "@/lib/api";
import { requireUserApi } from "@/lib/auth";
import { query } from "@/lib/db";

const schema = z.object({
  status: z.enum(["active", "blocked", "replacement_requested", "refunded"]),
});

type Params = { params: Promise<{ id: string }> };

export const PATCH = withApiErrors(async (request: Request, { params }: Params) => {
  const user = await requireUserApi();
  const { id } = await params;
  const parsed = schema.safeParse(await request.json());
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid status" }, { status: 400 });
  }

  const existing = await query<{ id: string; status: string }>(
    "SELECT id, status FROM accounts WHERE id = $1",
    [id]
  );
  if (existing.length === 0) {
    return NextResponse.json({ error: "Account not found" }, { status: 404 });
  }

  await query(
    "UPDATE accounts SET status = $1, updated_at = now() WHERE id = $2",
    [parsed.data.status, id]
  );

  await query(
    "INSERT INTO audit_log (actor_user_id, action, entity_type, entity_id, metadata) VALUES ($1, 'account.status_change', 'account', $2, $3::jsonb)",
    [user.id, id, JSON.stringify({ from: existing[0].status, to: parsed.data.status })]
  );

  return NextResponse.json({ ok: true, status: parsed.data.status });
});
