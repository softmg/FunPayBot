import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { query } from "./db";
import { verifySession } from "./session";

export type Role = "admin" | "manager";

export type CurrentUser = {
  id: string;
  email: string;
  role: Role;
  display_name: string;
};

const sessionCookie = "funpaybot_user";

export async function getCurrentUser(): Promise<CurrentUser | null> {
  const cookieStore = await cookies();
  const token = cookieStore.get(sessionCookie)?.value;
  if (!token) {
    return null;
  }

  const userId = verifySession(token);
  if (!userId) {
    return null;
  }

  const rows = await query<CurrentUser>(
    "SELECT id, email, role, display_name FROM users WHERE id = $1 AND is_active = TRUE",
    [userId]
  );
  return rows[0] ?? null;
}

export async function requireUser(): Promise<CurrentUser> {
  const user = await getCurrentUser();
  if (!user) {
    redirect("/login");
  }
  return user;
}

export async function requireAdmin(): Promise<CurrentUser> {
  const user = await requireUser();
  if (user.role !== "admin") {
    redirect("/");
  }
  return user;
}

export { sessionCookie };

