import { describe, expect, it } from "vitest";
import { ApiError, apiErrorResponse, withApiErrors } from "./api";

describe("apiErrorResponse", () => {
  it("renders an ApiError as a JSON response with its status", async () => {
    const response = apiErrorResponse(new ApiError(403, "Forbidden"));
    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({ error: "Forbidden" });
  });

  it("re-throws non-ApiError values", () => {
    const boom = new Error("unexpected");
    expect(() => apiErrorResponse(boom)).toThrow(boom);
  });
});

describe("withApiErrors", () => {
  it("passes through a successful response", async () => {
    const handler = withApiErrors(async () =>
      Response.json({ ok: true }, { status: 200 })
    );
    const response = await handler();
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ ok: true });
  });

  it("converts a thrown 401 into an Unauthorized response", async () => {
    const handler = withApiErrors(async () => {
      throw new ApiError(401, "Unauthorized");
    });
    const response = await handler();
    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({ error: "Unauthorized" });
  });

  it("converts a thrown 403 into a Forbidden response", async () => {
    const handler = withApiErrors(async () => {
      throw new ApiError(403, "Forbidden");
    });
    const response = await handler();
    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({ error: "Forbidden" });
  });

  it("preserves handler arguments", async () => {
    const handler = withApiErrors(async (factor: number) =>
      Response.json({ doubled: factor * 2 }, { status: 200 })
    );
    const response = await handler(21);
    await expect(response.json()).resolves.toEqual({ doubled: 42 });
  });

  it("lets unexpected errors propagate", async () => {
    const handler = withApiErrors(async () => {
      throw new Error("db down");
    });
    await expect(handler()).rejects.toThrow("db down");
  });
});
