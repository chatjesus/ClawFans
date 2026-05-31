"""
P0-2 — conversation privacy.

A conversation owned by one user must not be readable, sendable-to, or
deletable by another user. Anonymous conversations (clerk_user_id IS NULL)
intentionally stay open — that's the logged-out demo fallback.

Cross-user access returns 403 (the project's chosen convention — see
chat._ensure_conv_visible).

The conftest `client` stubs Clerk verification so the bearer token IS the
user id: `Authorization: Bearer alice` => user_id "alice".
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


def _create_conv(client, char_id: int, uid: str | None) -> int:
    headers = _auth(uid) if uid else {}
    r = client.post(
        "/api/chat/conversations", json={"character_id": char_id}, headers=headers
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_other_user_cannot_read_my_conversation(client, db):
    char_id = _seed_character(db)
    conv_id = _create_conv(client, char_id, "alice")

    r_bob = client.get(f"/api/chat/conversations/{conv_id}", headers=_auth("bob"))
    assert r_bob.status_code == 403, (
        f"Bob read Alice's conversation (status {r_bob.status_code})"
    )

    r_alice = client.get(f"/api/chat/conversations/{conv_id}", headers=_auth("alice"))
    assert r_alice.status_code == 200, r_alice.text


def test_other_user_cannot_delete_my_conversation(client, db):
    char_id = _seed_character(db)
    conv_id = _create_conv(client, char_id, "alice")

    r_bob = client.delete(f"/api/chat/conversations/{conv_id}", headers=_auth("bob"))
    assert r_bob.status_code == 403

    # Conversation still exists for Alice.
    r_alice = client.get(f"/api/chat/conversations/{conv_id}", headers=_auth("alice"))
    assert r_alice.status_code == 200


def test_other_user_cannot_send_to_my_conversation(client, db):
    """The gap: send_message had no ownership check, so anyone could inject
    messages into another user's private chat (and trigger LLM billing)."""
    char_id = _seed_character(db)
    conv_id = _create_conv(client, char_id, "alice")

    with client.stream(
        "POST",
        f"/api/chat/conversations/{conv_id}/messages",
        json={"content": "intrusion"},
        headers=_auth("bob"),
    ) as resp:
        body = "".join(resp.iter_lines()) if resp.status_code == 200 else resp.read().decode()

    assert resp.status_code == 403, (
        f"Bob sent a message into Alice's conversation (status {resp.status_code}). "
        f"body={body[:200]}"
    )


def test_anonymous_conversation_is_shared(client, db):
    """No-auth fallback: a conversation with no owner is readable by anyone."""
    char_id = _seed_character(db)
    conv_id = _create_conv(client, char_id, None)  # anonymous

    r = client.get(f"/api/chat/conversations/{conv_id}", headers=_auth("whoever"))
    assert r.status_code == 200, r.text
