"""
Web proactive recall — the character reaches out FIRST to a quiet web user,
staged on a background tick (not only on reopen like the return greeting).

Human need: 被需要 / 陪伴. This is the web-side equivalent of Telegram's
schedule_proactive_jobs. Two seams under test:
1. Pure policy: should_stage_proactive(...) + in_quiet_hours(...).
2. Staging: stage_web_proactive_messages persists one is_proactive assistant
   Message for an inactive conversation, respects the gap, and is idempotent.
"""
from datetime import datetime, timedelta

import pytest

from models.database import Character, Conversation, Message
from services.web_proactive import (
    in_quiet_hours,
    should_stage_proactive,
    stage_web_proactive_messages,
    TRIGGER_AFTER_HOURS,
)

# A fixed "now" in the afternoon so we're never accidentally in quiet hours.
NOON = datetime(2026, 6, 1, 15, 0, 0)


# ── Pure policy ────────────────────────────────────────────────────────────────

def test_in_quiet_hours_wraps_midnight():
    assert in_quiet_hours(datetime(2026, 6, 1, 23, 30)) is True   # 23:30
    assert in_quiet_hours(datetime(2026, 6, 1, 3, 0)) is True     # 03:00
    assert in_quiet_hours(datetime(2026, 6, 1, 7, 0)) is False    # 07:00 (window end)
    assert in_quiet_hours(datetime(2026, 6, 1, 15, 0)) is False   # afternoon


def _gate(**over):
    base = dict(
        last_active_at=NOON - timedelta(hours=TRIGGER_AFTER_HOURS + 1),
        last_proactive_at=None,
        now=NOON,
        has_history=True,
        proactive_enabled=True,
        has_pending_proactive=False,
    )
    base.update(over)
    return should_stage_proactive(**base)


def test_stages_after_long_silence():
    assert _gate() is True


def test_no_stage_when_recently_active():
    assert _gate(last_active_at=NOON - timedelta(hours=2)) is False


def test_no_stage_when_opted_out():
    assert _gate(proactive_enabled=False) is False


def test_no_stage_without_history():
    assert _gate(has_history=False, last_active_at=None) is False


def test_no_stage_when_pending_proactive_unanswered():
    assert _gate(has_pending_proactive=True) is False


def test_no_stage_inside_gap_since_last_proactive():
    # Quiet 25h, but we already pinged 5h ago — gap (20h) not yet elapsed.
    assert _gate(last_proactive_at=NOON - timedelta(hours=5)) is False


def test_stages_after_gap_elapsed():
    assert _gate(last_proactive_at=NOON - timedelta(hours=21)) is True


def test_no_stage_in_quiet_hours():
    midnight = datetime(2026, 6, 1, 2, 0, 0)
    assert _gate(now=midnight, last_active_at=midnight - timedelta(hours=30)) is False


# ── Staging (DB + stubbed LLM) ──────────────────────────────────────────────────

def _make_conv(db, *, intimacy=0, hours_quiet=30, enabled=True, last_proactive_at=None):
    char = Character(name="Luna", system_prompt="p", greeting="hi", category="Featured")
    db.add(char)
    db.commit()
    db.refresh(char)
    quiet_since = NOON - timedelta(hours=hours_quiet)
    conv = Conversation(
        character_id=char.id,
        title="t",
        intimacy_level=intimacy,
        last_active_at=quiet_since,
        last_proactive_at=last_proactive_at,
        proactive_enabled=enabled,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    # Plant prior history at the quiet-since moment.
    db.add(Message(conversation_id=conv.id, role="user", content="晚安", created_at=quiet_since))
    db.commit()
    return char, conv


def _stub_llm(monkeypatch, text="*抬起头* 你终于来了……我等了好久。"):
    async def fake(*_a, **_k):
        return text
    monkeypatch.setattr("services.proactive_greeting.chat_completion", fake)


@pytest.mark.asyncio
async def test_stages_one_proactive_message(db, monkeypatch):
    _stub_llm(monkeypatch)
    _char, conv = _make_conv(db)

    staged = await stage_web_proactive_messages(db, now=NOON)
    assert staged == 1

    msgs = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id, Message.role == "assistant")
        .all()
    )
    assert len(msgs) == 1
    assert msgs[0].is_proactive is True
    assert msgs[0].content

    db.refresh(conv)
    assert conv.last_proactive_at == NOON


@pytest.mark.asyncio
async def test_does_not_stage_for_recently_active(db, monkeypatch):
    _stub_llm(monkeypatch)
    _char, conv = _make_conv(db, hours_quiet=2)
    staged = await stage_web_proactive_messages(db, now=NOON)
    assert staged == 0


@pytest.mark.asyncio
async def test_idempotent_within_gap(db, monkeypatch):
    """Second scan right after the first stages nothing: the newest message is
    now an unanswered proactive, and the gap has not elapsed."""
    _stub_llm(monkeypatch)
    _char, _conv = _make_conv(db)
    assert await stage_web_proactive_messages(db, now=NOON) == 1
    assert await stage_web_proactive_messages(db, now=NOON) == 0


@pytest.mark.asyncio
async def test_respects_opt_out(db, monkeypatch):
    _stub_llm(monkeypatch)
    _char, _conv = _make_conv(db, enabled=False)
    assert await stage_web_proactive_messages(db, now=NOON) == 0


# ── API: poll endpoint + checkin dedupe ─────────────────────────────────────────

def _auth(uid="alice"):
    return {"Authorization": f"Bearer {uid}"}


def test_poll_returns_staged_proactive(client, db):
    char = Character(name="C", system_prompt="p", greeting="hi", category="Featured")
    db.add(char)
    db.commit()
    db.refresh(char)
    conv_id = client.post(
        "/api/chat/conversations", json={"character_id": char.id}, headers=_auth()
    ).json()["id"]

    # Scheduler staged a proactive message while the tab was open.
    db.add(Message(conversation_id=conv_id, role="assistant", content="想你了", is_proactive=True))
    db.commit()

    r = client.get(f"/api/chat/conversations/{conv_id}/poll?after_id=0", headers=_auth())
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["is_proactive"] is True
    assert rows[0]["content"] == "想你了"


def test_checkin_does_not_double_greet_after_staged_proactive(client, db):
    char = Character(name="C", system_prompt="p", greeting="hi", category="Featured")
    db.add(char)
    db.commit()
    db.refresh(char)
    conv_id = client.post(
        "/api/chat/conversations", json={"character_id": char.id}, headers=_auth()
    ).json()["id"]

    old = datetime.utcnow() - timedelta(hours=30)
    db.add(Message(conversation_id=conv_id, role="user", content="晚安", created_at=old))
    # The scheduler already reached out while the user was away.
    db.add(Message(
        conversation_id=conv_id, role="assistant", content="你去哪了",
        is_proactive=True, created_at=old + timedelta(hours=1),
    ))
    db.commit()

    r = client.post(f"/api/chat/conversations/{conv_id}/checkin", headers=_auth())
    assert r.status_code == 200, r.text
    assert r.json().get("greeting") is None  # deduped: no second greeting
