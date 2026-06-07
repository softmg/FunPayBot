import { NextResponse } from "next/server";
import { z } from "zod";
import { requireAdmin } from "@/lib/auth";
import { query } from "@/lib/db";

const addSchema = z.object({
  word: z.string().min(1).max(200),
});

const deleteSchema = z.object({
  id: z.string().uuid(),
});

export async function GET() {
  await requireAdmin();
  const words = await query("SELECT id, word, created_at FROM forbidden_words ORDER BY word");
  return NextResponse.json({ words });
}

export async function POST(request: Request) {
  const admin = await requireAdmin();
  const parsed = addSchema.safeParse(await request.json());
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid payload" }, { status: 400 });
  }

  const normalized = parsed.data.word.trim().toLowerCase();
  const existing = await query("SELECT id FROM forbidden_words WHERE lower(word) = $1", [normalized]);
  if (existing.length > 0) {
    return NextResponse.json({ error: "Word already exists" }, { status: 409 });
  }

  const rows = await query<{ id: string }>(
    "INSERT INTO forbidden_words (word, created_by) VALUES ($1, $2) RETURNING id",
    [normalized, admin.id]
  );

  await query(
    "INSERT INTO audit_log (actor_user_id, action, entity_type, entity_id, metadata) VALUES ($1, 'forbidden_word.add', 'forbidden_word', $2, $3::jsonb)",
    [admin.id, rows[0].id, JSON.stringify({ word: normalized })]
  );

  return NextResponse.json({ id: rows[0].id }, { status: 201 });
}

export async function DELETE(request: Request) {
  const admin = await requireAdmin();
  const parsed = deleteSchema.safeParse(await request.json());
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid payload" }, { status: 400 });
  }

  const deleted = await query<{ word: string }>(
    "DELETE FROM forbidden_words WHERE id = $1 RETURNING word",
    [parsed.data.id]
  );
  if (deleted.length === 0) {
    return NextResponse.json({ error: "Word not found" }, { status: 404 });
  }

  await query(
    "INSERT INTO audit_log (actor_user_id, action, entity_type, entity_id, metadata) VALUES ($1, 'forbidden_word.delete', 'forbidden_word', $2, $3::jsonb)",
    [admin.id, parsed.data.id, JSON.stringify({ word: deleted[0].word })]
  );

  return NextResponse.json({ ok: true });
}
