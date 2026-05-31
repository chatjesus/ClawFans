"""
P1-10 — allowed CORS origins must be configurable per-environment.

main.py hard-codes the production origin (clawfans.tinyclaw.dev). Anyone
self-hosting or moving domains has to edit source. Origins should come
from the ALLOWED_ORIGINS env var, with the local-dev origins as default.
"""


def test_allowed_origins_default_includes_localhost(monkeypatch):
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    from main import get_allowed_origins
    origins = get_allowed_origins()
    assert "http://localhost:3000" in origins


def test_allowed_origins_read_from_env(monkeypatch):
    monkeypatch.setenv(
        "ALLOWED_ORIGINS", "https://app.example.com, https://www.example.com"
    )
    from main import get_allowed_origins
    origins = get_allowed_origins()
    assert "https://app.example.com" in origins
    assert "https://www.example.com" in origins
    # whitespace around the comma must be trimmed
    assert all(o == o.strip() for o in origins)
