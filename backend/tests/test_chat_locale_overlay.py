"""
P0 regression test — locale handling must still work after we refactored
chat_service to re-fetch the character.

User-visible behavior: if I open a chat with ?locale=en and an English
translation exists, the LLM must be prompted in English (including the
"always reply in English" directive). If we accidentally lost the locale
overlay during refactoring, the bot starts replying in Chinese — the
single most damaging UX regression for a 15-language product.

We assert against the messages list that gets handed to the LLM, since
that IS the public contract between our backend and Ollama.
"""
from models.database import Character, CharacterTranslation


ORIGINAL_PROMPT = "原始系统提示词"
TRANSLATED_PROMPT = "Translated English system prompt"


def _seed_character_with_en_translation(db) -> int:
    char = Character(
        name="TestChar",
        description="desc",
        system_prompt=ORIGINAL_PROMPT,
        greeting="hi",
        category="Featured",
    )
    db.add(char)
    db.commit()
    db.refresh(char)
    tr = CharacterTranslation(
        character_id=char.id,
        locale="en",
        description="en desc",
        greeting="en hi",
        system_prompt=TRANSLATED_PROMPT,
    )
    db.add(tr)
    db.commit()
    return char.id


def test_locale_en_injects_translated_prompt_and_language_directive(client, db, monkeypatch):
    char_id = _seed_character_with_en_translation(db)

    captured: dict = {}

    async def capturing_stream(messages, **_kwargs):
        captured["messages"] = messages
        yield "ok"

    # Patch the binding chat_service actually uses.
    monkeypatch.setattr(
        "services.chat_service.chat_completion_stream", capturing_stream
    )

    r = client.post("/api/chat/conversations", json={"character_id": char_id})
    conv_id = r.json()["id"]

    with client.stream(
        "POST",
        f"/api/chat/conversations/{conv_id}/messages?locale=en",
        json={"content": "hello"},
    ) as resp:
        assert resp.status_code == 200
        for _ in resp.iter_lines():
            pass

    assert "messages" in captured, "LLM was never called"
    system_msg = captured["messages"][0]
    assert system_msg["role"] == "system"
    body = system_msg["content"]

    assert TRANSLATED_PROMPT in body, (
        f"Locale overlay was dropped — translated prompt not in system message.\n"
        f"--- system message ---\n{body[:1500]}"
    )
    assert "Always reply in English" in body, (
        "Language directive missing — bot will reply in original-language Chinese."
    )


def test_locale_en_does_not_persist_prompt_mutation(client, db):
    """Even when locale overlay is applied, the character row in the DB must
    stay unchanged — overlay is per-request, not a write-through."""
    char_id = _seed_character_with_en_translation(db)

    r = client.post("/api/chat/conversations", json={"character_id": char_id})
    conv_id = r.json()["id"]

    with client.stream(
        "POST",
        f"/api/chat/conversations/{conv_id}/messages?locale=en",
        json={"content": "hi"},
    ) as resp:
        for _ in resp.iter_lines():
            pass

    db.expire_all()
    after = db.query(Character).filter(Character.id == char_id).first()
    assert after.system_prompt == ORIGINAL_PROMPT, (
        f"Locale overlay leaked into the database. Got: {after.system_prompt!r}"
    )
