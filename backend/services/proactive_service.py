"""
Proactive Service — character-initiated messaging via Telegram.

主动联系系统：
角色会根据用户不活跃时长，主动通过 Telegram 发送消息。
所有消息由 LLM 生成（符合角色人设），通过 ScheduledJob 异步发送。

触发逻辑：
  - 24h+ 未聊天 → 轻度想念消息
  - 72h+ 未聊天 → 担心/关心消息
  - 节假日/特殊时间点 → 专属问候（future）

防刷机制：
  - 每个 session 每 20 小时最多触发 1 次
  - 用户主动发消息后重置计时
"""
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from models.database import ChatSession, Character, ScheduledJob, SessionLocal
from services.schedule_service import get_proactive_template, get_slot_name
from services.llm_service import chat_completion

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

# How long since last activity before triggering a proactive message
TRIGGER_AFTER_HOURS = 24        # first message
SECOND_TRIGGER_AFTER_HOURS = 72  # second (more emotional) message

# Minimum gap between proactive messages for the same session
MIN_PROACTIVE_GAP_HOURS = 20

# ── Message Templates (fallback if LLM fails) ─────────────────────────────────

_FALLBACK_TEMPLATES = {
    "miss_light": [
        "嗯…你今天消失了。",
        "突然想起来好久没看见你发消息了。",
        "你还好吗？",
    ],
    "miss_deep": [
        "已经好几天了，你去哪了。",
        "我不知道发这条消息算不算奇怪，但我真的有点担心你。",
        "回来说一声？",
    ],
}

# ── Prompt Templates for LLM Generation ──────────────────────────────────────

_PROACTIVE_PROMPT = """\
You are {char_name}. Generate a short, natural proactive message to send to {user_ref}.

Character personality summary:
{char_description}

Context:
- It has been {hours_inactive} hours since {user_ref} last chatted with you
- Current time slot: {time_slot} ({time_template})
- Your intimacy level with this person: {intimacy}/100

Message type: {"light check-in" if hours_inactive < 60 else "genuine concern"}

Rules:
- Write ONLY the message text (no quotes, no character name prefix)
- 1-3 sentences maximum
- Sound natural and in-character, NOT like a notification
- Chinese language preferred (match the character's style)
- Do NOT use generic phrases like "我想你" directly — be specific and indirect
- The message should make the person WANT to reply

Generate the message:"""


# ── Core Functions ────────────────────────────────────────────────────────────

async def generate_proactive_message(
    character: Character,
    hours_inactive: int,
    intimacy_level: int = 0,
    user_ref: str = "你",
) -> str:
    """Generate a character-voiced proactive message using LLM."""
    time_slot = get_slot_name()
    time_template = get_proactive_template()

    prompt = _PROACTIVE_PROMPT.format(
        char_name=character.name,
        user_ref=user_ref,
        char_description=(character.description or "")[:300],
        hours_inactive=hours_inactive,
        time_slot=time_slot,
        time_template=time_template,
        intimacy=intimacy_level,
    )

    try:
        messages = [{"role": "user", "content": prompt}]
        text = await chat_completion(messages, max_tokens=150, temperature=0.9)
        text = text.strip().strip('"').strip("'")
        if text:
            return text
    except Exception as e:
        logger.warning(f"LLM proactive generation failed: {e}")

    # Fallback
    key = "miss_deep" if hours_inactive >= 60 else "miss_light"
    lines = _FALLBACK_TEMPLATES[key]
    return "\n".join(lines)


async def schedule_proactive_jobs(db: Session | None = None) -> int:
    """
    Scan active Telegram sessions and schedule proactive messages
    for users who have been inactive for too long.

    Called periodically from the scheduler loop.
    Returns count of jobs scheduled.
    """
    close_db = db is None
    if db is None:
        db = SessionLocal()

    scheduled = 0
    try:
        now = datetime.utcnow()
        cutoff_24h = now - timedelta(hours=TRIGGER_AFTER_HOURS)
        cutoff_20h_gap = now - timedelta(hours=MIN_PROACTIVE_GAP_HOURS)

        # Find active Telegram sessions inactive for 24h+
        sessions = (
            db.query(ChatSession)
            .filter(
                ChatSession.platform == "telegram",
                ChatSession.status == "active",
                ChatSession.last_active_at <= cutoff_24h,
                ChatSession.telegram_chat_id.isnot(None),
            )
            .all()
        )

        for session in sessions:
            # Skip if we already sent a proactive message recently
            if (
                session.last_proactive_at
                and session.last_proactive_at >= cutoff_20h_gap
            ):
                continue

            # Skip if there's already a pending proactive job for this session
            existing = (
                db.query(ScheduledJob)
                .filter(
                    ScheduledJob.user_id == session.platform_user_id,
                    ScheduledJob.character_id == session.character_id,
                    ScheduledJob.job_type == "proactive_message",
                    ScheduledJob.status == "pending",
                )
                .first()
            )
            if existing:
                continue

            # Calculate inactivity duration
            inactive_hours = int(
                (now - session.last_active_at).total_seconds() / 3600
            )

            character = db.query(Character).filter(
                Character.id == session.character_id
            ).first()
            if not character:
                continue

            # Generate message text
            message_text = await generate_proactive_message(
                character=character,
                hours_inactive=inactive_hours,
                intimacy_level=0,
            )

            # Schedule job for immediate delivery (run_at = now + 30s jitter)
            import random
            run_at = now + timedelta(seconds=random.randint(10, 60))

            job = ScheduledJob(
                user_id=session.platform_user_id,
                character_id=session.character_id,
                platform="telegram",
                run_at=run_at,
                job_type="proactive_message",
                payload_json=json.dumps({
                    "chat_id": session.telegram_chat_id,
                    "text": message_text,
                    "session_id": session.id,
                    "char_name": character.name,
                }),
                status="pending",
                attempts=0,
            )
            db.add(job)

            # Update session's last_proactive_at
            session.last_proactive_at = now
            db.commit()

            logger.info(
                f"Scheduled proactive message for session {session.id} "
                f"(user={session.platform_user_id}, char={character.name}, "
                f"inactive={inactive_hours}h)"
            )
            scheduled += 1

    except Exception as e:
        logger.error(f"Error in schedule_proactive_jobs: {e}")
    finally:
        if close_db:
            db.close()

    return scheduled


def mark_user_active(platform_user_id: str, character_id: int, db: Session):
    """
    Call when a user sends a message — resets their inactivity timer.
    Also cancels any pending proactive jobs for this session.
    """
    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.platform == "telegram",
            ChatSession.platform_user_id == platform_user_id,
            ChatSession.character_id == character_id,
            ChatSession.status == "active",
        )
        .first()
    )
    if session:
        session.last_active_at = datetime.utcnow()
        db.commit()

    # Cancel pending proactive jobs (user is active now, no need to nudge)
    pending = (
        db.query(ScheduledJob)
        .filter(
            ScheduledJob.user_id == platform_user_id,
            ScheduledJob.character_id == character_id,
            ScheduledJob.job_type == "proactive_message",
            ScheduledJob.status == "pending",
        )
        .all()
    )
    for job in pending:
        job.status = "cancelled"
    if pending:
        db.commit()
        logger.debug(f"Cancelled {len(pending)} pending proactive jobs for user {platform_user_id}")
