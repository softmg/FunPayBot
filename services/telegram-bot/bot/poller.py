import asyncio
import logging

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import settings
from bot.credential_confirmations import create_pending_credentials
from bot.credentials import extract_credentials
from bot.db import db
from bot.last_chat import set_last_relay_chat

logger = logging.getLogger(__name__)
_funpay_account_id: int | None = None


async def poll_funpay_messages(bot) -> None:
    """Background task that polls FunPay for new seller messages and relays them to assigned managers."""
    interval = settings.funpay_poll_interval_seconds
    logger.info("Опросчик запущен, интервал=%dс", interval)

    while True:
        try:
            await _poll_once(bot)
        except asyncio.CancelledError:
            logger.info("Опросчик остановлен")
            return
        except Exception:
            logger.exception("Сбой итерации опросчика")

        await asyncio.sleep(interval)


async def _poll_once(bot) -> None:
    """Single poll iteration: fetch chats, detect new messages, relay to managers."""
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            account_id = await _get_funpay_account_id(client)
            response = await client.get(
                f"{settings.funpay_api_url}/chats",
                params={"update": "true"},
                headers=settings.internal_headers(),
            )
        except httpx.TimeoutException as exc:
            logger.warning("Таймаут при получении списка чатов: %s", exc)
            return

    if not response.is_success:
        logger.warning("Не удалось получить список чатов: %s", response.status_code)
        return

    chats = response.json().get("chats", [])

    for chat in chats:
        try:
            await _process_chat(bot, chat, account_id)
        except Exception:
            logger.exception("Сбой обработки чата %s", chat.get("id"))


async def _process_chat(bot, chat: dict, account_id: int | None) -> None:
    chat_id = chat.get("id")
    chat_name = chat.get("name")
    if chat_id is None:
        return

    funpay_chat_id = str(chat_id)
    internal_chat_id = await db.ensure_chat(funpay_chat_id, chat_name)

    manager_tg_id = await db.get_manager_telegram_id_for_chat(funpay_chat_id)
    if manager_tg_id is None:
        manager_tg_id = await db.assign_chat_to_pending_order(funpay_chat_id, internal_chat_id)
        if manager_tg_id is None:
            return

    watermark = await db.get_watermark(funpay_chat_id)
    node_msg_id = _as_int(chat.get("node_msg_id"))

    if watermark is not None and node_msg_id is not None and node_msg_id <= watermark:
        return

    await _fetch_and_relay_new_messages(bot, internal_chat_id, funpay_chat_id, chat_name, manager_tg_id, watermark, account_id)


def _as_int(value) -> int | None:
    """Parse a FunPay id to int, tolerating missing or non-numeric values."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def _get_funpay_account_id(client: httpx.AsyncClient) -> int | None:
    global _funpay_account_id
    if _funpay_account_id is not None:
        return _funpay_account_id
    response = await client.get(
        f"{settings.funpay_api_url}/session",
        headers=settings.internal_headers(),
    )
    if not response.is_success:
        logger.warning("Не удалось получить статус FunPay-сессии: %s", response.status_code)
        return None
    account_id = response.json().get("id")
    if account_id is None:
        return None
    _funpay_account_id = int(account_id)
    return _funpay_account_id


async def _fetch_and_relay_new_messages(
    bot,
    internal_chat_id: str,
    funpay_chat_id: str,
    chat_name: str | None,
    manager_tg_id: int,
    watermark: int | None,
    account_id: int | None,
) -> None:
    """Fetch chat history and relay messages newer than the watermark."""
    params: dict = {"chat_id": funpay_chat_id}
    if watermark is not None:
        params["from_id"] = watermark

    async with httpx.AsyncClient(timeout=20) as client:
        try:
            response = await client.get(
                f"{settings.funpay_api_url}/chats/{funpay_chat_id}/history",
                params=params,
                headers=settings.internal_headers(),
            )
        except httpx.TimeoutException as exc:
            logger.warning("Таймаут при получении истории чата %s: %s", funpay_chat_id, exc)
            return

    if not response.is_success:
        logger.warning("Не удалось получить историю чата %s: %s", funpay_chat_id, response.status_code)
        return

    messages = response.json().get("messages", [])

    for msg in messages:
        msg_id = msg.get("id")
        if msg_id is None:
            continue

        numeric_msg_id = _as_int(msg_id)
        if watermark is not None and numeric_msg_id is not None and numeric_msg_id <= watermark:
            continue

        text = msg.get("text", "")
        author = msg.get("author", "Продавец")
        author_id = msg.get("author_id")

        await db.save_inbound_message(internal_chat_id, str(msg_id), author, text)
        set_last_relay_chat(manager_tg_id, internal_chat_id)

        try:
            formatted = f"💬 *{_escape_md(chat_name or funpay_chat_id)}*\n{_escape_md(author)}: {_escape_md(text)}"
            buttons = []
            can_capture_delivery = (
                text.strip()
                and author.lower() != "funpay"
                and (account_id is None or _as_int(author_id) != account_id)
            )
            if can_capture_delivery:
                raw_token = create_pending_credentials(manager_tg_id, text.strip(), internal_chat_id)
                buttons.append(
                    [InlineKeyboardButton("Сохранить сообщение как аккаунт", callback_data=f"confirm_credentials:{raw_token}")]
                )

            credentials = extract_credentials(text)
            if can_capture_delivery and credentials and credentials != text.strip():
                parsed_token = create_pending_credentials(manager_tg_id, credentials, internal_chat_id)
                formatted = (
                    f"{formatted}\n\n"
                    f"Найдены возможные данные аккаунта:\n`{_escape_md(credentials)}`"
                )
                buttons.append(
                    [InlineKeyboardButton("Сохранить найденные данные", callback_data=f"confirm_credentials:{parsed_token}")]
                )
            reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
            await bot.send_message(
                chat_id=manager_tg_id,
                text=formatted,
                parse_mode="MarkdownV2",
                reply_markup=reply_markup,
            )
        except Exception:
            logger.exception("Не удалось отправить сообщение менеджеру %d", manager_tg_id)


def _escape_md(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    special = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in text)
