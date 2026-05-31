"""
Empty/failed generations must not be silent.

Ollama can answer 200 OK but put an error in the stream body
(e.g. `{"error": "this model requires a subscription"}`), or a model can
otherwise yield no content. When that happened, chat_completion_stream
yielded nothing and the whole chat turn produced an empty reply with no
signal — which the UI then rendered as "the character stopped replying".

Contract:
- An in-band Ollama error surfaces as a raised RuntimeError (→ becomes a
  visible SSE error event), not a silent empty stream.
- max_tokens (num_predict) is configurable via OLLAMA_MAX_TOKENS, with a
  default high enough to leave room for a reasoning model's answer.
"""
import asyncio
import httpx
import pytest


async def _drain(gen):
    out = []
    async for c in gen:
        out.append(c)
    return out


class _ErrStreamResponse:
    status_code = 200
    def raise_for_status(self):
        pass
    async def aiter_lines(self):
        yield '{"error": "this model requires a subscription, upgrade for access"}'


class _ErrCtx:
    async def __aenter__(self):
        return _ErrStreamResponse()
    async def __aexit__(self, *_a):
        return False


class _ErrClient:
    def __init__(self, *_a, **_k):
        pass
    async def __aenter__(self):
        return self
    async def __aexit__(self, *_a):
        return False
    def stream(self, *_a, **_k):
        return _ErrCtx()


def test_inband_ollama_error_raises_not_silent(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _ErrClient)
    from services.llm_service import chat_completion_stream

    with pytest.raises(RuntimeError, match="subscription"):
        asyncio.run(_drain(chat_completion_stream([{"role": "user", "content": "hi"}])))


# ── max_tokens config ─────────────────────────────────────────────────────────

class _OkStreamResponse:
    status_code = 200
    def raise_for_status(self):
        pass
    async def aiter_lines(self):
        yield '{"message": {"content": "hi"}, "done": true}'


class _OkCtx:
    async def __aenter__(self):
        return _OkStreamResponse()
    async def __aexit__(self, *_a):
        return False


class _CapturingClient:
    last_payload: dict | None = None
    def __init__(self, *_a, **_k):
        pass
    async def __aenter__(self):
        return self
    async def __aexit__(self, *_a):
        return False
    def stream(self, _method, _url, json=None, **_k):
        type(self).last_payload = json
        return _OkCtx()


def test_max_tokens_respects_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_MAX_TOKENS", "1024")
    monkeypatch.setattr(httpx, "AsyncClient", _CapturingClient)
    _CapturingClient.last_payload = None

    from services.llm_service import chat_completion_stream
    asyncio.run(_drain(chat_completion_stream([{"role": "user", "content": "hi"}])))

    assert _CapturingClient.last_payload["options"]["num_predict"] == 1024


def test_max_tokens_default_leaves_room_for_reasoning(monkeypatch):
    monkeypatch.delenv("OLLAMA_MAX_TOKENS", raising=False)
    monkeypatch.setattr(httpx, "AsyncClient", _CapturingClient)
    _CapturingClient.last_payload = None

    from services.llm_service import chat_completion_stream
    asyncio.run(_drain(chat_completion_stream([{"role": "user", "content": "hi"}])))

    assert _CapturingClient.last_payload["options"]["num_predict"] >= 512
