"""
Voice synthesis should fail *gracefully* when no TTS engine is available.

Previously the /api/voice/synthesize and /api/voice/message/{id} endpoints
raised HTTP 500 whenever synthesis produced no audio (e.g. no local engine
installed and online models disabled). A missing/absent voice engine is an
expected, transient condition — not a server crash — so it must surface as
HTTP 503 {"detail": "voice engine unavailable"} instead.

We mount only api.voice's router on a minimal FastAPI app (mirroring
tests/conftest.py) and stub synthesize_speech_streaming to return None.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from models import database as db_mod
from models.database import Base, get_db, Character, Conversation, Message


async def _no_audio(*_args, **_kwargs):
    """Drop-in for synthesize_speech_streaming: engine produced nothing."""
    return None


@pytest.fixture
def voice_client(engine, monkeypatch):
    """TestClient against a minimal app mounting only the voice router, with a
    TTS engine that yields no audio."""
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr(db_mod, "SessionLocal", TestingSession)
    monkeypatch.setattr(db_mod, "engine", engine)

    # The endpoint produces no audio. Patch the name in both the module that
    # defines it and the one that imported it by name (api.voice binds it at
    # import time, so patching only services.voice_service would not reach it).
    monkeypatch.setattr("services.voice_service.synthesize_speech_streaming", _no_audio)

    from api import voice as voice_mod
    monkeypatch.setattr(voice_mod, "synthesize_speech_streaming", _no_audio)

    app = FastAPI()
    app.include_router(voice_mod.router)

    def _override_get_db():
        s = TestingSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as c:
        yield c


def _seed_character(engine) -> int:
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    s = TestingSession()
    try:
        char = Character(name="C", description="", system_prompt="p", greeting="hi")
        s.add(char)
        s.commit()
        s.refresh(char)
        return char.id
    finally:
        s.close()


def _seed_message(engine, char_id: int) -> int:
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    s = TestingSession()
    try:
        conv = Conversation(character_id=char_id, clerk_user_id="alice")
        s.add(conv)
        s.commit()
        s.refresh(conv)
        msg = Message(conversation_id=conv.id, role="assistant", content="hello there")
        s.add(msg)
        s.commit()
        s.refresh(msg)
        return msg.id
    finally:
        s.close()


def test_synthesize_returns_503_when_no_audio(voice_client, engine):
    """POST /api/voice/synthesize -> 503 (not 500) when no audio is produced."""
    char_id = _seed_character(engine)

    resp = voice_client.post(
        "/api/voice/synthesize",
        json={"text": "hello there", "character_id": char_id},
    )

    assert resp.status_code == 503, (
        f"expected 503 for unavailable voice engine, got {resp.status_code}"
    )
    assert resp.json() == {"detail": "voice engine unavailable"}


def test_message_tts_returns_503_when_no_audio(voice_client, engine):
    """GET /api/voice/message/{id} -> 503 (not 500) when no audio is produced."""
    char_id = _seed_character(engine)
    msg_id = _seed_message(engine, char_id)

    resp = voice_client.get(f"/api/voice/message/{msg_id}")

    assert resp.status_code == 503, (
        f"expected 503 for unavailable voice engine, got {resp.status_code}"
    )
    assert resp.json() == {"detail": "voice engine unavailable"}
