"""
TTS Service — dual-engine text-to-speech.

Engine priority:
  1. GPT-SoVITS (local, port 9880) — best Chinese character voice quality
  2. edge-tts  (Microsoft neural, free, no API key needed) — always-available fallback

Voice is selected by analyzing character tags + description for gender/age/personality.
"""

import re
from typing import AsyncIterator

import httpx

# ── Edge-TTS voice profiles ───────────────────────────────────────────────────
# voice_id → (display_name, gender, personality_keywords)
# Full list: https://learn.microsoft.com/azure/ai-services/speech-service/language-support
VOICE_PROFILES = {
    # ── Female voices (actually available in edge-tts 7.x) ──
    "zh-CN-XiaoxiaoNeural":  ("晓晓", "female", ["温柔", "甜美", "撒娇", "贴心", "善良", "软萌", "疗愈", "御姐", "成熟", "冷傲", "soft", "sweet", "warm", "gentle", "healing", "mature"]),
    "zh-CN-XiaoyiNeural":    ("晓伊", "female", ["活泼", "开朗", "元气", "热情", "职场", "律师", "知性", "文艺", "lively", "energetic", "professional", "intellectual"]),
    # ── Male voices ──
    "zh-CN-YunxiNeural":     ("云希", "male", ["少年", "青年", "普通", "帅气", "室友", "同学", "朋友", "young", "casual", "college", "friend", "roommate"]),
    "zh-CN-YunjianNeural":   ("云健", "male", ["严肃", "权威", "霸道", "总裁", "成熟男", "深沉", "serious", "authoritative", "dominant", "mature", "CEO", "boss"]),
    "zh-CN-YunxiaNeural":    ("云夏", "male", ["温暖", "体贴", "暖男", "绅士", "治愈", "warm", "caring", "gentleman", "tender"]),
    "zh-CN-YunyangNeural":   ("云扬", "male", ["播音", "正式", "专业", "新闻", "formal", "news", "professional"]),
}

_EDGE_DEFAULT_FEMALE = "zh-CN-XiaoxiaoNeural"
_EDGE_DEFAULT_MALE   = "zh-CN-YunxiNeural"

# English fallback voices — used when text is detected as English
_EN_FEMALE = "en-US-JennyNeural"
_EN_MALE   = "en-US-GuyNeural"


def pick_voice_for_character(
    tags: str,
    description: str = "",
    name: str = "",
    voice_id: str = "",
) -> str:
    """
    Select the best edge-tts voice for a character.
    Priority: stored voice_id > keyword matching in tags+description+name.
    """
    # 1. Use stored voice_id if valid
    if voice_id and voice_id in VOICE_PROFILES:
        return voice_id

    # 2. Combine all text for analysis
    corpus = f"{tags} {description} {name}".lower()

    # 3. Detect gender first
    male_signals = ["男", "boy", "男性", "男生", "male", "他是", "先生", "总裁", "大叔",
                    "jake", "marcus", "ethan", "ryan", "chen", "zhang", "li wei"]
    female_signals = ["女", "girl", "女性", "女生", "female", "她是", "小姐", "姐姐",
                      "妹妹", "女友", "luna", "aria", "mika", "elena", "kim", "sage"]

    male_score = sum(1 for w in male_signals if w in corpus)
    female_score = sum(1 for w in female_signals if w in corpus)
    is_male = male_score > female_score

    # 4. Score each voice profile against corpus keywords
    best_voice = _EDGE_DEFAULT_MALE if is_male else _EDGE_DEFAULT_FEMALE
    best_score = 0

    for voice_id_candidate, (_, gender, keywords) in VOICE_PROFILES.items():
        # Skip wrong-gender voices (unless no strong gender signal)
        if is_male and gender == "female" and male_score > 0:
            continue
        if not is_male and gender == "male" and female_score > 0:
            continue

        score = sum(1 for kw in keywords if kw.lower() in corpus)
        if score > best_score:
            best_score = score
            best_voice = voice_id_candidate

    return best_voice

# ── GPT-SoVITS config ─────────────────────────────────────────────────────────
_SOVITS_BASE = "http://127.0.0.1:9880"

# Map archetype → reference audio path (relative to GPT-SoVITS install dir)
# Users should place .wav files in the GPT-SoVITS/voices/ folder
_SOVITS_REF_MAP: dict[str, str] = {
    "御姐":    "voices/yuejie.wav",
    "温柔":    "voices/wenrou.wav",
    "可爱":    "voices/kawaii.wav",
    "活泼":    "voices/lively.wav",
    "职场":    "voices/office.wav",
    "男":      "voices/male.wav",
}
_SOVITS_DEFAULT_REF = "voices/default.wav"


# ── Helpers ───────────────────────────────────────────────────────────────────



def _pick_sovits_ref(tags: str) -> str:
    for kw, path in _SOVITS_REF_MAP.items():
        if kw in tags:
            return path
    return _SOVITS_DEFAULT_REF


