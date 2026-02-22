"""
Telegram channel adapter: connects Telegram Bot API to the gateway.
Uses python-telegram-bot library with polling mode.
"""
import asyncio
import logging
import re

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ChatAction

from channels.telegram.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CONFIG
from gateway.contracts import InboundEvent, AgentReply, Platform
from gateway.handler import handle_inbound
from models.database import SessionLocal

logger = logging.getLogger(__name__)


async def _get_db():
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


# ── Command Handlers ─────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text(
        "Welcome to ClawFans!\n\n"
        "I'm your AI character chat companion.\n\n"
        "Commands:\n"
        "  /char - List or switch characters\n"
        "  /status - Show current session\n"
        "  /reset - Start a new session\n"
        "  /bind <code> - Link your web account\n\n"
        "Just send a message to start chatting!"
    )


async def cmd_char(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /char command: list or switch characters."""
    args = " ".join(context.args) if context.args else ""
    db = await _get_db()
    try:
        event = InboundEvent(
            platform=Platform.TELEGRAM,
            platform_user_id=str(update.effective_user.id),
            command="char",
            command_args=args,
        )
        reply = await handle_inbound(event, db)
        await update.message.reply_text(reply.text or "No response.")
    finally:
        db.close()


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command."""
    db = await _get_db()
    try:
        event = InboundEvent(
            platform=Platform.TELEGRAM,
            platform_user_id=str(update.effective_user.id),
            command="status",
        )
        reply = await handle_inbound(event, db)
        await update.message.reply_text(reply.text or "No active session.")
    finally:
        db.close()


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reset command: deactivate current session."""
    db = await _get_db()
    try:
        from models.database import ChatSession
        session = (
            db.query(ChatSession)
            .filter(
                ChatSession.platform == "telegram",
                ChatSession.platform_user_id == str(update.effective_user.id),
                ChatSession.status == "active",
            )
            .first()
        )
        if session:
            session.status = "reset"
            db.commit()
            await update.message.reply_text("Session reset. Send a message to start fresh!")
        else:
            await update.message.reply_text("No active session to reset.")
    finally:
        db.close()


async def cmd_bind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /bind <code>: link Telegram to web account."""
    code = " ".join(context.args).strip() if context.args else ""
    if not code:
        await update.message.reply_text("Usage: /bind <code>\nGet a bind code from the web app.")
        return
    # M4 will implement actual binding logic
    await update.message.reply_text(
        f"Bind code received: {code}\n"
        f"[Binding will be available after M4 implementation]"
    )


# ── Message Handler ──────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages."""
    if not update.message or not update.message.text:
        return

    user_id = str(update.effective_user.id)
    text = update.message.text.strip()

    if not text:
        return

    # Allowlist check
    if TELEGRAM_CONFIG["allowlist_mode"]:
        if int(user_id) not in TELEGRAM_CONFIG["allowed_user_ids"]:
            await update.message.reply_text("Access denied. Contact the admin.")
            return

    # Send typing indicator
    await update.message.chat.send_action(ChatAction.TYPING)

    db = await _get_db()
    try:
        # Determine character_id from active session or default
        from models.database import ChatSession
        session = (
            db.query(ChatSession)
            .filter(
                ChatSession.platform == "telegram",
                ChatSession.platform_user_id == user_id,
                ChatSession.status == "active",
            )
            .order_by(ChatSession.last_active_at.desc())
            .first()
        )
        character_id = session.character_id if session else TELEGRAM_CONFIG["default_character_id"]

        event = InboundEvent(
            platform=Platform.TELEGRAM,
            platform_user_id=user_id,
            character_id=character_id,
            text=text,
        )

        reply = await handle_inbound(event, db)

        # Split long messages for Telegram's 4096 char limit
        reply_text = reply.text or "..."
        max_len = TELEGRAM_CONFIG["max_message_length"]

        chunks = []
        while reply_text:
            if len(reply_text) <= max_len:
                chunks.append(reply_text)
                break
            split_pos = reply_text.rfind("\n", 0, max_len)
            if split_pos == -1:
                split_pos = max_len
            chunks.append(reply_text[:split_pos])
            reply_text = reply_text[split_pos:].lstrip()

        for i, chunk in enumerate(chunks):
            if i > 0:
                await asyncio.sleep(TELEGRAM_CONFIG["typing_delay_seconds"])
                await update.message.chat.send_action(ChatAction.TYPING)
            await update.message.reply_text(chunk)

    except Exception as e:
        logger.error(f"Error processing message from {user_id}: {e}")
        await update.message.reply_text("Something went wrong. Please try again.")
    finally:
        db.close()


# ── Bot Setup ────────────────────────────────────────────────────────────────

def create_telegram_app() -> Application | None:
    """Create and configure the Telegram bot application."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning(
            "TELEGRAM_BOT_TOKEN not set. Telegram channel disabled.\n"
            "Set it via environment variable or in channels/telegram/config.py"
        )
        return None

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("char", cmd_char))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("bind", cmd_bind))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app


async def start_telegram_polling():
    """Start the Telegram bot in polling mode (for development)."""
    app = create_telegram_app()
    if not app:
        return

    # Set bot commands for nice UI
    commands = [
        BotCommand("char", "List or switch characters"),
        BotCommand("status", "Show current session info"),
        BotCommand("reset", "Reset the current session"),
        BotCommand("bind", "Link your web account"),
    ]

    await app.initialize()
    await app.bot.set_my_commands(commands)
    await app.start()
    logger.info("Telegram bot started (polling mode)")

    await app.updater.start_polling(drop_pending_updates=True)

    return app


async def stop_telegram(app: Application):
    """Gracefully stop the Telegram bot."""
    if app and app.updater:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        logger.info("Telegram bot stopped")
