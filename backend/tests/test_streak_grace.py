"""
Streak should not punish irregular users (one missed day = grace, not reset),
and milestone copy must not guilt-trip lonely users with loss/abandonment framing
("失去/失落/被抛弃"). Warmth via cherishing shared time, not fear of loss.
"""
from datetime import date, timedelta

from models.database import Character, Conversation
from services.streak_service import update_streak, STREAK_MILESTONES


def _conv(db, streak, days_ago):
    char = Character(name="x", description="d", system_prompt="s", greeting="h", category="Romance")
    db.add(char); db.commit(); db.refresh(char)
    conv = Conversation(character_id=char.id, streak_days=streak,
                        last_chat_date=(date.today() - timedelta(days=days_ago)).isoformat())
    db.add(conv); db.commit(); db.refresh(conv)
    return conv


def test_consecutive_day_increments(db):
    r = update_streak(_conv(db, 5, 1), db)
    assert r["streak_days"] == 6 and not r["broken"]


def test_one_missed_day_is_graced_not_reset(db):
    r = update_streak(_conv(db, 5, 2), db)  # missed exactly one day
    assert r["streak_days"] == 5 and not r["broken"]  # preserved, not punished


def test_long_gap_resets(db):
    r = update_streak(_conv(db, 5, 4), db)  # 4-day gap
    assert r["streak_days"] == 1 and r["broken"]


def test_milestone_copy_has_no_guilt_framing():
    for days, m in STREAK_MILESTONES.items():
        notice = m["char_notice"]
        for bad in ("失去", "失落", "抛弃"):
            assert bad not in notice, f"milestone {days} guilt-trips with '{bad}'"
