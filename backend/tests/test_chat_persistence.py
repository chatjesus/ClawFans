"""
P0 regression test — chat side effects must persist to the database.

Observed in production (clawfans.db): every conversation has
intimacy_level=0, streak_days=0, last_chat_date=None, despite having
many real messages. Root cause: chat_service mutates the `character`
and `conversation` ORM objects that were loaded in the request handler's
sync scope, but by the time the StreamingResponse runs them, FastAPI has
already torn down the `Depends(get_db)` session — leaving those objects
detached. New rows still INSERT, but UPDATEs on those detached objects
are silently dropped.

These tests describe the user-facing behavior — they say nothing about
HOW the fix works, only that intimacy, streak and message_count survive
across requests.
"""
from sqlalchemy import text

from models.database import Character, Conversation


def _seed_character(db) -> int:
    char = Character(
        name="TestChar",
        description="desc",
        system_prompt="You are a test character.",
        greeting="hi",
        category="Featured",
    )
    db.add(char)
    db.commit()
    db.refresh(char)
    return char.id


def _start_conversation(client, char_id: int) -> int:
    r = client.post("/api/chat/conversations", json={"character_id": char_id})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _send(client, conv_id: int, content: str = "hello") -> None:
    with client.stream(
        "POST",
        f"/api/chat/conversations/{conv_id}/messages",
        json={"content": content},
    ) as resp:
        assert resp.status_code == 200, resp.text
        for _ in resp.iter_lines():
            pass


def _read_conv(db, conv_id: int):
    with db.get_bind().connect() as conn:
        return conn.execute(
            text(
                "SELECT intimacy_level, streak_days, last_chat_date "
                "FROM conversations WHERE id = :id"
            ),
            {"id": conv_id},
        ).first()


def test_intimacy_level_persists_after_one_message(client, db):
    char_id = _seed_character(db)
    conv_id = _start_conversation(client, char_id)

    _send(client, conv_id, "hello")

    row = _read_conv(db, conv_id)
    assert row.intimacy_level > 0, (
        f"intimacy_level was not persisted (got {row.intimacy_level}). "
        f"chat_service mutated the conversation in memory but the change "
        f"never reached the database."
    )


def test_streak_first_message_sets_last_chat_date(client, db):
    char_id = _seed_character(db)
    conv_id = _start_conversation(client, char_id)

    _send(client, conv_id, "hi")

    row = _read_conv(db, conv_id)
    assert row.streak_days == 1, f"streak_days should be 1, got {row.streak_days}"
    assert row.last_chat_date is not None, "last_chat_date should be set on first message"


def test_character_message_count_increments(client, db):
    char_id = _seed_character(db)
    conv_id = _start_conversation(client, char_id)

    with db.get_bind().connect() as conn:
        before = conn.execute(
            text("SELECT message_count FROM characters WHERE id = :id"), {"id": char_id}
        ).scalar()

    _send(client, conv_id, "hi")

    with db.get_bind().connect() as conn:
        after = conn.execute(
            text("SELECT message_count FROM characters WHERE id = :id"), {"id": char_id}
        ).scalar()

    assert after > before, (
        f"character.message_count did not increase ({before} -> {after}). "
        f"chat_service does `character.message_count += 2` on a detached object."
    )
