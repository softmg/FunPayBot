import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { requireUser } from "@/lib/auth";
import { POST } from "./route";

vi.mock("@/lib/auth", () => ({
  requireUser: vi.fn()
}));

const mockedRequireUser = vi.mocked(requireUser);

function jsonRequest(body: unknown) {
  return new Request("http://localhost/api/lots/warranty", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body)
  });
}

describe("lots warranty route", () => {
  beforeEach(() => {
    process.env.FUNPAY_API_URL = "http://funpay-api:8000";
    mockedRequireUser.mockResolvedValue({
      id: "user-1",
      email: "manager@example.com",
      role: "manager",
      display_name: "Manager"
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
    delete process.env.FUNPAY_API_URL;
  });

  it("forwards title fallback to funpay-api", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      Response.json({ url: "https://funpay.com/lots/1355/1/", warranty: "Гарантия: 24 часа" }, { status: 200 })
    ) as unknown as typeof fetch;

    const response = await POST(jsonRequest({ url: "https://funpay.com/lots/1355/1/", title: "Лот. Гарантия: 24 часа" }));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({ warranty: "Гарантия: 24 часа" });
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://funpay-api:8000/lots/warranty?url=https%3A%2F%2Ffunpay.com%2Flots%2F1355%2F1%2F&title=%D0%9B%D0%BE%D1%82.+%D0%93%D0%B0%D1%80%D0%B0%D0%BD%D1%82%D0%B8%D1%8F%3A+24+%D1%87%D0%B0%D1%81%D0%B0",
      expect.objectContaining({ cache: "no-store" })
    );
  });
});
