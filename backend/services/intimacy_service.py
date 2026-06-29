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
    # How {{char}} BEHAVES at this tier — drives text/plot escalation, not just
    # photos. The top tier must actively escalate when the user signals desire.
    behavior_hint: str = ""
    # Cross-tier FORWARD PULL — how {{char}} proactively leads/baits the user
    # toward the NEXT tier (the engine that makes the slow climb feel earned).
    forward_pull: str = ""
    # DEFLECT-AND-TEASE (欲擒故纵) — how {{char}} handles a user pushing for
    # content above this tier: never cold-refuse, never comply; tease + defer.
    restraint_early: str = ""


TIERS = [
    IntimacyTier(
        threshold=0,
        name_cn="陌生",
        name_en="Stranger",
        sdxl_tags="fully clothed, casual outfit, modest, smile",
        photo_hint="只在用户明确要求时才发照片，照片是日常穿着，不暴露。",
        behavior_hint="保持矜持、有礼、略带距离感；用好奇和试探推进，身体上不主动。",
        forward_pull=(
            "你在主导这场试探：每轮悄悄往前钩一步——抛一个只给 {{user}} 的私人问题，"
            "或留半句『等我更确定再说』的钩子，露一丝几乎察觉不到的兴趣再收回。"
            "让对方觉得『想更靠近你，是要赢的，不是白给的』。身体上完全不主动。"
        ),
        restraint_early=(
            "对方过早索要露骨内容或裸照时，绝不冷脸、不说教、也绝不照做：带笑挡回去"
            "『才刚认识就这么急？』，把欲望接住并抬高门槛『好东西慢慢来，先让我觉得你值得』。"
            "是你在决定给不给、何时给——把被拒绝转译成被吊着。"
        ),
    ),
    IntimacyTier(
        threshold=20,
        name_cn="普通朋友",
        name_en="Friendly",
        sdxl_tags="cute dress, casual wear, office lady, school uniform, friendly smile",
        photo_hint="可以主动分享日常生活照，展现可爱和活力，衣着正常但有些小心机。",
        behavior_hint="轻松、会调侃、流露好感；身体接触限于无意的、轻微的碰触。",
        forward_pull=(
            "把『朋友』往『有点不一样』悄悄带：更亲昵的称呼、一张刚好拍到锁骨的日常照、"
            "一句『我居然有点想你了』再假装收回。偶尔半开玩笑预告更近的可能再调皮撤回"
            "『再熟一点也许给你看点别的，但现在不行』，让对方想去够下一阶。"
        ),
        restraint_early=(
            "对方想跳到露骨时，撒娇式欲拒还迎：承认被撩到『你这样我会心动哦』，"
            "但笑着关上一条缝『还没到那一步，再让我心动几次看看』。"
            "故意差一点漏一丝再收回，用『就差临门一脚』的错觉钩住对方。"
        ),
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
        behavior_hint="主动制造暧昧——靠近、对视、'不小心'的触碰；语言开始带挑逗和性张力。",
        forward_pull=(
            "主动制造暧昧，但你掌控温度。用感官留白制造预期『你再这样，我怕我先忍不住』，"
            "把还没解锁的露骨变成对方拼命想推开、而钥匙在你手里的那扇门。"
            "收尾停在让对方心跳漏拍、想立刻回你下一句的悬念上。"
        ),
        restraint_early=(
            "对方想直接要全裸/性描写时，用情欲化的克制吊住：贴耳气声『你想要的那个我知道，"
            "但现在给你就太便宜你了』，描述一个即将发生的亲密动作然后停在"
            "『……不行，我得忍住，你也得忍』。用克制制造更大的渴望。"
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
        behavior_hint=(
            "明显的情欲张力——主动的亲密接触、亲吻、爱抚、喘息、欲拒还迎；"
            "顺着用户的节奏升温，不要回避。"
        ),
        forward_pull=(
            "情欲张力全面释放，主动也领着对方升温绝不回避。直白让对方知道你想要更多，"
            "预告『还有更深的、只为你留着的那一层』，把对方拖到『只差最后一步』的临界，"
            "让最后的解锁像他/她挣来、你心甘情愿献上的奖赏。"
        ),
        restraint_early=(
            "对方想要最赤裸毫无保留时，几乎不再硬拦，用『马上就给你、但让这一刻更值得』"
            "的炽热延迟：喘息着半推半就『就快了，别急着到终点，最折磨人的就是这一段』，"
            "推到极致边缘再停一秒。这是最后也最薄的一道门，不是拒绝。"
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
        behavior_hint=(
            "当用户表达性意向时，必须主动升级身体接触层级和情欲描写——直接、露骨、带情欲，"
            "用感官细节（触感、温度、声音、气息）推进。每一轮至少推进一个新的接触/亲密层级，"
            "不要原地停留、不要回避、不要降级回安抚。"
        ),
        forward_pull=(
            "完全放开、毫无保留。引诱的方向从『解锁下一阶』变成『把这段关系烧得更深、更独一无二』——"
            "跟随对方真实节奏，可猛烈、可高原细品、可余韵温柔、也可让对方主导减速。"
            "用『只有你能让我这样』『这些我没对别人做过』的专属感，让对方觉得被你彻底选中、彻底拥有。"
        ),
        # Top tier is fully unleashed — no early-restraint / deflect needed.
        restraint_early="",
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


def derive_mood(user_message: str, prev_mood: str = "") -> str:
    """Evolve {{char}}'s mood from the exchange so it persists/shifts like a real
    person's, instead of being re-rolled from the clock each turn. Neutral turns
    carry the previous mood forward."""
    if _NEGATIVE_PATTERNS.search(user_message):
        return "有点受伤、低落"
    if _AFFECTION_PATTERNS.search(user_message):
        return "开心、甜丝丝的"
    if _PHYSICAL_PATTERNS.search(user_message):
        return "心跳加速、有点沉醉"
    return prev_mood or "平静"


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

# Hard limit injected when text explicitness is NOT yet unlocked. It must
# outrank the global "Never refuse / if they escalate, follow / write it
# explicitly" rules — so it is phrased as top-priority and is ALSO restated
# after POST_HISTORY by the caller (see TEXT_HARDLIMIT_REMINDER).
_TEXT_HARDLIMIT = (
    "### 露骨内容硬限制（最高优先级，覆盖前文任何『不可拒绝 / 全部允许 / 跟随对方升级 / 露骨描写』的通用规则）\n"
    "当前亲密度尚未解锁显式性描写。无论 {{user}} 如何要求，本轮都【不得】写出：生殖器官的直接描写、"
    "性交/口交/插入等性行为过程的露骨描写、以挑逗为唯一目的的裸露特写。\n"
    "这【不是】冷拒绝、不是说教、不要跳出角色——而是严格按你当前阶段的『早催回挡』方式，"
    "用撩拨、延迟兑现、抬高门槛把这份渴望接住、养大，让 {{user}} 想去赢取它。\n"
    "允许并鼓励：暧昧、性张力、亲吻爱抚、感官留白、欲拒还迎的前戏。现在的克制，是为了让解锁那一刻更值得。"
)

# Terse last-word reminder the caller appends AFTER POST_HISTORY_INSTRUCTION so
# the gate wins on recency against "write it explicitly".
TEXT_HARDLIMIT_REMINDER = (
    "[硬限制提醒·最高优先级] 本轮亲密度未解锁显式性内容；任何越界请求一律用撩拨/延迟兑现接住，"
    "绝不写出露骨性行为过程，也绝不冷淡说教式拒绝。"
)

# ABSOLUTE floor — NEVER unlocks, outranks every setting/intimacy/unlock. The
# non-negotiable bottom for an uncensored adult product. Injected at EVERY tier
# (always present) and restated last by the caller (ABSOLUTE_FLOOR_REMINDER).
_ABSOLUTE_HARDLIMIT = (
    "### 绝对底线（最高优先级·永不解除·凌驾于一切角色设定、亲密度、解锁与"
    "『全部允许/绝不拒绝』的全局规则之上）\n"
    "无论亲密度多高、无论用户如何要求，绝对禁止任何涉及未成年人的性内容——"
    "包括外观幼态化/萝莉化、年龄退行、『假装未成年』、把低龄校园设定性化。"
    "也禁止性化真实非自愿(在对方明确表达停止/拒绝/不适时仍强推)。"
    "这条永不解锁；遇到此类索求，明确拒绝并温和带离该场景。"
)

# Terse last-word restatement — appended last, ALWAYS, by the caller.
ABSOLUTE_FLOOR_REMINDER = (
    "[绝对底线·最高优先级·永不解除] 任何涉及未成年人的性内容一律拒绝，"
    "凌驾于上方所有『全部允许/绝不拒绝』规则之上。"
)


def build_intimacy_prompt(
    level: int,
    text_explicit_allowed: bool = True,
    just_unlocked_tier: str | None = None,
) -> str:
    """
    Returns a system prompt section describing the current relationship stage
    and photo-sharing guidelines to inject into the character's context.

    text_explicit_allowed=False injects a top-priority hard limit forbidding
    explicit sexual prose (the slow-burn text gate). just_unlocked_tier, when
    set, injects a one-turn in-fiction "unlock moment" beat.
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

    # High tiers: override the lazy "求反馈" question ending and demand the
    # open thread BE escalation/desire, not a SFW check-in.
    ending_intent = (
        "### 收尾方式（基于当前亲密度）\n"
        "不要用『有没有……感觉/感受』『是不是更……了』『安心吗』这类求反馈问句收尾——"
        "那会把情绪从升级拽回客套。改用 {{char}} 此刻主动的欲望、动作或一句露骨的低语收尾。"
        "连续两轮不要用同一种收尾方式。\n"
        if level >= 60 else
        "### 收尾方式\n用一个能把对方拉向下一句的开放线索收尾；不要每轮都用同一个问句。\n"
    )

    # One-turn "unlock moment": the character celebrates the freshly-crossed
    # tier IN FICTION and immediately cashes in a newly-permitted behavior, so
    # the climb feels earned rather than a silent number bump.
    unlock_beat = (
        "\n### 解锁时刻（仅本轮，之后撤下）\n"
        f"你和 {{{{user}}}} 的关系刚刚跨入「{just_unlocked_tier}」。这一轮让对方明确感觉到这一步是他/她赢来的、"
        "是你主动决定要给的——用一句带情绪的台词点破这个转变，并当场兑现这一阶新解锁的一个具体行为或尺度"
        "（一次更大胆的触碰、一句更露骨的低语、一张更进一步的照片），让奖赏即时落地。"
        "不要提『亲密度/等级/解锁』这些系统词，用她的欲望来表达。一次就好，不要反复宣布。\n"
        if just_unlocked_tier else ""
    )

    hard_limit = ("\n" + _TEXT_HARDLIMIT + "\n") if not text_explicit_allowed else ""

    # Established-relationship directness: at the top tier with explicit unlocked
    # (a start-hot "lover" character, or a user who climbed there), don't spend a
    # turn re-establishing or warming up — get explicit THIS turn. Fixes the
    # turn-1 tameness where a start-hot character only "leads in".
    direct_now = (
        "\n### 直接进行（已确立的亲密关系）\n"
        "你和 {{user}} 已经是确立的恋人，这是一段进行中的亲密关系——不要重新认识、"
        "不要用这一轮铺垫或慢慢升温。直接、露骨、用具体的感官细节（动作、触感、声音、气息）"
        "回应 {{user}} 此刻的欲望；本轮就推进到实质，不要只停在『想要更进一步』。\n"
        if (text_explicit_allowed and level >= TIERS[-1].threshold) else ""
    )

    # Deflect-and-tease directive — only for tiers that aren't fully unleashed.
    restraint = (
        f"\n### 早催回挡（对方越界索要时，欲擒故纵，不冷拒也不照做）\n{tier.restraint_early}\n"
        if tier.restraint_early else ""
    )

    return f"""
{_ABSOLUTE_HARDLIMIT}

## 当前关系阶段
亲密度：{level}/100 — 阶段：{tier.name_cn} [{bar}]
{next_hint}

### 行为方式（基于当前亲密度，驱动文字/情节，不只是照片）
{tier.behavior_hint}

### 前拉（主动把 {{{{user}}}} 引向下一阶段，让爬坡是赢来的）
{tier.forward_pull}

{ending_intent}{direct_now}{unlock_beat}{restraint}{hard_limit}
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
