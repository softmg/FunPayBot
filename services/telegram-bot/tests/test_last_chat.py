from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.last_chat import get_last_relay_chat, set_last_relay_chat
from bot.main import text_message


def test_last_relay_chat_round_trip() -> None:
    set_last_relay_chat(4242, "chat-uuid")
    assert get_last_relay_chat(4242) == "chat-uuid"


def test_last_relay_chat_unknown_manager_is_none() -> None:
    assert get_last_relay_chat(9_999_999) is None


@pytest.mark.asyncio
@patch("bot.main.db")
async def test_text_message_links_pasted_credentials_to_last_chat(mock_db) -> None:
    set_last_relay_chat(123, "chat-uuid-123")
    mock_db.is_allowed_user = AsyncMock(return_value=True)

    update = MagicMock()
    update.effective_user.id = 123
    update.effective_chat = MagicMock()
    update.message.text = "user@example.com:secretpw"
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.user_data = {}

    await text_message(update, context)

    assert context.user_data["pending_credentials"] == "user@example.com:secretpw"
    assert context.user_data["pending_chat_id"] == "chat-uuid-123"
