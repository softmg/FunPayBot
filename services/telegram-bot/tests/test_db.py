from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
@patch("bot.db.asyncpg")
async def test_is_allowed_user_admin_ids(mock_asyncpg) -> None:
    """Admin IDs from config should always be allowed without DB check."""
    from bot.db import Database

    db = Database()
    with patch("bot.db.settings") as mock_settings:
        mock_settings.admin_ids = {12345}
        assert await db.is_allowed_user(12345) is True


@pytest.mark.asyncio
async def test_is_allowed_user_db_lookup() -> None:
    """Users in the DB with matching telegram_user_id should be allowed."""
    from bot.db import Database

    db = Database()
    db.pool = MagicMock()
    db.pool.fetchrow = AsyncMock(return_value={"id": "uuid-1"})

    with patch("bot.db.settings") as mock_settings:
        mock_settings.admin_ids = set()
        assert await db.is_allowed_user(99999) is True
    db.pool.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_is_allowed_user_denied() -> None:
    """Unknown users should be denied."""
    from bot.db import Database

    db = Database()
    db.pool = MagicMock()
    db.pool.fetchrow = AsyncMock(return_value=None)

    with patch("bot.db.settings") as mock_settings:
        mock_settings.admin_ids = set()
        assert await db.is_allowed_user(11111) is False


@pytest.mark.asyncio
async def test_confirm_account_with_chat_id() -> None:
    """confirm_account should pass chat_id to the INSERT."""
    from bot.db import Database

    db = Database()
    db.pool = MagicMock()
    db.pool.fetchrow = AsyncMock(side_effect=[
        {"id": "user-uuid", "role": "manager", "display_name": "Test"},
        {"id": "account-uuid"},
    ])
    db.pool.execute = AsyncMock()

    account_id = await db.confirm_account(12345, "user@test.com:pass123", "chat-uuid")
    assert account_id == "account-uuid"

    insert_call = db.pool.fetchrow.call_args_list[1]
    assert "chat_id" in insert_call.args[0]
    assert insert_call.args[3] == "chat-uuid"


@pytest.mark.asyncio
async def test_ensure_chat_upserts() -> None:
    """ensure_chat should return internal UUID."""
    from bot.db import Database

    db = Database()
    db.pool = MagicMock()
    db.pool.fetchrow = AsyncMock(return_value={"id": "internal-uuid"})

    result = await db.ensure_chat("fp-chat-123", "seller_name")
    assert result == "internal-uuid"


@pytest.mark.asyncio
async def test_get_watermark_uses_bigint_message_ids() -> None:
    """FunPay message IDs can exceed PostgreSQL 32-bit integer range."""
    from bot.db import Database

    db = Database()
    db.pool = MagicMock()
    db.pool.fetchrow = AsyncMock(return_value={"max_id": 4_762_328_683})

    result = await db.get_watermark("fp-chat-123")

    assert result == 4_762_328_683
    query = db.pool.fetchrow.call_args.args[0]
    assert "external_message_id::bigint" in query
    assert "external_message_id::int" not in query
    assert "external_message_id ~ '^[0-9]+$'" in query


@pytest.mark.asyncio
async def test_assign_chat_to_pending_order_links_chat() -> None:
    """assign_chat_to_pending_order should claim the newest pending order for a new chat."""
    from bot.db import Database

    class AsyncContext:
        def __init__(self, value=None) -> None:
            self.value = value

        async def __aenter__(self):
            return self.value

        async def __aexit__(self, exc_type, exc, tb):
            return False

    connection = MagicMock()
    connection.fetchrow = AsyncMock(
        return_value={
            "id": "order-uuid",
            "assigned_manager_id": "manager-uuid",
            "telegram_user_id": 12345,
        }
    )
    connection.execute = AsyncMock()
    connection.transaction.return_value = AsyncContext()

    pool = MagicMock()
    pool.acquire.return_value = AsyncContext(connection)

    db = Database()
    db.pool = pool

    result = await db.assign_chat_to_pending_order("fp-chat-123", "chat-uuid")

    assert result == 12345
    assert connection.execute.call_count == 3
    connection.execute.assert_any_call(
        """
                    UPDATE orders
                    SET chat_id = $2,
                        status = CASE WHEN status = 'payment_pending' THEN 'paid' ELSE status END,
                        updated_at = now()
                    WHERE id = $1
                    """,
        "order-uuid",
        "chat-uuid",
    )
