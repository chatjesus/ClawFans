"""
Anonymous users must NOT see (or get handed) another user's conversations.

Regression for a live bug: list_conversations returned ALL conversations to
anonymous callers, so the chat UI reused a logged-in user's stale conversation
as "most recent" and then 403'd on send (surfaced as "Conversation not found").
Anonymous must see ONLY anonymous (clerk_user_id IS NULL) conversations.
"""
from models.database import Character


def _seed_char(db) -> int:
    char = Character(name="苏糖", description="d", system_prompt="s",
                     greeting="hi", category="Romance")
    db.add(char); db.commit(); db.refresh(char)
    return char.id


def test_anonymous_lists_only_anonymous_conversations(client, db):
    cid = _seed_char(db)
    # anonymous-owned conversation (no Authorization header)
    anon_id = client.post("/api/chat/conversations", json={"character_id": cid}).json()["id"]
    # a logged-in user's conversation (bearer token == user id via test stub)
    bob_id = client.post("/api/chat/conversations", json={"character_id": cid},
                         headers={"Authorization": "Bearer bob"}).json()["id"]

    # anonymous caller lists conversations for this character
    listed = client.get(f"/api/chat/conversations?character_id={cid}").json()
    ids = [c["id"] for c in listed]

    assert anon_id in ids, "anonymous must see its own conversation"
    assert bob_id not in ids, "anonymous must NOT see a logged-in user's conversation"


def test_logged_in_user_still_sees_own_and_anonymous(client, db):
    cid = _seed_char(db)
    anon_id = client.post("/api/chat/conversations", json={"character_id": cid}).json()["id"]
    bob_id = client.post("/api/chat/conversations", json={"character_id": cid},
                         headers={"Authorization": "Bearer bob"}).json()["id"]

    listed = client.get(f"/api/chat/conversations?character_id={cid}",
                        headers={"Authorization": "Bearer bob"}).json()
    ids = [c["id"] for c in listed]
    assert bob_id in ids and anon_id in ids  # own + anonymous both visible
