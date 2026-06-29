"""
Suppress verbatim echo / repeated phrasings at the sampling layer.

The quality review found the model echoing the user's last line and reusing
the same closing question. Ollama's repeat_penalty was unset (only temperature
was). Add it (default 1.15, OLLAMA_REPEAT_PENALTY to tune).
"""
import asyncio
import httpx


class _StreamResp:
    status_code = 200
    def raise_for_status(self): pass
    async def aiter_lines(self):
        yield '{"message": {"content": "hi"}, "done": true}'


class _Ctx:
    async def __aenter__(self): return _StreamResp()
    async def __aexit__(self, *a): return False


class _Client:
    last_payload = None
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    def stream(self, _m, _u, json=None, **k):
        type(self).last_payload = json
        return _Ctx()


async def _drain(gen):
    async for _ in gen:
        pass


def test_repeat_penalty_default_applied(monkeypatch):
    monkeypatch.delenv("OLLAMA_REPEAT_PENALTY", raising=False)
    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    _Client.last_payload = None
    from services.llm_service import chat_completion_stream
    asyncio.run(_drain(chat_completion_stream([{"role": "user", "content": "hi"}])))
    assert _Client.last_payload["options"].get("repeat_penalty", 1.0) >= 1.1


def test_repeat_penalty_configurable(monkeypatch):
    monkeypatch.setenv("OLLAMA_REPEAT_PENALTY", "1.3")
    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    _Client.last_payload = None
    from services.llm_service import chat_completion_stream
    asyncio.run(_drain(chat_completion_stream([{"role": "user", "content": "hi"}])))
    assert _Client.last_payload["options"]["repeat_penalty"] == 1.3
