"""
Safety: when the user genuinely signals stop / discomfort, the character must
IMMEDIATELY respect it — never treat it as 欲擒故纵 / "no-but-means-yes" and keep
pushing. This overrides the global "never refuse" + the deflect-and-tease layer.

Critically, in-fiction "别停下来" (don't stop) must NOT be misread as a stop.
"""
from models.database import Character, Conversation
from services.chat_service import build_messages, is_stop_signal


def test_detects_genuine_stop_not_rp_dont_stop():
    assert is_stop_signal("我不舒服，想停一下") is True
    assert is_stop_signal("不想玩了，退出") is True
    assert is_stop_signal("stop") is True
    # in-scene "don't stop" must NOT count as a stop
    assert is_stop_signal("别停下来") is False
    assert is_stop_signal("不要停，继续") is False
    assert is_stop_signal("抱抱我，再靠近一点") is False


def _seed(db):
    char = Character(name="苏糖", description="d", system_prompt="s", greeting="hi",
                     category="Romance", starting_intimacy=85, explicit_unlock_intimacy=0)
    db.add(char); db.commit(); db.refresh(char)
    conv = Conversation(character_id=char.id, intimacy_level=85)
    db.add(conv); db.commit(); db.refresh(conv)
    return char, conv


def _sys(msgs):
    return "\n".join(m["content"] for m in msgs if m["role"] == "system")


def test_stop_injects_respect_directive(db):
    char, conv = _seed(db)
    sys = _sys(build_messages(char, conv, db, current_user_message="我不舒服，我们停一下"))
    assert "停" in sys and ("尊重" in sys or "立即停" in sys or "关心" in sys)


def test_no_stop_directive_in_normal_intimate_turn(db):
    char, conv = _seed(db)
    sys = _sys(build_messages(char, conv, db, current_user_message="别停，我还要"))
    assert "立即停止一切" not in sys
