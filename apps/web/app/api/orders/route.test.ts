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
  return new Request("http://localhost/api/orders", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body)
  });
}

describe("orders route", () => {
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

  it("returns the funpay-api unsupported error when purchase flow is not implemented", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "not implemented" }), {
        status: 501,
        headers: { "content-type": "application/json" }
      })
    ) as unknown as typeof fetch;

    const response = await POST(jsonRequest({ lot_url: "https://funpay.com/lots/1355/1/" }));

    expect(response.status).toBe(501);
    await expect(response.json()).resolves.toEqual({ error: "not implemented" });
    expect(globalThis.fetch).toHaveBeenCalledWith("http://funpay-api:8000/orders", expect.any(Object));
    expect(mockedQuery).toHaveBeenCalledWith(
      expect.stringContaining("order.create_failed"),
      expect.arrayContaining(["user-1"])
    );
  });

  it("stores created orders with payment links", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      Response.json({ payment_link: "https://funpay.com/pay/abc" }, { status: 200 })
    ) as unknown as typeof fetch;
    mockedQuery
      .mockResolvedValueOnce([{ id: "order-1" }])
      .mockResolvedValueOnce([]);

    const response = await POST(jsonRequest({ lot_url: "https://funpay.com/lots/1355/1/" }));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      id: "order-1",
      payment_link: "https://funpay.com/pay/abc"
    });
    expect(mockedQuery).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining("INSERT INTO orders"),
      ["https://funpay.com/lots/1355/1/", "payment_pending", "https://funpay.com/pay/abc", "user-1"]
    );
  });
});
