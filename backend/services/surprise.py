"""
Daily surprise / gacha — variable-reward engine.

Intermittent variable reinforcement is the strongest engagement hook a
companion product has. Once per day the user opens a surprise of random
rarity; rarer pulls grant more intimacy (the endpoint layers a bolder
message/image on top). Rarity weights are operator-tunable via ops-config.

The draw is RNG-injectable so it's deterministic in tests.
"""
import random
from typing import Optional

from sqlalchemy.orm import Session

from models.database import Conversation
from services.ops_config import get_ops_value

# Intimacy granted per rarity (rarer = bigger bond jump).
RARITY_INTIMACY = {"common": 1, "rare": 3, "epic": 6, "legendary": 12}
_DEFAULT_WEIGHTS = {"common": 60, "rare": 28, "epic": 10, "legendary": 2}


def draw_rarity(weights: dict, rng: Optional[random.Random] = None) -> str:
    """Weighted random rarity. Ignores non-positive weights."""
    r = rng or random
    pool = [(k, max(0, int(v))) for k, v in weights.items() if int(v) > 0]
    if not pool:
        return "common"
    keys = [k for k, _ in pool]
    w = [v for _, v in pool]
    return r.choices(keys, weights=w, k=1)[0]


def perform_surprise(
    conv: Conversation, db: Session, today: str, rng: Optional[random.Random] = None
) -> Optional[dict]:
    """Draw the day's surprise if available. Returns {rarity, intimacy_bonus}
    or None (disabled, or already drawn today). Applies the intimacy bonus and
    marks the day. The caller layers content (message/image) on top."""
    if not get_ops_value(db, "surprise_enabled", True):
        return None
    if conv.last_surprise_date == today:
        return None

    weights = get_ops_value(db, "surprise_rarity_weights", _DEFAULT_WEIGHTS)
    rarity = draw_rarity(weights, rng)
    bonus_amount = RARITY_INTIMACY.get(rarity, 1)

    old = conv.intimacy_level or 0
    new_level = min(100, old + bonus_amount)
    conv.intimacy_level = new_level
    conv.last_surprise_date = today
    db.commit()

    return {"rarity": rarity, "intimacy_bonus": new_level - old}


# Tone scales with rarity — the rarer the pull, the bolder/more explicit.
_RARITY_TONE = {
    "common": "轻松、甜蜜",
    "rare": "撩拨、带点心机",
    "epic": "暧昧、大胆",
    "legendary": "极度亲密、直接、带情欲",
}


async def generate_surprise_message(character, conversation, rarity: str, db: Session) -> str:
    """An in-character line delivering the surprise, scaled by rarity + the
    current intimacy stage (so legendary at high intimacy can be explicit)."""
    from services.llm_service import chat_completion
    from services.intimacy_service import build_intimacy_prompt

    level = getattr(conversation, "intimacy_level", 0) or 0
    tone = _RARITY_TONE.get(rarity, "甜蜜")
    prompt = [
        {
            "role": "system",
            "content": (
                f"你是 {character.name}。{character.system_prompt}\n"
                f"{build_intimacy_prompt(level)}\n"
                f"你刚抽到一个「{rarity}」稀有度的惊喜要送给 {{user}}——主动给他一句惊喜的话，"
                f"语气：{tone}。越稀有越大胆、越露骨。1-2 句，带一个 *动作*。"
                f"只输出这句话本身，不要解释。"
            ),
        }
    ]
    text = await chat_completion(prompt, max_tokens=400)
    return (text or "").strip()
