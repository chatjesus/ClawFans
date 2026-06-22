"""
Voice Service — Google Cloud TTS with character-specific voice profiles.

Uses Chirp 3 HD voices for Chinese (cmn-CN). Each character's voice_id maps to
a Google Cloud TTS voice name. Falls back to sensible defaults by character gender.

Free tier: 1M characters/month on Chirp 3 HD.
"""
import os
import uuid
import logging
import asyncio
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

GCP_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

VOICE_DIR = Path(__file__).parent.parent / "uploads" / "voice"
VOICE_DIR.mkdir(parents=True, exist_ok=True)

# ── Voice Profiles ────────────────────────────────────────────────────────────
# Map character voice_id → TTS config. Characters without explicit voice_id
# get auto-assigned based on name/tags heuristics.

VOICE_PROFILES = {
    # Female voices — varied personality tones (Chirp 3 HD doesn't support pitch)
    "gentle_female":    {"name": "cmn-CN-Chirp3-HD-Kore",         "rate": 0.95},
    "cool_female":      {"name": "cmn-CN-Chirp3-HD-Aoede",        "rate": 0.90},
    "sweet_female":     {"name": "cmn-CN-Chirp3-HD-Leda",         "rate": 1.0},
    "mature_female":    {"name": "cmn-CN-Chirp3-HD-Sulafat",      "rate": 0.88},
    "energetic_female": {"name": "cmn-CN-Chirp3-HD-Gacrux",       "rate": 1.05},
    "mysterious_female":{"name": "cmn-CN-Chirp3-HD-Vindemiatrix", "rate": 0.92},
    "cute_female":      {"name": "cmn-CN-Chirp3-HD-Despina",      "rate": 1.1},

    # Male voices
    "warm_male":        {"name": "cmn-CN-Chirp3-HD-Charon",       "rate": 0.92},
    "playful_male":     {"name": "cmn-CN-Chirp3-HD-Puck",         "rate": 1.0},
    "deep_male":        {"name": "cmn-CN-Chirp3-HD-Fenrir",       "rate": 0.85},
    "gentle_male":      {"name": "cmn-CN-Chirp3-HD-Enceladus",    "rate": 0.95},
    "cold_male":        {"name": "cmn-CN-Chirp3-HD-Schedar",      "rate": 0.88},

    # Default
    "default_female":   {"name": "cmn-CN-Chirp3-HD-Kore",         "rate": 1.0},
    "default_male":     {"name": "cmn-CN-Chirp3-HD-Charon",       "rate": 1.0},
}

# Keywords in character tags/description → voice profile mapping
_FEMALE_VOICE_MAP = [
    (["温柔", "gentle", "healing", "治愈", "温暖"],           "gentle_female"),
    (["御姐", "cool", "冷酷", "高冷", "冰"],                  "cool_female"),
    (["甜美", "sweet", "萝莉", "loli", "可爱", "cute"],       "cute_female"),
    (["成熟", "mature", "大人", "sexy", "性感", "魅惑"],       "mature_female"),
    (["元气", "energetic", "活泼", "明朗"],                    "energetic_female"),
    (["神秘", "mysterious", "暗黑", "dark", "gothic"],        "mysterious_female"),
]

_MALE_VOICE_MAP = [
    (["温柔", "gentle", "暖男"],                              "gentle_male"),
    (["调皮", "playful", "阳光", "搞笑"],                     "playful_male"),
    (["霸道", "冷酷", "cool", "dark", "vampire"],             "cold_male"),
    (["低音", "deep", "成熟", "mature"],                      "deep_male"),
]


def resolve_voice_profile(voice_id: str, tags: str = "", description: str = "") -> dict:
    """Resolve a character's voice profile from voice_id or auto-detect from tags."""
    if voice_id and voice_id in VOICE_PROFILES:
        return VOICE_PROFILES[voice_id]

    combined = f"{tags} {description}".lower()

    is_male = any(k in combined for k in ["男", "male", "boy", "他", "哥", "daddy", "vampire lord"])
    voice_map = _MALE_VOICE_MAP if is_male else _FEMALE_VOICE_MAP

    for keywords, profile_id in voice_map:
        if any(k.lower() in combined for k in keywords):
            return VOICE_PROFILES[profile_id]

    return VOICE_PROFILES["default_male" if is_male else "default_female"]


# ── TTS Client ────────────────────────────────────────────────────────────────

_TTS_WORKER_SCRIPT = Path(__file__).parent.parent / "scripts" / "_tts_worker.py"
if not _TTS_WORKER_SCRIPT.exists():
    _TTS_WORKER_SCRIPT = Path(__file__).parent.parent.parent / "scripts" / "_tts_worker.py"


async def _synthesize_subprocess(text: str, voice_name: str, rate: float) -> bytes:
    """Run TTS in a completely separate Python process (avoids gRPC/uvicorn conflicts on Windows)."""
    import tempfile, json, subprocess

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        out_path = tmp.name

    args_json = json.dumps({
        "text": text,
        "voice_name": voice_name,
        "rate": rate,
        "credentials": GCP_CREDENTIALS,
        "output": out_path,
    })

    proc = await asyncio.create_subprocess_exec(
        "python", str(_TTS_WORKER_SCRIPT), args_json,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=25.0)

    if proc.returncode != 0:
        err_msg = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"TTS worker failed: {err_msg}")

    data = Path(out_path).read_bytes()
    try:
        os.unlink(out_path)
    except OSError:
        pass
    return data


