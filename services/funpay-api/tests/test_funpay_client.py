import pytest

from app.funpay_client import FunPayNotConfiguredError, FunPayUnsupportedOperationError, FunPayClient


@pytest.mark.asyncio
async def test_send_message_requires_golden_key() -> None:
    client = FunPayClient()

    with pytest.raises(FunPayNotConfiguredError):
        await client.send_message("123", "hello")


@pytest.mark.asyncio
async def test_create_order_is_explicitly_unsupported_without_live_spike(monkeypatch) -> None:
    client = FunPayClient()

    async def fake_ensure_account():
        return object()

    monkeypatch.setattr(client, "_ensure_account", fake_ensure_account)

    with pytest.raises(FunPayUnsupportedOperationError):
        await client.create_order("https://funpay.com/lots/offer?id=1")

