"""
Configurable adult-operations layer.

A single source of truth for the operator-tunable levers that drive an adult
companion product's monetization and engagement. Mechanics read these instead
of hardcoding; operators change them via the admin API (api/admin.py) — no
redeploy. Stored as JSON-encoded key/value rows (models.database.OpsConfig)
merged over the DEFAULTS below.
"""
import json

from sqlalchemy.orm import Session

from models.database import OpsConfig

# Sane defaults. Every lever an operator can tune must appear here.
DEFAULTS: dict = {
    # Intimacy at which explicit text/images unlock (Candy.AI-style gating).
    "nsfw_unlock_intimacy": 40,
    # How fast the relationship deepens. <1 slow-burn, >1 aggressive.
    "intimacy_gain_multiplier": 1.0,
    # How long the user must be away before the character reaches out first.
    "proactive_greeting_min_hours": 6,
    # Intimacy granted for the first message of a new day (check-in reward).
    "daily_checkin_intimacy_bonus": 2,
    # Operator master switch for explicit image generation.
    "nsfw_images_enabled": True,
    # Gate the most explicit content behind a VIP/paid flag (paywall hook).
    "vip_only_explicit": False,
}


def get_ops_config(db: Session) -> dict:
    """Return the full config: DEFAULTS overlaid with any stored overrides."""
    cfg = dict(DEFAULTS)
    for row in db.query(OpsConfig).all():
        try:
            cfg[row.key] = json.loads(row.value)
        except (ValueError, TypeError):
            cfg[row.key] = row.value
    return cfg


def get_ops_value(db: Session, key: str, default=None):
    """One value, with the DEFAULTS fallback (or an explicit default)."""
    row = db.query(OpsConfig).filter(OpsConfig.key == key).first()
    if row is not None:
        try:
            return json.loads(row.value)
        except (ValueError, TypeError):
            return row.value
    return DEFAULTS.get(key, default)


def set_ops_values(db: Session, updates: dict) -> dict:
    """Upsert each key (JSON-encoded). Returns the merged config."""
    for key, value in updates.items():
        row = db.query(OpsConfig).filter(OpsConfig.key == key).first()
        encoded = json.dumps(value)
        if row is None:
            db.add(OpsConfig(key=key, value=encoded))
        else:
            row.value = encoded
    db.commit()
    return get_ops_config(db)
