import asyncio
import logging

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.config import settings
from bot.credential_confirmations import pop_pending_credentials
from bot.credentials import extract_credentials
from bot.db import db
from bot.last_chat import get_last_relay_chat
from bot.poller import poll_funpay_messages

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

_poller_task: asyncio.Task | None = None


def _redact_secrets(value: str) -> str:
    if settings.telegram_bot_token:
        value = value.replace(settings.telegram_bot_token, "<redacted>")
        value = value.replace(f"bot{settings.telegram_bot_token}", "bot<redacted>")
    return value


class SensitiveLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _redact_secrets(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(_redact_secrets(arg) if isinstance(arg, str) else arg for arg in record.args)
        elif isinstance(record.args, dict):
            record.args = {
                key: _redact_secrets(value) if isinstance(value, str) else value
                for key, value in record.args.items()
            }
        return True


for handler in logging.getLogger().handlers:
    handler.addFilter(SensitiveLogFilter())


async def guarded(update: Update) -> bool:
    user = update.effective_user
    if not user or not await db.is_allowed_user(user.id):
        if update.effective_chat:
            await update.effective_chat.send_message("Доступ запрещен.")
        return False
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guarded(update):
        return
    await update.effective_chat.send_message(
        "FunPayBot готов к работе.\n"
        "/send <chat_id> <message> — отправить сообщение продавцу\n"
        "/chats — список ваших назначенных чатов\n"
        "/assign <chat_id> <telegram_user_id> — назначить чат (только админ)"
    )


async def send_to_seller(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guarded(update):
        return
    if len(context.args) < 2:
        await update.effective_chat.send_message("Использование: /send <funpay_chat_id> <message>")
        return

    chat_id = context.args[0]
    body = " ".join(context.args[1:])
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            f"{settings.funpay_api_url}/chats/send",
            json={"chat_id": chat_id, "body": body},
            headers=settings.internal_headers(),
        )
    if not response.is_success:
        await update.effective_chat.send_message("Не удалось отправить сообщение.")
        return
    await db.save_outbound_message(update.effective_user.id, chat_id, body)
    await update.effective_chat.send_message("Отправлено.")


async def list_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List chats assigned to the current manager."""
    if not await guarded(update):
        return
    chats = await db.get_assigned_chats(update.effective_user.id)
    if not chats:
        await update.effective_chat.send_message("Вам не назначено ни одного чата.")
        return
    lines = []
    for chat in chats:
        seller = chat["seller_name"] or "Неизвестно"
        lines.append(f"• {chat['funpay_chat_id']} — {seller}")
    await update.effective_chat.send_message("Ваши назначенные чаты:\n" + "\n".join(lines))


async def assign_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to assign a FunPay chat to a manager by Telegram user ID."""
    if not await guarded(update):
        return
    user = await db.user_by_telegram(update.effective_user.id)
    if not user or user["role"] != "admin":
        if update.effective_user.id not in settings.admin_ids:
            await update.effective_chat.send_message("Только для администратора.")
            return

    if len(context.args) < 2:
        await update.effective_chat.send_message("Использование: /assign <funpay_chat_id> <manager_telegram_id>")
        return

    funpay_chat_id = context.args[0]
    try:
        manager_tg_id = int(context.args[1])
    except ValueError:
        await update.effective_chat.send_message("Некорректный Telegram ID.")
        return

    manager = await db.user_by_telegram(manager_tg_id)
    if not manager:
        await update.effective_chat.send_message("Менеджер с таким Telegram ID не найден.")
        return

    await db.ensure_chat(funpay_chat_id)
    await db.assign_chat(funpay_chat_id, manager["id"])
    await update.effective_chat.send_message(f"Чат {funpay_chat_id} назначен пользователю {manager['display_name']}.")


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guarded(update):
        return
    if not update.message or not update.message.text:
        return
    credentials = extract_credentials(update.message.text)
    if not credentials:
        await update.message.reply_text(
            "Не удалось распознать данные для входа. Отправьте логин:пароль или используйте /send для чата с продавцом."
        )
        return
    context.user_data["pending_credentials"] = credentials
    context.user_data["pending_chat_id"] = get_last_relay_chat(update.effective_user.id)
    await update.message.reply_text(
        f"Подтвердить данные?\n{credentials}",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Подтвердить", callback_data="confirm_credentials")]]
        ),
    )


async def confirm_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not await db.is_allowed_user(query.from_user.id):
        await query.edit_message_text("Доступ запрещен.")
        return
    callback_data = query.data or ""
    pending = None
    if callback_data.startswith("confirm_credentials:"):
        token = callback_data.split(":", 1)[1]
        pending = pop_pending_credentials(token)
        if pending is None:
            await query.edit_message_text("Данные уже подтверждены или устарели.")
            return
        if pending.manager_telegram_id != query.from_user.id:
            await query.edit_message_text("Эти данные назначены другому менеджеру.")
            return

    credentials = pending.credentials if pending else context.user_data.get("pending_credentials")
    if not credentials:
        await query.edit_message_text("Нет ожидающих подтверждения данных.")
        return
    chat_id = pending.chat_id if pending else context.user_data.get("pending_chat_id")
    account_id = await db.confirm_account(query.from_user.id, credentials, chat_id)
    context.user_data.pop("pending_credentials", None)
    context.user_data.pop("pending_chat_id", None)
    await query.edit_message_text(f"Аккаунт {account_id} сохранен.")


async def post_init(application: Application) -> None:
    global _poller_task
    await db.connect()
    logger.info("База данных Telegram-бота подключена")
    _poller_task = asyncio.create_task(poll_funpay_messages(application.bot))
    logger.info("Фоновая задача опроса запущена")


async def post_shutdown(application: Application) -> None:
    global _poller_task
    if _poller_task and not _poller_task.done():
        _poller_task.cancel()
        try:
            await _poller_task
        except asyncio.CancelledError:
            pass
    await db.close()


def main() -> None:
    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN не настроен; Telegram-бот отключен")
        asyncio.run(asyncio.Event().wait())
        return

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("send", send_to_seller))
    application.add_handler(CommandHandler("chats", list_chats))
    application.add_handler(CommandHandler("assign", assign_chat))
    application.add_handler(CallbackQueryHandler(confirm_credentials, pattern=r"^confirm_credentials(:[0-9a-f]+)?$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
