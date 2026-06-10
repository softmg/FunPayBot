from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.credential_confirmations import PendingCredentials
from bot.main import confirm_credentials


@pytest.mark.asyncio
@patch("bot.main.db")
@patch("bot.main.pop_pending_credentials")
async def test_confirm_credentials_saves_tokenized_pending_credentials(mock_pop_pending, mock_db) -> None:
    mock_pop_pending.return_value = PendingCredentials(
        manager_telegram_id=12345,
        credentials="user@example.com:secret",
        chat_id="chat-uuid",
    )
    mock_db.is_allowed_user = AsyncMock(return_value=True)
    mock_db.confirm_account = AsyncMock(return_value="account-uuid")

    query = MagicMock()
    query.data = "confirm_credentials:abc123"
    query.from_user.id = 12345
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = MagicMock(callback_query=query)
    context = MagicMock()
    context.user_data = {}

    await confirm_credentials(update, context)

    mock_pop_pending.assert_called_once_with("abc123")
    mock_db.confirm_account.assert_called_once_with(12345, "user@example.com:secret", "chat-uuid")
    query.edit_message_text.assert_called_once_with("Аккаунт account-uuid сохранен.")
