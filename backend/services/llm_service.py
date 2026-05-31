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


async def chat_completion_stream(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.95,
    max_tokens: int = 400,
) -> AsyncGenerator[str, None]:
    """Stream chat completion from Ollama. Yields text chunks as they arrive."""
    model = model or get_default_model()
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
            "num_ctx": _num_ctx(),
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
    max_tokens: int = 400,
) -> str:
    """Non-streaming chat completion. Returns full response text."""
    model = model or get_default_model()
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
            "num_ctx": _num_ctx(),
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
