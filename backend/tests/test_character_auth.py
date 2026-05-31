"""
P0-2 — character write protection.

Creating, editing, deleting characters (and editing translations) must
require auth, and edits/deletes are creator-only. Seed/system characters
(clerk_creator_id IS NULL) are editable by nobody through the API.

bearer token == user id (see conftest).
"""
from models.database import Character


def _auth(uid: str) -> dict:
    return {"Authorization": f"Bearer {uid}"}


def _new_char_payload(name="Mine") -> dict:
    return {
        "name": name,
        "description": "d",
        "system_prompt": "p",
        "greeting": "hi",
        "avatar_url": "",
        "tags": "",
        "category": "Featured",
        "is_public": True,
    }


def _seed_system_character(db) -> int:
    """A seed character has no clerk_creator_id."""
    char = Character(name="Seed", system_prompt="p", greeting="hi", category="Featured")
    db.add(char)
    db.commit()
    db.refresh(char)
    return char.id


def test_anonymous_cannot_create_character(client):
    r = client.post("/api/characters/", json=_new_char_payload())
    assert r.status_code == 401, r.text


def test_authenticated_user_can_create_character(client):
    r = client.post("/api/characters/", json=_new_char_payload(), headers=_auth("alice"))
    assert r.status_code == 201, r.text


def test_anonymous_cannot_delete_character(client, db):
    char_id = _seed_system_character(db)
    r = client.delete(f"/api/characters/{char_id}")
    assert r.status_code == 401, r.text


def test_non_creator_cannot_delete_character(client):
    # Alice creates a character.
    r = client.post("/api/characters/", json=_new_char_payload(), headers=_auth("alice"))
    char_id = r.json()["id"]

    # Bob tries to delete it.
    r_bob = client.delete(f"/api/characters/{char_id}", headers=_auth("bob"))
    assert r_bob.status_code == 403, r_bob.text


def test_creator_can_update_own_character(client):
    r = client.post("/api/characters/", json=_new_char_payload(), headers=_auth("alice"))
    char_id = r.json()["id"]

    r_upd = client.put(
        f"/api/characters/{char_id}",
        json={"description": "updated"},
        headers=_auth("alice"),
    )
    assert r_upd.status_code == 200, r_upd.text
    assert r_upd.json()["description"] == "updated"


def test_system_character_cannot_be_edited_by_anyone(client, db):
    char_id = _seed_system_character(db)
    r = client.put(
        f"/api/characters/{char_id}",
        json={"description": "hijacked"},
        headers=_auth("alice"),
    )
    assert r.status_code == 403, r.text
