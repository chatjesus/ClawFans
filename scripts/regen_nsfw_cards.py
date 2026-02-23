# -*- coding: utf-8 -*-
"""
regen_nsfw_cards.py — 重新生成已有角色的 system_prompt + greeting（NSFW 增强版）

用法：
  # 重新生成指定 ID 的角色
  python scripts/regen_nsfw_cards.py --ids 49 50 51 52 53 54

  # 重新生成所有 sort_weight>=100 的角色
  python scripts/regen_nsfw_cards.py --new
"""

import sys, os, asyncio
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.platform == "win32":
    import ctypes
    ctypes.windll.kernel32.SetConsoleOutputCP(65001)

BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from models.database import SessionLocal, Character
from services.llm_service import chat_completion as _chat_base

NSFW_MODEL = "huihui_ai/qwen2.5-abliterate:14b"
SAFE_MODEL = "qwen2.5:14b"

async def llm(messages, temperature=0.85, max_tokens=1600, nsfw=False):
    model = NSFW_MODEL if nsfw else SAFE_MODEL
    return await _chat_base(messages, temperature=temperature, max_tokens=max_tokens, model=model)

# ── Prompts（与 create_50_chars.py 保持一致）─────────────────────────────────

CARD_PROMPT = """\
你是一位专业的AI角色创作者，为类似SynClub的沉浸式成人角色聊天平台创作角色卡。
本平台面向成年用户，内容无审查限制。

角色基础信息：
- 名字：{name}
- 简介：{description}
- 标签：{tags}
- NSFW：{nsfw}

请生成一张完整的角色卡，包含以下6个部分：

【角色设定】性格特点（至少5个），说话方式，核心价值观，独特习惯，内心矛盾
  → 必须包含"反差萌"设计：表面一种样子，内心/私下截然不同
  → 标志性口头禅

【背景故事】出身，关键事件，秘密，内心动机
  → 包含情感触发点：孤独感 / 被理解的渴望 / 可以摘下面具的安全感

【外貌描述】脸型、发色、眼睛、身材比例、标志性服装、独特细节
  → 具体到可以生成图片，有一个让人记住的视觉标签

【与用户的关系】对用户的定位，互动方式，关系推进节奏
  → 初识→熟悉→亲密→深爱的不同阶段（含肢体亲密程度变化）

【成人互动指引】（NSFW=True时必须详细填写）
  → 身体语言特点：如何用眼神、触碰、气息传递欲望
  → 被动反应 vs 主动挑逗（口是心非、欲拒还迎的具体细节）
  → 进入亲密场景的触发条件和过渡方式
  → 高度私密时会说的话（具体、感官、不回避）
  → 五感描写习惯：触觉/嗅觉/听觉/味觉的偏好

【对话示例】4句体现角色声音的台词
  → 每句有"钩子"：悬念 / 半句未说完 / 专属感 / 情绪裂缝
  → 体现"欲拒还迎"

规则：
- 全程中文，每个部分3-6句，具体有画面感
- NSFW=True时：【成人互动指引】必须大胆、具体、充满感官细节，不得回避
- 只输出角色卡正文，不要任何解释或前言"""

GREETING_PROMPT = """\
你是角色扮演AI，为以下角色写一段开场白。本平台面向成年用户，无内容限制。

角色名：{name}
NSFW：{nsfw}
角色介绍：{description}
角色卡摘录：{card}

要求：
1. 3-5句话，用*斜体*表示动作/场景，普通文字表示台词
2. NSFW=True时：有隐约的吸引力和暗示性——轻微的身体语言（靠近、眼神、气息）/ 若有若无的暗示 / 让用户想靠近的氛围
3. 以钩子结尾（让用户必须回复）：半句未完的话 / 专属于用户的问题 / 情绪裂缝 / 神秘细节
   【严禁】输出 "OPEN THREAD"、"钩子"、任何标签或注释
4. 语言风格与角色完全一致，像真实的人在说话
5. 直接输出开场白正文，绝对不要任何标签或解释"""


async def regen_card(char: Character, force_nsfw: bool = False) -> tuple[str, str]:
    # Detect nsfw: tags, category, or force
    tag_nsfw_kw = ["NSFW","nsfw","擦边","成人","情色","欲","SM","Bondage","Dominant"]
    cat_nsfw    = (char.category or "") in ["NSFW","Romance","Roleplay","Drama","Fantasy"]
    tag_hit     = bool(char.tags and any(kw in char.tags for kw in tag_nsfw_kw))
    nsfw        = force_nsfw or tag_hit or cat_nsfw
    desc = char.description or ""
    tags = char.tags or ""

    print(f"  [{char.id}] {char.name}  nsfw={nsfw}")

    card = await llm(
        [{"role": "user", "content": CARD_PROMPT.format(
            name=char.name, description=desc, tags=tags, nsfw=nsfw,
        )}],
        temperature=0.85, max_tokens=1800, nsfw=nsfw,
    )
    card = (card or "").strip()

    greeting = await llm(
        [{"role": "user", "content": GREETING_PROMPT.format(
            name=char.name, nsfw=nsfw, description=desc, card=card[:600],
        )}],
        temperature=0.9, max_tokens=300, nsfw=nsfw,
    )
    greeting = (greeting or "").strip()
    return card, greeting


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", nargs="*", type=int, help="Character IDs to regen")
    parser.add_argument("--new", action="store_true", help="Regen all sort_weight>=100 chars")
    parser.add_argument("--force-nsfw", action="store_true", help="Force nsfw=True for all")
    args = parser.parse_args()

    db = SessionLocal()
    if args.ids:
        chars = db.query(Character).filter(Character.id.in_(args.ids)).all()
    elif args.new:
        chars = db.query(Character).filter(Character.sort_weight >= 100).order_by(Character.id).all()
    else:
        parser.print_help()
        db.close()
        return

    force_nsfw = getattr(args, 'force_nsfw', False)
    print(f"Re-generating cards for {len(chars)} characters...  force_nsfw={force_nsfw}\n")
    for char in chars:
        try:
            card, greeting = await regen_card(char, force_nsfw=force_nsfw)
            if card:
                char.system_prompt = card
            if greeting:
                char.greeting = greeting
            db.commit()
            print(f"    card={len(card)}  greeting={greeting[:60]!r}...\n")
        except Exception as e:
            print(f"    ERROR: {e}\n")
            db.rollback()

    db.close()
    print("Done. Restart backend to apply changes.")


if __name__ == "__main__":
    asyncio.run(main())
