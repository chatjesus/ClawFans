"""
LLM Service – wraps Ollama API (OpenAI-compatible) for chat completions.
"""
import httpx
from typing import AsyncGenerator

import os
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = os.environ.get("OLLAMA_DEFAULT_MODEL", "qwen2.5:14b")


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
            "num_ctx": 8192,
        },
    }

    # #region agent log
    import json as _jl, time as _tl
    _total_chars = sum(len(m.get("content","")) for m in messages)
    try:
        with open("debug-c16f2f.log","a",encoding="utf-8") as _f:
            _f.write(_jl.dumps({"sessionId":"c16f2f","runId":"run1","hypothesisId":"A","location":"llm_service.py:stream_start","message":"stream_request","data":{"total_chars":_total_chars,"num_messages":len(messages),"num_ctx":payload["options"]["num_ctx"]},"timestamp":int(_tl.time()*1000)})+"\n")
    except Exception: pass
    # #endregion
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
                chunk_count = 0
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            chunk = data["message"]["content"]
                            if chunk:
                                chunk_count += 1
                                yield chunk
                        if data.get("done", False):
                            # #region agent log
                            try:
                                with open("debug-c16f2f.log","a",encoding="utf-8") as _f2:
                                    _f2.write(_jl.dumps({"sessionId":"c16f2f","runId":"run1","hypothesisId":"A","location":"llm_service.py:stream_done","message":"stream_finished","data":{"chunk_count":chunk_count,"prompt_eval_count":data.get("prompt_eval_count"),"eval_count":data.get("eval_count")},"timestamp":int(_tl.time()*1000)})+"\n")
                            except Exception: pass
                            # #endregion
                            break
                    except json.JSONDecodeError:
                        continue
                # #region agent log
                if chunk_count == 0:
                    try:
                        with open("debug-c16f2f.log","a",encoding="utf-8") as _f3:
                            _f3.write(_jl.dumps({"sessionId":"c16f2f","runId":"run1","hypothesisId":"A","location":"llm_service.py:empty","message":"EMPTY_RESPONSE","data":{"total_chars":_total_chars,"num_ctx_sent":payload["options"]["num_ctx"]},"timestamp":int(_tl.time()*1000)})+"\n")
                    except Exception: pass
                # #endregion
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
            "num_ctx": 8192,
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

