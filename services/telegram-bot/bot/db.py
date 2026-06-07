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

    async def confirm_account(self, telegram_user_id: int, credentials: str) -> str:
        assert self.pool
        user = await self.user_by_telegram(telegram_user_id)
        row = await self.pool.fetchrow(
            """
            INSERT INTO accounts (credentials, confirmed_by)
            VALUES ($1, $2)
            RETURNING id
            """,
            credentials,
            user["id"] if user else None,
        )
        await self.pool.execute(
            """
            INSERT INTO audit_log (actor_user_id, action, entity_type, entity_id, metadata)
            VALUES ($1, 'account.confirm_from_telegram', 'account', $2, $3::jsonb)
            """,
            user["id"] if user else None,
            row["id"],
            json.dumps({"source": "telegram"}),
        )
        return str(row["id"])


db = Database()
