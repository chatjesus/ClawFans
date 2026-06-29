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
import re
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

MIMO_BASE_URL = os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com")
MIMO_MODEL = os.getenv("MIMO_TTS_MODEL", "mimo-v2.5-tts")
MIMO_DEFAULT_VOICE = os.getenv("MIMO_VOICE", "mimo_default")

# ── Per-character voice selection ─────────────────────────────────────────────
# MiMo-V2.5-TTS preset voices. This is a zh-CN product, so persona auto-mapping
# targets the four Chinese presets; the English ones are honored only as an
# explicit override.
MIMO_VOICES = {"冰糖", "茉莉", "苏打", "白桦", "Mia", "Chloe", "Milo", "Dean"}

# voice_id holds a Google/local VOICE_PROFILES key (see voice_service). Map each
# to the MiMo preset that matches its gender + tone, so a character keeps a
# consistent voice across engines.
_PROFILE_TO_MIMO = {
    "gentle_female": "冰糖", "sweet_female": "冰糖", "cute_female": "冰糖",
    "energetic_female": "冰糖", "default_female": "冰糖",
    "cool_female": "茉莉", "mature_female": "茉莉", "mysterious_female": "茉莉",
    "warm_male": "苏打", "playful_male": "苏打", "gentle_male": "苏打",
    "default_male": "苏打",
    "deep_male": "白桦", "cold_male": "白桦",
}

# Persona keyword heuristics for characters with no explicit voice_id. Checked
# female-first with a female default (the product skews female companions).
# ASCII markers match whole words (so "king" doesn't fire inside "cracking");
# CJK markers match as substrings.
_FEMALE_MARKERS = ("she", "her", "woman", "women", "girl", "goddess", "queen",
                   "mistress", "priestess", "witch", "idol", "lady", "女", "少女",
                   "御姐", "妹", "姐", "妈", "母", "妻")
_MALE_MARKERS = ("he", "his", "him", "guy", "man", "boyfriend", "king", "lord",
                 "prince", "ceo", "coach", "mr", "sir", "daddy", "男", "哥",
                 "少年", "大叔", "总裁", "君", "爸", "父")
_FEMALE_MATURE = ("mysterious", "mature", "elegant", "cool", "dominant", "seduct",
                  "seduction", "seductive", "sensual", "goddess", "queen",
                  "mistress", "御姐", "成熟", "高冷", "魅惑", "神秘", "女王", "妖")
_MALE_DEEP = ("deep", "cold", "dominant", "ruthless", "king", "lord", "ceo",
              "mafia", "boss", "vampire", "总裁", "霸道", "成熟", "mature", "冷")

_WORD_SPLIT = re.compile(r"[^a-z0-9一-鿿]+")


def _matches(markers, norm: str, words: set) -> bool:
    """Whole-word match for ASCII markers, substring for CJK."""
    return any((m in words) if m.isascii() else (m in norm) for m in markers)


def resolve_mimo_voice(voice_id: str = "", tags: str = "", description: str = "") -> str:
    """Pick the MiMo preset voice that fits a character's persona.

    Priority: explicit MiMo preset name in voice_id > known Google-profile id >
    gender+tone heuristic on tags/description > female default (冰糖).
    """
    if voice_id in MIMO_VOICES:
        return voice_id
    if voice_id in _PROFILE_TO_MIMO:
        return _PROFILE_TO_MIMO[voice_id]

    norm = " " + _WORD_SPLIT.sub(" ", f"{tags} {description}".lower()).strip() + " "
    words = set(norm.split())
    is_female = _matches(_FEMALE_MARKERS, norm, words)
    is_male = (not is_female) and _matches(_MALE_MARKERS, norm, words)

    if is_male:
        return "白桦" if _matches(_MALE_DEEP, norm, words) else "苏打"
    return "茉莉" if _matches(_FEMALE_MATURE, norm, words) else "冰糖"


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
