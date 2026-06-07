import asyncio
import sys
from pathlib import Path
from typing import Any

from app.config import settings
from app.funpay_serializers import chat_shortcut_to_dict, chat_to_dict, message_to_dict, order_to_dict
from app.throttle import SlidingWindowThrottle

vendor_path = Path(__file__).resolve().parents[1] / "vendor"
if str(vendor_path) not in sys.path:
    sys.path.insert(0, str(vendor_path))

from FunPayAPI import Account  # noqa: E402
from FunPayAPI.common import exceptions  # noqa: E402


class FunPayNotConfiguredError(RuntimeError):
    pass


class FunPayUnsupportedOperationError(RuntimeError):
    pass


class FunPayClient:
    def __init__(self) -> None:
        self.throttle = SlidingWindowThrottle(settings.funpay_max_actions_per_minute)
        self._account: Account | None = None
        self._lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return bool(settings.funpay_golden_key)

    async def session_status(self) -> dict:
        if not self.configured:
            return {"configured": False, "authenticated": False}
        try:
            account = await self._ensure_account()
        except Exception as exc:
            return {"configured": True, "authenticated": False, "error": str(exc)}
        return {
            "configured": True,
            "authenticated": True,
            "id": account.id,
            "username": account.username,
            "active_purchases": account.active_purchases,
            "active_sales": account.active_sales,
        }

    async def refresh_session(self) -> dict:
        await self.throttle.acquire()
        async with self._lock:
            self._account = None
            account = await asyncio.to_thread(self._build_account)
            self._account = account
        return {
            "authenticated": True,
            "id": account.id,
            "username": account.username,
            "active_purchases": account.active_purchases,
            "active_sales": account.active_sales,
        }

    async def list_chats(self, update: bool = True) -> list[dict]:
        account = await self._ensure_account()
        await self.throttle.acquire()

        def call() -> list[dict]:
            chats = account.get_chats(update=update)
            return [chat_shortcut_to_dict(chat) for chat in chats.values()]

        return await self._call_locked(call)

    async def get_chat(self, chat_id: int) -> dict:
        account = await self._ensure_account()
        await self.throttle.acquire()
        return await self._call_locked(lambda: chat_to_dict(account.get_chat(chat_id)))

    async def get_chat_history(
        self,
        chat_id: int | str,
        last_message_id: int | None = None,
        interlocutor_username: str | None = None,
        from_id: int = 0,
    ) -> list[dict]:
        account = await self._ensure_account()
        await self.throttle.acquire()

        def call() -> list[dict]:
            messages = account.get_chat_history(
                chat_id,
                last_message_id=last_message_id,
                interlocutor_username=interlocutor_username,
                from_id=from_id,
            )
            return [message_to_dict(message) for message in messages]

        return await self._call_locked(call)

    async def send_message(self, chat_id: int | str, body: str) -> dict:
        account = await self._ensure_account()
        await self.throttle.acquire()

        def call() -> dict:
            message = account.send_message(chat_id, body)
            return {"status": "sent", "message": message_to_dict(message)}

        return await self._call_locked(call)

    async def fetch_messages(self, chat_id: int | str | None = None) -> list[dict]:
        if chat_id is not None:
            return await self.get_chat_history(chat_id)
        chats = await self.list_chats(update=True)
        return [
            {
                "chat_id": chat["id"],
                "chat_name": chat["name"],
                "text": chat["last_message_text"],
                "unread": chat["unread"],
                "node_msg_id": chat["node_msg_id"],
                "user_msg_id": chat["user_msg_id"],
            }
            for chat in chats
        ]

    async def get_order(self, order_id: str) -> dict:
        account = await self._ensure_account()
        await self.throttle.acquire()
        return await self._call_locked(lambda: order_to_dict(account.get_order(order_id)))

    async def refund_order(self, order_id: str) -> dict:
        account = await self._ensure_account()
        await self.throttle.acquire()

        def call() -> dict:
            account.refund(order_id)
            return {"status": "refunded", "order_id": order_id}

        return await self._call_locked(call)

    async def create_order(self, lot_url: str) -> dict:
        await self._ensure_account()
        raise FunPayUnsupportedOperationError(
            "The vendored FunPayAPI exposes chat/order/refund methods, but no verified buyer-side "
            "purchase/payment-link method. This endpoint needs a live FunPay payment-link spike."
        )

    async def _ensure_account(self) -> Account:
        if not self.configured:
            raise FunPayNotConfiguredError("FUNPAY_GOLDEN_KEY is not configured")
        if self._account is not None:
            return self._account

        await self.throttle.acquire()
        async with self._lock:
            if self._account is None:
                self._account = await asyncio.to_thread(self._build_account)
            return self._account

    async def _call_locked(self, func: Any) -> Any:
        async with self._lock:
            try:
                return await asyncio.to_thread(func)
            except exceptions.UnauthorizedError:
                self._account = None
                raise

    def _build_account(self) -> Account:
        account = Account(settings.funpay_golden_key, settings.funpay_user_agent).get()
        return account


funpay_client = FunPayClient()