def _detect_language(text: str) -> str:
    """Return 'zh' if text is predominantly Chinese, else 'en'."""
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    ascii_words = len(re.findall(r"[a-zA-Z]+", text))
    # If there are more CJK characters than ASCII words, treat as Chinese
    return "zh" if chinese_chars >= ascii_words else "en"


def _clean_for_tts(text: str) -> str:
    """Remove markdown, action asterisks, and image tags before TTS."""
    # Normalize smart/curly quotes → plain ASCII quotes (these break edge-tts)
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    # Strip [IMG:...] [SCENE:...] tags
    text = re.sub(r"\[(?:IMG|SCENE):[^\]]*\]", "", text)
    # Strip markdown bold/italic, keep inner text
    text = re.sub(r"\*{1,3}([^*]*)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,2}([^_]*)_{1,2}", r"\1", text)
    # Collapse whitespace
    text = re.sub(r"\n{2,}", "\n", text).strip()
    return text


def split_sentences(text: str) -> list[str]:
    """Split Chinese text into TTS-friendly sentences (≤50 chars each)."""
    # Split on sentence-ending punctuation
    parts = re.split(r"(?<=[。！？…\n])", text)
    result = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Further split very long sentences at commas
        if len(part) > 60:
            sub = re.split(r"(?<=[，、；])", part)
            result.extend(s.strip() for s in sub if s.strip())
        else:
            result.append(part)
    return result


# ── Engine availability check ─────────────────────────────────────────────────

async def gptsovits_available() -> bool:
    """Return True if GPT-SoVITS API server is reachable on port 9880."""
    try:
        async with httpx.AsyncClient(timeout=1.5) as c:
            r = await c.get(f"{_SOVITS_BASE}/")
            return r.status_code < 500
    except Exception:
        return False


# ── Synthesis streams ─────────────────────────────────────────────────────────

async def _stream_edge_tts(text: str, voice: str) -> AsyncIterator[bytes]:
    """Yield raw MP3 bytes from edge-tts (with 20s timeout guard)."""
    try:
        import edge_tts
    except ImportError:
        raise RuntimeError("edge-tts not installed — run: pip install edge-tts")

    import asyncio

    async def _gen():
        communicate = edge_tts.Communicate(text, voice, rate="+5%", pitch="+0Hz")
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]

    # Wrap with timeout — if edge-tts hangs, fail after 20s instead of forever
    try:
        async with asyncio.timeout(20):
            async for data in _gen():
                yield data
    except asyncio.TimeoutError:
        print(f"[TTS] edge-tts timeout for voice={voice}, len={len(text)}")
        return


async def _stream_sovits(text: str, ref_audio: str) -> AsyncIterator[bytes]:
    """Yield WAV/MP3 bytes from GPT-SoVITS API v2."""
    params = {
        "text": text,
        "text_lang": "zh",
        "ref_audio_path": ref_audio,
        "streaming_mode": "true",
        "media_type": "wav",
    }
    async with httpx.AsyncClient(timeout=60.0) as c:
        async with c.stream("GET", f"{_SOVITS_BASE}/tts", params=params) as r:
            r.raise_for_status()
            async for chunk in r.aiter_bytes(chunk_size=4096):
                yield chunk


# ── Public API ────────────────────────────────────────────────────────────────

async def synthesize_stream(
    text: str,
    tags: str = "",
    category: str = "",
    description: str = "",
    name: str = "",
    voice_id: str = "",
) -> AsyncIterator[bytes]:
    """
    Synthesize text and stream audio bytes.
    Uses local GPT-SoVITS by default. edge-tts is only allowed when
    ALLOW_ONLINE_MODELS=1 is explicitly set.
    Voice is matched from character tags + description.
    """
    cleaned = _clean_for_tts(text)
    if not cleaned:
        return

    if await gptsovits_available():
        ref = _pick_sovits_ref(tags)
        async for chunk in _stream_sovits(cleaned, ref):
            yield chunk
    else:
        import os
        if os.getenv("ALLOW_ONLINE_MODELS") != "1":
            raise RuntimeError("Local GPT-SoVITS is not running; online TTS is disabled.")
        lang = _detect_language(cleaned)
        if lang == "en":
            # Detect gender from stored voice to pick matching English voice
            stored = pick_voice_for_character(tags, description, name, voice_id)
            gender = VOICE_PROFILES.get(stored, ("", "female", []))[1]
            voice = _EN_MALE if gender == "male" else _EN_FEMALE
        else:
            voice = pick_voice_for_character(tags, description, name, voice_id)
        print(f"[TTS] lang={lang} voice={voice} char={name!r} text_preview={cleaned[:60]!r}")
        chunk_count = 0
        async for chunk in _stream_edge_tts(cleaned, voice):
            chunk_count += 1
            yield chunk
        print(f"[TTS] done: {chunk_count} chunks for char={name!r}")


async def get_engine_info() -> dict:
    """Return current TTS engine status."""
    sovits = await gptsovits_available()
    return {
        "engine": "gptsovits" if sovits else "offline-unavailable",
        "gptsovits_available": sovits,
        "gptsovits_url": _SOVITS_BASE,
        "voices": list(VOICE_PROFILES.keys()),
    }
