import asyncio
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup
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


class FunPayPurchaseFlowError(RuntimeError):
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
        account = await self._ensure_account()
        await self.throttle.acquire()

        def call() -> dict:
            return create_order_from_offer(account, lot_url)

        return await self._call_locked(call)

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


def create_order_from_offer(account: Account, lot_url: str) -> dict:
    lot_id = extract_lot_id(lot_url)
    response = account.method(
        "get",
        f"lots/offer?id={lot_id}",
        {"accept": "*/*"},
        {},
        raise_not_200=True,
        locale="en",
    )
    offer_page_url = response.url
    form = parse_order_form(response.text, str(offer_page_url))
    post_response = account.method(
        "post",
        form["action"],
        {
            "accept": "*/*",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "referer": str(offer_page_url),
        },
        form["payload"],
        raise_not_200=True,
    )
    payment_link = extract_payment_link(post_response, str(offer_page_url))
    return {
        "status": "payment_pending",
        "lot_url": lot_url,
        "offer_id": lot_id,
        "payment_link": payment_link,
        "payment_method": form["payment_method"],
    }


def extract_lot_id(lot_url: str) -> int:
    parsed = urlparse(lot_url)
    query_id = parse_qs(parsed.query).get("id", [None])[0]
    if query_id and query_id.isdigit():
        return int(query_id)
    match = re.search(r"/(?:lots|chips)/offer/(\d+)", parsed.path)
    if match:
        return int(match.group(1))
    raise FunPayPurchaseFlowError("Lot URL does not contain a FunPay offer id")


def parse_order_form(html: str, page_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form", action=re.compile(r"/orders/new\b"))
    if form is None:
        error = soup.find("p", class_="lead")
        detail = error.get_text(" ", strip=True) if error else "FunPay order form was not found"
        raise FunPayPurchaseFlowError(detail)

    payload = {
        field["name"]: field.get("value", "")
        for field in form.find_all("input")
        if field.get("name") and field.get("name") != "sum"
    }
    payload["amount"] = payload.get("amount") or "1"

    method = choose_payment_method(form)
    payload["method"] = method["id"]
    return {
        "action": urljoin(page_url, form["action"]),
        "payload": payload,
        "payment_method": method,
    }


def choose_payment_method(form: Any) -> dict:
    options = []
    for option in form.select('select[name="method"] option[value]'):
        value = option.get("value", "").strip()
        title = option.get_text(" ", strip=True)
        if not value or value == "0" or "hidden" in option.get("class", []):
            continue
        content = option.get("data-content", "")
        options.append(
            {
                "id": value,
                "title": title,
                "currency": option.get("data-cy"),
                "label": f"{title} {content}".lower(),
            }
        )
    if not options:
        raise FunPayPurchaseFlowError("FunPay did not offer any payment methods")

    preferred_keywords = ("usdt", "crypto", "cryptocurrency", "tron", "trc20", "erc20")
    selected = next(
        (option for option in options if any(keyword in option["label"] for keyword in preferred_keywords)),
        options[0],
    )
    return {key: value for key, value in selected.items() if key != "label"}


def extract_payment_link(response: Any, fallback_url: str) -> str:
    location = response.headers.get("location")
    if location:
        return urljoin(fallback_url, location)

    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        data = response.json()
        for key in ("payment_link", "payment_url", "url", "location", "redirect"):
            value = data.get(key)
            if isinstance(value, str) and value:
                return urljoin(fallback_url, value)

    soup = BeautifulSoup(response.text, "html.parser")
    for selector in ("a[href]", "form[action]"):
        attr = "href" if selector == "a[href]" else "action"
        for node in soup.select(selector):
            value = node.get(attr)
            if value and re.search(r"(orders/|pay|payment|checkout)", value, re.IGNORECASE):
                return urljoin(fallback_url, value)

    current_url = str(response.url)
    if current_url and current_url != fallback_url:
        return current_url

    raise FunPayPurchaseFlowError("FunPay order was created, but no payment link was found in the response")
