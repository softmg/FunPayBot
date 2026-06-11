import { NextResponse } from "next/server";
import { z } from "zod";
import { withApiErrors } from "@/lib/api";
import { requireUserApi } from "@/lib/auth";

const schema = z.object({
  url: z.string().url(),
  title: z.string().optional()
});

function extractError(payload: unknown, fallback: string) {
  if (payload && typeof payload === "object" && "detail" in payload && typeof payload.detail === "string") {
    return payload.detail;
  }
  if (payload && typeof payload === "object" && "error" in payload && typeof payload.error === "string") {
    return payload.error;
  }
  return fallback;
}

export const POST = withApiErrors(async (request: Request) => {
  await requireUserApi();
  const parsed = schema.safeParse(await request.json());
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid warranty payload" }, { status: 400 });
  }

  if (!process.env.FUNPAY_API_URL) {
    return NextResponse.json({ error: "FUNPAY_API_URL is not configured" }, { status: 503 });
  }

  const params = new URLSearchParams({ url: parsed.data.url });
  if (parsed.data.title) {
    params.set("title", parsed.data.title);
  }

  const response = await fetch(`${process.env.FUNPAY_API_URL}/lots/warranty?${params.toString()}`, {
    cache: "no-store"
  });
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    return NextResponse.json(
      { error: extractError(payload, "FunPay warranty lookup failed") },
      { status: response.status }
    );
  }

  return NextResponse.json(payload);
});
