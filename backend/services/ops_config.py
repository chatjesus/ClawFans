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
    # Intimacy at which explicit IMAGES unlock (Candy.AI-style gating).
    "nsfw_unlock_intimacy": 40,
    # Intimacy at which explicit TEXT unlocks — the slow-burn foundation.
    # Below this, build_intimacy_prompt injects a hard limit (deflect-and-tease,
    # no explicit prose). Default 60 (the 暧昧 tier) so text unlocks no earlier
    # than — ideally slightly later than — images.
    "text_explicit_unlock_intimacy": 60,
    # Text parity for vip_only_explicit (which gates images only). When True,
    # explicit prose stays locked even above threshold unless the user is VIP.
    "vip_only_explicit_text": False,
    # Trial safety: while True, the global vip_only_* kill-switches are
    # NEUTRALIZED so an operator (or a slip) can't strip explicit content from
    # everyone at once (the Replika-trauma move). Flip False only post-validation
    # when a real per-user paywall exists.
    "monetization_locked": True,
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
    # Daily surprise / gacha: master switch + rarity weights (dopamine cadence +
    # monetization lever — rarer = bigger reward, lower odds).
    "surprise_enabled": True,
    "surprise_rarity_weights": {"common": 60, "rare": 28, "epic": 10, "legendary": 2},
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


def is_text_explicit_allowed(db: Session, level: int, unlock_override: int | None = None) -> bool:
    """Single source of truth for the slow-burn TEXT gate. Explicit prose is
    allowed only at/above the unlock threshold and never when
    ``vip_only_explicit_text`` paywalls it. Mirror of the image gate in
    chat_service.process_reply_images. Used by every prompt-assembly path
    (chat, proactive greeting, surprise) so the gate can't leak.

    unlock_override (Character.explicit_unlock_intimacy) lets a specific
    character relax/remove the gate for the anchored core user — None falls
    back to the global ``text_explicit_unlock_intimacy``."""
    unlock = unlock_override if unlock_override is not None \
        else get_ops_value(db, "text_explicit_unlock_intimacy", 60)
    if level < unlock:
        return False
    if get_ops_value(db, "vip_only_explicit_text", False) \
            and not get_ops_value(db, "monetization_locked", True):
        return False
    return True


def is_image_explicit_allowed(db: Session, level: int, unlock_override: int | None = None) -> bool:
    """Image-explicitness gate, parallel to is_text_explicit_allowed. Honors a
    per-character ``explicit_unlock_intimacy`` override so a start-hot character's
    PHOTOS unlock in step with its text (no SFW-image / explicit-text split).
    Falls back to the global ``nsfw_unlock_intimacy``; ``vip_only_explicit`` clamps."""
    unlock = unlock_override if unlock_override is not None \
        else get_ops_value(db, "nsfw_unlock_intimacy", 40)
    if level < unlock:
        return False
    if get_ops_value(db, "vip_only_explicit", False) \
            and not get_ops_value(db, "monetization_locked", True):
        return False
    return True


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
