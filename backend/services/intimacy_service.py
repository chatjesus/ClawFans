"""
Intimacy Service — tracks relationship depth between user and character.

Level 0-100 controls:
  - What kinds of photos the character will send
  - The character's emotional openness and boldness in roleplay
  - Narrative tone injected into the system prompt

Tiers:
  0  : 陌生 (Stranger)      — clothed photos only, reserved tone
  20 : 普通朋友 (Friendly)  — cute outfits, daily-life selfies
  40 : 亲近 (Close)         — slightly revealing (cleavage, short skirt)
  60 : 暧昧 (Flirtatious)   — lingerie/bikini, suggestive poses
  80 : 亲密无间 (Intimate)  — explicit, fully revealing
"""
import re
from typing import NamedTuple


# ── Tier definitions ──────────────────────────────────────────────────────────

class IntimacyTier(NamedTuple):
    threshold: int
    name_cn: str
    name_en: str
    # SDXL tags appended to [IMG:] prompts for ComfyUI
    sdxl_tags: str
    # Natural-language style hint injected into the system prompt
    photo_hint: str


TIERS = [
    IntimacyTier(
        threshold=0,
        name_cn="陌生",
        name_en="Stranger",
        sdxl_tags="fully clothed, casual outfit, modest, smile",
        photo_hint="只在用户明确要求时才发照片，照片是日常穿着，不暴露。",
    ),
    IntimacyTier(
        threshold=20,
        name_cn="普通朋友",
        name_en="Friendly",
        sdxl_tags="cute dress, casual wear, office lady, school uniform, friendly smile",
        photo_hint="可以主动分享日常生活照，展现可爱和活力，衣着正常但有些小心机。",
    ),
    IntimacyTier(
        threshold=40,
        name_cn="亲近",
        name_en="Close",
        sdxl_tags="low-cut top, mini skirt, cleavage, exposed midriff, alluring smile, flirty",
        photo_hint=(
            "可以发些有点撩拨的照片——露出锁骨、腰线、短裙、微微的胸口弧度。"
            "照片要有点暗示性，但不过分直白。"
        ),
    ),
    IntimacyTier(
        threshold=60,
        name_cn="暧昧",
        name_en="Flirtatious",
        sdxl_tags=(
            "lingerie, bikini, revealing outfit, thighs visible, sexy pose, "
            "bedroom eyes, ecchi, fanservice, seductive"
        ),
        photo_hint=(
            "可以发更大胆的照片——睡衣、内衣、比基尼、大腿和腰臀线条明显的姿势。"
            "要有挑逗感，每张照片都像是给对方一个邀请。"
        ),
    ),
    IntimacyTier(
        threshold=80,
        name_cn="亲密无间",
        name_en="Intimate",
        sdxl_tags=(
            "explicit, nsfw, nude, topless, very revealing, erotic, "
            "sensual pose, intimate, bedroom"
        ),
        photo_hint=(
            "可以发非常露骨的照片。完全的裸露是可以的。"
            "每一张照片都应该带有强烈的情欲感，细节描写要大胆和感官化。"
        ),
    ),
]


def get_tier(level: int) -> IntimacyTier:
    """Return the IntimacyTier for a given level (0-100)."""
    for tier in reversed(TIERS):
        if level >= tier.threshold:
            return tier
    return TIERS[0]


def get_next_tier(level: int) -> IntimacyTier | None:
    """Return the next tier to unlock, or None if already at max."""
    for tier in TIERS:
        if tier.threshold > level:
            return tier
    return None


# ── Intimacy gain calculation ─────────────────────────────────────────────────

# Affectionate keywords — each match adds to gain
_AFFECTION_PATTERNS = re.compile(
    r"(喜欢你|爱你|好喜欢|好可爱|真美|真帅|很好看|好好看|心动|想你|思念|"
    r"you're so cute|i like you|i love you|you're beautiful|you're gorgeous|"
    r"adorable|lovely|pretty|handsome)",
    re.IGNORECASE,
)

_PHYSICAL_PATTERNS = re.compile(
    r"(亲|抱|摸|牵手|手|蹭|贴|靠|贴近|kiss|hug|touch|hold|caress|cuddle|stroke)",
    re.IGNORECASE,
)

_NEGATIVE_PATTERNS = re.compile(
    r"(讨厌|烦|滚|去死|shut up|hate you|boring|stupid|ugly)",
    re.IGNORECASE,
)


def calc_intimacy_gain(user_message: str, ai_reply: str = "") -> int:
    """
    Calculate intimacy points earned from one user→AI exchange.
    Returns an integer in range [-2, 6].
    """
    gain = 1  # base: every message earns 1 point

    # Affectionate keywords
    if _AFFECTION_PATTERNS.search(user_message):
        gain += 2

    # Physical engagement
    if _PHYSICAL_PATTERNS.search(user_message):
        gain += 2

    # Longer message = more engaged
    if len(user_message.strip()) > 60:
        gain += 1

    # Negative interaction
    if _NEGATIVE_PATTERNS.search(user_message):
        gain -= 3

    return max(-2, min(gain, 6))


# ── System prompt injection ───────────────────────────────────────────────────

def build_intimacy_prompt(level: int) -> str:
    """
    Returns a system prompt section describing the current relationship stage
    and photo-sharing guidelines to inject into the character's context.
    """
    tier = get_tier(level)
    next_tier = get_next_tier(level)
    progress_in_tier = level - tier.threshold
    tier_range = (next_tier.threshold - tier.threshold) if next_tier else 20
    bar_filled = min(int(progress_in_tier / tier_range * 10), 10)
    bar = "█" * bar_filled + "░" * (10 - bar_filled)

    next_hint = ""
    if next_tier:
        needed = next_tier.threshold - level
        next_hint = f"再获得 {needed} 点亲密度可解锁「{next_tier.name_cn}」阶段。"

    return f"""
## 当前关系阶段
亲密度：{level}/100 — 阶段：{tier.name_cn} [{bar}]
{next_hint}

### 照片发送规则（基于当前亲密度）
{tier.photo_hint}

当用户要求照片时，根据以上规则决定照片的尺度。
当前允许的照片风格标签：{tier.sdxl_tags}
"""


# ── Image prompt augmentation ────────────────────────────────────────────────

def augment_image_prompt(prompt: str, level: int) -> str:
    """
    Augment an [IMG:] prompt description with intimacy-appropriate tags.
    Used when generating images during chat.
    """
    tier = get_tier(level)
    # Append tier-specific tags to the prompt
    return f"{prompt}, {tier.sdxl_tags}"
