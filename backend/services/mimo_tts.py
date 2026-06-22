"""
Xiaomi MiMo TTS adapter.

MiMo speech synthesis is an OpenAI-chat-shaped endpoint:
  POST {base}/v1/chat/completions   header: api-key: <key>
  body: {model, messages:[{role:"assistant", content:<text>}], audio:{format,voice}}
  resp: choices[0].message.audio.data = base64 audio (wav)

Returns decoded audio bytes (wav). Key comes from MIMO_API_KEY env (or arg);
never hardcode it. NOTE for this product: MiMo is a cloud API with content
moderation — explicit text may be rejected/sanitized and the text leaves the
machine. Use for tame lines; keep explicit voice on local GPT-SoVITS.
"""
import base64
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

MIMO_BASE_URL = os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com")
MIMO_MODEL = os.getenv("MIMO_TTS_MODEL", "mimo-v2.5-tts")
MIMO_DEFAULT_VOICE = os.getenv("MIMO_VOICE", "mimo_default")


async def synthesize_mimo(
    text: str,
    voice: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    audio_format: str = "wav",
) -> Optional[bytes]:
    """Synthesize ``text`` via MiMo TTS. Returns audio bytes, or None on
    missing key / empty text / failure."""
    api_key = api_key or os.getenv("MIMO_API_KEY")
    if not api_key or not text or not text.strip():
        return None

    base_url = (base_url or MIMO_BASE_URL).rstrip("/")
    model = model or MIMO_MODEL
    voice = voice or MIMO_DEFAULT_VOICE

    payload = {
        "model": model,
        # Per MiMo docs: the text to synthesize goes in an assistant message.
        "messages": [{"role": "assistant", "content": text}],
        "audio": {"format": audio_format, "voice": voice},
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            resp = await client.post(
                f"{base_url}/v1/chat/completions",
                headers={"api-key": api_key, "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            b64 = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("audio", {})
                .get("data")
            )
            if not b64:
                logger.warning("MiMo TTS returned no audio (possibly moderated): %s", str(data)[:200])
                return None
            return base64.b64decode(b64)
    except Exception as e:
        logger.error(f"MiMo TTS failed: {e}")
        return None
