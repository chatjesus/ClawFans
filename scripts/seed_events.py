"""
seed_events.py — 为每个角色用 LLM 生成专属里程碑剧本

每个角色生成 5 个事件（触发条件: 亲密度 ≥ 20/35/50/70/85）
每个事件包含：
  - 标题 (title): 文学感强的场景名
  - 描述 (description): 2-3段沉浸感叙事，营造强烈氛围
  - 3个选项 (choices): 不同情感路线，各有亲密度加减
  - outcome_prompt: 指导 LLM 生成角色反应的 prompt

用法：
  python scripts/seed_events.py [--char-id N] [--force]
"""
import os, sys, json, asyncio, argparse, re
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from models.database import SessionLocal, Character, CharacterEvent, ConversationEvent

# ─────────────────────────────────────────────────────────────────────────────
# LLM helper

async def _llm(prompt: str, model: str = "qwen2.5:14b") -> str:
    import httpx
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.95, "num_predict": 1500},
    }
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post("http://localhost:11434/api/chat", json=payload)
        r.raise_for_status()
        return r.json()["message"]["content"].strip()

# ─────────────────────────────────────────────────────────────────────────────
# 5 milestone templates — one per intimacy tier

MILESTONES = [
    {
        "sort_order": 1,
        "trigger": {"type": "intimacy_gte", "value": 20},
        "event_type": "milestone",
        "theme": "破冰 — 她第一次向你袒露了一件只对少数人说过的事，有点脆弱，有点勇敢。",
    },
    {
        "sort_order": 2,
        "trigger": {"type": "intimacy_gte", "value": 35},
        "event_type": "milestone",
        "theme": "暧昧临界 — 她发来一条深夜消息，语气有些反常，像是鼓足了勇气才发出来的。",
    },
    {
        "sort_order": 3,
        "trigger": {"type": "intimacy_gte", "value": 50},
        "event_type": "milestone",
        "theme": "亲密升温 — 你们之间发生了一件小事，但那一刻你们都感觉到了什么已经不同了。",
    },
    {
        "sort_order": 4,
        "trigger": {"type": "intimacy_gte", "value": 70},
        "event_type": "milestone",
        "theme": "坦白 — 她用最直接的方式告诉你她对你的感受，没有试探，没有隐藏。",
    },
    {
        "sort_order": 5,
        "trigger": {"type": "intimacy_gte", "value": 85},
        "event_type": "special",
        "theme": "专属时刻 — 她为你创造了一个只属于你们两个人的特别时刻，并给你看了一直没给别人看过的那一面。",
    },
]

