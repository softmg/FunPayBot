import { describe, expect, it, vi } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { areLotRowPropsEqual, LotRow } from "./search-panel";

const lot = {
  title: "Test lot",
  url: "https://funpay.com/lots/offer?id=1",
  price: "10",
  reviews: 25,
  warranty: null
};

const handlers = {
  onLoadWarranty: vi.fn()
};

describe("lot row memoization", () => {
  it("keeps rows stable when parent-owned state is unchanged", () => {
    const props = {
      lot,
      warrantyState: undefined,
      ...handlers
    };

    expect(areLotRowPropsEqual(props, { ...props })).toBe(true);
  });

  it("rerenders only the row whose parent-owned warranty state changed", () => {
    const props = {
      lot,
      warrantyState: undefined,
      ...handlers
    };
    const nextProps = {
      ...props,
      warrantyState: { pending: true, error: "" }
    };

    expect(areLotRowPropsEqual(props, nextProps)).toBe(false);
  });
});

describe("lot row warranty control", () => {
  it("renders warranty loading as a compact text action", () => {
    const markup = renderToStaticMarkup(
      createElement(
        "table",
        null,
        createElement(
          "tbody",
          null,
          createElement(LotRow, {
            lot,
            warrantyState: undefined,
            ...handlers
          })
        )
      )
    );

    expect(markup).toContain('class="text-button warranty-load-button"');
    expect(markup).toContain(">Загрузить</button>");
    expect(markup).not.toContain('class="button" type="button">Загрузить</button>');
  });
});
