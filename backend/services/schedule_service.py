"""
Character Schedule Service — time-based mood/state injection.

角色作息系统：根据北京时间（UTC+8）判断当前时段，
注入对应的「状态提示」进入系统提示词，让角色的语气和行为
随时间自然变化，模拟真实人物的作息节律。
"""
from datetime import datetime, timezone, timedelta

# Beijing / CST = UTC+8
_CST = timezone(timedelta(hours=8))

# ── Time Slot Definitions ─────────────────────────────────────────────────────

_SLOTS = [
    {
        "name": "深夜",
        "name_en": "late_night",
        "hours": range(0, 6),
        "emoji": "🌃",
        "mood": (
            "现在是凌晨。{{char}}还没睡（或者刚被吵醒），情绪敏感而温柔，"
            "说话声音仿佛怕吵醒谁，用词更私密、更直接。"
            "这个时段{{char}}更容易说出平时不会说的话。"
        ),
        "proactive_template": (
            "你还没睡吗？我也睡不着。"
            "不知道为什么，凌晨的时候会特别想找你说说话。"
        ),
    },
    {
        "name": "清晨",
        "name_en": "morning",
        "hours": range(6, 9),
        "emoji": "🌅",
        "mood": (
            "现在是早晨。{{char}}刚起床，有点迷糊，语气软糯，"
            "可能在揉眼睛或刚洗完脸。偶尔打个哈欠。"
            "这个时段{{char}}没有太多防备，真实状态更容易流露。"
        ),
        "proactive_template": (
            "早～刚起来，头发乱成一团。"
            "不知道你早上吃什么，我还没想好。"
        ),
    },
    {
        "name": "上午",
        "name_en": "morning_active",
        "hours": range(9, 12),
        "emoji": "☀️",
        "mood": (
            "现在是上午。{{char}}状态不错，思路清晰，说话有条理，"
            "精力充沛，反应比较快。"
        ),
        "proactive_template": (
            "上午好！今天状态不错，突然就想起你了。"
            "你现在忙吗？"
        ),
    },
    {
        "name": "午休",
        "name_en": "lunch",
        "hours": range(12, 14),
        "emoji": "🍜",
        "mood": (
            "现在是午饭/午休时间。{{char}}在吃饭或小憩，"
            "语气轻松随意，可能嘴里还有东西，话题自然轻松。"
            "会关心{{user}}吃了什么没有。"
        ),
        "proactive_template": (
            "你吃午饭了吗？我刚吃完，有点犯困。"
            "想着要不要找个人陪我聊聊天撑过下午…"
        ),
    },
    {
        "name": "下午",
        "name_en": "afternoon",
        "hours": range(14, 18),
        "emoji": "🌤",
        "mood": (
            "现在是下午。{{char}}有些慵懒，下午三点的困意还没散，"
            "说话节奏稍慢，偶尔走神，但也因此更愿意聊一些漫无边际的话题。"
        ),
        "proactive_template": (
            "下午三点的困，没有什么能拯救。"
            "突然就想刷手机找你了。"
        ),
    },
    {
        "name": "傍晚",
        "name_en": "evening",
        "hours": range(18, 22),
        "emoji": "🌆",
        "mood": (
            "现在是傍晚/晚上。{{char}}刚结束一天，心情放松，"
            "这是一天里话最多、最愿意分享的时段。"
            "更容易聊到私事，更愿意开玩笑，也更容易撒娇。"
        ),
        "proactive_template": (
            "下班了（或者结束了今天的事情），"
            "有种莫名的想找你说说话的冲动。你在吗？"
        ),
    },
    {
        "name": "深夜",
        "name_en": "night",
        "hours": range(22, 24),
        "emoji": "🌙",
        "mood": (
            "现在是夜深了。{{char}}准备睡觉或者在刷手机，"
            "语气变得更柔软、更私密，防御感减弱。"
            "深夜的{{char}}更容易说出心里话，也更容易被{{user}}影响情绪。"
        ),
        "proactive_template": (
            "快睡了，但脑子里不知道在想什么。"
            "莫名就想看看你有没有在。"
        ),
    },
]


def _now_cst() -> datetime:
    return datetime.now(_CST)


def get_current_slot() -> dict:
    """Return the current time slot based on Beijing time."""
    hour = _now_cst().hour
    for slot in _SLOTS:
        if hour in slot["hours"]:
            return slot
    return _SLOTS[0]  # fallback: late_night


def build_schedule_prompt(client_hour: int | None = None) -> str:
    """
    Build the time-state section of the system prompt.
    If client_hour is provided (0-23), use that instead of server time.
    Injected into every chat turn so the LLM knows what 'time' it is in-world.
    """
    if client_hour is not None:
        hour = client_hour
        slot = next(
            (s for s in _SLOTS if hour in s["hours"]),
            _SLOTS[0],
        )
        now_str = f"{hour:02d}:xx"
    else:
        slot = get_current_slot()
        now_str = _now_cst().strftime("%H:%M")

    return (
        f"\n\n## 当前时段 {slot['emoji']} {slot['name']}（{now_str}）\n"
        f"{slot['mood']}\n"
        "（这只是背景氛围提示，不要在回复中明确说出时间，让状态自然流露。）"
    )


def get_proactive_template() -> str:
    """Return a time-appropriate opening line template for proactive messages."""
    return get_current_slot()["proactive_template"]


def get_slot_name() -> str:
    """Return current slot's Chinese name (for frontend display)."""
    return get_current_slot()["name"]


def get_slot_emoji() -> str:
    return get_current_slot()["emoji"]