def _strip_roleplay_markers(text: str) -> str:
    """Remove *action* markers and image tags, keep only speakable text."""
    import re
    text = re.sub(r"\*[^*]+\*", "", text)
    text = re.sub(r"\[IMG:[^\]]+\]", "", text)
    text = re.sub(r"\[SCENE:\d+\]", "", text)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def _mimo_bytes(clean_text: str) -> Optional[bytes]:
    """MiMo cloud TTS bytes when opted in (MIMO_API_KEY + TTS_ENGINE=mimo),
    else None so the caller falls back to the local engine."""
    if not (os.getenv("MIMO_API_KEY") and os.getenv("TTS_ENGINE", "").lower() == "mimo"):
        return None
    try:
        from services.mimo_tts import synthesize_mimo
        return await synthesize_mimo(clean_text)
    except Exception as e:
        logger.warning(f"MiMo TTS error, falling back to local: {e}")
        return None


async def synthesize_speech(
    text: str,
    voice_id: str = "",
    tags: str = "",
    description: str = "",
    max_chars: int = 300,
) -> Optional[str]:
    """
    Convert text to speech using Google Cloud TTS.
    Returns the URL path to the generated audio file, or None on failure.
    """
    clean_text = _strip_roleplay_markers(text)
    if not clean_text or len(clean_text) < 2:
        return None

    if len(clean_text) > max_chars:
        clean_text = clean_text[:max_chars]

    # MiMo cloud TTS (opt-in via MIMO_API_KEY + TTS_ENGINE=mimo). Falls through
    # to the local engine if MiMo yields nothing (e.g. content moderation).
    mimo_audio = await _mimo_bytes(clean_text)
    if mimo_audio:
        fname = f"tts_{uuid.uuid4().hex[:12]}.wav"
        (VOICE_DIR / fname).write_bytes(mimo_audio)
        logger.info(f"MiMo TTS audio saved: {fname} ({len(clean_text)} chars)")
        return f"/uploads/voice/{fname}"

    if os.getenv("ALLOW_ONLINE_MODELS") != "1":
        audio_bytes = await _local_tts_bytes(clean_text, tags, description, voice_id)
        if not audio_bytes:
            return None
        fname = f"tts_{uuid.uuid4().hex[:12]}.wav"
        filepath = VOICE_DIR / fname
        filepath.write_bytes(audio_bytes)
        logger.info(f"Local TTS audio saved: {filepath} ({len(clean_text)} chars)")
        return f"/uploads/voice/{fname}"

    profile = resolve_voice_profile(voice_id, tags, description)

    try:
        audio_bytes = await _synthesize_subprocess(
            clean_text, profile["name"], profile.get("rate", 1.0)
        )
    except Exception as e:
        logger.warning(f"Google Cloud TTS failed ({e}), falling back to edge-tts")
        audio_bytes = await _fallback_edge_tts(clean_text, voice_id, tags, description)

    if not audio_bytes:
        return None

    fname = f"tts_{uuid.uuid4().hex[:12]}.mp3"
    filepath = VOICE_DIR / fname
    filepath.write_bytes(audio_bytes)
    logger.info(f"TTS audio saved: {filepath} ({len(clean_text)} chars)")
    return f"/uploads/voice/{fname}"


async def _fallback_edge_tts(text: str, voice_id: str, tags: str, description: str) -> Optional[bytes]:
    """Fallback: use edge-tts when Google Cloud TTS is unavailable."""
    try:
        from services.tts_service import pick_voice_for_character, _clean_for_tts
        import edge_tts, io

        cleaned = _clean_for_tts(text)
        if not cleaned:
            return None

        voice = pick_voice_for_character(tags, description, voice_id=voice_id)
        communicate = edge_tts.Communicate(cleaned, voice, rate="+5%", pitch="+0Hz")

        buf = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])

        data = buf.getvalue()
        if data:
            logger.info(f"TTS fallback (edge-tts): voice={voice}, {len(data)} bytes")
        return data or None
    except Exception as e2:
        logger.error(f"TTS edge-tts fallback also failed: {e2}")
        return None


async def _local_tts_bytes(text: str, tags: str, description: str = "", voice_id: str = "") -> Optional[bytes]:
    """Use local GPT-SoVITS only; no cloud or edge fallback."""
    try:
        from services.tts_service import synthesize_stream
        chunks = []
        async for chunk in synthesize_stream(text, tags=tags, description=description, voice_id=voice_id):
            chunks.append(chunk)
        return b"".join(chunks) or None
    except Exception as e:
        logger.error(f"Local TTS failed: {e}")
        return None


async def synthesize_speech_streaming(
    text: str,
    voice_id: str = "",
    tags: str = "",
    description: str = "",
    max_chars: int = 300,
) -> Optional[bytes]:
    """
    Same as synthesize_speech but returns raw MP3 bytes directly.
    Falls back to edge-tts if Google Cloud TTS fails.
    """
    clean_text = _strip_roleplay_markers(text)
    if not clean_text or len(clean_text) < 2:
        return None

    if len(clean_text) > max_chars:
        clean_text = clean_text[:max_chars]

    # MiMo cloud TTS (opt-in), else local engine.
    mimo_audio = await _mimo_bytes(clean_text)
    if mimo_audio:
        return mimo_audio

    if os.getenv("ALLOW_ONLINE_MODELS") != "1":
        return await _local_tts_bytes(clean_text, tags, description, voice_id)

    profile = resolve_voice_profile(voice_id, tags, description)

    try:
        return await _synthesize_subprocess(
            clean_text, profile["name"], profile.get("rate", 1.0)
        )
    except Exception as e:
        logger.warning(f"Google Cloud TTS failed ({e}), falling back to edge-tts")
        return await _fallback_edge_tts(clean_text, voice_id, tags, description)
