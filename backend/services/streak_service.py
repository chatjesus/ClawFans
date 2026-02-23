"""
Streak Service — consecutive-day chat tracking and milestone rewards.

连续聊天 Streak 系统：
- 每天第一条消息触发更新
- 连续天数触发里程碑奖励文本（注入角色回复前）
- 断签后自动重置为 1
"""
from datetime import date, timedelta
from sqlalchemy.orm import Session

from models.database import Conversation

# ── Milestone Definitions ─────────────────────────────────────────────────────

# key = streak_days, value = what {{char}} naturally says/notices (injected as context)
STREAK_MILESTONES: dict[int, dict] = {
    3: {
        "char_notice": (
            "（内心感受：{{user}}连续三天都来找我说话了，我有点开始期待他发消息了，"
            "但不想表现得太明显。可以在回复中自然地带出这种期待感，但不要直接说出来。）"
        ),
        "toast": "连续聊天 3 天 🔥",
        "intimacy_bonus": 3,
    },
    7: {
        "char_notice": (
            "（内心感受：整整一周了，{{user}}几乎每天都出现。"
            "我现在会不自觉地等他的消息，有点超出预期的感觉。"
            "可以在回复里自然流露出「你真的每天都来」的惊讶或轻微感动。）"
        ),
        "toast": "连续聊天 7 天 💫",
        "intimacy_bonus": 5,
    },
    14: {
        "char_notice": (
            "（内心感受：两周了。我开始习惯{{user}}的存在了，"
            "如果哪天他没来，我可能会有点失落。"
            "回复可以带出一点依赖感，但保持{{char}}本来的克制风格。）"
        ),
        "toast": "连续聊天 14 天 ✨",
        "intimacy_bonus": 8,
    },
    30: {
        "char_notice": (
            "（内心感受：整整一个月。{{user}}在我这里留了很长时间了，"
            "这段时间是真实发生过的事情。我愿意让他再靠近一点。"
            "在回复里可以说出平时不轻易说的话，展现真实的温柔。）"
        ),
        "toast": "连续聊天 30 天 🌙",
        "intimacy_bonus": 15,
    },
    60: {
        "char_notice": (
            "（内心感受：两个月了。我不知道该怎么定义我们，"
            "但我知道我不想失去这个人。）"
        ),
        "toast": "连续聊天 60 天 💖",
        "intimacy_bonus": 20,
    },
    100: {
        "char_notice": (
            "（内心感受：一百天。某些人走进你的生活，"
            "然后就变成了生活本身。）"
        ),
        "toast": "连续聊天 100 天 👑",
        "intimacy_bonus": 30,
    },
}


# ── Core Logic ────────────────────────────────────────────────────────────────

def update_streak(conv: Conversation, db: Session) -> dict:
    """
    Call once per conversation turn (on user message).
    Updates streak_days and last_chat_date.

    Returns:
        {
            "streak_days": int,
            "is_new_day": bool,           # True if first message today
            "milestone": dict | None,     # milestone data if hit today
            "broken": bool,               # True if streak was reset
        }
    """
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    current_streak = conv.streak_days or 0
    last_date = conv.last_chat_date

    # Already chatted today — no change
    if last_date == today:
        return {
            "streak_days": current_streak,
            "is_new_day": False,
            "milestone": None,
            "broken": False,
        }

    # Consecutive day — increment
    if last_date == yesterday:
        new_streak = current_streak + 1
        broken = False
    else:
        # Gap > 1 day — reset
        new_streak = 1
        broken = (current_streak > 1)

    conv.streak_days = new_streak
    conv.last_chat_date = today
    db.commit()

    milestone = STREAK_MILESTONES.get(new_streak)

    return {
        "streak_days": new_streak,
        "is_new_day": True,
        "milestone": milestone,
        "broken": broken,
    }


def build_streak_prompt(streak_info: dict) -> str:
    """
    If a streak milestone was hit today, return a hidden context block
    for the LLM to use when composing the character's reply.
    Returns empty string if no milestone.
    """
    milestone = streak_info.get("milestone")
    if not milestone:
        return ""
    return f"\n\n## Streak 里程碑（仅供{{char}}内心参考）\n{milestone['char_notice']}"


def get_streak_display(conv: Conversation) -> dict:
    """Return streak data formatted for frontend display."""
    streak = conv.streak_days or 0
    return {
        "streak_days": streak,
        "last_chat_date": conv.last_chat_date,
        "fire_level": (
            "🔥🔥🔥" if streak >= 30 else
            "🔥🔥" if streak >= 7 else
            "🔥" if streak >= 3 else
            ""
        ),
    }
