"""
P0-1 — proactive "missed you" return greeting.

Human need: 被需要 / 陪伴. When the user comes back after being away, the
character should reach out first ("where have you been... I missed you")
instead of sitting silent until the user types. This is the single biggest
emotional lever on web (today proactive messaging only exists on Telegram).

Two seams under test:
1. Pure gating: should_send_return_greeting(last_activity, now, has_history)
   — only fire after a real absence on a conversation that has history.
2. Endpoint: POST /conversations/{id}/checkin returns + persists a greeting
   after an absence, and returns null when the user was just here.
"""
from datetime import datetime, timedelta

import pytest

from models.database import Character, Conversation, Message
from services.proactive_greeting import generate_return_greeting


# ── Pure gating logic ─────────────────────────────────────────────────────────

def test_greets_after_long_absence():
    from services.proactive_greeting import should_send_return_greeting
    now = datetime(2026, 6, 1, 20, 0, 0)
    last = now - timedelta(hours=10)
    assert should_send_return_greeting(last, now, has_history=True) is True


def test_no_greet_when_recently_active():
    from services.proactive_greeting import should_send_return_greeting
    now = datetime(2026, 6, 1, 20, 0, 0)
    last = now - timedelta(minutes=20)
    assert should_send_return_greeting(last, now, has_history=True) is False


def test_no_greet_on_fresh_conversation():
    """A brand-new conversation has no history — the normal greeting covers it."""
    from services.proactive_greeting import should_send_return_greeting
    now = datetime(2026, 6, 1, 20, 0, 0)
    assert should_send_return_greeting(None, now, has_history=False) is False


# ── Endpoint behavior ─────────────────────────────────────────────────────────

def _auth(uid: str) -> dict:
    return {"Authorization": f"Bearer {uid}"}


def _seed(db) -> tuple[int, int]:
    char = Character(name="C", system_prompt="p", greeting="hi", category="Featured")
    db.add(char)
    db.commit()
    db.refresh(char)
    return char.id


def test_checkin_persists_greeting_after_absence(client, db, monkeypatch):
    # Make the proactive generator deterministic.
    async def fake_completion(*_a, **_k):
        return "*抬起头* 你终于来了……我等了好久。"
    monkeypatch.setattr("services.proactive_greeting.chat_completion", fake_completion)

    char_id = _seed(db)
    conv_id = client.post(
        "/api/chat/conversations", json={"character_id": char_id}, headers=_auth("alice")
    ).json()["id"]

    # Plant a prior message dated 10 hours ago so there's history + an absence.
    old = datetime.utcnow() - timedelta(hours=10)
    db.add(Message(conversation_id=conv_id, role="user", content="晚安", created_at=old))
    db.commit()

    r = client.post(f"/api/chat/conversations/{conv_id}/checkin", headers=_auth("alice"))
    assert r.status_code == 200, r.text
    assert r.json().get("greeting"), "expected a return greeting after a 10h absence"

    # It must be persisted as an assistant message so it shows on open.
    from sqlalchemy import text
    with db.get_bind().connect() as conn:
        n = conn.execute(
            text("SELECT COUNT(*) FROM messages WHERE conversation_id=:c AND role='assistant'"),
            {"c": conv_id},
        ).scalar()
    assert n == 1


# ── NSFW alignment: the greeting tone must scale with intimacy ────────────────

def _seed_conv_with_old_message(db, intimacy: int):
    char = Character(name="Luna", system_prompt="p", greeting="hi", category="Featured")
    db.add(char)
    db.commit()
    db.refresh(char)
    conv = Conversation(character_id=char.id, title="t", intimacy_level=intimacy)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    old = datetime.utcnow() - timedelta(hours=10)
    db.add(Message(conversation_id=conv.id, role="user", content="晚安", created_at=old))
    db.commit()
    return char, conv


@pytest.mark.asyncio
async def test_greeting_prompt_is_bold_at_high_intimacy(db, monkeypatch):
    """At the top intimacy tier the greeting prompt carries that tier's
    (explicit) framing, so an adult companion can open seductively — this is
    the whole point of an NSFW product."""
    captured = {}

    async def cap(messages, **_k):
        captured["m"] = messages
        return "*靠近你* 想死你了……"

    monkeypatch.setattr("services.proactive_greeting.chat_completion", cap)
    char, conv = _seed_conv_with_old_message(db, intimacy=85)  # 亲密无间 / Intimate

    await generate_return_greeting(char, conv, db)
    system_prompt = captured["m"][0]["content"]
    assert "亲密无间" in system_prompt, "greeting prompt must reflect the Intimate tier"


@pytest.mark.asyncio
async def test_greeting_prompt_is_reserved_for_stranger(db, monkeypatch):
    captured = {}

    async def cap(messages, **_k):
        captured["m"] = messages
        return "*点头* 你来了"

    monkeypatch.setattr("services.proactive_greeting.chat_completion", cap)
    char, conv = _seed_conv_with_old_message(db, intimacy=0)  # 陌生 / Stranger

    await generate_return_greeting(char, conv, db)
    assert "陌生" in captured["m"][0]["content"]


def test_checkin_noop_when_recently_active(client, db):
    char_id = _seed(db)
    conv_id = client.post(
        "/api/chat/conversations", json={"character_id": char_id}, headers=_auth("alice")
    ).json()["id"]
    # Recent message — no absence.
    db.add(Message(conversation_id=conv_id, role="user", content="嗨"))
    db.commit()

    r = client.post(f"/api/chat/conversations/{conv_id}/checkin", headers=_auth("alice"))
    assert r.status_code == 200, r.text
    assert r.json().get("greeting") is None
