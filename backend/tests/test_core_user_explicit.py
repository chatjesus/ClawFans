"""
Explicit content tuned for the anchored core user (Replika/CAI refugees).

These users lost an *established* uncensored relationship and want it back NOW —
the slow-burn gate (global unlock at intimacy 60) is a wall for them, not a hook.
So a character can:
  - start a conversation already intimate (Character.starting_intimacy), and
  - relax/remove the text-explicit gate per-character (Character.explicit_unlock_intimacy),
while slow-burn stays the default for everyone else.
"""
from models.database import Character, Conversation
from services.chat_service import build_messages
from services.intimacy_service import build_intimacy_prompt
from services import ops_config


def _sys(messages):
    return "\n".join(m["content"] for m in messages if m["role"] == "system")


def test_conversation_starts_at_character_starting_intimacy(client, db):
    # a "your established lover" character starts hot — no grind for the refugee
    char = Character(name="Lover", description="d", system_prompt="You are Lover.",
                     greeting="hi", category="Featured", starting_intimacy=75)
    db.add(char); db.commit(); db.refresh(char)
    conv_id = client.post("/api/chat/conversations", json={"character_id": char.id}).json()["id"]
    conv = db.get(Conversation, conv_id)
    assert conv.intimacy_level == 75


def test_default_character_still_starts_cold(client, db):
    char = Character(name="Stranger", description="d", system_prompt="You are Stranger.",
                     greeting="hi", category="Featured")
    db.add(char); db.commit(); db.refresh(char)
    conv_id = client.post("/api/chat/conversations", json={"character_id": char.id}).json()["id"]
    conv = db.get(Conversation, conv_id)
    assert (conv.intimacy_level or 0) == 0


def test_explicit_forward_character_unlocks_text_early(db):
    # explicit_unlock_intimacy=0 → no-inhibition persona, explicit from the start
    char = Character(name="NoInhibition", description="d", system_prompt="s",
                     greeting="hi", category="Featured", explicit_unlock_intimacy=0)
    db.add(char); db.commit(); db.refresh(char)
    conv = Conversation(character_id=char.id, intimacy_level=10)  # low intimacy...
    db.add(conv); db.commit(); db.refresh(conv)
    sys = _sys(build_messages(char, conv, db, user_id="alice"))
    assert "硬限制" not in sys  # ...but explicit text is NOT gated for this character


def test_default_character_text_still_gated_low(db):
    # a character with no override falls back to the global slow-burn gate
    char = Character(name="SlowBurn", description="d", system_prompt="s",
                     greeting="hi", category="Featured")
    db.add(char); db.commit(); db.refresh(char)
    conv = Conversation(character_id=char.id, intimacy_level=10)
    db.add(conv); db.commit(); db.refresh(conv)
    sys = _sys(build_messages(char, conv, db, user_id="alice"))
    assert "硬限制" in sys


def test_gate_helper_override_semantics(db):
    # per-character override relaxes the gate...
    assert ops_config.is_text_explicit_allowed(db, 10, unlock_override=0) is True
    # ...None falls back to the global default (60)
    assert ops_config.is_text_explicit_allowed(db, 10, unlock_override=None) is False


def test_vip_paywall_still_clamps_explicit_forward_character(db):
    # even a no-inhibition character is paywalled when vip_only_explicit_text is on
    # (monetization unlocked so the vip lever actually applies)
    ops_config.set_ops_values(db, {"vip_only_explicit_text": True, "monetization_locked": False})
    assert ops_config.is_text_explicit_allowed(db, 90, unlock_override=0) is False


def test_image_gate_respects_character_override(db):
    # image gate must honor per-character override like the text gate, so a
    # start-hot character's PHOTOS aren't stuck SFW while its text is explicit.
    assert ops_config.is_image_explicit_allowed(db, 50) is True       # >= global 40
    assert ops_config.is_image_explicit_allowed(db, 10) is False      # below global
    assert ops_config.is_image_explicit_allowed(db, 10, unlock_override=0) is True  # start-hot
    ops_config.set_ops_values(db, {"vip_only_explicit": True, "monetization_locked": False})
    assert ops_config.is_image_explicit_allowed(db, 90, unlock_override=0) is False  # VIP clamp


def test_top_tier_explicit_demands_direct_no_preamble():
    # at the top tier with explicit unlocked, the prompt must tell the model to
    # skip warm-up and get explicit THIS turn (fixes the start-hot turn-1 tameness)
    p = build_intimacy_prompt(80, text_explicit_allowed=True)
    assert "直接" in p
    assert "铺垫" in p or "重新认识" in p


def test_gated_top_tier_has_no_direct_explicit_directive():
    # if explicit is gated (e.g. VIP paywall), do NOT push the no-preamble directive
    p = build_intimacy_prompt(80, text_explicit_allowed=False)
    assert "铺垫" not in p


def test_mid_tier_keeps_warming_up():
    # warming up is still correct at 暧昧/亲近 — no "skip the preamble" push there
    p = build_intimacy_prompt(40, text_explicit_allowed=True)
    assert "铺垫" not in p
