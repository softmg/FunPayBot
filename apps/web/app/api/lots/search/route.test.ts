import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { requireUser } from "@/lib/auth";
import { query } from "@/lib/db";
import { POST } from "./route";

vi.mock("@/lib/auth", () => ({
  requireUser: vi.fn()
}));

vi.mock("@/lib/db", () => ({
  query: vi.fn()
}));

const mockedRequireUser = vi.mocked(requireUser);
const mockedQuery = vi.mocked(query);

function jsonRequest(body: unknown) {
  return new Request("http://localhost/api/lots/search", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body)
  });
}

describe("lots search route", () => {
  beforeEach(() => {
    process.env.FUNPAY_API_URL = "http://funpay-api:8000";
    mockedRequireUser.mockResolvedValue({
      id: "user-1",
      email: "manager@example.com",
      role: "manager",
      display_name: "Manager"
    });
    mockedQuery.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.clearAllMocks();
    delete process.env.FUNPAY_API_URL;
  });

  it("preserves upstream timeout errors", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      Response.json({ detail: "Timed out while fetching FunPay page" }, { status: 504 })
    ) as unknown as typeof fetch;

    const response = await POST(jsonRequest({ query: "chatgpt", forbidden_words: [] }));

    expect(response.status).toBe(504);
    await expect(response.json()).resolves.toEqual({ error: "Timed out while fetching FunPay page" });
  });
});
