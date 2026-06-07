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
from bot.credentials import extract_credentials
from bot.db import db
from bot.poller import poll_funpay_messages

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

_poller_task: asyncio.Task | None = None


async def guarded(update: Update) -> bool:
    user = update.effective_user
    if not user or not await db.is_allowed_user(user.id):
        if update.effective_chat:
            await update.effective_chat.send_message("Access denied.")
        return False
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guarded(update):
        return
    await update.effective_chat.send_message(
        "FunPayBot is ready.\n"
        "/send <chat_id> <message> — relay to seller\n"
        "/chats — list your assigned chats\n"
        "/assign <chat_id> <telegram_user_id> — assign chat (admin)"
    )


async def send_to_seller(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guarded(update):
        return
    if len(context.args) < 2:
        await update.effective_chat.send_message("Usage: /send <funpay_chat_id> <message>")
        return

    chat_id = context.args[0]
    body = " ".join(context.args[1:])
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            f"{settings.funpay_api_url}/chats/send",
            json={"chat_id": chat_id, "body": body},
        )
    if not response.is_success:
        await update.effective_chat.send_message("Message failed.")
        return
    await db.save_outbound_message(update.effective_user.id, chat_id, body)
    await update.effective_chat.send_message("Sent.")


async def list_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List chats assigned to the current manager."""
    if not await guarded(update):
        return
    chats = await db.get_assigned_chats(update.effective_user.id)
    if not chats:
        await update.effective_chat.send_message("No chats assigned to you.")
        return
    lines = []
    for chat in chats:
        seller = chat["seller_name"] or "Unknown"
        lines.append(f"• {chat['funpay_chat_id']} — {seller}")
    await update.effective_chat.send_message("Your assigned chats:\n" + "\n".join(lines))


async def assign_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to assign a FunPay chat to a manager by Telegram user ID."""
    if not await guarded(update):
        return
    user = await db.user_by_telegram(update.effective_user.id)
    if not user or user["role"] != "admin":
        if update.effective_user.id not in settings.admin_ids:
            await update.effective_chat.send_message("Admin only.")
            return

    if len(context.args) < 2:
        await update.effective_chat.send_message("Usage: /assign <funpay_chat_id> <manager_telegram_id>")
        return

    funpay_chat_id = context.args[0]
    try:
        manager_tg_id = int(context.args[1])
    except ValueError:
        await update.effective_chat.send_message("Invalid Telegram ID.")
        return

    manager = await db.user_by_telegram(manager_tg_id)
    if not manager:
        await update.effective_chat.send_message("Manager not found for that Telegram ID.")
        return

    await db.ensure_chat(funpay_chat_id)
    await db.assign_chat(funpay_chat_id, manager["id"])
    await update.effective_chat.send_message(f"Chat {funpay_chat_id} assigned to {manager['display_name']}.")


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guarded(update):
        return
    if not update.message or not update.message.text:
        return
    credentials = extract_credentials(update.message.text)
    if not credentials:
        await update.message.reply_text("No credentials detected. Send login:password or use /send for seller chat.")
        return
    context.user_data["pending_credentials"] = credentials
    context.user_data["pending_chat_id"] = context.user_data.get("last_relay_chat_id")
    await update.message.reply_text(
        f"Confirm credentials?\n{credentials}",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Confirm", callback_data="confirm_credentials")]]
        ),
    )


async def confirm_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not await db.is_allowed_user(query.from_user.id):
        await query.edit_message_text("Access denied.")
        return
    credentials = context.user_data.get("pending_credentials")
    if not credentials:
        await query.edit_message_text("No pending credentials.")
        return
    chat_id = context.user_data.get("pending_chat_id")
    account_id = await db.confirm_account(query.from_user.id, credentials, chat_id)
    context.user_data.pop("pending_credentials", None)
    context.user_data.pop("pending_chat_id", None)
    await query.edit_message_text(f"Saved account {account_id}.")


async def post_init(application: Application) -> None:
    global _poller_task
    await db.connect()
    logger.info("telegram bot database connected")
    _poller_task = asyncio.create_task(poll_funpay_messages(application.bot))
    logger.info("poller background task started")


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
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

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
    application.add_handler(CallbackQueryHandler(confirm_credentials, pattern="^confirm_credentials$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

