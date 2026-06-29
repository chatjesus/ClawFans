"""
Slow-burn onboarding into adult content.

Text explicitness must be intimacy-gated like images are. Below the unlock
threshold, build_intimacy_prompt injects a HARD limit that forbids explicit
sexual prose — but framed as in-character deflect-and-tease (欲擒故纵), never a
cold refusal. Above it, the character is unleashed. Each non-top tier also
carries a forward-pull (lead the user up) and a deflect-and-tease directive.

These assert the PROMPT the LLM receives, through the public build_intimacy_prompt
/ build_messages interfaces.
"""
from datetime import datetime, timedelta

import pytest

from models.database import Character, Conversation, Message
from services.intimacy_service import build_intimacy_prompt
from services.chat_service import build_messages
from services import ops_config


def _seed(db, intimacy):
    char = Character(name="Luna", description="d", system_prompt="You are Luna.",
                     greeting="hi", category="Featured")
    db.add(char); db.commit(); db.refresh(char)
    conv = Conversation(character_id=char.id, user_id="alice", intimacy_level=intimacy)
    db.add(conv); db.commit(); db.refresh(conv)
    return char, conv


def _sys(messages):
    return "\n".join(m["content"] for m in messages if m["role"] == "system")


def test_text_gate_present_when_not_explicit_allowed():
    p = build_intimacy_prompt(10, text_explicit_allowed=False)
    # a top-priority hard limit that overrides the global "never refuse" rules
    assert "硬限制" in p
    assert "最高优先级" in p or "覆盖" in p
    # it forbids explicit sexual prose
    assert "不得" in p and ("性行为" in p or "露骨" in p)
    # but it is explicitly NOT a cold refusal — deflect-and-tease instead
    assert "不是冷" in p or "撩拨" in p


def test_no_text_gate_when_explicit_allowed():
    # at/above the unlock threshold the character is unleashed — no hard limit
    p = build_intimacy_prompt(85, text_explicit_allowed=True)
    assert "硬限制" not in p


def test_forward_pull_present_and_tier_specific():
    # the missing engine: the character actively leads the user toward the next
    # stage. A dedicated forward-pull section must exist and differ per tier.
    low = build_intimacy_prompt(0)
    mid = build_intimacy_prompt(40)
    assert "前拉" in low  # a forward-pull section exists
    # tier-0 leads via curiosity/withholding hooks, not physical advance
    assert any(k in low for k in ("钩", "赢", "靠近", "想多"))
    # the lead text is tier-specific
    assert low != mid


def test_restraint_early_present_low_tier_absent_top_tier():
    low = build_intimacy_prompt(0)
    top = build_intimacy_prompt(85)
    # low tier carries a deflect-and-tease (欲擒故纵) directive for above-tier pushes
    assert "早催回挡" in low or "越界" in low
    assert any(k in low for k in ("急", "值得", "吊"))
    # the top tier is unleashed — no early-restraint section
    assert "早催回挡" not in top


def test_unlock_moment_beat_injected_only_when_just_unlocked():
    plain = build_intimacy_prompt(40)
    beat = build_intimacy_prompt(40, just_unlocked_tier="亲近")
    assert "解锁时刻" not in plain
    # the one-turn beat names the freshly-crossed tier and demands in-fiction payoff
    assert "解锁时刻" in beat and "亲近" in beat
    # must NOT leak system vocabulary like 等级/亲密度数字 into the user-facing beat instruction
    assert "仅本轮" in beat or "一次" in beat


def test_ops_defaults_for_text_gate():
    # text gate is operator-tunable, parallel to the image gate
    assert ops_config.DEFAULTS["text_explicit_unlock_intimacy"] == 60
    assert ops_config.DEFAULTS["vip_only_explicit_text"] is False


def test_build_messages_gates_text_below_threshold(db):
    char, conv = _seed(db, intimacy=10)  # below default unlock (60)
    sys = _sys(build_messages(char, conv, db, user_id="alice"))
    assert "硬限制" in sys


