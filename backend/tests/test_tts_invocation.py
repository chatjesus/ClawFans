"""
Voice generation is silently dead.

chat.send_message does `result.display_reply or result.full_reply`, but
StreamResult has no `display_reply` attribute, so the very first access
raises AttributeError. It's swallowed by the surrounding try/except and
logged as a "TTS error" — meaning synthesize_speech is NEVER called and
the voice feature never works for anyone.

Contract: after an assistant reply streams, TTS is invoked with that reply.
"""
from models.database import Character


def _auth(uid: str) -> dict:
    return {"Authorization": f"Bearer {uid}"}


def _seed_character(db) -> int:
    char = Character(
        name="C", description="", system_prompt="p", greeting="hi", category="Featured"
    )
    db.add(char)
    db.commit()
    db.refresh(char)
    return char.id


def test_tts_is_invoked_with_reply_text(client, db, monkeypatch):
    calls: list[str] = []

    async def recording_tts(text, **_kwargs):
        calls.append(text)
        return None

    monkeypatch.setattr("services.voice_service.synthesize_speech", recording_tts)

    char_id = _seed_character(db)
    conv_id = client.post(
        "/api/chat/conversations", json={"character_id": char_id}, headers=_auth("alice")
    ).json()["id"]

    with client.stream(
        "POST",
        f"/api/chat/conversations/{conv_id}/messages",
        json={"content": "say hi"},
        headers=_auth("alice"),
    ) as resp:
        for _ in resp.iter_lines():
            pass

    assert calls, "synthesize_speech was never called — voice generation is dead"
    assert calls[0].strip(), "TTS was called with empty text"
