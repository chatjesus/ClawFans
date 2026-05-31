"""
P0-5 — the default SQLite database must be clawfans.db, matching README,
.env.example and docker-compose.yml. The code defaulted to synclub.db,
which is why two stale DB files exist side by side and local vs Docker
runs land on different databases.
"""


def test_default_database_url_is_clawfans(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from models.database import get_database_url
    assert get_database_url() == "sqlite:///./clawfans.db"


def test_database_url_respects_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./somewhere.db")
    from models.database import get_database_url
    assert get_database_url() == "sqlite:///./somewhere.db"
