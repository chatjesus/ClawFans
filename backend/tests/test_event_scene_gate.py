"""
Story events must not interrupt an active intimate/explicit scene.

Events were triggered purely by intimacy/message-count, ignoring what the user
was actually doing — so a canned "深夜emo求陪伴" event popped up mid-explicit
scene, feeling disconnected. check_events now defers when the latest user
message signals an intimate/sexual moment, firing only at conversational lulls.
"""
import json

from models.database import Character, Conversation, CharacterEvent, Message
from services.event_service import check_events


def _setup(db, last_user_text):
    char = Character(name="苏糖", description="d", system_prompt="s",
                     greeting="hi", category="Romance")
    db.add(char); db.commit(); db.refresh(char)
    db.add(CharacterEvent(
        char_id=char.id, title="深夜的勇气", description="深夜emo场景",
        trigger_json=json.dumps({"type": "intimacy_gte", "value": 0}),
        choices_json=json.dumps([{"text": "我在这儿", "intimacy_delta": 1}]),
    ))
    db.commit()
    conv = Conversation(character_id=char.id, intimacy_level=80)
    db.add(conv); db.commit(); db.refresh(conv)
    db.add(Message(conversation_id=conv.id, role="user", content=last_user_text))
    db.commit()
    return char, conv


def test_event_fires_at_a_conversational_lull(db):
    char, conv = _setup(db, "你好啊，今天过得怎么样？")
    assert check_events(conv, char, db) is not None  # benign → event may fire


def test_event_deferred_during_intimate_scene(db):
    char, conv = _setup(db, "抱抱你，我现在就想要你")
    assert check_events(conv, char, db) is None  # hot scene → event deferred
