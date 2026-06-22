"""
Full-conversation playthrough + scene gameplay (catches the "卡死/frozen" class).

The reported symptom: a chat turn shows "…" forever. At the pipeline level that
means a turn's SSE stream never emits `done`. These integration tests run a
multi-turn story, an image-intent turn, and several characters through the REAL
SSE endpoint (LLM stubbed by conftest, so fast + deterministic) and assert every
turn COMPLETES — i.e. emits content and a final `done`, never hanging.

(Live "卡死" with the 30B model is latency/VRAM-reload, not a logic hang — these
lock the logic so a real deadlock/regression would be caught here.)
"""
import json

from models.database import Character


def _auth(uid: str) -> dict:
    return {"Authorization": f"Bearer {uid}"}


def _seed_char(db, name="C") -> int:
    c = Character(name=name, system_prompt="p", greeting="hi", category="Featured")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c.id


def _new_conv(client, char_id, uid="alice") -> int:
    return client.post(
        "/api/chat/conversations", json={"character_id": char_id}, headers=_auth(uid)
    ).json()["id"]


def _send(client, conv_id, content, uid="alice") -> list[dict]:
    events: list[dict] = []
    with client.stream(
        "POST", f"/api/chat/conversations/{conv_id}/messages",
        json={"content": content}, headers=_auth(uid),
    ) as r:
        assert r.status_code == 200, r.text
        for ln in r.iter_lines():
            if ln.startswith("data: "):
                events.append(json.loads(ln[6:]))
    return events


def test_full_story_completes_every_turn(client, db):
    """A multi-turn conversation must finish every turn — no frozen '…'."""
    conv = _new_conv(client, _seed_char(db))
    story = ["你好", "今天过得怎么样", "我有点想你", "看看你", "晚安"]
    for turn in story:
        events = _send(client, conv, turn)
        assert any(e.get("done") for e in events), f"turn '{turn}' never reached done (frozen)"
        assert any("content" in e for e in events), f"turn '{turn}' produced no content"


def test_image_intent_turn_emits_scene_and_completes(client, db, monkeypatch):
    """A 'show me' turn surfaces a pre-generated scene image and still completes."""
    monkeypatch.setattr(
        "api.chat.get_pregenerated_scenes",
        lambda cid: {0: "/uploads/scenes/x/scene_0.png"},
    )
    conv = _new_conv(client, _seed_char(db))
    events = _send(client, conv, "看看你")
    assert any("image" in e for e in events), "image-intent turn emitted no scene image"
    assert any(e.get("done") for e in events)


def test_multiple_characters_each_reply(client, db):
    """Every character can be opened and replies — not just the first."""
    for i in range(4):
        conv = _new_conv(client, _seed_char(db, f"Char{i}"))
        events = _send(client, conv, "你好")
        assert any(e.get("done") for e in events), f"Char{i} never completed"
        assert any("content" in e for e in events), f"Char{i} no content"
