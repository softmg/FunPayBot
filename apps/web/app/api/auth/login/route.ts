import { randomBytes } from "crypto";
import bcrypt from "bcryptjs";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { z } from "zod";
import { sessionCookie } from "@/lib/auth";
import { query } from "@/lib/db";
import { signSession } from "@/lib/session";
import { SESSION_MAX_AGE_SECONDS } from "@/lib/session-config";

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(1)
});

type LoginUser = {
  id: string;
  email: string;
  password_hash: string;
  role: "admin" | "manager";
};

/**
 * A throwaway bcrypt hash compared against when the requested account does not
 * exist, so the response time of a missing account matches that of a wrong
 * password. This prevents distinguishing registered emails by timing.
 */
const DUMMY_PASSWORD_HASH = bcrypt.hashSync(randomBytes(32).toString("hex"), 12);

/**
 * Creates the configured bootstrap admin the first time the system is used.
 * Idempotent and race-safe: only attempted when no users exist yet, and the
 * insert is a no-op if another concurrent request already created the account.
 */
async function ensureBootstrapAdmin(email: string, password: string) {
  const existing = await query<{ exists: number }>("SELECT 1 AS exists FROM users LIMIT 1");
  if (existing.length > 0) {
    return;
  }
  const hash = await bcrypt.hash(password, 12);
  await query(
    `INSERT INTO users (email, password_hash, role, display_name)
     VALUES ($1, $2, 'admin', 'Admin')
     ON CONFLICT (email) DO NOTHING`,
    [email, hash]
  );
}

export async function POST(request: Request) {
  const parsed = schema.safeParse(await request.json());
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid login payload" }, { status: 400 });
  }

  const bootstrapEmail = process.env.BOOTSTRAP_ADMIN_EMAIL;
  const bootstrapPassword = process.env.BOOTSTRAP_ADMIN_PASSWORD;
  if (
    bootstrapEmail &&
    bootstrapPassword &&
    parsed.data.email.toLowerCase() === bootstrapEmail.toLowerCase()
  ) {
    await ensureBootstrapAdmin(bootstrapEmail, bootstrapPassword);
  }

  const rows = await query<LoginUser>(
    "SELECT id, email, password_hash, role FROM users WHERE email = $1 AND is_active = TRUE",
    [parsed.data.email]
  );
  const user = rows[0];
  // Always run a comparison (against a dummy hash when the user is missing) so
  // the timing of unknown emails matches that of wrong passwords.
  const passwordMatches = await bcrypt.compare(
    parsed.data.password,
    user?.password_hash ?? DUMMY_PASSWORD_HASH
  );
  if (!user || !passwordMatches) {
    return NextResponse.json({ error: "Invalid email or password" }, { status: 401 });
  }

  const cookieStore = await cookies();
  cookieStore.set(sessionCookie, signSession(user.id), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: SESSION_MAX_AGE_SECONDS
  });

  return NextResponse.json({ ok: true, role: user.role });
}

