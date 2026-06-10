export type LotSortDirection = "asc" | "desc";
export type LotSortField = "price" | "reviews";

export type SortableLot = {
  price: string | null;
  reviews: number;
};

export type LotSort = {
  field: LotSortField;
  direction: LotSortDirection;
};

function parsePrice(price: string | null): number | null {
  if (!price) {
    return null;
  }

  const normalized = price
    .replace(/\s/g, "")
    .replace(/[^\d,.-]/g, "")
    .replace(",", ".");
  const value = Number(normalized);

  return Number.isFinite(value) ? value : null;
}

function compareNullableNumbers(
  left: number | null,
  right: number | null,
  direction: LotSortDirection
): number {
  if (left === null && right === null) {
    return 0;
  }
  if (left === null) {
    return 1;
  }
  if (right === null) {
    return -1;
  }

  const comparison = left - right;

  return direction === "asc" ? comparison : -comparison;
}

export function sortLots<TLot extends SortableLot>(lots: readonly TLot[], sort: LotSort | null): TLot[] {
  if (!sort) {
    return [...lots];
  }

  return lots
    .map((lot, index) => ({ lot, index }))
    .sort((left, right) => {
      const comparison =
        sort.field === "price"
          ? compareNullableNumbers(parsePrice(left.lot.price), parsePrice(right.lot.price), sort.direction)
          : left.lot.reviews - right.lot.reviews;

      if (comparison === 0) {
        return left.index - right.index;
      }

      return sort.field === "reviews" && sort.direction === "desc" ? -comparison : comparison;
    })
    .map(({ lot }) => lot);
}
