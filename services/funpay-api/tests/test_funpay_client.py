from html import escape

import pytest

from app.funpay_client import (
    FunPayNotConfiguredError,
    FunPayPurchaseFlowError,
    FunPayClient,
    extract_payment_link,
    extract_lot_id,
    is_payment_link,
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
async def test_create_order_submits_confirmation_form(monkeypatch) -> None:
    client = FunPayClient()
    calls = []

    async def fake_ensure_account():
        return FakeTwoStepAccount(calls)

    monkeypatch.setattr(client, "_ensure_account", fake_ensure_account)

    result = await client.create_order("https://funpay.com/lots/offer?id=68954385", "21")

    assert result["payment_link"] == "https://funpay.com/orders/ABCDEF/"
    assert len(calls) == 3
    assert calls[1]["payload"]["method"] == "21"
    assert calls[2]["api_method"] == "https://funpay.com/en/orders/new"
    assert calls[2]["headers"]["referer"] == "https://funpay.com/en/orders/new"
    assert calls[2]["payload"]["gate"] == "31"
    assert "preview" not in calls[2]["payload"]


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


def test_parse_order_form_uses_payment_titles_and_prices_from_data_content() -> None:
    options = """
      {apple_pay}
      {google_pay}
      {bank_card}
      {sbp}
    """.format(
        apple_pay=payment_option_html("41", "Bank card", "Apple Pay", "402.08 $", class_name="hidden"),
        google_pay=payment_option_html("38", "Bank card", "Google Pay", "402.08 $"),
        bank_card=payment_option_html("39", "Bank card", "Bank card", "402.08 $"),
        sbp=payment_option_html(
            "21",
            "СБП (оплата по QR)",
            "СБП (оплата по QR)",
            "28 334.24 ₽",
            currency="rub",
            unit="₽",
        ),
    )

    form = parse_order_form(order_form_html(options), "https://funpay.com/en/lots/offer?id=68954385")

    assert form["payment_methods"] == [
        {"id": "41", "title": "Apple Pay", "currency": "usd", "price": "402.08 $", "unit": "$"},
        {"id": "38", "title": "Google Pay", "currency": "usd", "price": "402.08 $", "unit": "$"},
        {"id": "39", "title": "Bank card", "currency": "usd", "price": "402.08 $", "unit": "$"},
        {"id": "21", "title": "СБП (оплата по QR)", "currency": "rub", "price": "28 334.24 ₽", "unit": "₽"},
    ]


def test_parse_order_form_rejects_unavailable_selected_payment_method() -> None:
    with pytest.raises(FunPayPurchaseFlowError):
        parse_order_form(order_form_html(), "https://funpay.com/en/lots/offer?id=68954385", "999")


def test_extract_payment_link_rejects_chat_redirect() -> None:
    response = FakeResponse(url="https://funpay.com/en/chat/")

    with pytest.raises(FunPayPurchaseFlowError, match="no payment link"):
        extract_payment_link(response, "https://funpay.com/en/lots/offer?id=68954385")


@pytest.mark.parametrize("url", ["https://funpay.com/en/orders/", "https://funpay.com/orders/new"])
def test_is_payment_link_rejects_generic_order_pages(url: str) -> None:
    assert not is_payment_link(url)


def test_is_payment_link_accepts_specific_order_pages() -> None:
    assert is_payment_link("https://funpay.com/orders/ABCDEF/")


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


class FakeTwoStepAccount:
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
            return FakeResponse(
                order_form_html(
                    '<option value="21" data-cy="rub">Faster Payments System</option>'
                    '<option value="42" data-cy="usd">USDT TRC20</option>'
                )
            )
        if len(self.calls) == 2:
            return FakeResponse(confirmation_form_html(), url="https://funpay.com/en/orders/new")
        return FakeResponse(headers={"location": "/orders/ABCDEF/"}, url="https://funpay.com/en/orders/new")


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


def confirmation_form_html() -> str:
    return """
    <form action="https://funpay.com/en/orders/new" method="post">
      <input type="hidden" name="csrf_token" value="csrf">
      <input type="hidden" name="type" value="lot">
      <input type="hidden" name="method" value="21">
      <input type="hidden" name="gate" value="31">
      <input type="hidden" name="offer_id" value="68954385">
      <input type="hidden" name="price_guard" value="guard">
      <input type="text" name="amount" value="1">
      <input type="text" name="player" value="">
      <button type="submit">Pay</button>
    </form>
    """


def payment_option_html(
    value: str,
    fallback_title: str,
    data_title: str,
    data_price: str,
    *,
    currency: str = "usd",
    unit: str = "$",
    class_name: str | None = None,
) -> str:
    class_attr = f' class="{class_name}"' if class_name else ""
    data_content = (
        '<span class="payment">'
        f'<span class="payment-logo payment-method-{value}"></span>'
        f'<span class="payment-title">{data_title}</span>'
        f'<span class="payment-value">{data_price}</span>'
        "</span>"
    )
    return (
        f'<option value="{value}"{class_attr} data-cy="{currency}" '
        f'data-unit="{unit}" data-content="{escape(data_content, quote=True)}">{fallback_title}</option>'
    )
