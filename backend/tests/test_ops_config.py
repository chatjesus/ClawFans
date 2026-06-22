"""
Configurable adult-operations layer.

An operator must be able to tune the product's monetization/engagement levers
without code changes: how fast intimacy grows, at what intimacy explicit
content unlocks, how often the character proactively reaches out, daily
check-in rewards, whether explicit image gen is on. These live in a single
config store (DB-backed, with sane defaults) read by the mechanics and edited
via an admin API.

This file covers the store + the admin API. Mechanics reading the config are
tested in their own files.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models.database import Base


def _mk_session():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=eng)
    return sessionmaker(bind=eng)()


# ── Store ─────────────────────────────────────────────────────────────────────

def test_defaults_present_when_empty():
    from services.ops_config import get_ops_config
    cfg = get_ops_config(_mk_session())
    # The adult-ops levers operators care about must all have defaults.
    for key in (
        "nsfw_unlock_intimacy",
        "intimacy_gain_multiplier",
        "proactive_greeting_min_hours",
        "daily_checkin_intimacy_bonus",
        "nsfw_images_enabled",
    ):
        assert key in cfg, f"missing default for {key}"


def test_set_overrides_default_preserving_types():
    from services.ops_config import get_ops_config, set_ops_values, get_ops_value
    db = _mk_session()
    set_ops_values(db, {"nsfw_unlock_intimacy": 20, "intimacy_gain_multiplier": 2.5,
                        "nsfw_images_enabled": False})
    cfg = get_ops_config(db)
    assert cfg["nsfw_unlock_intimacy"] == 20          # int preserved
    assert cfg["intimacy_gain_multiplier"] == 2.5      # float preserved
    assert cfg["nsfw_images_enabled"] is False          # bool preserved
    # Untouched key keeps its default.
    assert get_ops_value(db, "proactive_greeting_min_hours") == \
        get_ops_config(_mk_session())["proactive_greeting_min_hours"]


# ── Admin API ─────────────────────────────────────────────────────────────────

def _admin_client(engine):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from models.database import get_db
    from api.admin import router as admin_router

    TS = sessionmaker(bind=engine)
    app = FastAPI()
    app.include_router(admin_router)

    def _override():
        s = TS()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    return TestClient(app)


def _engine():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=eng)
    return eng


def test_admin_get_and_put_round_trip(monkeypatch):
    monkeypatch.delenv("OPS_ADMIN_TOKEN", raising=False)  # dev mode: no gate
    client = _admin_client(_engine())

    r = client.get("/api/admin/ops-config")
    assert r.status_code == 200
    assert r.json()["nsfw_unlock_intimacy"] == 40  # default

    r2 = client.put("/api/admin/ops-config", json={"nsfw_unlock_intimacy": 10})
    assert r2.status_code == 200
    assert r2.json()["nsfw_unlock_intimacy"] == 10

    assert client.get("/api/admin/ops-config").json()["nsfw_unlock_intimacy"] == 10


def test_admin_gate_blocks_without_token(monkeypatch):
    monkeypatch.setenv("OPS_ADMIN_TOKEN", "s3cret")
    client = _admin_client(_engine())

    # No / wrong token → 403
    assert client.get("/api/admin/ops-config").status_code == 403
    assert client.put("/api/admin/ops-config", json={"nsfw_unlock_intimacy": 1},
                      headers={"X-Admin-Token": "wrong"}).status_code == 403

    # Correct token → allowed
    ok = client.get("/api/admin/ops-config", headers={"X-Admin-Token": "s3cret"})
    assert ok.status_code == 200
