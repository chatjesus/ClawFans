"""
P0-4 regression test — Ollama base URL and model name must be configurable
via env vars, as documented in README, .env.example and docker-compose.yml.

Bug: llm_service hard-codes OLLAMA_BASE_URL and reads the wrong env var
name (OLLAMA_DEFAULT_MODEL) for the model. Inside Docker the compose file
sets `OLLAMA_BASE_URL=http://ollama:11434` to reach the Ollama service —
but the backend ignores it and tries `http://localhost:11434`, which is
the backend container itself. Result: no LLM, ever.

We don't care HOW the URL is propagated — we test the behaviour: when env
says http://custom:5000, the HTTP client targets http://custom:5000.
"""
import asyncio
import httpx


class _FakeResponse:
    status_code = 200
    def raise_for_status(self): pass
    def json(self): return {"models": []}


class _FakeAsyncClient:
    last_get_url: str | None = None

    def __init__(self, *_args, **_kwargs): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *_a): return False
    async def get(self, url, **_kwargs):
        type(self).last_get_url = url
        return _FakeResponse()


def test_check_ollama_health_uses_OLLAMA_BASE_URL_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://custom-host:5000")
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.last_get_url = None

    from services.llm_service import check_ollama_health
    asyncio.run(check_ollama_health())

    assert _FakeAsyncClient.last_get_url is not None, "httpx client was never invoked"
    assert _FakeAsyncClient.last_get_url.startswith("http://custom-host:5000"), (
        f"check_ollama_health hit {_FakeAsyncClient.last_get_url!r} — "
        f"the OLLAMA_BASE_URL env var was not honoured."
    )


def test_default_model_uses_OLLAMA_MODEL_env(monkeypatch):
    """The model env var documented everywhere is OLLAMA_MODEL — not
    OLLAMA_DEFAULT_MODEL. Verify the code reads the correct name."""
    monkeypatch.setenv("OLLAMA_MODEL", "my-custom-model:7b")
    monkeypatch.delenv("OLLAMA_DEFAULT_MODEL", raising=False)

    from services.llm_service import get_default_model
    assert get_default_model() == "my-custom-model:7b", (
        "DEFAULT_MODEL was not resolved from OLLAMA_MODEL env var."
    )


class _FakeStreamResponse:
    status_code = 200
    def raise_for_status(self): pass
    async def aiter_lines(self):
        yield '{"message": {"content": "hi"}, "done": true}'


class _FakeStreamCtx:
    async def __aenter__(self): return _FakeStreamResponse()
    async def __aexit__(self, *_a): return False


class _CapturingClient:
    last_payload: dict | None = None

    def __init__(self, *_a, **_k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *_a): return False
    def stream(self, _method, _url, json=None, **_k):
        type(self).last_payload = json
        return _FakeStreamCtx()


async def _drain_stream(gen):
    async for _ in gen:
        pass


def test_num_ctx_defaults_above_4096(monkeypatch):
    """4096 truncates the multi-layer system prompt + history. Default must be
    larger so Qwen 2.5 keeps the whole context."""
    monkeypatch.delenv("OLLAMA_NUM_CTX", raising=False)
    monkeypatch.setattr(httpx, "AsyncClient", _CapturingClient)
    _CapturingClient.last_payload = None

    from services.llm_service import chat_completion_stream
    asyncio.run(_drain_stream(chat_completion_stream([{"role": "user", "content": "hi"}])))

    ctx = _CapturingClient.last_payload["options"]["num_ctx"]
    assert ctx >= 8192, f"num_ctx default is too small ({ctx}); history will be truncated."


def test_num_ctx_respects_OLLAMA_NUM_CTX_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_NUM_CTX", "16384")
    monkeypatch.setattr(httpx, "AsyncClient", _CapturingClient)
    _CapturingClient.last_payload = None

    from services.llm_service import chat_completion_stream
    asyncio.run(_drain_stream(chat_completion_stream([{"role": "user", "content": "hi"}])))

    assert _CapturingClient.last_payload["options"]["num_ctx"] == 16384
