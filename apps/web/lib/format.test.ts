import { describe, expect, it } from "vitest";
import { formatPrice } from "./format";

describe("formatPrice", () => {
  it("formats prices with two decimal places", () => {
    expect(formatPrice("1221.995927")).toBe("1\u00a0222,00 ₽");
  });

  it("preserves unknown values", () => {
    expect(formatPrice(null)).toBe("Неизвестно");
  });
});
