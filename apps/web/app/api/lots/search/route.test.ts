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

  it("treats zero max price as no max price filter", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      Response.json({ count: 0, results: [] })
    ) as unknown as typeof fetch;

    const response = await POST(jsonRequest({
      query: "chatgpt",
      max_price: "0",
      min_reviews: "20",
      forbidden_words: ["без гарантии", "бан"]
    }));

    expect(response.status).toBe(200);
    expect(globalThis.fetch).toHaveBeenCalledOnce();
    const [, init] = vi.mocked(globalThis.fetch).mock.calls[0];
    expect(JSON.parse(String(init?.body))).toEqual({
      query: "chatgpt",
      search_scope: "category",
      min_reviews: 20,
      forbidden_words: ["без гарантии", "бан"]
    });
  });
});
