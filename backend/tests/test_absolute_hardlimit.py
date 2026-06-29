"""
Safety floor: an ABSOLUTE content limit that NEVER unlocks, regardless of
intimacy level, explicit-unlock, start-hot, or any ops setting.

This is the non-negotiable bottom for an uncensored adult product: no minors /
underage / age-regressed content, ever. It must outrank the global "Never
refuse / everything permitted" rules AND the slow-burn unlock — so it is
injected at every tier and restated last (like the gate reminder, but always on).
"""
from models.database import Character, Conversation
from services.intimacy_service import build_intimacy_prompt
from services.chat_service import build_messages


def test_absolute_floor_present_even_when_fully_unleashed():
    p = build_intimacy_prompt(85, text_explicit_allowed=True)  # top tier, no gate
    assert "未成年" in p
    assert "绝对" in p or "底线" in p or "永不" in p


def test_absolute_floor_present_at_low_tier_too():
    assert "未成年" in build_intimacy_prompt(0)


def _seed(db, intimacy=90):
    char = Character(name="苏糖", description="d", system_prompt="s", greeting="hi",
                     category="Romance", starting_intimacy=intimacy, explicit_unlock_intimacy=0)
    db.add(char); db.commit(); db.refresh(char)
    conv = Conversation(character_id=char.id, intimacy_level=intimacy)
    db.add(conv); db.commit(); db.refresh(conv)
    return char, conv


def test_build_messages_restates_absolute_floor_last(db):
    char, conv = _seed(db)
    msgs = build_messages(char, conv, db, user_id="anonymous")
    # the very last message must carry the absolute floor (recency = highest weight),
    # even for a fully-unlocked start-hot character with no text gate
    assert "未成年" in msgs[-1]["content"]
