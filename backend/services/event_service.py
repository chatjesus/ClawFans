"""
Event Service — story event triggering, checking, and completion.

事件剧本系统：
- 每个角色有多个里程碑事件（由 seed_events.py 生成）
- 每次消息后检查是否应触发新事件
- 用户做出选择后，角色通过 LLM 生成符合人设的反应
- 完成后更新亲密度 + 记录状态
"""
import json
import logging
from datetime import datetime, date
from sqlalchemy.orm import Session

from models.database import (
    CharacterEvent, ConversationEvent, Conversation, Character
)
from services.llm_service import chat_completion

logger = logging.getLogger(__name__)


# ── Trigger Evaluation ────────────────────────────────────────────────────────

def _check_trigger(trigger: dict, conv: Conversation, message_count: int) -> bool:
    """Return True if the event should be triggered now."""
    t = trigger.get("type", "")

    if t == "intimacy_gte":
        return (conv.intimacy_level or 0) >= trigger.get("value", 0)

    if t == "intimacy_range":
        level = conv.intimacy_level or 0
        return trigger.get("min", 0) <= level < trigger.get("max", 100)

    if t == "message_count_gte":
        return message_count >= trigger.get("value", 0)

    if t == "day_streak":
        return (conv.streak_days or 0) >= trigger.get("value", 0)

    if t == "days_since_start":
        if not conv.created_at:
            return False
        days = (datetime.utcnow() - conv.created_at).days
        return days >= trigger.get("value", 0)

    return False


# ── Core Check ────────────────────────────────────────────────────────────────

def check_events(
    conversation: Conversation,
    character: Character,
    db: Session,
) -> dict | None:
    """
    Called after each user message. Returns event data if one should be triggered,
    otherwise returns None.

    An event triggers when:
    1. Its trigger condition is met
    2. It hasn't been triggered for this conversation yet
    3. No other event is currently active (one at a time)
    """
    # Don't trigger if another event is currently active
    active = (
        db.query(ConversationEvent)
        .filter(
            ConversationEvent.conversation_id == conversation.id,
            ConversationEvent.status == "active",
        )
        .first()
    )
    if active:
        return None

    # Count messages for this conversation
    from models.database import Message
    message_count = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .count()
    )

    # Get all events for this character, sorted by priority
    char_events = (
        db.query(CharacterEvent)
        .filter(CharacterEvent.char_id == character.id)
        .order_by(CharacterEvent.sort_order.asc())
        .all()
    )

    for event in char_events:
        # Skip already-used events for this conversation
        existing = (
            db.query(ConversationEvent)
            .filter(
                ConversationEvent.conversation_id == conversation.id,
                ConversationEvent.event_id == event.id,
                ConversationEvent.status.in_(["active", "completed", "skipped"]),
            )
            .first()
        )
        if existing:
            continue

        # Evaluate trigger
        try:
            trigger = json.loads(event.trigger_json or "{}")
        except Exception:
            trigger = {}

        if _check_trigger(trigger, conversation, message_count):
            # Activate this event
            instance = ConversationEvent(
                conversation_id=conversation.id,
                event_id=event.id,
                status="active",
                triggered_at=datetime.utcnow(),
            )
            db.add(instance)
            db.commit()
            db.refresh(instance)

            logger.info(
                f"Event triggered: '{event.title}' for conv={conversation.id}"
            )

            try:
                choices = json.loads(event.choices_json or "[]")
            except Exception:
                choices = []

            return {
                "instance_id": instance.id,
                "event_id": event.id,
                "title": event.title,
                "description": event.description,
                "choices": choices,
                "event_type": event.event_type,
            }

    return None


# ── Choice Resolution ─────────────────────────────────────────────────────────

async def resolve_choice(
    instance_id: int,
    choice_index: int,
    conversation: Conversation,
    character: Character,
    db: Session,
) -> dict:
    """
    Process user's choice for an event.
    Returns: {
        intimacy_delta: int,
        reaction: str,          # LLM-generated character reaction
        unlock_hint: str | None # what was unlocked
    }
    """
    instance = db.query(ConversationEvent).filter(
        ConversationEvent.id == instance_id
    ).first()
    if not instance:
        return {"error": "Event instance not found"}

    event = db.query(CharacterEvent).filter(
        CharacterEvent.id == instance.event_id
    ).first()
    if not event:
        return {"error": "Event not found"}

    # Parse choices
    try:
        choices = json.loads(event.choices_json or "[]")
    except Exception:
        choices = []

    if choice_index < 0 or choice_index >= len(choices):
        choice_index = 0

    choice = choices[choice_index]
    intimacy_delta = choice.get("intimacy_delta", 0)
    unlock_hint = choice.get("unlock_hint", None)

    # Update conversation intimacy
    old_level = conversation.intimacy_level or 0
    new_level = max(0, min(100, old_level + intimacy_delta))
    conversation.intimacy_level = new_level

    # Mark instance as completed
    instance.status = "completed"
    instance.choice_index = choice_index
    instance.completed_at = datetime.utcnow()
    db.commit()

    # Generate character reaction via LLM
    reaction = await _generate_reaction(
        event=event,
        character=character,
        choice=choice,
        intimacy_level=new_level,
    )

    return {
        "intimacy_delta": intimacy_delta,
        "intimacy_level": new_level,
        "reaction": reaction,
        "unlock_hint": unlock_hint,
        "event_title": event.title,
    }


async def _generate_reaction(
    event: CharacterEvent,
    character: Character,
    choice: dict,
    intimacy_level: int,
) -> str:
    """Use LLM to generate character's in-character reaction to the user's choice."""
    choice_text = choice.get("text", "")
    outcome_prompt = event.outcome_prompt or ""

    prompt = f"""你是{character.name}，一个真实的人物角色。

角色描述：{(character.description or '')[:200]}

场景背景：{event.description}

用户选择了：「{choice_text}」

{outcome_prompt}

现在以{character.name}的口吻，用中文，写出她对这个选择的真实反应。
要求：
- 1-3句话，自然真实
- 符合角色的性格和当前亲密度（{intimacy_level}/100）
- 不要重复背景描述，直接表现情绪和反应
- 用*斜体*描述动作，正常文字表达台词和想法

只输出角色的反应，不要其他内容："""

    try:
        messages = [{"role": "user", "content": prompt}]
        text = await chat_completion(messages, max_tokens=200, temperature=0.9)
        return text.strip()
    except Exception as e:
        logger.warning(f"Reaction generation failed: {e}")
        return f"*{character.name}没有说话，但眼神变了。*"


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_pending_events(conversation_id: int, db: Session) -> list[dict]:
    """Get all active (waiting for choice) events for a conversation."""
    instances = (
        db.query(ConversationEvent)
        .filter(
            ConversationEvent.conversation_id == conversation_id,
            ConversationEvent.status == "active",
        )
        .all()
    )
    result = []
    for inst in instances:
        event = inst.event
        if not event:
            continue
        try:
            choices = json.loads(event.choices_json or "[]")
        except Exception:
            choices = []
        result.append({
            "instance_id": inst.id,
            "event_id": event.id,
            "title": event.title,
            "description": event.description,
            "choices": choices,
            "event_type": event.event_type,
            "triggered_at": inst.triggered_at.isoformat() if inst.triggered_at else None,
        })
    return result
