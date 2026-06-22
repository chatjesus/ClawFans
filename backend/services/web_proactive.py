"""
Web proactive recall — the character reaches out FIRST to a web user who has
gone quiet, without waiting for them to reopen the chat.

Telegram already does this (services/proactive_service.py). Web only had the
on-open return greeting (services/proactive_greeting.py), which never fires if
the user never comes back. This stages a real assistant Message (flagged
is_proactive) in the conversation on a background scheduler tick, so it is
waiting in the thread next time they open — and the poll endpoint lets an
already-open tab surface it live.

Guardrails (also required by OPENCLAW_INTEGRATION_PLAN.md): per-conversation
opt-out, quiet hours, a minimum gap between proactive messages, one unanswered
proactive at a time, and it only fires on a conversation that has real history.
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from models.database import Character, Conversation, Message
from services.proactive_greeting import generate_return_greeting

# Reach out after this long quiet (mirrors Telegram's 24h first-touch).
TRIGGER_AFTER_HOURS = 24
# Never stage two proactive messages closer than this — caps at ~1/day.
MIN_PROACTIVE_GAP_HOURS = 20
# Local quiet hours [start, end): no proactive sends overnight. Wraps midnight.
QUIET_HOURS = (23, 7)


def in_quiet_hours(now: datetime, quiet: tuple[int, int] = QUIET_HOURS) -> bool:
    """True if ``now`` falls inside the quiet window. Handles windows that wrap
    midnight, e.g. (23, 7) means 23:00–06:59."""
    start, end = quiet
    h = now.hour
    if start <= end:
        return start <= h < end
    return h >= start or h < end


def should_stage_proactive(
    *,
    last_active_at: datetime | None,
    last_proactive_at: datetime | None,
    now: datetime,
    has_history: bool,
    proactive_enabled: bool,
    has_pending_proactive: bool,
    trigger_after_hours: float = TRIGGER_AFTER_HOURS,
    min_gap_hours: float = MIN_PROACTIVE_GAP_HOURS,
) -> bool:
    """Pure gate. Stage a proactive message only when every guardrail passes.

    Kept side-effect free so the policy is unit-testable without a DB or LLM."""
    if not proactive_enabled:
        return False
    if not has_history or last_active_at is None:
        return False
    if has_pending_proactive:
        return False
    if in_quiet_hours(now):
        return False
    if (now - last_active_at).total_seconds() < trigger_after_hours * 3600:
        return False
    if (
        last_proactive_at is not None
        and (now - last_proactive_at).total_seconds() < min_gap_hours * 3600
    ):
        return False
    return True


def _last_message(db: Session, conversation_id: int) -> Message | None:
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.id.desc())
        .first()
    )


async def stage_web_proactive_messages(db: Session | None = None, now: datetime | None = None) -> int:
    """Scan web conversations that have gone quiet and stage one proactive
    assistant message each. Returns the number staged.

    Safe to call on a tick: opens its own session if none is passed."""
    now = now or datetime.utcnow()

    # Whole batch shares one clock; if it's quiet hours, nothing goes out.
    if in_quiet_hours(now):
        return 0

    close = db is None
    if db is None:
        from models.database import SessionLocal
        db = SessionLocal()

    staged = 0
    try:
        cutoff = now - timedelta(hours=TRIGGER_AFTER_HOURS)
        candidates = (
            db.query(Conversation)
            .filter(
                Conversation.proactive_enabled == True,  # noqa: E712 — SQLite stores 1/0
                Conversation.last_active_at.isnot(None),
                Conversation.last_active_at <= cutoff,
            )
            .all()
        )

        for conv in candidates:
            last_msg = _last_message(db, conv.id)
            has_history = last_msg is not None
            # Don't keep nagging: skip if the newest message is an
            # un-replied-to proactive we already sent.
            has_pending = bool(
                last_msg
                and last_msg.role == "assistant"
                and getattr(last_msg, "is_proactive", False)
            )

            if not should_stage_proactive(
                last_active_at=conv.last_active_at,
                last_proactive_at=conv.last_proactive_at,
                now=now,
                has_history=has_history,
                proactive_enabled=bool(conv.proactive_enabled),
                has_pending_proactive=has_pending,
            ):
                continue

            character = (
                db.query(Character).filter(Character.id == conv.character_id).first()
            )
            if character is None:
                continue

            text = await generate_return_greeting(character, conv, db, now=now)
            if not text:
                continue

            db.add(
                Message(
                    conversation_id=conv.id,
                    role="assistant",
                    content=text,
                    is_proactive=True,
                    created_at=now,
                )
            )
            conv.last_proactive_at = now
            conv.updated_at = now  # surfaces a "new message" marker in the sidebar
            db.commit()
            staged += 1

        return staged
    finally:
        if close:
            db.close()
