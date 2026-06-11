import { afterEach, describe, expect, it, vi } from "vitest";
import { POST } from "./route";

const cookieDelete = vi.fn();
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ delete: cookieDelete }))
}));

describe("logout route", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("clears the session cookie and redirects to /login with 303", async () => {
    const request = new Request("http://localhost/api/auth/logout", { method: "POST" });
    const response = await POST(request);

    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toBe("http://localhost/login");
    expect(cookieDelete).toHaveBeenCalledWith("funpaybot_user");
  });
});
