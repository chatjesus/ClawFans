"""
Daily check-in reward — reciprocity + habit loop.

Coming back each day grants a small intimacy bump (the operator-tunable
`daily_checkin_intimacy_bonus`), once per calendar day. Emotionally: the
relationship visibly deepens just for showing up, so showing up becomes a
habit. Called from the chat /checkin endpoint when the user opens a chat.
"""
from sqlalchemy.orm import Session

from models.database import Conversation
from services.ops_config import get_ops_value


def grant_daily_checkin(conv: Conversation, db: Session, today: str) -> int:
    """Grant the daily intimacy bonus if it hasn't been claimed today.
    Returns the intimacy actually granted (0 if already claimed today).
    ``today`` is an ISO date string ("2026-06-01")."""
    if conv.last_checkin_date == today:
        return 0

    bonus = int(get_ops_value(db, "daily_checkin_intimacy_bonus", 2))
    if bonus <= 0:
        conv.last_checkin_date = today
        db.commit()
        return 0

    current = conv.intimacy_level or 0
    new_level = min(100, current + bonus)
    granted = new_level - current

    conv.intimacy_level = new_level
    conv.last_checkin_date = today
    db.commit()
    return granted
