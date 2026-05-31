"""
P1-6 — a chat reply must not be lost if the client disconnects mid-stream.

Today generate_reply_stream only persists the assistant message AFTER the
`async for` loop fully drains. If the consumer stops early (browser tab
closed, network drop, SSE cancelled), GeneratorExit fires at the `yield`
and the save code never runs — the user loses a reply the model already
produced (and already spent GPU time on).

Contract under test: consuming generate_reply_stream persists the
assistant reply that was streamed, even when the consumer stops early.
"""
import pytest

from models.database import Character, Conversation, Message
from services.chat_service import generate_reply_stream, StreamResult


def _seed(db):
    char = Character(name="C", system_prompt="x", category="Featured")
    db.add(char)
    db.commit()
    db.refresh(char)
    conv = Conversation(character_id=char.id, title="t")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return char, conv


@pytest.mark.asyncio
async def test_reply_persisted_when_consumer_disconnects_midstream(db, monkeypatch):
    async def chunky_stream(*_a, **_k):
        for piece in ["Hel", "lo ", "there"]:
            yield piece

    monkeypatch.setattr(
        "services.chat_service.chat_completion_stream", chunky_stream
    )

    char, conv = _seed(db)

    gen = generate_reply_stream(char, conv, "hi", db, result_holder=StreamResult())
    first = await gen.__anext__()        # consume exactly one chunk
    assert first == "Hel"
    await gen.aclose()                    # simulate client disconnect

    db.expire_all()
    saved = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id, Message.role == "assistant")
        .all()
    )
    assert saved, "assistant reply was lost on mid-stream disconnect"
    assert "Hel" in saved[0].content


@pytest.mark.asyncio
async def test_full_reply_persisted_on_normal_completion(db, monkeypatch):
    async def chunky_stream(*_a, **_k):
        for piece in ["Hel", "lo ", "there"]:
            yield piece

    monkeypatch.setattr(
        "services.chat_service.chat_completion_stream", chunky_stream
    )

    char, conv = _seed(db)

    result = StreamResult()
    collected = ""
    async for chunk in generate_reply_stream(char, conv, "hi", db, result_holder=result):
        collected += chunk

    assert collected == "Hello there"
    db.expire_all()
    saved = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id, Message.role == "assistant")
        .all()
    )
    assert len(saved) == 1, "exactly one assistant message expected on clean completion"
    assert saved[0].content == "Hello there"
