from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True


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


@patch("app.main.fetch_funpay_warranty", new_callable=AsyncMock)
def test_warranty_endpoint(mock_warranty: AsyncMock) -> None:
    mock_warranty.return_value = "Гарантия: 24 часа"
    response = client.get("/lots/warranty", params={"url": "https://funpay.com/lots/1355/1/"})
    assert response.status_code == 200
    assert response.json()["warranty"] == "Гарантия: 24 часа"


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
    response = client.post("/orders", json={"lot_url": "https://funpay.com/lots/1355/1/"})
    assert response.status_code == 501
