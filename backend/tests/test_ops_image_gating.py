"""
The NSFW-image ops-config levers must gate on-the-fly [IMG:] generation:

  • nsfw_images_enabled  — operator master switch; False = no generation at all.
  • nsfw_unlock_intimacy — intimacy threshold that flips the explicit (nsfw=True) flag.
  • vip_only_explicit    — paywall hook; True forces non-explicit regardless of intimacy.

These exercise the real ``process_reply_images`` code path with ``generate_image``
stubbed so no ComfyUI/Gemini call ever happens.
"""
import pytest

from models.database import Character, Conversation
from services.ops_config import set_ops_values
import services.chat_service as chat_service


def _seed_conv(db, intimacy=0):
    char = Character(name="C", system_prompt="p", greeting="hi", category="Featured")
    db.add(char)
    db.commit()
    db.refresh(char)
    conv = Conversation(character_id=char.id, title="t", intimacy_level=intimacy)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return char, conv


def _stub_generate_image(monkeypatch):
    """Replace chat_service.generate_image with a recorder. Returns the call log."""
    calls = []

    async def fake_generate_image(prompt, *args, **kwargs):
        calls.append({"prompt": prompt, "args": args, "kwargs": kwargs})
        return "/uploads/generated/fake.png"

    monkeypatch.setattr(chat_service, "generate_image", fake_generate_image)
    return calls


@pytest.mark.asyncio
async def test_master_switch_off_skips_all_img_generation(db, monkeypatch):
    """nsfw_images_enabled=False → no [IMG:] generation, generate_image untouched."""
    calls = _stub_generate_image(monkeypatch)
    char, conv = _seed_conv(db, intimacy=50)
    set_ops_values(db, {"nsfw_images_enabled": False})

    reply = "Here you go *smiles* [IMG: a cozy bedroom selfie]"
    instant, generated = await chat_service.process_reply_images(
        reply, conv.id, char.id, avatar_url=None, db=db, intimacy_level=50
    )

    assert generated == []
    assert calls == []


@pytest.mark.asyncio
async def test_defaults_do_generate_img(db, monkeypatch):
    """With defaults, an [IMG:] reply generates exactly one image."""
    calls = _stub_generate_image(monkeypatch)
    char, conv = _seed_conv(db, intimacy=50)

    reply = "Here you go *smiles* [IMG: a cozy bedroom selfie]"
    instant, generated = await chat_service.process_reply_images(
        reply, conv.id, char.id, avatar_url=None, db=db, intimacy_level=50
    )

    assert len(generated) == 1
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_unlock_intimacy_low_threshold_passes_nsfw_true(db, monkeypatch):
    """nsfw_unlock_intimacy=10 with intimacy 20 → explicit (nsfw=True)."""
    calls = _stub_generate_image(monkeypatch)
    char, conv = _seed_conv(db, intimacy=20)
    set_ops_values(db, {"nsfw_unlock_intimacy": 10})

    reply = "*leans in* [IMG: a sultry pose]"
    await chat_service.process_reply_images(
        reply, conv.id, char.id, avatar_url=None, db=db, intimacy_level=20
    )

    assert len(calls) == 1
    assert calls[0]["kwargs"]["nsfw"] is True


@pytest.mark.asyncio
async def test_unlock_intimacy_high_threshold_passes_nsfw_false(db, monkeypatch):
    """nsfw_unlock_intimacy=90 with intimacy 20 → non-explicit (nsfw=False)."""
    calls = _stub_generate_image(monkeypatch)
    char, conv = _seed_conv(db, intimacy=20)
    set_ops_values(db, {"nsfw_unlock_intimacy": 90})

    reply = "*leans in* [IMG: a sultry pose]"
    await chat_service.process_reply_images(
        reply, conv.id, char.id, avatar_url=None, db=db, intimacy_level=20
    )

    assert len(calls) == 1
    assert calls[0]["kwargs"]["nsfw"] is False


@pytest.mark.asyncio
async def test_vip_only_explicit_forces_nsfw_false(db, monkeypatch):
    """vip_only_explicit=True forces non-explicit even above the unlock threshold."""
    calls = _stub_generate_image(monkeypatch)
    char, conv = _seed_conv(db, intimacy=80)
    set_ops_values(db, {"vip_only_explicit": True})

    reply = "*leans in* [IMG: a sultry pose]"
    await chat_service.process_reply_images(
        reply, conv.id, char.id, avatar_url=None, db=db, intimacy_level=80
    )

    assert len(calls) == 1
    assert calls[0]["kwargs"]["nsfw"] is False
