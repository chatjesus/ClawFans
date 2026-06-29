"""
LLM Service – wraps Ollama API (OpenAI-compatible) for chat completions.

Configuration is read from env at call time (not at import time) so changes
to OLLAMA_BASE_URL / OLLAMA_MODEL take effect without re-importing the
module. Defaults match README and docker-compose.yml.
"""
import json
import os
from typing import AsyncGenerator

import httpx


def _base_url() -> str:
    """Resolve the Ollama base URL from env on every call."""
    return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


def get_default_model() -> str:
    """Resolve the default model name from env on every call."""
    return os.environ.get("OLLAMA_MODEL", "qwen2.5:14b")


def _num_ctx() -> int:
    """Context window size. Default 8192 — the multi-layer system prompt plus
    chat history routinely exceeds 4096, which silently truncates history.
    Qwen 2.5 supports far larger; raise via OLLAMA_NUM_CTX if you have VRAM."""
    try:
        return int(os.environ.get("OLLAMA_NUM_CTX", "8192"))
    except ValueError:
        return 8192


def _max_tokens() -> int:
    """Default reply length (num_predict). 800, not 400 — reasoning models
    (e.g. qwen3) spend part of the budget on hidden thinking, and 400 left some
    replies empty. Tune via OLLAMA_MAX_TOKENS."""
    try:
        return int(os.environ.get("OLLAMA_MAX_TOKENS", "800"))
    except ValueError:
        return 800


def _keep_alive() -> str:
    """How long Ollama keeps the model resident after a request. Default 30m so
    a big model isn't evicted between turns (reloading ~18GB looks like a freeze).
    Set OLLAMA_KEEP_ALIVE=-1 to keep it loaded forever."""
    return os.environ.get("OLLAMA_KEEP_ALIVE", "30m")


def _repeat_penalty() -> float:
    """Penalize token repetition. Default 1.15 — without it the model echoed
    the user's last line and reused the same closing question. Tune via
    OLLAMA_REPEAT_PENALTY."""
    try:
        return float(os.environ.get("OLLAMA_REPEAT_PENALTY", "1.15"))
    except ValueError:
        return 1.15


async def chat_completion_stream(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.95,
    max_tokens: int | None = None,
) -> AsyncGenerator[str, None]:
    """Stream chat completion from Ollama. Yields text chunks as they arrive."""
    model = model or get_default_model()
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "keep_alive": _keep_alive(),
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens if max_tokens is not None else _max_tokens(),
            "num_ctx": _num_ctx(),
            "repeat_penalty": _repeat_penalty(),
        },
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            async with client.stream(
                "POST",
                f"{_base_url()}/api/chat",
                json=payload,
            ) as response:
                if response.status_code == 404:
                    raise RuntimeError(
                        f"Model '{model}' not found. It may still be downloading. "
                        f"Check progress with: ollama pull {model}"
                    )
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    # Ollama can answer 200 OK with an in-band error (model needs a
                    # subscription, not pulled, etc.). Surface it instead of ending
                    # the stream silently with no content.
                    if isinstance(data, dict) and data.get("error"):
                        raise RuntimeError(f"Ollama error: {data['error']}")
                    if "message" in data and "content" in data["message"]:
                        chunk = data["message"]["content"]
                        if chunk:
                            yield chunk
                    if data.get("done", False):
                        break
    except httpx.ConnectError:
        raise RuntimeError(
            "Cannot connect to Ollama. Make sure Ollama is running (ollama serve)."
        )


async def chat_completion(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.85,
    max_tokens: int | None = None,
) -> str:
    """Non-streaming chat completion. Returns full response text."""
    model = model or get_default_model()
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "keep_alive": _keep_alive(),
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens if max_tokens is not None else _max_tokens(),
            "num_ctx": _num_ctx(),
            "repeat_penalty": _repeat_penalty(),
        },
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            resp = await client.post(
                f"{_base_url()}/api/chat",
                json=payload,
            )
            if resp.status_code == 404:
                raise RuntimeError(
                    f"Model '{model}' not found. It may still be downloading. "
                    f"Check progress with: ollama pull {model}"
                )
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")
    except httpx.ConnectError:
        raise RuntimeError(
            "Cannot connect to Ollama. Make sure Ollama is running (ollama serve)."
        )


async def check_ollama_health() -> bool:
    """Check if Ollama server is running."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.get(f"{_base_url()}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False


async def list_models() -> list[str]:
    """List available models from Ollama."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.get(f"{_base_url()}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []
