"""
Tests for the Memory CRUD API (P0-3).

Self-contained: we do NOT rely on the shared `client` fixture in conftest.py
(which mounts the chat/characters routers). Instead we build our own minimal
FastAPI app that mounts ONLY the memory_api router, mirroring the hermetic
setup in conftest.py — in-memory SQLite via StaticPool, an overridden get_db,
and a stubbed verify_clerk_token so a Bearer token IS the user id.
"""
import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Make the backend package importable (same trick conftest.py uses).
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from models.database import Base, get_db, UserMemory


async def _identity_verify(token: str):
    """Test-only: treat the bearer token AS the user id (no Clerk needed)."""
    if not token or token == "invalid":
        return None
    return token


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture
def TestingSession(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db(TestingSession):
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(engine, TestingSession, monkeypatch):
    # Stub Clerk verification BEFORE importing the router so the symbol the
    # router resolves at call time is our identity stub.
    monkeypatch.setattr("auth.clerk.verify_clerk_token", _identity_verify)

    from api.memory_api import router as memory_router

    app = FastAPI()
    app.include_router(memory_router)

    def _override_get_db():
        s = TestingSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as c:
        yield c


def _auth(user_id: str) -> dict:
    return {"Authorization": f"Bearer {user_id}"}


def _seed(db, **kwargs):
    defaults = dict(
        user_id="alice",
        character_id=1,
        key="favorite_color",
        value="blue",
        confidence=0.9,
    )
    defaults.update(kwargs)
    mem = UserMemory(**defaults)
    db.add(mem)
    db.commit()
    db.refresh(mem)
    return mem


# ── 1. GET scoping: only the caller's memories for that character ────────────

def test_get_returns_only_callers_memories_for_character(client, db):
    _seed(db, user_id="alice", character_id=1, key="color", value="blue")
    _seed(db, user_id="alice", character_id=2, key="city", value="NYC")  # other char
    _seed(db, user_id="bob", character_id=1, key="color", value="red")   # other user

    resp = client.get("/api/memory?character_id=1", headers=_auth("alice"))
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    item = data[0]
    assert item["key"] == "color"
    assert item["value"] == "blue"
    # Exact response shape from the contract.
    assert set(item.keys()) == {"id", "key", "value", "confidence", "created_at"}


def test_get_returns_empty_list_when_no_memories(client, db):
    _seed(db, user_id="bob", character_id=1)
    resp = client.get("/api/memory?character_id=1", headers=_auth("alice"))
    assert resp.status_code == 200
    assert resp.json() == []


# ── 2. GET anonymous → 401 ──────────────────────────────────────────────────

def test_get_anonymous_is_unauthorized(client, db):
    _seed(db, user_id="alice", character_id=1)
    resp = client.get("/api/memory?character_id=1")  # no Authorization header
    assert resp.status_code == 401


# ── 3. DELETE by owner → 204, row gone ───────────────────────────────────────

def test_delete_by_owner_removes_row(client, db):
    mem = _seed(db, user_id="alice", character_id=1)
    mem_id = mem.id

    resp = client.delete(f"/api/memory/{mem_id}", headers=_auth("alice"))
    assert resp.status_code == 204

    assert db.query(UserMemory).filter(UserMemory.id == mem_id).first() is None


# ── 4. DELETE by non-owner → 403, row still exists ───────────────────────────

def test_delete_by_non_owner_is_forbidden(client, db):
    mem = _seed(db, user_id="alice", character_id=1)
    mem_id = mem.id

    resp = client.delete(f"/api/memory/{mem_id}", headers=_auth("bob"))
    assert resp.status_code == 403

    assert db.query(UserMemory).filter(UserMemory.id == mem_id).first() is not None


def test_delete_missing_is_not_found(client, db):
    resp = client.delete("/api/memory/99999", headers=_auth("alice"))
    assert resp.status_code == 404


# ── 5. PUT by owner updates value ────────────────────────────────────────────

def test_put_by_owner_updates_value(client, db):
    mem = _seed(db, user_id="alice", character_id=1, value="blue")
    mem_id = mem.id

    resp = client.put(
        f"/api/memory/{mem_id}",
        json={"value": "green"},
        headers=_auth("alice"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == mem_id
    assert body["value"] == "green"
    assert set(body.keys()) == {"id", "key", "value", "confidence", "created_at"}

    db.expire_all()
    refreshed = db.query(UserMemory).filter(UserMemory.id == mem_id).first()
    assert refreshed.value == "green"


def test_put_by_non_owner_is_forbidden(client, db):
    mem = _seed(db, user_id="alice", character_id=1, value="blue")
    mem_id = mem.id

    resp = client.put(
        f"/api/memory/{mem_id}",
        json={"value": "hacked"},
        headers=_auth("bob"),
    )
    assert resp.status_code == 403

    db.expire_all()
    refreshed = db.query(UserMemory).filter(UserMemory.id == mem_id).first()
    assert refreshed.value == "blue"


def test_put_missing_is_not_found(client, db):
    resp = client.put(
        "/api/memory/99999",
        json={"value": "x"},
        headers=_auth("alice"),
    )
    assert resp.status_code == 404
