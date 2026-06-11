import bcrypt from "bcryptjs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { query } from "@/lib/db";
import { POST } from "./route";

vi.mock("@/lib/db", () => ({
  query: vi.fn()
}));

const cookieSet = vi.fn();
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ set: cookieSet }))
}));

const mockedQuery = vi.mocked(query);

function jsonRequest(body: unknown) {
  return new Request("http://localhost/api/auth/login", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body)
  });
}

describe("login route", () => {
  beforeEach(() => {
    process.env.NEXTAUTH_SECRET = "a-strong-test-secret";
    delete process.env.BOOTSTRAP_ADMIN_EMAIL;
    delete process.env.BOOTSTRAP_ADMIN_PASSWORD;
    mockedQuery.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("rejects an invalid payload", async () => {
    const response = await POST(jsonRequest({ email: "not-an-email", password: "" }));
    expect(response.status).toBe(400);
  });

  it("returns 401 and still runs a bcrypt comparison for unknown emails", async () => {
    const compareSpy = vi.spyOn(bcrypt, "compare");
    mockedQuery.mockResolvedValueOnce([]); // user lookup: no match

    const response = await POST(jsonRequest({ email: "ghost@example.com", password: "whatever" }));

    expect(response.status).toBe(401);
    // The comparison must run even when the user is missing (constant-time path).
    expect(compareSpy).toHaveBeenCalledOnce();
    expect(cookieSet).not.toHaveBeenCalled();
  });

  it("returns 401 for an existing user with the wrong password", async () => {
    const hash = await bcrypt.hash("correct-password", 4);
    mockedQuery.mockResolvedValueOnce([
      { id: "user-1", email: "admin@example.com", password_hash: hash, role: "admin" }
    ]);

    const response = await POST(jsonRequest({ email: "admin@example.com", password: "wrong-password" }));

    expect(response.status).toBe(401);
    expect(cookieSet).not.toHaveBeenCalled();
  });

  it("sets a session cookie on success", async () => {
    const hash = await bcrypt.hash("correct-password", 4);
    mockedQuery.mockResolvedValueOnce([
      { id: "user-1", email: "admin@example.com", password_hash: hash, role: "admin" }
    ]);

    const response = await POST(jsonRequest({ email: "admin@example.com", password: "correct-password" }));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ ok: true, role: "admin" });
    expect(cookieSet).toHaveBeenCalledOnce();
    const [, token, options] = cookieSet.mock.calls[0];
    expect(String(token).startsWith("user-1.")).toBe(true);
    expect(options).toMatchObject({ httpOnly: true, path: "/" });
  });

  it("bootstraps the first admin race-safely for the configured email", async () => {
    process.env.BOOTSTRAP_ADMIN_EMAIL = "admin@example.com";
    process.env.BOOTSTRAP_ADMIN_PASSWORD = "bootstrap-pass";
    mockedQuery
      .mockResolvedValueOnce([]) // ensureBootstrapAdmin: no existing users
      .mockResolvedValueOnce([]) // ensureBootstrapAdmin: insert
      .mockResolvedValueOnce([]); // user lookup still empty -> 401

    const response = await POST(jsonRequest({ email: "admin@example.com", password: "bootstrap-pass" }));

    expect(response.status).toBe(401);
    const insertCall = mockedQuery.mock.calls.find(([sql]) => String(sql).includes("INSERT INTO users"));
    expect(insertCall?.[0]).toContain("ON CONFLICT (email) DO NOTHING");
  });

  it("does not attempt bootstrap for non-bootstrap emails", async () => {
    process.env.BOOTSTRAP_ADMIN_EMAIL = "admin@example.com";
    process.env.BOOTSTRAP_ADMIN_PASSWORD = "bootstrap-pass";
    mockedQuery.mockResolvedValueOnce([]); // user lookup only

    const response = await POST(jsonRequest({ email: "someone@example.com", password: "x" }));

    expect(response.status).toBe(401);
    const insertCall = mockedQuery.mock.calls.find(([sql]) => String(sql).includes("INSERT INTO users"));
    expect(insertCall).toBeUndefined();
  });
});
