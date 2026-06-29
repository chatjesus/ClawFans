"""
A real person's mood persists and shifts from interactions — it shouldn't be
re-rolled from the clock every turn. Conversation.current_mood is derived from
the exchange and injected into the prompt so emotional state carries forward.
"""
from models.database import Character, Conversation
from services.intimacy_service import derive_mood
from services.chat_service import build_messages


def test_derive_mood_shifts_with_interaction():
    # negative interaction cools the mood; affection warms it
    neg = derive_mood("你真讨厌，烦死了", prev_mood="开心")
    assert "低落" in neg or "受伤" in neg
    aff = derive_mood("我好喜欢你呀", prev_mood="平静")
    assert "开心" in aff or "甜" in aff


def test_derive_mood_carries_forward_when_neutral():
    assert derive_mood("今天天气不错啊", prev_mood="有点吃醋") == "有点吃醋"


def _seed(db):
    char = Character(name="苏糖", description="d", system_prompt="s", greeting="h", category="Romance")
    db.add(char); db.commit(); db.refresh(char)
    conv = Conversation(character_id=char.id, intimacy_level=50, current_mood="有点吃醋")
    db.add(conv); db.commit(); db.refresh(conv)
    return char, conv


def test_build_messages_injects_persisted_mood(db):
    char, conv = _seed(db)
    sys = "\n".join(m["content"] for m in build_messages(char, conv, db) if m["role"] == "system")
    assert "吃醋" in sys and "心情" in sys
