import asyncio
import logging

import httpx

from bot.config import settings
from bot.db import db

logger = logging.getLogger(__name__)


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
            response = await client.get(f"{settings.funpay_api_url}/chats", params={"update": "true"})
        except httpx.TimeoutException as exc:
            logger.warning("Таймаут при получении списка чатов: %s", exc)
            return

    if not response.is_success:
        logger.warning("Не удалось получить список чатов: %s", response.status_code)
        return

    chats = response.json().get("chats", [])

    for chat in chats:
        chat_id = chat.get("id")
        chat_name = chat.get("name")
        if chat_id is None:
            continue

        funpay_chat_id = str(chat_id)
        internal_chat_id = await db.ensure_chat(funpay_chat_id, chat_name)

        manager_tg_id = await db.get_manager_telegram_id_for_chat(funpay_chat_id)
        if manager_tg_id is None:
            manager_tg_id = await db.assign_chat_to_pending_order(funpay_chat_id, internal_chat_id)
            if manager_tg_id is None:
                continue

        watermark = await db.get_watermark(funpay_chat_id)
        node_msg_id = chat.get("node_msg_id")

        if watermark is not None and node_msg_id is not None and int(node_msg_id) <= watermark:
            continue

        await _fetch_and_relay_new_messages(bot, internal_chat_id, funpay_chat_id, chat_name, manager_tg_id, watermark)


async def _fetch_and_relay_new_messages(
    bot,
    internal_chat_id: str,
    funpay_chat_id: str,
    chat_name: str | None,
    manager_tg_id: int,
    watermark: int | None,
) -> None:
    """Fetch chat history and relay messages newer than the watermark."""
    params: dict = {"chat_id": funpay_chat_id}
    if watermark is not None:
        params["from_id"] = watermark

    async with httpx.AsyncClient(timeout=20) as client:
        try:
            response = await client.get(f"{settings.funpay_api_url}/chats/{funpay_chat_id}/history", params=params)
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

        if watermark is not None and int(msg_id) <= watermark:
            continue

        text = msg.get("text", "")
        author = msg.get("author", "Продавец")

        await db.save_inbound_message(internal_chat_id, str(msg_id), author, text)

        try:
            formatted = f"💬 *{_escape_md(chat_name or funpay_chat_id)}*\n{_escape_md(author)}: {_escape_md(text)}"
            await bot.send_message(
                chat_id=manager_tg_id,
                text=formatted,
                parse_mode="MarkdownV2",
            )
        except Exception:
            logger.exception("Не удалось отправить сообщение менеджеру %d", manager_tg_id)


def _escape_md(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    special = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in text)
