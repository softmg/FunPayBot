from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from bot.poller import _poll_once, _escape_md


@pytest.mark.asyncio
@patch("bot.poller.db")
@patch("bot.poller.httpx.AsyncClient")
async def test_poll_once_skips_unassigned_chats(mock_client_class, mock_db) -> None:
    """Chats without an assigned manager should be skipped."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get.return_value = MagicMock(
        is_success=True,
        json=lambda: {"chats": [{"id": 100, "name": "seller1", "node_msg_id": 5}]},
    )
    mock_client_class.return_value = mock_client

    mock_db.ensure_chat = AsyncMock(return_value="internal-uuid")
    mock_db.get_manager_telegram_id_for_chat = AsyncMock(return_value=None)
    mock_db.assign_chat_to_pending_order = AsyncMock(return_value=None)

    bot = MagicMock()
    await _poll_once(bot)

    mock_db.ensure_chat.assert_called_once_with("100", "seller1")
    mock_db.assign_chat_to_pending_order.assert_called_once_with("100", "internal-uuid")
    mock_db.save_inbound_message.assert_not_called()
    bot.send_message.assert_not_called()


@pytest.mark.asyncio
@patch("bot.poller.db")
@patch("bot.poller.httpx.AsyncClient")
async def test_poll_once_skips_when_no_new_messages(mock_client_class, mock_db) -> None:
    """If watermark matches node_msg_id, no history fetch should happen."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get.return_value = MagicMock(
        is_success=True,
        json=lambda: {"chats": [{"id": 200, "name": "seller2", "node_msg_id": 10}]},
    )
    mock_client_class.return_value = mock_client

    mock_db.ensure_chat = AsyncMock(return_value="internal-uuid")
    mock_db.get_manager_telegram_id_for_chat = AsyncMock(return_value=12345)
    mock_db.get_watermark = AsyncMock(return_value=10)

    bot = MagicMock()
    await _poll_once(bot)

    assert mock_client.get.call_count == 1


@pytest.mark.asyncio
@patch("bot.poller.db")
@patch("bot.poller.httpx.AsyncClient")
async def test_poll_once_relays_new_messages(mock_client_class, mock_db) -> None:
    """New messages should be saved to DB and relayed to the manager."""
    chats_response = MagicMock(
        is_success=True,
        json=lambda: {"chats": [{"id": 300, "name": "seller3", "node_msg_id": 15}]},
    )
    history_response = MagicMock(
        is_success=True,
        json=lambda: {"messages": [{"id": 15, "text": "Here are your credentials", "author": "seller3"}]},
    )

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=[chats_response, history_response])
    mock_client_class.return_value = mock_client

    mock_db.get_manager_telegram_id_for_chat = AsyncMock(return_value=99999)
    mock_db.get_watermark = AsyncMock(return_value=10)
    mock_db.ensure_chat = AsyncMock(return_value="internal-uuid")
    mock_db.assign_chat_to_pending_order = AsyncMock()
    mock_db.save_inbound_message = AsyncMock()

    bot = AsyncMock()
    await _poll_once(bot)

    mock_db.save_inbound_message.assert_called_once_with("internal-uuid", "15", "seller3", "Here are your credentials")
    mock_db.assign_chat_to_pending_order.assert_not_called()
    bot.send_message.assert_called_once()
    assert bot.send_message.call_args.kwargs["reply_markup"] is None


@pytest.mark.asyncio
@patch("bot.poller.db")
@patch("bot.poller.httpx.AsyncClient")
async def test_poll_once_auto_assigns_pending_order_chat(mock_client_class, mock_db) -> None:
    """A new paid-order chat should be linked to the pending order manager before relay."""
    chats_response = MagicMock(
        is_success=True,
        json=lambda: {"chats": [{"id": 400, "name": "seller4", "node_msg_id": 20}]},
    )
    history_response = MagicMock(
        is_success=True,
        json=lambda: {"messages": [{"id": 20, "text": "login:pass", "author": "seller4"}]},
    )

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=[chats_response, history_response])
    mock_client_class.return_value = mock_client

    mock_db.ensure_chat = AsyncMock(return_value="internal-uuid")
    mock_db.get_manager_telegram_id_for_chat = AsyncMock(return_value=None)
    mock_db.assign_chat_to_pending_order = AsyncMock(return_value=77777)
    mock_db.get_watermark = AsyncMock(return_value=None)
    mock_db.save_inbound_message = AsyncMock()

    bot = AsyncMock()
    await _poll_once(bot)

    mock_db.assign_chat_to_pending_order.assert_called_once_with("400", "internal-uuid")
    mock_db.save_inbound_message.assert_called_once_with("internal-uuid", "20", "seller4", "login:pass")
    bot.send_message.assert_called_once()


@pytest.mark.asyncio
@patch("bot.poller.create_pending_credentials", return_value="abc123")
@patch("bot.poller.db")
@patch("bot.poller.httpx.AsyncClient")
async def test_poll_once_prefills_detected_credentials(mock_client_class, mock_db, mock_create_pending) -> None:
    chats_response = MagicMock(
        is_success=True,
        json=lambda: {"chats": [{"id": 500, "name": "seller5", "node_msg_id": 25}]},
    )
    history_response = MagicMock(
        is_success=True,
        json=lambda: {
            "messages": [
                {
                    "id": 25,
                    "text": "ввести: siptqrmuw86489+4913fda6@outlook.com----#C#QrNA6jd7r$eFd",
                    "author": "seller5",
                }
            ]
        },
    )

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=[chats_response, history_response])
    mock_client_class.return_value = mock_client

    mock_db.ensure_chat = AsyncMock(return_value="internal-uuid")
    mock_db.get_manager_telegram_id_for_chat = AsyncMock(return_value=55555)
    mock_db.get_watermark = AsyncMock(return_value=None)
    mock_db.save_inbound_message = AsyncMock()

    bot = AsyncMock()
    await _poll_once(bot)

    mock_create_pending.assert_called_once_with(
        55555,
        "siptqrmuw86489+4913fda6@outlook.com:#C#QrNA6jd7r$eFd",
        "internal-uuid",
    )
    assert "Найдены данные аккаунта" in bot.send_message.call_args.kwargs["text"]
    assert bot.send_message.call_args.kwargs["reply_markup"] is not None


def test_escape_md_escapes_special_chars() -> None:
    assert _escape_md("hello_world") == "hello\\_world"
    assert _escape_md("price: 100$") == "price: 100$"
    assert _escape_md("*bold*") == "\\*bold\\*"


@pytest.mark.asyncio
@patch("bot.poller.db")
@patch("bot.poller.httpx.AsyncClient")
async def test_poll_once_handles_timeout(mock_client_class, mock_db) -> None:
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get.side_effect = httpx.ReadTimeout("timed out")
    mock_client_class.return_value = mock_client

    bot = MagicMock()
    await _poll_once(bot)

    bot.send_message.assert_not_called()
