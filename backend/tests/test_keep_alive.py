"""
Keep the model warm. The big abliterated model gets evicted from VRAM after
idle, so the next turn reloads ~18GB and the chat looks frozen ("…") for
30-60s. Sending Ollama a keep_alive keeps it resident → no reload stall.
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


def test_stream_request_keeps_model_warm(monkeypatch):
    monkeypatch.delenv("OLLAMA_KEEP_ALIVE", raising=False)
    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    _Client.last_payload = None
    from services.llm_service import chat_completion_stream
    asyncio.run(_drain(chat_completion_stream([{"role": "user", "content": "hi"}])))
    assert _Client.last_payload.get("keep_alive"), "no keep_alive → model evicts → frozen reloads"


def test_keep_alive_configurable(monkeypatch):
    monkeypatch.setenv("OLLAMA_KEEP_ALIVE", "-1")  # keep loaded forever
    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    _Client.last_payload = None
    from services.llm_service import chat_completion_stream
    asyncio.run(_drain(chat_completion_stream([{"role": "user", "content": "hi"}])))
    assert str(_Client.last_payload["keep_alive"]) == "-1"
