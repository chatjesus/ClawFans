"""
The vip_only_explicit / vip_only_explicit_text levers are GLOBAL kill-switches —
flipping them True strips explicit content from EVERY user (incl. paying ones),
exactly the monetization-driven removal that traumatized Replika/CAI refugees.

monetization_locked (default True for the trial) neutralizes those levers so an
operator (or a slip) can't yank content out from under users. Real per-user
paywalls are a post-validation concern.
"""
from services import ops_config


def test_monetization_locked_by_default():
    assert ops_config.DEFAULTS["monetization_locked"] is True


def test_vip_levers_neutralized_while_locked(db):
    # even if an operator flips the global vip switches, locked trial ignores them
    ops_config.set_ops_values(db, {"vip_only_explicit": True, "vip_only_explicit_text": True})
    assert ops_config.is_text_explicit_allowed(db, 90) is True
    assert ops_config.is_image_explicit_allowed(db, 90) is True


def test_vip_levers_apply_once_monetization_unlocked(db):
    ops_config.set_ops_values(db, {
        "monetization_locked": False,
        "vip_only_explicit": True,
        "vip_only_explicit_text": True,
    })
    assert ops_config.is_text_explicit_allowed(db, 90) is False
    assert ops_config.is_image_explicit_allowed(db, 90) is False
