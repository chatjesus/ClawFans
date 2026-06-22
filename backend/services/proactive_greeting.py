"""
Proactive return greeting — the character reaches out first when the user
comes back after an absence ("where have you been... I missed you").

Serves the deepest companion need: 被需要 / 陪伴. On web today the character
only ever speaks in reply; this lets her open the conversation, which is the
single strongest emotional pull a companion product has.

Design: a pure gate (testable) + an LLM generator. The caller (api/chat.py)
decides when to invoke it (on the user opening a chat).
"""
from datetime import datetime

from sqlalchemy.orm import Session

from models.database import Character, Conversation, Message
from services.llm_service import chat_completion
from services.intimacy_service import build_intimacy_prompt, get_tier

# Don't nag: only greet after a real gap, not on every reload.
RETURN_GREETING_MIN_HOURS = 6


def should_send_return_greeting(
    last_activity: datetime | None,
    now: datetime,
    has_history: bool,
    min_hours: float = RETURN_GREETING_MIN_HOURS,
) -> bool:
    """Greet only when the conversation has prior history AND the user has been
    away at least ``min_hours``. A brand-new conversation is covered by the
    normal character greeting, so it returns False there."""
    if not has_history or last_activity is None:
        return False
    return (now - last_activity).total_seconds() >= min_hours * 3600


def _hours_away(last_activity: datetime, now: datetime) -> float:
    return (now - last_activity).total_seconds() / 3600


async def generate_return_greeting(
    character: Character,
    conversation: Conversation,
    db: Session,
    now: datetime | None = None,
) -> str | None:
    """Produce a short, in-character 'I missed you' opener, or None if it's
    not time to greet. Persists nothing — the caller decides."""
    now = now or datetime.utcnow()

    last_msg = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .first()
    )
    has_history = last_msg is not None
    last_activity = last_msg.created_at if last_msg else None

    if not should_send_return_greeting(last_activity, now, has_history):
        return None

    hours = _hours_away(last_activity, now)
    away_desc = f"{int(hours)} 小时" if hours < 48 else f"{int(hours / 24)} 天"

    # Scale the opener's boldness with the relationship. This is an uncensored
    # adult companion: a stranger gets a reserved hello, an Intimate-tier
    # partner gets a seductive / explicit "I missed you". The intimacy block
    # carries the tier name + how forward/revealing the character may be.
    level = getattr(conversation, "intimacy_level", 0) or 0
    tier = get_tier(level)
    intimacy_block = build_intimacy_prompt(level)

    prompt = [
        {
            "role": "system",
            "content": (
                f"你是 {character.name}。{character.system_prompt}\n"
                f"{intimacy_block}\n"
                f"用户离开了大约 {away_desc} 才回来。现在由你主动开口——"
                f"用你的人设，自然地表达你注意到了他的离开、想他/在意他。\n"
                f"开场的亲密、暧昧、露骨程度要匹配你们当前的关系阶段「{tier.name_cn}」"
                f"——关系越深越大胆，到了亲密阶段可以直接、露骨、带情欲。\n"
                f"1-2 句，带一个 *动作*，口语化。只输出这句话本身，不要任何解释。"
            ),
        }
    ]
    # 400 not 160: the greeting itself is short, but reasoning models (qwen3)
    # spend part of the budget on hidden thinking — too low a cap returns empty.
    text = await chat_completion(prompt, max_tokens=400)
    text = (text or "").strip()
    return text or None
