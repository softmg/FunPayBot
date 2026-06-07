import bcrypt from "bcryptjs";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { z } from "zod";
import { sessionCookie } from "@/lib/auth";
import { query } from "@/lib/db";

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

async function ensureBootstrapAdmin(email: string, password: string) {
  const existing = await query<{ count: string }>("SELECT count(*) FROM users");
  if (Number(existing[0]?.count ?? 0) > 0) {
    return;
  }
  const hash = await bcrypt.hash(password, 12);
  await query(
    "INSERT INTO users (email, password_hash, role, display_name) VALUES ($1, $2, 'admin', 'Admin')",
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
  if (bootstrapEmail && bootstrapPassword) {
    await ensureBootstrapAdmin(bootstrapEmail, bootstrapPassword);
  }

  const rows = await query<LoginUser>(
    "SELECT id, email, password_hash, role FROM users WHERE email = $1 AND is_active = TRUE",
    [parsed.data.email]
  );
  const user = rows[0];
  if (!user || !(await bcrypt.compare(parsed.data.password, user.password_hash))) {
    return NextResponse.json({ error: "Invalid email or password" }, { status: 401 });
  }

  const cookieStore = await cookies();
  cookieStore.set(sessionCookie, user.id, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/"
  });

  return NextResponse.json({ ok: true, role: user.role });
}

