from app.config import settings
from app.throttle import SlidingWindowThrottle


class FunPayClient:
    def __init__(self) -> None:
        self.throttle = SlidingWindowThrottle(settings.funpay_max_actions_per_minute)

    @property
    def configured(self) -> bool:
        return bool(settings.funpay_golden_key)

    async def send_message(self, chat_id: str, body: str) -> dict:
        await self.throttle.acquire()
        if not self.configured:
            return {
                "status": "dry_run",
                "chat_id": chat_id,
                "body": body,
                "detail": "FUNPAY_GOLDEN_KEY is not configured",
            }
        raise NotImplementedError("Wire Python FunPayAPI send_message after live API verification.")

    async def fetch_messages(self) -> list[dict]:
        await self.throttle.acquire()
        if not self.configured:
            return []
        raise NotImplementedError("Wire Python FunPayAPI polling after live API verification.")

    async def create_order(self, lot_url: str) -> dict:
        await self.throttle.acquire()
        if not self.configured:
            return {
                "status": "dry_run",
                "lot_url": lot_url,
                "payment_link": None,
                "detail": "FUNPAY_GOLDEN_KEY is not configured",
            }
        raise NotImplementedError("Wire Python FunPayAPI purchase flow after payment-link spike.")


funpay_client = FunPayClient()

