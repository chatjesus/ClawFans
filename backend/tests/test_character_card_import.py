"""
Tests for Character Card Import (P0-2).

Covers the pure mapping function `card_to_character_fields` and the
`POST /api/characters/import` endpoint (auth, v2-wrapper + flat shapes,
ownership).
"""
import pytest

from services.character_card import card_to_character_fields
from models.database import Character


# ── Pure unit tests for card_to_character_fields ────────────────────────────

def test_card_to_character_fields_maps_v2_card():
    """A v2 card's data maps to name/greeting/system_prompt correctly."""
    card = {
        "name": "Aria",
        "description": "A cheerful bard with silver hair.",
        "personality": "Bubbly, witty, fiercely loyal.",
        "scenario": "You meet Aria at a tavern.",
        "first_mes": "Oh! A new face — come, sit by me!",
        "mes_example": "{{user}}: Hi\n{{char}}: Hello there, traveler!",
    }

    fields = card_to_character_fields(card)

    assert fields["name"] == "Aria"
    assert fields["greeting"] == "Oh! A new face — come, sit by me!"
    # system_prompt assembles labeled sections, non-empty
    assert fields["system_prompt"]
    assert "Bubbly, witty, fiercely loyal." in fields["system_prompt"]
    assert "A cheerful bard with silver hair." in fields["system_prompt"]
    assert "You meet Aria at a tavern." in fields["system_prompt"]
    assert "Hello there, traveler!" in fields["system_prompt"]
    # description truncates / falls back from card description
    assert fields["description"].startswith("A cheerful bard")


def test_card_to_character_fields_raises_without_name():
    """A card with no name raises ValueError."""
    with pytest.raises(ValueError):
        card_to_character_fields({"description": "no name here"})


def test_card_to_character_fields_greeting_fallback():
    """Missing first_mes falls back to a default greeting."""
    fields = card_to_character_fields({"name": "Nameless", "personality": "Quiet."})
    assert fields["greeting"] == "Hello!"


# ── Endpoint tests ───────────────────────────────────────────────────────────

VALID_V2_CARD = {
    "spec": "chara_card_v2",
    "data": {
        "name": "Aria",
        "description": "A cheerful bard with silver hair.",
        "personality": "Bubbly, witty, fiercely loyal.",
        "scenario": "You meet Aria at a tavern.",
        "first_mes": "Oh! A new face — come, sit by me!",
        "mes_example": "{{user}}: Hi\n{{char}}: Hello there, traveler!",
    },
}

VALID_FLAT_CARD = {
    "name": "Rex",
    "description": "A gruff mercenary.",
    "personality": "Blunt, dependable.",
    "scenario": "A smoky war room.",
    "first_mes": "State your business.",
    "mes_example": "{{user}}: Help\n{{char}}: Fine. Once.",
}


def test_import_anonymous_returns_401(client):
    """No Authorization header → 401."""
    resp = client.post("/api/characters/import", json=VALID_V2_CARD)
    assert resp.status_code == 401


def test_import_authed_v2_card_creates_owned_character(client, db):
    """Authed import of a v2 card → 201, name matches, owned by 'alice'."""
    resp = client.post(
        "/api/characters/import",
        json=VALID_V2_CARD,
        headers={"Authorization": "Bearer alice"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Aria"
    assert body["category"] == "Imported"
    assert body["is_public"] is True
    assert body["system_prompt"]
    assert body["greeting"] == "Oh! A new face — come, sit by me!"

    # Verify ownership via the DB.
    char = db.query(Character).filter(Character.id == body["id"]).first()
    assert char is not None
    assert char.clerk_creator_id == "alice"


def test_import_authed_flat_card_works(client, db):
    """The flat (non-wrapped) card shape also imports successfully."""
    resp = client.post(
        "/api/characters/import",
        json=VALID_FLAT_CARD,
        headers={"Authorization": "Bearer bob"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Rex"
    assert body["greeting"] == "State your business."

    char = db.query(Character).filter(Character.id == body["id"]).first()
    assert char is not None
    assert char.clerk_creator_id == "bob"


def test_import_missing_name_returns_400(client):
    """A card with no name → 400."""
    resp = client.post(
        "/api/characters/import",
        json={"data": {"description": "anonymous blob"}},
        headers={"Authorization": "Bearer alice"},
    )
    assert resp.status_code == 400
