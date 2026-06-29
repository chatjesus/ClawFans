"""
The model must not invent a shared past.

The quality review found {{char}} "remembering" things {{user}} never said.
build_messages injects retrieved memories under a "What ... Remembers" block;
that block must carry a guard telling the model those facts are the ONLY thing
it knows about {{user}} and that it must not fabricate others.
"""
from models.database import Character, Conversation, UserMemory
from services.chat_service import build_messages


def _seed_char_conv(db):
    char = Character(
        name="Luna",
        description="desc",
        system_prompt="You are Luna.",
        greeting="hi",
        category="Featured",
    )
    db.add(char)
    db.commit()
    db.refresh(char)
    conv = Conversation(character_id=char.id, user_id="alice")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return char, conv


def _system_text(messages):
    return next(m["content"] for m in messages if m["role"] == "system")


def test_memory_block_carries_no_fabrication_guard(db):
    char, conv = _seed_char_conv(db)
    db.add(UserMemory(user_id="alice", character_id=char.id,
                      key="job", value="设计师", confidence=0.9))
    db.commit()

    msgs = build_messages(char, conv, db, user_id="alice")
    sys = _system_text(msgs)

    # the real memory is present...
    assert "设计师" in sys
    # ...and it is fenced with a no-invention guard
    assert "不要" in sys and ("编造" in sys or "捏造" in sys or "虚构" in sys)


def test_no_memory_block_when_user_anonymous(db):
    char, conv = _seed_char_conv(db)
    msgs = build_messages(char, conv, db, user_id="anonymous")
    sys = _system_text(msgs)
    # anonymous users have no memory block at all
    assert "Remembers" not in sys
