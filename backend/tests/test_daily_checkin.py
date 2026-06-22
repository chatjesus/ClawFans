"""
Daily check-in reward — a reciprocity/habit loop (deeply 符合人性): coming
back each day visibly deepens the bond. The amount is the operator-tunable
`daily_checkin_intimacy_bonus` lever; the reward fires once per calendar day.
"""
from models.database import Character, Conversation
from services.ops_config import set_ops_values


def _seed(db, intimacy=0, last_checkin=None):
    char = Character(name="C", system_prompt="p", greeting="hi", category="Featured")
    db.add(char)
    db.commit()
    db.refresh(char)
    conv = Conversation(
        character_id=char.id, title="t",
        intimacy_level=intimacy, last_checkin_date=last_checkin,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def test_first_checkin_of_day_grants_configured_bonus(db):
    from services.checkin import grant_daily_checkin
    conv = _seed(db, intimacy=10)
    set_ops_values(db, {"daily_checkin_intimacy_bonus": 3})

    bonus = grant_daily_checkin(conv, db, "2026-06-01")
    assert bonus == 3
    db.refresh(conv)
    assert conv.intimacy_level == 13
    assert conv.last_checkin_date == "2026-06-01"


def test_second_checkin_same_day_grants_nothing(db):
    from services.checkin import grant_daily_checkin
    conv = _seed(db, intimacy=10, last_checkin="2026-06-01")
    set_ops_values(db, {"daily_checkin_intimacy_bonus": 3})

    assert grant_daily_checkin(conv, db, "2026-06-01") == 0
    db.refresh(conv)
    assert conv.intimacy_level == 10  # unchanged


def test_next_day_checkin_grants_again(db):
    from services.checkin import grant_daily_checkin
    conv = _seed(db, intimacy=10, last_checkin="2026-06-01")
    set_ops_values(db, {"daily_checkin_intimacy_bonus": 2})

    assert grant_daily_checkin(conv, db, "2026-06-02") == 2
    db.refresh(conv)
    assert conv.intimacy_level == 12


def test_bonus_is_capped_at_100(db):
    from services.checkin import grant_daily_checkin
    conv = _seed(db, intimacy=99)
    set_ops_values(db, {"daily_checkin_intimacy_bonus": 5})

    grant_daily_checkin(conv, db, "2026-06-01")
    db.refresh(conv)
    assert conv.intimacy_level == 100
