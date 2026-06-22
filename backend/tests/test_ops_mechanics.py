"""
The ops-config levers must actually change runtime behavior (not just store a
value). These exercise the mechanics through their real code paths with the
config set to non-default values.
"""
from datetime import datetime, timedelta

import pytest

from models.database import Character, Conversation, Message
from services.ops_config import set_ops_values


def _seed_conv(db, intimacy=0):
    char = Character(name="C", system_prompt="p", greeting="hi", category="Featured")
    db.add(char)
    db.commit()
    db.refresh(char)
    conv = Conversation(character_id=char.id, title="t", intimacy_level=intimacy)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return char, conv


@pytest.mark.asyncio
async def test_proactive_hours_lever_suppresses_greeting(db, monkeypatch):
    """Raising proactive_greeting_min_hours above the actual gap stops the
    proactive greeting — an operator can dial companion pushiness up or down."""
    async def fake(*_a, **_k):
        return "想你了"
    monkeypatch.setattr("services.proactive_greeting.chat_completion", fake)
    from services.proactive_greeting import generate_return_greeting

    char, conv = _seed_conv(db)
    old = datetime.utcnow() - timedelta(hours=10)
    db.add(Message(conversation_id=conv.id, role="user", content="晚安", created_at=old))
    db.commit()

    # Default (6h) would greet after 10h. Raise the lever to 100h → no greeting.
    set_ops_values(db, {"proactive_greeting_min_hours": 100})
    assert await generate_return_greeting(char, conv, db) is None


@pytest.mark.asyncio
async def test_intimacy_gain_multiplier_lever(db, monkeypatch):
    """intimacy_gain_multiplier scales how fast the relationship deepens."""
    async def fake_stream(*_a, **_k):
        yield "好的"
    monkeypatch.setattr("services.chat_service.chat_completion_stream", fake_stream)
    from services.chat_service import generate_reply_stream, StreamResult

    char, conv = _seed_conv(db, intimacy=0)
    set_ops_values(db, {"intimacy_gain_multiplier": 5.0})

    async for _ in generate_reply_stream(char, conv, "hi", db, result_holder=StreamResult()):
        pass

    db.expire_all()
    refreshed = db.query(Conversation).filter(Conversation.id == conv.id).first()
    # Base gain for a short message is 1; ×5 → 5.
    assert refreshed.intimacy_level == 5
