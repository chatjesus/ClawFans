"""
LLM Service – wraps Ollama API (OpenAI-compatible) for chat completions.
"""
import httpx
from typing import AsyncGenerator

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "huihui_ai/qwen2.5-abliterate:14b"


async def chat_completion_stream(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.95,
    max_tokens: int = 2048,
) -> AsyncGenerator[str, None]:
    """
    Stream chat completion from Ollama.
    Yields text chunks as they arrive.
    """
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            async with client.stream(
                "POST",
                f"{OLLAMA_BASE_URL}/api/chat",
                json=payload,
            ) as response:
                if response.status_code == 404:
                    raise RuntimeError(
                        f"Model '{model}' not found. It may still be downloading. "
                        f"Check progress with: ollama pull {model}"
                    )
                response.raise_for_status()
                import json
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            chunk = data["message"]["content"]
                            if chunk:
                                yield chunk
                        if data.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue
    except httpx.ConnectError:
        raise RuntimeError(
            "Cannot connect to Ollama. Make sure Ollama is running (ollama serve)."
        )


async def chat_completion(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.85,
    max_tokens: int = 2048,
) -> str:
    """
    Non-streaming chat completion. Returns full response text.
    """
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
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
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False


async def list_models() -> list[str]:
    """List available models from Ollama."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []

