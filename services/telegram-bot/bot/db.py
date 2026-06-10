import json

import asyncpg

from bot.config import settings


class Database:
    def __init__(self) -> None:
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(settings.database_url)

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    async def is_allowed_user(self, telegram_user_id: int) -> bool:
        if telegram_user_id in settings.admin_ids:
            return True
        assert self.pool
        row = await self.pool.fetchrow(
            "SELECT id FROM users WHERE telegram_user_id = $1 AND is_active = TRUE",
            telegram_user_id,
        )
        return row is not None

    async def user_by_telegram(self, telegram_user_id: int):
        assert self.pool
        return await self.pool.fetchrow(
            "SELECT id, role, display_name FROM users WHERE telegram_user_id = $1 AND is_active = TRUE",
            telegram_user_id,
        )

    async def save_outbound_message(self, telegram_user_id: int, chat_id: str, body: str) -> None:
        assert self.pool
        user = await self.user_by_telegram(telegram_user_id)
        await self.pool.execute(
            """
            INSERT INTO audit_log (actor_user_id, action, entity_type, metadata)
            VALUES ($1, 'telegram.message_seller', 'funpay_chat', $2::jsonb)
            """,
            user["id"] if user else None,
            json.dumps({"funpay_chat_id": chat_id, "body": body}),
        )

    async def confirm_account(self, telegram_user_id: int, credentials: str, chat_id: str | None = None) -> str:
        assert self.pool
        user = await self.user_by_telegram(telegram_user_id)
        row = await self.pool.fetchrow(
            """
            INSERT INTO accounts (credentials, confirmed_by, chat_id)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            credentials,
            user["id"] if user else None,
            chat_id,
        )
        await self.pool.execute(
            """
            INSERT INTO audit_log (actor_user_id, action, entity_type, entity_id, metadata)
            VALUES ($1, 'account.confirm_from_telegram', 'account', $2, $3::jsonb)
            """,
            user["id"] if user else None,
            row["id"],
            json.dumps({"source": "telegram", "chat_id": chat_id}),
        )
        return str(row["id"])

    async def ensure_chat(self, funpay_chat_id: str, seller_name: str | None = None) -> str:
        """Upsert a funpay_chats row and return its internal UUID."""
        assert self.pool
        row = await self.pool.fetchrow(
            """
            INSERT INTO funpay_chats (funpay_chat_id, seller_name)
            VALUES ($1, $2)
            ON CONFLICT (funpay_chat_id) DO UPDATE SET seller_name = COALESCE($2, funpay_chats.seller_name)
            RETURNING id
            """,
            funpay_chat_id,
            seller_name,
        )
        return str(row["id"])

    async def assign_chat_to_pending_order(self, funpay_chat_id: str, internal_chat_id: str) -> int | None:
        """Attach a new FunPay chat to the newest pending order and return manager Telegram ID."""
        assert self.pool
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                order = await connection.fetchrow(
                    """
                    SELECT orders.id, orders.assigned_manager_id, users.telegram_user_id
                    FROM orders
                    JOIN users ON users.id = orders.assigned_manager_id
                    WHERE orders.chat_id IS NULL
                      AND orders.status IN ('created', 'payment_pending', 'paid', 'credentials_pending')
                      AND orders.created_at >= now() - interval '24 hours'
                      AND users.is_active = TRUE
                      AND users.telegram_user_id IS NOT NULL
                    ORDER BY orders.created_at DESC
                    LIMIT 1
                    FOR UPDATE OF orders SKIP LOCKED
                    """
                )
                if not order:
                    return None

                await connection.execute(
                    """
                    UPDATE funpay_chats
                    SET assigned_manager_id = $2,
                        chat_url = COALESCE(chat_url, $3),
                        updated_at = now()
                    WHERE id = $1
                    """,
                    internal_chat_id,
                    order["assigned_manager_id"],
                    f"https://funpay.com/en/chat/?node={funpay_chat_id}",
                )
                await connection.execute(
                    """
                    UPDATE orders
                    SET chat_id = $2,
                        status = CASE WHEN status = 'payment_pending' THEN 'paid' ELSE status END,
                        updated_at = now()
                    WHERE id = $1
                    """,
                    order["id"],
                    internal_chat_id,
                )
                await connection.execute(
                    """
                    INSERT INTO audit_log (actor_user_id, action, entity_type, entity_id, metadata)
                    VALUES ($1, 'order.chat_auto_assigned', 'order', $2, $3::jsonb)
                    """,
                    order["assigned_manager_id"],
                    order["id"],
                    json.dumps({"funpay_chat_id": funpay_chat_id}),
                )
                return order["telegram_user_id"]

    async def assign_chat(self, funpay_chat_id: str, manager_user_id: str) -> None:
        """Assign a FunPay chat to a manager."""
        assert self.pool
        await self.pool.execute(
            """
            UPDATE funpay_chats SET assigned_manager_id = $2, updated_at = now()
            WHERE funpay_chat_id = $1
            """,
            funpay_chat_id,
            manager_user_id,
        )

    async def get_assigned_chats(self, telegram_user_id: int) -> list:
        """Return chats assigned to a manager by their Telegram ID."""
        assert self.pool
        user = await self.user_by_telegram(telegram_user_id)
        if not user:
            return []
        return await self.pool.fetch(
            """
            SELECT funpay_chat_id, seller_name, chat_url
            FROM funpay_chats
            WHERE assigned_manager_id = $1
            ORDER BY updated_at DESC
            """,
            user["id"],
        )

    async def get_watermark(self, funpay_chat_id: str) -> int | None:
        """Get the latest external_message_id for a chat for delta detection."""
        assert self.pool
        row = await self.pool.fetchrow(
            """
            SELECT MAX(external_message_id::bigint) AS max_id
            FROM funpay_messages fm
            JOIN funpay_chats fc ON fc.id = fm.chat_id
            WHERE fc.funpay_chat_id = $1 AND fm.external_message_id ~ '^[0-9]+$'
            """,
            funpay_chat_id,
        )
        return row["max_id"] if row and row["max_id"] is not None else None

    async def save_inbound_message(self, internal_chat_id: str, external_message_id: str, sender_name: str | None, body: str) -> None:
        """Save an inbound message from a seller."""
        assert self.pool
        existing = await self.pool.fetchrow(
            "SELECT id FROM funpay_messages WHERE chat_id = $1 AND external_message_id = $2",
            internal_chat_id,
            external_message_id,
        )
        if existing:
            return
        await self.pool.execute(
            """
            INSERT INTO funpay_messages (chat_id, external_message_id, direction, sender_name, body)
            VALUES ($1, $2, 'inbound', $3, $4)
            """,
            internal_chat_id,
            external_message_id,
            sender_name,
            body,
        )

    async def get_manager_telegram_id_for_chat(self, funpay_chat_id: str) -> int | None:
        """Look up the Telegram user ID of the manager assigned to a chat."""
        assert self.pool
        row = await self.pool.fetchrow(
            """
            SELECT u.telegram_user_id
            FROM funpay_chats fc
            JOIN users u ON u.id = fc.assigned_manager_id
            WHERE fc.funpay_chat_id = $1 AND u.is_active = TRUE
            """,
            funpay_chat_id,
        )
        return row["telegram_user_id"] if row else None


db = Database()
