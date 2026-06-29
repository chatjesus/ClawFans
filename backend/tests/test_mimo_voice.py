"""
Each character's TTS voice must fit its persona.

The MiMo path used to synthesize every character with the global default voice.
resolve_mimo_voice maps a character (explicit voice_id / Google-profile id /
persona keywords) to one of MiMo's preset zh-CN voices, and _mimo_bytes threads
it into the actual synthesis call.

MiMo zh-CN presets: 冰糖 (sweet female), 茉莉 (elegant/mature female),
苏打 (young/playful male), 白桦 (deep/mature male).
"""
import asyncio

from services.mimo_tts import resolve_mimo_voice, MIMO_VOICES


def test_persona_keywords_map_to_fitting_voice():
    # mature / cool / seductive woman -> 茉莉
    assert resolve_mimo_voice(tags="御姐,高冷,魅惑") == "茉莉"
    assert resolve_mimo_voice(description="an elegant, mysterious goddess of seduction, she...") == "茉莉"
    # sweet / cute / gentle woman -> 冰糖
    assert resolve_mimo_voice(description="a sweet, cute girl-next-door, bubbly and warm") == "冰糖"
    # cold / dominant man -> 白桦
    assert resolve_mimo_voice(description="a cold, dominant CEO; he is ruthless and deep-voiced") == "白桦"
    # playful / warm man -> 苏打
    assert resolve_mimo_voice(description="a playful, warm guy; he loves cracking jokes") == "苏打"


def test_explicit_voice_id_overrides():
    # a literal MiMo preset in voice_id wins outright
    assert resolve_mimo_voice(voice_id="茉莉") == "茉莉"
    # every Google-profile id used by the seed characters maps by gender+tone
    assert resolve_mimo_voice(voice_id="cool_female") == "茉莉"
    assert resolve_mimo_voice(voice_id="mysterious_female") == "茉莉"
    assert resolve_mimo_voice(voice_id="mature_female") == "茉莉"
    assert resolve_mimo_voice(voice_id="cute_female") == "冰糖"
    assert resolve_mimo_voice(voice_id="gentle_female") == "冰糖"
    assert resolve_mimo_voice(voice_id="playful_male") == "苏打"
    assert resolve_mimo_voice(voice_id="deep_male") == "白桦"


def test_default_is_a_valid_preset():
    v = resolve_mimo_voice()  # no signal at all
    assert v in MIMO_VOICES


def test_mimo_skipped_for_explicit_content(monkeypatch):
    # explicit lines would be silently moderated/dropped by cloud MiMo, leaving the
    # voice reverse-disconnected from the text. Explicit → skip MiMo, go local.
    monkeypatch.setenv("MIMO_API_KEY", "x")
    monkeypatch.setenv("TTS_ENGINE", "mimo")

    async def fake_syn(text, voice=None, **k):
        return b"RIFFmimo"

    monkeypatch.setattr("services.mimo_tts.synthesize_mimo", fake_syn)
    from services.voice_service import _mimo_bytes
    assert asyncio.run(_mimo_bytes("露骨内容", explicit=True)) is None      # skip cloud
    assert asyncio.run(_mimo_bytes("普通问候", explicit=False)) == b"RIFFmimo"  # tame ok


def test_mimo_bytes_synthesizes_with_persona_voice(monkeypatch):
    # the MiMo path must pass the persona-resolved voice, not the global default
    monkeypatch.setenv("MIMO_API_KEY", "x")
    monkeypatch.setenv("TTS_ENGINE", "mimo")
    captured = {}

    async def fake_syn(text, voice=None, **k):
        captured["voice"] = voice
        return b"RIFFfakeaudio"

    monkeypatch.setattr("services.mimo_tts.synthesize_mimo", fake_syn)
    from services.voice_service import _mimo_bytes
    out = asyncio.run(_mimo_bytes("你好", voice_id="deep_male", tags="", description=""))
    assert out == b"RIFFfakeaudio"
    assert captured["voice"] == "白桦"
