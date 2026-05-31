"""
P0-2 — write endpoints must require authentication.

Currently anyone (no Authorization header, no token) can create / update /
delete characters and other people's conversations. This file pins down
the *minimum* auth contract; ownership tests come next.
"""
import pytest


VALID_CHARACTER_PAYLOAD = {
    "name": "Hacker McSpoof",
    "description": "",
    "system_prompt": "x",
    "greeting": "",
    "avatar_url": "",
    "tags": "",
    "category": "Featured",
    "is_public": True,
}


def test_anonymous_cannot_create_character(client):
    r = client.post("/api/characters/", json=VALID_CHARACTER_PAYLOAD)
    assert r.status_code == 401, (
        f"Anonymous request created a character (status {r.status_code}). "
        f"Auth is required."
    )


def _seed_char(db, name="Existing") -> int:
    from models.database import Character
    char = Character(name=name, system_prompt="x", category="Featured")
    db.add(char)
    db.commit()
    db.refresh(char)
    return char.id


def test_anonymous_cannot_update_character(client, db):
    char_id = _seed_char(db)
    r = client.put(f"/api/characters/{char_id}", json={"name": "hijacked"})
    assert r.status_code == 401, r.text


def test_anonymous_cannot_delete_character(client, db):
    char_id = _seed_char(db)
    r = client.delete(f"/api/characters/{char_id}")
    assert r.status_code == 401, r.text


def test_anonymous_cannot_upsert_translation(client, db):
    char_id = _seed_char(db)
    r = client.put(
        f"/api/characters/{char_id}/translations",
        json={"locale": "en", "description": "x"},
    )
    assert r.status_code == 401, r.text


# ── Ownership: a user can only edit their own characters ─────────────────


def _bearer(user_id: str) -> dict:
    return {"Authorization": f"Bearer {user_id}"}


def test_authed_user_can_create_and_own_character(client):
    r = client.post("/api/characters/", json=VALID_CHARACTER_PAYLOAD, headers=_bearer("alice"))
    assert r.status_code == 201, r.text
    char_id = r.json()["id"]

    # Same user can update their own
    r2 = client.put(f"/api/characters/{char_id}", json={"name": "Alice's revised"}, headers=_bearer("alice"))
    assert r2.status_code == 200, r2.text
    assert r2.json()["name"] == "Alice's revised"


def test_user_cannot_update_another_users_character(client):
    # Alice creates
    r = client.post("/api/characters/", json=VALID_CHARACTER_PAYLOAD, headers=_bearer("alice"))
    char_id = r.json()["id"]

    # Bob tries to update Alice's character — must be denied
    r2 = client.put(
        f"/api/characters/{char_id}",
        json={"name": "Bob's takeover"},
        headers=_bearer("bob"),
    )
    assert r2.status_code == 403, r2.text


def test_user_cannot_delete_another_users_character(client):
    r = client.post("/api/characters/", json=VALID_CHARACTER_PAYLOAD, headers=_bearer("alice"))
    char_id = r.json()["id"]

    r2 = client.delete(f"/api/characters/{char_id}", headers=_bearer("bob"))
    assert r2.status_code == 403, r2.text


# ── Conversation ownership ───────────────────────────────────────────────


def _alice_char_and_conv(client) -> tuple[int, int]:
    r = client.post("/api/characters/", json=VALID_CHARACTER_PAYLOAD, headers=_bearer("alice"))
    char_id = r.json()["id"]
    r = client.post(
        "/api/chat/conversations",
        json={"character_id": char_id},
        headers=_bearer("alice"),
    )
    return char_id, r.json()["id"]


def test_user_cannot_read_another_users_conversation(client):
    _char_id, conv_id = _alice_char_and_conv(client)

    r = client.get(f"/api/chat/conversations/{conv_id}", headers=_bearer("bob"))
    assert r.status_code in (403, 404), (
        f"Bob read Alice's conversation (status {r.status_code})."
    )


def test_user_cannot_delete_another_users_conversation(client):
    _char_id, conv_id = _alice_char_and_conv(client)

    r = client.delete(f"/api/chat/conversations/{conv_id}", headers=_bearer("bob"))
    assert r.status_code in (403, 404), (
        f"Bob deleted Alice's conversation (status {r.status_code})."
    )


def test_authed_user_cannot_edit_ownerless_character(client, db):
    """Seed / legacy characters have no clerk_creator_id. They must be
    treated as system-owned and immutable via the API — otherwise any
    logged-in user could rewrite Luna's prompt."""
    char_id = _seed_char(db, name="SystemSeed")  # no clerk_creator_id

    r = client.put(
        f"/api/characters/{char_id}",
        json={"name": "defaced"},
        headers=_bearer("randouser"),
    )
    assert r.status_code == 403, (
        f"An authed user edited an ownerless system character (status {r.status_code})."
    )


def test_user_cannot_read_another_users_messages(client):
    _char_id, conv_id = _alice_char_and_conv(client)

    r = client.get(
        f"/api/chat/conversations/{conv_id}/messages", headers=_bearer("bob")
    )
    assert r.status_code in (403, 404), (
        f"Bob read messages of Alice's conversation (status {r.status_code})."
    )
