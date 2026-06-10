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
  return new Request("http://localhost/api/orders/payment-methods", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body)
  });
}

describe("order payment methods route", () => {
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

  it("returns payment methods from funpay-api", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      Response.json({
        payment_methods: [{ id: "42", title: "USDT TRC20", currency: "usd" }]
      }, { status: 200 })
    ) as unknown as typeof fetch;

    const response = await POST(jsonRequest({ lot_url: "https://funpay.com/lots/offer?id=1" }));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      payment_methods: [{ id: "42", title: "USDT TRC20", currency: "usd" }]
    });
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://funpay-api:8000/orders/payment-methods",
      expect.objectContaining({ body: JSON.stringify({ lot_url: "https://funpay.com/lots/offer?id=1" }) })
    );
    expect(mockedQuery).toHaveBeenCalledWith(
      expect.stringContaining("order.payment_methods"),
      expect.arrayContaining(["user-1"])
    );
  });

  it("returns a timeout error when funpay-api payment method lookup hangs", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(
      new DOMException("The operation was aborted", "AbortError")
    ) as unknown as typeof fetch;

    const response = await POST(jsonRequest({ lot_url: "https://funpay.com/lots/offer?id=1" }));

    expect(response.status).toBe(504);
    await expect(response.json()).resolves.toEqual({ error: "FunPay payment methods lookup timed out" });
    expect(mockedQuery).toHaveBeenCalledWith(
      expect.stringContaining("order.payment_methods_failed"),
      expect.arrayContaining(["user-1"])
    );
  });
});
