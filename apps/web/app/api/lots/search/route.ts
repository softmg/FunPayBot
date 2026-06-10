import { NextResponse } from "next/server";
import { z } from "zod";
import { requireUser } from "@/lib/auth";
import { query } from "@/lib/db";

const schema = z.object({
  query: z.string().default(""),
  search_scope: z.enum(["category", "site"]).default("category"),
  max_price: z.coerce.number().positive().optional(),
  min_reviews: z.coerce.number().int().nonnegative().default(0),
  forbidden_words: z.array(z.string()).default([])
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

export async function POST(request: Request) {
  const user = await requireUser();
  const parsed = schema.safeParse(await request.json());
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid search payload" }, { status: 400 });
  }

  const dbWords = await query<{ word: string }>("SELECT word FROM forbidden_words");
  const mergedForbidden = [
    ...new Set([
      ...parsed.data.forbidden_words.map((w) => w.toLowerCase()),
      ...dbWords.map((r) => r.word.toLowerCase()),
    ]),
  ];

  const response = await fetch(`${process.env.FUNPAY_API_URL}/lots/search`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ ...parsed.data, forbidden_words: mergedForbidden }),
    cache: "no-store"
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const status = response.status === 504 ? 504 : 502;
    return NextResponse.json(
      { error: extractError(payload, "FunPay lot search failed") },
      { status }
    );
  }
  const data = payload;

  await query(
    "INSERT INTO lot_searches (user_id, query, max_price, min_reviews, results_count) VALUES ($1, $2, $3, $4, $5)",
    [user.id, parsed.data.query, parsed.data.max_price ?? null, parsed.data.min_reviews, data.count ?? 0]
  );
  await query(
    "INSERT INTO audit_log (actor_user_id, action, entity_type, metadata) VALUES ($1, 'lot.search', 'lot_search', $2)",
    [user.id, JSON.stringify({ query: parsed.data.query, search_scope: parsed.data.search_scope, results_count: data.count ?? 0 })]
  );

  return NextResponse.json(data);
}
