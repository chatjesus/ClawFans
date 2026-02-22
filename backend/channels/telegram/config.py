"""
Telegram bot configuration.
Set TELEGRAM_BOT_TOKEN environment variable or edit this file.
"""
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

TELEGRAM_CONFIG = {
    "typing_delay_seconds": 1.5,
    "max_message_length": 4096,
    "default_character_id": 1,
    "allowlist_mode": False,
    "allowed_user_ids": [],
}
