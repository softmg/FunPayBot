from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True


def test_health_open_even_when_token_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "internal_api_token", "s3cret")
    response = client.get("/health")
    assert response.status_code == 200


@patch("app.main.search_lots", new_callable=AsyncMock)
def test_protected_route_rejects_missing_token(mock_search: AsyncMock, monkeypatch) -> None:
    monkeypatch.setattr(settings, "internal_api_token", "s3cret")
    response = client.post("/lots/search", json={"query": "test"})
    assert response.status_code == 401
    mock_search.assert_not_awaited()


@patch("app.main.search_lots", new_callable=AsyncMock)
def test_protected_route_rejects_wrong_token(mock_search: AsyncMock, monkeypatch) -> None:
    monkeypatch.setattr(settings, "internal_api_token", "s3cret")
    response = client.post("/lots/search", json={"query": "test"}, headers={"X-Internal-Token": "nope"})
    assert response.status_code == 401
    mock_search.assert_not_awaited()


@patch("app.main.search_lots", new_callable=AsyncMock)
def test_protected_route_accepts_valid_token(mock_search: AsyncMock, monkeypatch) -> None:
    monkeypatch.setattr(settings, "internal_api_token", "s3cret")
    mock_search.return_value = []
    response = client.post("/lots/search", json={"query": "test"}, headers={"X-Internal-Token": "s3cret"})
    assert response.status_code == 200
    mock_search.assert_awaited_once()


@patch("app.main.search_lots", new_callable=AsyncMock)
def test_lots_search_returns_results(mock_search: AsyncMock) -> None:
    mock_search.return_value = [
        {"title": "Test lot", "url": "https://funpay.com/lots/1355/1/", "price": "45", "reviews": 10, "warranty": None}
    ]
    response = client.post("/lots/search", json={"query": "test", "forbidden_words": []})
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["results"][0]["title"] == "Test lot"
    mock_search.assert_awaited_once()


@patch("app.main.search_lots", new_callable=AsyncMock)
def test_lots_search_empty_query(mock_search: AsyncMock) -> None:
    mock_search.return_value = []
    response = client.post("/lots/search", json={})
    assert response.status_code == 200
    assert response.json()["count"] == 0


@patch("app.main.search_lots", new_callable=AsyncMock)
def test_lots_search_accepts_site_scope(mock_search: AsyncMock) -> None:
    mock_search.return_value = []
    response = client.post("/lots/search", json={"query": "gemini api", "search_scope": "site"})

    assert response.status_code == 200
    assert response.json()["count"] == 0
    assert mock_search.await_args.kwargs["scope"] == "site"


@patch("app.main.search_lots", new_callable=AsyncMock)
def test_lots_search_returns_504_on_timeout(mock_search: AsyncMock) -> None:
    from app.parser import FunPayUpstreamTimeoutError

    mock_search.side_effect = FunPayUpstreamTimeoutError("Timed out while fetching FunPay page")
    response = client.post("/lots/search", json={"query": "test"})

    assert response.status_code == 504
    assert response.json()["detail"] == "Timed out while fetching FunPay page"


@patch("app.main.fetch_funpay_warranty", new_callable=AsyncMock)
def test_warranty_endpoint(mock_warranty: AsyncMock) -> None:
    mock_warranty.return_value = "Гарантия: 24 часа"
    response = client.get(
        "/lots/warranty",
        params={"url": "https://funpay.com/lots/1355/1/", "title": "Лот. Гарантия: 24 часа"},
    )
    assert response.status_code == 200
    assert response.json()["warranty"] == "Гарантия: 24 часа"
    mock_warranty.assert_awaited_once_with(
        "https://funpay.com/lots/1355/1/",
        title="Лот. Гарантия: 24 часа",
    )


@patch("app.main.funpay_client")
def test_session_get_unconfigured(mock_client) -> None:
    mock_client.session_status = AsyncMock(return_value={"configured": False, "authenticated": False})
    response = client.get("/session")
    assert response.status_code == 200
    assert response.json()["configured"] is False


@patch("app.main.funpay_client")
def test_chats_send_requires_body(mock_client) -> None:
    response = client.post("/chats/send", json={"chat_id": "123", "body": ""})
    assert response.status_code == 422


@patch("app.main.funpay_client")
def test_orders_create_returns_501(mock_client) -> None:
    from app.funpay_client import FunPayUnsupportedOperationError

    mock_client.create_order = AsyncMock(side_effect=FunPayUnsupportedOperationError("not implemented"))
    response = client.post(
        "/orders",
        json={"lot_url": "https://funpay.com/lots/1355/1/", "payment_method_id": "42"},
    )
    assert response.status_code == 501


@patch("app.main.funpay_client")
def test_order_payment_methods_returns_results(mock_client) -> None:
    mock_client.list_payment_methods = AsyncMock(
        return_value={
            "lot_url": "https://funpay.com/lots/offer?id=1",
            "offer_id": 1,
            "payment_methods": [{"id": "42", "title": "USDT TRC20", "currency": "usd"}],
        }
    )

    response = client.post("/orders/payment-methods", json={"lot_url": "https://funpay.com/lots/offer?id=1"})

    assert response.status_code == 200
    assert response.json()["payment_methods"][0]["id"] == "42"
