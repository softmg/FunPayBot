import bcrypt from "bcryptjs";
import { NextResponse } from "next/server";
import { z } from "zod";
import { withApiErrors } from "@/lib/api";
import { requireAdminApi } from "@/lib/auth";
import { query } from "@/lib/db";

const createSchema = z.object({
  email: z.string().email(),
  password: z.string().min(6),
  role: z.enum(["admin", "manager"]),
  display_name: z.string().min(1),
  telegram_user_id: z.number().int().positive().optional(),
});

const updateSchema = z.object({
  id: z.string().uuid(),
  role: z.enum(["admin", "manager"]).optional(),
  display_name: z.string().min(1).optional(),
  telegram_user_id: z.number().int().positive().nullable().optional(),
  is_active: z.boolean().optional(),
  password: z.string().min(6).optional(),
});

export const GET = withApiErrors(async () => {
  await requireAdminApi();
  const users = await query(
    "SELECT id, email, role, display_name, telegram_user_id, is_active, created_at FROM users ORDER BY created_at"
  );
  return NextResponse.json({ users });
});

export const POST = withApiErrors(async (request: Request) => {
  const admin = await requireAdminApi();
  const parsed = createSchema.safeParse(await request.json());
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid user payload", details: parsed.error.flatten() }, { status: 400 });
  }

  const existing = await query("SELECT id FROM users WHERE email = $1", [parsed.data.email]);
  if (existing.length > 0) {
    return NextResponse.json({ error: "Email already exists" }, { status: 409 });
  }

  const hash = await bcrypt.hash(parsed.data.password, 12);
  const rows = await query<{ id: string }>(
    `INSERT INTO users (email, password_hash, role, display_name, telegram_user_id)
     VALUES ($1, $2, $3, $4, $5) RETURNING id`,
    [parsed.data.email, hash, parsed.data.role, parsed.data.display_name, parsed.data.telegram_user_id ?? null]
  );

  await query(
    "INSERT INTO audit_log (actor_user_id, action, entity_type, entity_id) VALUES ($1, 'user.create', 'user', $2)",
    [admin.id, rows[0].id]
  );

  return NextResponse.json({ id: rows[0].id }, { status: 201 });
});

export const PATCH = withApiErrors(async (request: Request) => {
  const admin = await requireAdminApi();
  const parsed = updateSchema.safeParse(await request.json());
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid update payload", details: parsed.error.flatten() }, { status: 400 });
  }

  const updates: string[] = [];
  const params: unknown[] = [];
  let paramIdx = 1;

  if (parsed.data.role !== undefined) {
    updates.push(`role = $${paramIdx++}`);
    params.push(parsed.data.role);
  }
  if (parsed.data.display_name !== undefined) {
    updates.push(`display_name = $${paramIdx++}`);
    params.push(parsed.data.display_name);
  }
  if (parsed.data.telegram_user_id !== undefined) {
    updates.push(`telegram_user_id = $${paramIdx++}`);
    params.push(parsed.data.telegram_user_id);
  }
  if (parsed.data.is_active !== undefined) {
    updates.push(`is_active = $${paramIdx++}`);
    params.push(parsed.data.is_active);
  }
  if (parsed.data.password !== undefined) {
    updates.push(`password_hash = $${paramIdx++}`);
    params.push(await bcrypt.hash(parsed.data.password, 12));
  }

  if (updates.length === 0) {
    return NextResponse.json({ error: "No fields to update" }, { status: 400 });
  }

  updates.push(`updated_at = now()`);
  params.push(parsed.data.id);

  await query(
    `UPDATE users SET ${updates.join(", ")} WHERE id = $${paramIdx}`,
    params
  );

  await query(
    "INSERT INTO audit_log (actor_user_id, action, entity_type, entity_id, metadata) VALUES ($1, 'user.update', 'user', $2, $3::jsonb)",
    [admin.id, parsed.data.id, JSON.stringify({ fields: Object.keys(parsed.data).filter(k => k !== "id") })]
  );

  return NextResponse.json({ ok: true });
});
