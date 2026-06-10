import pytest

from app.funpay_client import (
    FunPayNotConfiguredError,
    FunPayClient,
    extract_lot_id,
    parse_order_form,
)


@pytest.mark.asyncio
async def test_send_message_requires_golden_key() -> None:
    client = FunPayClient()

    with pytest.raises(FunPayNotConfiguredError):
        await client.send_message("123", "hello")


@pytest.mark.asyncio
async def test_create_order_uses_funpay_order_form(monkeypatch) -> None:
    client = FunPayClient()
    calls = []

    async def fake_ensure_account():
        return FakeAccount(calls)

    monkeypatch.setattr(client, "_ensure_account", fake_ensure_account)

    result = await client.create_order("https://funpay.com/lots/offer?id=68954385", "42")

    assert result["status"] == "payment_pending"
    assert result["offer_id"] == 68954385
    assert result["payment_link"] == "https://funpay.com/orders/ABCDEF/"
    assert calls[1]["payload"]["offer_id"] == "68954385"
    assert calls[1]["payload"]["method"] == "42"


@pytest.mark.asyncio
async def test_list_payment_methods_uses_funpay_order_form(monkeypatch) -> None:
    client = FunPayClient()
    calls = []

    async def fake_ensure_account():
        return FakeAccount(calls)

    monkeypatch.setattr(client, "_ensure_account", fake_ensure_account)

    result = await client.list_payment_methods("https://funpay.com/lots/offer?id=68954385")

    assert result["offer_id"] == 68954385
    assert result["payment_methods"] == [
        {"id": "40", "title": "Bank card", "currency": "eur"},
        {"id": "42", "title": "USDT TRC20", "currency": "usd"},
    ]
    assert len(calls) == 1


def test_extract_lot_id_from_offer_url() -> None:
    assert extract_lot_id("https://funpay.com/lots/offer?id=123") == 123


def test_parse_order_form_lists_payment_methods_without_choosing_one() -> None:
    form = parse_order_form(order_form_html(), "https://funpay.com/en/lots/offer?id=68954385")

    assert form["action"] == "https://funpay.com/en/orders/new"
    assert form["payload"]["csrf_token"] == "csrf"
    assert form["payload"]["amount"] == "1"
    assert "method" not in form["payload"]
    assert form["payment_method"] is None
    assert form["payment_methods"] == [
        {"id": "40", "title": "Bank card", "currency": "eur"},
        {"id": "42", "title": "USDT TRC20", "currency": "usd"},
    ]


def test_parse_order_form_applies_selected_payment_method() -> None:
    form = parse_order_form(order_form_html(), "https://funpay.com/en/lots/offer?id=68954385", "42")

    assert form["payload"]["method"] == "42"
    assert form["payment_method"] == {"id": "42", "title": "USDT TRC20", "currency": "usd"}


def test_parse_order_form_rejects_unavailable_selected_payment_method() -> None:
    from app.funpay_client import FunPayPurchaseFlowError

    with pytest.raises(FunPayPurchaseFlowError):
        parse_order_form(order_form_html(), "https://funpay.com/en/lots/offer?id=68954385", "999")


class FakeResponse:
    def __init__(self, text: str = "", url: str = "https://funpay.com/en/lots/offer?id=68954385", headers=None) -> None:
        self.text = text
        self.url = url
        self.headers = headers or {}


class FakeAccount:
    def __init__(self, calls: list) -> None:
        self.calls = calls

    def method(self, request_method, api_method, headers, payload, **kwargs):
        self.calls.append(
            {
                "request_method": request_method,
                "api_method": api_method,
                "headers": headers,
                "payload": payload,
                "kwargs": kwargs,
            }
        )
        if request_method == "get":
            return FakeResponse(order_form_html())
        return FakeResponse(headers={"location": "/orders/ABCDEF/"})


def order_form_html(options: str | None = None) -> str:
    return f"""
    <form action="https://funpay.com/en/orders/new" method="post">
      <input type="hidden" name="csrf_token" value="csrf">
      <input type="hidden" name="type" value="lot">
      <input type="hidden" name="preview" value="1">
      <input type="hidden" name="offer_id" value="68954385">
      <input type="hidden" name="price_guard" value="guard">
      <input type="text" name="amount" value="1">
      <input type="text" name="sum" value="">
      <select name="method">
        <option value="0" class="hidden">&nbsp;</option>
        {options or '<option value="40" data-cy="eur">Bank card</option><option value="42" data-cy="usd">USDT TRC20</option>'}
      </select>
    </form>
    """
