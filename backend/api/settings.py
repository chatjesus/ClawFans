"""
Settings API: manage platform configuration (Telegram, Discord, etc.)
Stores config in a JSON file so it persists across restarts.
"""
import os
import json
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "platform_config.json")

_telegram_app = None


def _load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "telegram": {
            "bot_token": "",
            "enabled": False,
            "default_character_id": 1,
            "allowlist_mode": False,
            "allowed_user_ids": [],
        },
        "discord": {
            "bot_token": "",
            "enabled": False,
        },
    }


def _save_config(config: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


class TelegramConfig(BaseModel):
    bot_token: str = ""
    enabled: bool = False
    default_character_id: int = 1
    allowlist_mode: bool = False
    allowed_user_ids: list[int] = []


class PlatformStatus(BaseModel):
    platform: str
    enabled: bool
    connected: bool
    bot_username: Optional[str] = None
    error: Optional[str] = None


# ── GET all settings ────────────────────────────────────────

@router.get("/platforms")
def get_platform_settings():
    """Get all platform configurations (tokens are masked)."""
    config = _load_config()
    result = {}
    for platform, cfg in config.items():
        masked = dict(cfg)
        if "bot_token" in masked and masked["bot_token"]:
            token = masked["bot_token"]
            masked["bot_token_masked"] = token[:8] + "..." + token[-4:] if len(token) > 12 else "***"
            masked["bot_token_set"] = True
        else:
            masked["bot_token_masked"] = ""
            masked["bot_token_set"] = False
        masked.pop("bot_token", None)
        result[platform] = masked
    return result


# ── Telegram ────────────────────────────────────────────────

@router.get("/telegram")
def get_telegram_config():
    """Get Telegram configuration (token masked)."""
    config = _load_config()
    tg = config.get("telegram", {})
    token = tg.get("bot_token", "")
    return {
        "bot_token_set": bool(token),
        "bot_token_masked": (token[:8] + "..." + token[-4:]) if len(token) > 12 else ("***" if token else ""),
        "enabled": tg.get("enabled", False),
        "default_character_id": tg.get("default_character_id", 1),
        "allowlist_mode": tg.get("allowlist_mode", False),
        "allowed_user_ids": tg.get("allowed_user_ids", []),
    }


@router.put("/telegram")
async def update_telegram_config(data: TelegramConfig):
    """Update Telegram configuration and optionally start/stop the bot."""
    config = _load_config()

    if data.bot_token:
        config.setdefault("telegram", {})["bot_token"] = data.bot_token
    config.setdefault("telegram", {})["enabled"] = data.enabled
    config.setdefault("telegram", {})["default_character_id"] = data.default_character_id
    config.setdefault("telegram", {})["allowlist_mode"] = data.allowlist_mode
    config.setdefault("telegram", {})["allowed_user_ids"] = data.allowed_user_ids
    _save_config(config)

    if data.enabled and config["telegram"].get("bot_token"):
        result = await _start_telegram(config["telegram"]["bot_token"], data.default_character_id)
        return result
    else:
        await _stop_telegram()
        return {"status": "disabled", "connected": False}


@router.post("/telegram/test")
async def test_telegram_token(data: dict):
    """Test a Telegram bot token without saving it."""
    token = data.get("bot_token", "")
    if not token:
        raise HTTPException(400, "bot_token is required")

    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
        if resp.status_code == 200:
            bot_info = resp.json().get("result", {})
            return {
                "valid": True,
                "bot_username": bot_info.get("username", ""),
                "bot_name": bot_info.get("first_name", ""),
            }
        else:
            return {"valid": False, "error": "Invalid token"}
    except Exception as e:
        return {"valid": False, "error": str(e)}


@router.get("/telegram/status")
async def get_telegram_status():
    """Get current Telegram bot connection status."""
    global _telegram_app
    config = _load_config()
    tg = config.get("telegram", {})

    if not tg.get("bot_token"):
        return PlatformStatus(platform="telegram", enabled=False, connected=False)

    if _telegram_app:
        try:
            bot_info = await _telegram_app.bot.get_me()
            return PlatformStatus(
                platform="telegram",
                enabled=tg.get("enabled", False),
                connected=True,
                bot_username=f"@{bot_info.username}",
            )
        except Exception as e:
            return PlatformStatus(
                platform="telegram",
                enabled=tg.get("enabled", False),
                connected=False,
                error=str(e),
            )

    return PlatformStatus(
        platform="telegram",
        enabled=tg.get("enabled", False),
        connected=False,
    )


async def _start_telegram(token: str, default_character_id: int = 1) -> dict:
    """Start the Telegram bot with the given token."""
    global _telegram_app
    await _stop_telegram()

    try:
        from channels.telegram.config import TELEGRAM_CONFIG
        TELEGRAM_CONFIG["default_character_id"] = default_character_id

        import channels.telegram.config as tg_cfg
        tg_cfg.TELEGRAM_BOT_TOKEN = token

        from channels.telegram.adapter import start_telegram_polling
        _telegram_app = await start_telegram_polling()
        if _telegram_app:
            try:
                import asyncio as _aio
                bot_info = await _aio.wait_for(_telegram_app.bot.get_me(), timeout=8.0)
                username = f"@{bot_info.username}"
            except Exception:
                username = "(unknown)"
            logger.info(f"Telegram bot started: {username}")
            return {
                "status": "connected",
                "connected": True,
                "bot_username": username,
            }
        return {"status": "failed", "connected": False, "error": "App creation returned None"}
    except Exception as e:
        logger.error(f"Telegram start failed: {e}")
        return {"status": "failed", "connected": False, "error": str(e)}


async def _stop_telegram():
    """Stop the running Telegram bot if any."""
    global _telegram_app
    if _telegram_app:
        try:
            from channels.telegram.adapter import stop_telegram
            await stop_telegram(_telegram_app)
        except Exception as e:
            logger.warning(f"Telegram stop error: {e}")
        _telegram_app = None


async def auto_start_telegram():
    """Called on app startup to auto-connect if previously configured."""
    config = _load_config()
    tg = config.get("telegram", {})
    if tg.get("enabled") and tg.get("bot_token"):
        logger.info("Auto-starting Telegram bot from saved config...")
        await _start_telegram(tg["bot_token"], tg.get("default_character_id", 1))
