import { NextResponse } from "next/server";
import { z } from "zod";
import { requireAdmin } from "@/lib/auth";
import { query } from "@/lib/db";

const SENSITIVE_KEYS = new Set(["funpay_golden_key", "telegram_bot_token"]);

const updateSchema = z.object({
  settings: z.record(z.string(), z.string()),
});

function maskValue(key: string, value: string): string {
  if (SENSITIVE_KEYS.has(key) && value.length > 4) {
    return value.slice(0, 4) + "•".repeat(Math.min(value.length - 4, 20));
  }
  return value;
}

export async function GET() {
  await requireAdmin();
  const rows = await query<{ key: string; value: string; updated_at: string }>(
    "SELECT key, value, updated_at FROM settings ORDER BY key"
  );
  const settings: Record<string, { value: string; updated_at: string }> = {};
  for (const row of rows) {
    settings[row.key] = {
      value: maskValue(row.key, row.value),
      updated_at: row.updated_at,
    };
  }
  return NextResponse.json({ settings });
}

export async function PUT(request: Request) {
  const admin = await requireAdmin();
  const parsed = updateSchema.safeParse(await request.json());
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid settings payload" }, { status: 400 });
  }

  const changedKeys: string[] = [];
  for (const [key, value] of Object.entries(parsed.data.settings)) {
    await query(
      `INSERT INTO settings (key, value, updated_by, updated_at)
       VALUES ($1, $2, $3, now())
       ON CONFLICT (key) DO UPDATE SET value = $2, updated_by = $3, updated_at = now()`,
      [key, value, admin.id]
    );
    changedKeys.push(key);
  }

  await query(
    "INSERT INTO audit_log (actor_user_id, action, entity_type, metadata) VALUES ($1, 'settings.update', 'settings', $2::jsonb)",
    [admin.id, JSON.stringify({ keys: changedKeys })]
  );

  return NextResponse.json({ ok: true, updated: changedKeys });
}
