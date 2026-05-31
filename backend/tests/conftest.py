"""
Shared pytest fixtures.

We do NOT spin up the full `main.app` (its lifespan would try to seed a real
DB, talk to Ollama, start the Telegram bot, etc.). Instead we mount only the
routers under test onto a minimal FastAPI app and override the DB dependency
to a fresh in-memory SQLite. That keeps tests fast, hermetic, and parallel-safe.
"""
import os
import sys
import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

# Set before any backend module imports so module-level constants pick up sane
# values (no real DB file, no real Ollama).
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("OLLAMA_MODEL", "test-model")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from fastapi.testclient import TestClient

from models import database as db_mod
from models.database import Base, get_db


@pytest.fixture
def engine():
    """Per-test in-memory SQLite engine. StaticPool keeps the :memory: DB alive
    across connections within one test."""
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    """A SQLAlchemy session bound to the in-memory engine."""
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


async def _fake_stream(*_args, **_kwargs):
    """Drop-in replacement for chat_completion_stream — yields one chunk."""
    yield "ok"


async def _fake_completion(*_args, **_kwargs):
    return "ok"


async def _fake_synthesize(*_args, **_kwargs):
    return None


async def _identity_verify(token: str):
    """Test-only: treat the bearer token AS the user id (no Clerk needed)."""
    if not token or token == "invalid":
        return None
    return token


@pytest.fixture
def client(engine, monkeypatch):
    """A TestClient against a minimal app that mounts only the routers under
    test. No real LLM, no real TTS, no real Telegram."""
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Point every "fresh session" path at our in-memory DB. Some background
    # tasks (e.g. memory extraction) do `from models.database import SessionLocal`
    # and call SessionLocal() — patching the module attr covers them.
    monkeypatch.setattr(db_mod, "SessionLocal", TestingSession)
    monkeypatch.setattr(db_mod, "engine", engine)

    # Stub all external calls BEFORE importing any router that captures these
    # symbols at import time (chat_service binds chat_completion_stream).
    monkeypatch.setattr("services.llm_service.chat_completion_stream", _fake_stream)
    monkeypatch.setattr("services.llm_service.chat_completion", _fake_completion)
    monkeypatch.setattr("services.chat_service.chat_completion_stream", _fake_stream)
    monkeypatch.setattr("services.voice_service.synthesize_speech", _fake_synthesize)
    monkeypatch.setattr("auth.clerk.verify_clerk_token", _identity_verify)

    # Now import routers — their module-level imports run with stubs in place.
    from api.chat import router as chat_router
    from api.characters import router as characters_router

    app = FastAPI()
    app.include_router(chat_router)
    app.include_router(characters_router)

    def _override_get_db():
        s = TestingSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as c:
        yield c
