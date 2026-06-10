import { describe, expect, it } from "vitest";
import { sortLots } from "./lot-sort";

const lots = [
  { id: "mid", price: "100.50", reviews: 20 },
  { id: "unknown", price: null, reviews: 99 },
  { id: "low", price: "10,25 ₽", reviews: 5 },
  { id: "high", price: "1 200", reviews: 10 }
];

describe("sortLots", () => {
  it("sorts lots by numeric price ascending", () => {
    expect(sortLots(lots, { field: "price", direction: "asc" }).map((lot) => lot.id)).toEqual([
      "low",
      "mid",
      "high",
      "unknown"
    ]);
  });

  it("sorts lots by numeric price descending and keeps unknown prices last", () => {
    expect(sortLots(lots, { field: "price", direction: "desc" }).map((lot) => lot.id)).toEqual([
      "high",
      "mid",
      "low",
      "unknown"
    ]);
  });

  it("sorts lots by reviews in both directions", () => {
    expect(sortLots(lots, { field: "reviews", direction: "asc" }).map((lot) => lot.id)).toEqual([
      "low",
      "high",
      "mid",
      "unknown"
    ]);
    expect(sortLots(lots, { field: "reviews", direction: "desc" }).map((lot) => lot.id)).toEqual([
      "unknown",
      "mid",
      "high",
      "low"
    ]);
  });
});