# Extra events based on streak / message count
EXTRA_MILESTONES = [
    {
        "sort_order": 10,
        "trigger": {"type": "day_streak", "value": 7},
        "event_type": "anniversary",
        "theme": "连续七天 — 她注意到你每天都来，决定用某种方式表示这对她来说意味着什么。",
    },
    {
        "sort_order": 11,
        "trigger": {"type": "message_count_gte", "value": 30},
        "event_type": "daily",
        "theme": "熟悉感 — 聊了这么多，她发现你让她产生了一种说不清的依赖感，她想谈谈这件事。",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# Prompt template

EVENT_GEN_PROMPT = """你是一名顶级互动叙事游戏策划（代表作：恋与制作人、Mystic Messenger、心野）。

现在你需要为以下角色创作一段剧情事件：

角色名：{name}
角色描述：{description}
系统提示（人设）：{system_prompt}

事件主题：{theme}
事件类型：{event_type}

输出要求（必须是有效 JSON，不要加任何说明，直接输出 JSON）：

{{
  "title": "（文学感强的场景标题，4-10字，例如「凌晨三点的一条消息」）",
  "description": "（场景描述：2-4段，100-200字。用第二人称「你」，制造强烈氛围感，让用户感受到现场感。不要用括号标注旁白。结尾用悬念或问题引出选择。）",
  "choices": [
    {{
      "text": "（选项A：温柔/接受路线，10-20字）",
      "hint": "（可选：这个选择的隐性含义，8字内）",
      "intimacy_delta": 8
    }},
    {{
      "text": "（选项B：暧昧/调戏路线，10-20字）",
      "hint": "（可选）",
      "intimacy_delta": 5
    }},
    {{
      "text": "（选项C：保持距离/理性路线，10-20字）",
      "hint": "（可选）",
      "intimacy_delta": -2
    }}
  ],
  "outcome_prompt": "（给 LLM 的角色反应指引：描述角色在每种选项下大致的情绪和行为倾向，50字内，不要提具体选项内容）"
}}

只输出 JSON，不要其他文字："""

# ─────────────────────────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    """Try to parse JSON from LLM output, handling code fences."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"```[a-z]*\n?", "", text).rstrip("`").strip()
    # Find first { ... } block
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        return json.loads(m.group())
    return json.loads(text)


async def generate_event(char: Character, milestone: dict) -> dict | None:
    desc = (char.description or "")[:300]
    prompt_text = (char.system_prompt or "")[:400]
    prompt = EVENT_GEN_PROMPT.format(
        name=char.name,
        description=desc,
        system_prompt=prompt_text,
        theme=milestone["theme"],
        event_type=milestone["event_type"],
    )
    raw = await _llm(prompt)
    try:
        data = _extract_json(raw)
        return data
    except Exception as e:
        print(f"  !! JSON parse error for {char.name}/{milestone['sort_order']}: {e}")
        print(f"  Raw output: {raw[:200]}")
        return None


async def seed_character(char: Character, db, force: bool = False):
    print(f"\n[{char.id}] {char.name}")
    existing = db.query(CharacterEvent).filter(CharacterEvent.char_id == char.id).count()
    if existing > 0 and not force:
        print(f"  skip — {existing} events already exist (use --force to overwrite)")
        return

    if force:
        # Remove old events (cascade: also remove conversation instances)
        old_events = db.query(CharacterEvent).filter(CharacterEvent.char_id == char.id).all()
        for ev in old_events:
            db.query(ConversationEvent).filter(ConversationEvent.event_id == ev.id).delete()
            db.delete(ev)
        db.commit()

    all_milestones = MILESTONES + EXTRA_MILESTONES
    for milestone in all_milestones:
        print(f"  generating event: sort={milestone['sort_order']} theme={milestone['theme'][:30]}...")
        data = await generate_event(char, milestone)
        if not data:
            print("  !! skipped due to generation failure")
            continue
        event = CharacterEvent(
            char_id=char.id,
            event_type=milestone["event_type"],
            title=data.get("title", "未命名事件"),
            description=data.get("description", ""),
            trigger_json=json.dumps(milestone["trigger"], ensure_ascii=False),
            choices_json=json.dumps(data.get("choices", []), ensure_ascii=False),
            outcome_prompt=data.get("outcome_prompt", ""),
            sort_order=milestone["sort_order"],
        )
        db.add(event)
        db.commit()
        print(f"  ✓ '{data.get('title', '?')}'")
        await asyncio.sleep(1)  # avoid rate-limiting Ollama


async def main(args):
    db = SessionLocal()
    try:
        if args.char_id:
            chars = db.query(Character).filter(Character.id == args.char_id).all()
        else:
            chars = db.query(Character).filter(Character.sort_weight >= 50).order_by(Character.id.asc()).all()

        print(f"Seeding events for {len(chars)} characters...")
        for char in chars:
            await seed_character(char, db, force=args.force)
        print("\nDone!")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed story events for characters")
    parser.add_argument("--char-id", type=int, default=None, help="Only process this character ID")
    parser.add_argument("--force", action="store_true", help="Overwrite existing events")
    args = parser.parse_args()
    asyncio.run(main(args))
