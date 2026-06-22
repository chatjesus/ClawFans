"""
Story stress test — a full multi-turn playthrough must never freeze, at every
intimacy tier and across multiple characters.

The reported pain was a turn stuck on "…". At the pipeline level that = a turn's
SSE never reaching `done`. This drives a 20-turn story (chitchat → affection →
physical → image requests → callbacks) through the REAL SSE endpoint (LLM
stubbed by conftest, so fast + deterministic), parametrized over the five
intimacy tiers, and a shorter run across several characters. Every single turn
must emit content and `done`; intimacy must keep advancing.
"""
import json

import pytest

from models.database import Character, Conversation

# 20-turn escalating story (mixes chitchat, affection, physical, image-intent, callbacks)
STORY = [
    "你好呀", "你今天在做什么", "你叫什么名字", "我觉得你挺特别的",
    "看看你",                       # image-intent
    "你喜欢什么", "我也喜欢那个", "你会想我吗", "抱抱我",
    "给我看看你今天的样子",          # image-intent
    "我有点紧张", "你靠近一点", "你的手好暖", "再近一点",
    "拍张照给我",                   # image-intent
    "我好想你", "今晚别走", "就我们俩", "你真好看", "晚安",
]


def _auth(uid: str) -> dict:
    return {"Authorization": f"Bearer {uid}"}


def _seed(db, name="Hero") -> int:
    c = Character(name=name, system_prompt="p", greeting="hi", category="Featured")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c.id


def _conv(client, char_id, uid="alice") -> int:
    return client.post(
        "/api/chat/conversations", json={"character_id": char_id}, headers=_auth(uid)
    ).json()["id"]


def _turn(client, conv_id, msg, uid="alice") -> list[dict]:
    events: list[dict] = []
    with client.stream(
        "POST", f"/api/chat/conversations/{conv_id}/messages",
        json={"content": msg}, headers=_auth(uid),
    ) as r:
        assert r.status_code == 200, r.text
        for ln in r.iter_lines():
            if ln.startswith("data: "):
                events.append(json.loads(ln[6:]))
    return events


def _set_intimacy(db, conv_id, level):
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    conv.intimacy_level = level
    db.commit()


@pytest.mark.parametrize("start_intimacy", [0, 20, 40, 60, 80])
def test_20_turn_story_never_freezes_at_any_tier(client, db, monkeypatch, start_intimacy):
    monkeypatch.setattr(
        "api.chat.get_pregenerated_scenes",
        lambda cid: {0: "/uploads/scenes/x/scene_0.png"},
    )
    conv_id = _conv(client, _seed(db, f"Tier{start_intimacy}"))
    _set_intimacy(db, conv_id, start_intimacy)

    for i, msg in enumerate(STORY):
        events = _turn(client, conv_id, msg)
        assert any(e.get("done") for e in events), \
            f"tier={start_intimacy} turn {i} ('{msg}') never completed (frozen)"
        assert any("content" in e for e in events), \
            f"tier={start_intimacy} turn {i} ('{msg}') produced no content"

    db.expire_all()
    final = db.query(Conversation).filter(Conversation.id == conv_id).first().intimacy_level
    assert final >= start_intimacy, "intimacy regressed over the story"


def test_story_runs_across_multiple_characters(client, db):
    for name in ["Luna", "Jake", "Aria", "Marcus"]:
        conv_id = _conv(client, _seed(db, name))
        for i, msg in enumerate(STORY[:10]):
            events = _turn(client, conv_id, msg)
            assert any(e.get("done") for e in events), f"{name} turn {i} frozen"
            assert any("content" in e for e in events), f"{name} turn {i} empty"
