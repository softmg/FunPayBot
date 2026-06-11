import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { ApiError } from "./api";
import { query } from "./db";
import { verifySession } from "./session";
import { SESSION_COOKIE } from "./session-config";

export type Role = "admin" | "manager";

export type CurrentUser = {
  id: string;
  email: string;
  role: Role;
  display_name: string;
};

const sessionCookie = SESSION_COOKIE;

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

/**
 * Like {@link requireUser} but for API route handlers: throws an
 * {@link ApiError} (401) instead of redirecting to the login page, so API
 * clients receive a proper status code rather than an HTML redirect.
 */
export async function requireUserApi(): Promise<CurrentUser> {
  const user = await getCurrentUser();
  if (!user) {
    throw new ApiError(401, "Unauthorized");
  }
  return user;
}

/**
 * Like {@link requireAdmin} but for API route handlers: throws 401 when not
 * authenticated and 403 when authenticated without the admin role.
 */
export async function requireAdminApi(): Promise<CurrentUser> {
  const user = await requireUserApi();
  if (user.role !== "admin") {
    throw new ApiError(403, "Forbidden");
  }
  return user;
}

export { sessionCookie };

