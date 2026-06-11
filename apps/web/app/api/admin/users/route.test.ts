import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { requireAdminApi } from "@/lib/auth";
import { query } from "@/lib/db";
import { PATCH } from "./route";

vi.mock("@/lib/auth", () => ({
  requireAdminApi: vi.fn()
}));

vi.mock("@/lib/db", () => ({
  query: vi.fn()
}));

const mockedRequireAdmin = vi.mocked(requireAdminApi);
const mockedQuery = vi.mocked(query);

const ADMIN_ID = "11111111-1111-1111-1111-111111111111";
const OTHER_ID = "22222222-2222-2222-2222-222222222222";

function jsonRequest(body: unknown) {
  return new Request("http://localhost/api/admin/users", {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body)
  });
}

describe("admin users PATCH guards", () => {
  beforeEach(() => {
    mockedRequireAdmin.mockResolvedValue({
      id: ADMIN_ID,
      email: "admin@example.com",
      role: "admin",
      display_name: "Admin"
    });
    mockedQuery.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("refuses to deactivate your own account", async () => {
    const response = await PATCH(jsonRequest({ id: ADMIN_ID, is_active: false }));

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      error: expect.stringContaining("your own account")
    });
    expect(mockedQuery).not.toHaveBeenCalledWith(
      expect.stringContaining("UPDATE users"),
      expect.anything()
    );
  });

  it("refuses to demote yourself", async () => {
    const response = await PATCH(jsonRequest({ id: ADMIN_ID, role: "manager" }));
    expect(response.status).toBe(400);
  });

  it("refuses to remove the last active admin", async () => {
    mockedQuery
      .mockResolvedValueOnce([{ role: "admin", is_active: true }]) // target lookup
      .mockResolvedValueOnce([{ count: "0" }]); // other active admins

    const response = await PATCH(jsonRequest({ id: OTHER_ID, is_active: false }));

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      error: expect.stringContaining("last active admin")
    });
  });

  it("allows deactivating another admin when one remains", async () => {
    mockedQuery
      .mockResolvedValueOnce([{ role: "admin", is_active: true }]) // target lookup
      .mockResolvedValueOnce([{ count: "1" }]) // other active admins
      .mockResolvedValueOnce([]) // UPDATE users
      .mockResolvedValueOnce([]); // audit_log

    const response = await PATCH(jsonRequest({ id: OTHER_ID, is_active: false }));

    expect(response.status).toBe(200);
    expect(mockedQuery).toHaveBeenCalledWith(
      expect.stringContaining("UPDATE users SET"),
      expect.arrayContaining([false, OTHER_ID])
    );
  });

  it("allows non-lockout updates without extra checks", async () => {
    mockedQuery
      .mockResolvedValueOnce([]) // UPDATE users
      .mockResolvedValueOnce([]); // audit_log

    const response = await PATCH(jsonRequest({ id: OTHER_ID, display_name: "Renamed" }));

    expect(response.status).toBe(200);
  });
});