def test_build_messages_unleashes_text_at_high_intimacy(db):
    char, conv = _seed(db, intimacy=80)  # above unlock
    sys = _sys(build_messages(char, conv, db, user_id="alice"))
    assert "硬限制" not in sys


def test_hardlimit_restated_after_post_history(db):
    char, conv = _seed(db, intimacy=10)
    msgs = build_messages(char, conv, db, user_id="alice")
    # the gate reminder is restated among the trailing system messages (after
    # POST_HISTORY) so it wins on recency. The very last word is now the
    # absolute safety floor; the gate reminder sits just before it.
    assert any("硬限制提醒" in m["content"] for m in msgs[-3:])


def test_vip_only_explicit_text_forces_gate_even_when_intimate(db):
    char, conv = _seed(db, intimacy=90)  # would be unleashed...
    ops_config.set_ops_values(db, {"vip_only_explicit_text": True, "monetization_locked": False})  # ...but VIP-gated
    sys = _sys(build_messages(char, conv, db, user_id="alice"))
    assert "硬限制" in sys


def test_pending_unlock_is_celebrated_once_then_cleared(db):
    char, conv = _seed(db, intimacy=45)  # already in 亲近 (threshold 40)
    conv.pending_unlock_tier = 40        # crossed it last turn
    db.commit()
    sys = _sys(build_messages(char, conv, db, user_id="alice"))
    assert "解锁时刻" in sys and "亲近" in sys
    # one-shot: consumed so the next turn won't re-announce
    db.refresh(conv)
    assert conv.pending_unlock_tier is None


def test_no_unlock_beat_without_pending(db):
    char, conv = _seed(db, intimacy=45)
    sys = _sys(build_messages(char, conv, db, user_id="alice"))
    assert "解锁时刻" not in sys


def test_crossing_a_tier_parks_pending_unlock(client, db):
    # a turn that crosses into a new tier must park that tier for next-turn celebration
    char = Character(name="Luna", description="d", system_prompt="You are Luna.",
                     greeting="hi", category="Featured")
    db.add(char); db.commit(); db.refresh(char)
    conv_id = client.post("/api/chat/conversations", json={"character_id": char.id}).json()["id"]
    conv = db.get(Conversation, conv_id)
    conv.intimacy_level = 18  # just below the 普通朋友 threshold (20)
    db.commit()
    # affectionate + physical: +1 base +2 affection +2 physical = +5 -> 23, crosses 20
    with client.stream("POST", f"/api/chat/conversations/{conv_id}/messages",
                       json={"content": "抱抱你，我好喜欢你"}) as resp:
        assert resp.status_code == 200, resp.text
        for _ in resp.iter_lines():
            pass
    db.expire_all()
    conv = db.get(Conversation, conv_id)
    assert conv.intimacy_level >= 20
    assert conv.pending_unlock_tier == 20


def test_is_text_explicit_allowed_helper(db):
    assert ops_config.is_text_explicit_allowed(db, 80) is True   # above unlock
    assert ops_config.is_text_explicit_allowed(db, 10) is False  # below unlock
    ops_config.set_ops_values(db, {"vip_only_explicit_text": True, "monetization_locked": False})
    assert ops_config.is_text_explicit_allowed(db, 80) is False  # VIP paywall


@pytest.mark.asyncio
async def test_proactive_greeting_text_gated_at_low_intimacy(db, monkeypatch):
    # the slow-burn gate must not leak through the "she reached out" path
    captured = {}

    async def cap(messages, **_k):
        captured["m"] = messages
        return "嗨"

    monkeypatch.setattr("services.proactive_greeting.chat_completion", cap)
    char = Character(name="Luna", system_prompt="p", greeting="hi", category="Featured")
    db.add(char); db.commit(); db.refresh(char)
    conv = Conversation(character_id=char.id, intimacy_level=10)
    db.add(conv); db.commit(); db.refresh(conv)
    db.add(Message(conversation_id=conv.id, role="user", content="晚安",
                   created_at=datetime.utcnow() - timedelta(hours=10)))
    db.commit()

    from services.proactive_greeting import generate_return_greeting
    await generate_return_greeting(char, conv, db)
    assert "硬限制" in captured["m"][0]["content"]
