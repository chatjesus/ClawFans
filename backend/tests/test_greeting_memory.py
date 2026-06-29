"""
Proactive "I missed you" greetings must weave in a real memory / last topic, so
they feel like a person who remembers — not a generic push notification.
"""
from datetime import datetime, timedelta

import pytest

from models.database import Character, Conversation, Message, UserMemory
from services.proactive_greeting import generate_return_greeting


@pytest.mark.asyncio
async def test_greeting_weaves_in_memory_or_last_topic(db, monkeypatch):
    captured = {}

    async def cap(messages, **_k):
        captured["m"] = messages
        return "嗨，想你了"

    monkeypatch.setattr("services.proactive_greeting.chat_completion", cap)

    char = Character(name="苏糖", description="d", system_prompt="你是苏糖",
                     greeting="hi", category="Romance")
    db.add(char); db.commit(); db.refresh(char)
    conv = Conversation(character_id=char.id, clerk_user_id="alice", intimacy_level=50)
    db.add(conv); db.commit(); db.refresh(conv)
    # old message so the greeting actually fires (away > min_hours) + sets last topic
    db.add(Message(conversation_id=conv.id, role="user", content="我明天有个重要面试好紧张",
                   created_at=datetime.utcnow() - timedelta(hours=10)))
    db.add(UserMemory(user_id="alice", character_id=char.id, key="职业",
                      value="设计师", confidence=0.9))
    db.commit()

    out = await generate_return_greeting(char, conv, db)
    assert out  # it fired
    sys = captured["m"][0]["content"]
    # the greeting prompt must carry a real anchor (the memory fact or the topic)
    assert "设计师" in sys or "面试" in sys
