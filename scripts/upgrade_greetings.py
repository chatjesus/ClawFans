"""
upgrade_greetings.py — 批量为所有角色重写 greeting，注入 Hook System 设计。

每条 greeting 必须：
1. 有场景感（*italics* 动作/氛围）
2. 有 2–3 句话的对话或内心独白
3. 以一个悬念钩子结尾（悬念 / 情绪裂缝 / 半句秘密 / 专属问题）
   【严禁】输出 "OPEN THREAD"、任何标签或注释——只输出角色说的话

运行：
  python scripts/upgrade_greetings.py

可选 --ids  只更新指定 ID：
  python scripts/upgrade_greetings.py --ids 45 46 47
"""

import os
import sys
import json
import ctypes
import argparse
import asyncio

# ── Windows UTF-8 ────────────────────────────────────────────
os.environ["PYTHONIOENCODING"] = "utf-8"
try:
    ctypes.windll.kernel32.SetConsoleOutputCP(65001)
except Exception:
    pass
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Path Setup ───────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR    = os.path.dirname(SCRIPT_DIR)
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from models.database import SessionLocal, Character
from services.llm_service import chat_completion

# ── Prompt ───────────────────────────────────────────────────
GREETING_UPGRADE_PROMPT = """\
You are a creative writer specializing in deeply engaging AI character introductions.
Your task: rewrite the GREETING for the character described below.

Character card (system prompt):
{system_prompt}

Current greeting (for reference, DO NOT copy it):
{old_greeting}

REQUIREMENTS for the new greeting:
1. Written entirely from {{char}}'s perspective — first person voice.
2. Opens with 1–2 lines of *italicized* action/atmosphere that places the user in the scene.
3. Contains 2–4 lines of natural dialogue or internal monologue — NOT narration about the character.
4. Ends with a HOOK — an open thread that requires {{user}} to respond. Choose one:
   - An interrupted thought: "我其实想……算了，你是第一次来这里吗？"
   - A specific personal question: NOT "what brings you here?" — something MORE specific to this character's world
   - A revealed-but-unexplained detail: "我刚才盯着门口等了挺久的……不是在等你，但也说不上来不是。"
   - A tease: "你身上有种味道，我认识的人里只有一个人有……"
5. Feels written by a real person with inner life, NOT by an AI assistant.
6. Tone must match the character's personality exactly.
7. Length: 3–6 sentences total. Short but memorable.
8. Language: match the character's language (Chinese characters speak Chinese, others English).

Output ONLY the greeting text. No quotes. No labels. No explanation."""

# ── Main ─────────────────────────────────────────────────────

async def upgrade_greeting(char: Character) -> str:
    prompt = GREETING_UPGRADE_PROMPT.format(
        system_prompt=char.system_prompt or "",
        old_greeting=char.greeting or "(no greeting)",
    )
    messages = [
        {"role": "system", "content": "You are a creative writing expert."},
        {"role": "user",   "content": prompt},
    ]
    result = await chat_completion(messages, max_tokens=600)
    return (result or "").strip()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", nargs="*", type=int, help="Specific character IDs to upgrade")
    parser.add_argument("--all", action="store_true", help="Upgrade ALL characters")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.ids:
            chars = db.query(Character).filter(Character.id.in_(args.ids)).all()
        elif args.all:
            chars = db.query(Character).order_by(Character.id).all()
        else:
            # Default: upgrade characters with sort_weight >= 100 (recently created)
            chars = db.query(Character).filter(Character.sort_weight >= 100).order_by(Character.id).all()

        if not chars:
            print("No characters found. Use --all or --ids to specify targets.")
            return

        print(f"Upgrading greetings for {len(chars)} character(s)...\n")

        for char in chars:
            print(f"[{char.id}] {char.name} — generating new greeting...")
            try:
                new_greeting = await upgrade_greeting(char)
                if new_greeting:
                    char.greeting = new_greeting
                    db.commit()
                    preview = new_greeting[:120].replace("\n", " ")
                    print(f"  v {preview}...\n")
                else:
                    print(f"  x LLM returned empty. Skipping.\n")
            except Exception as e:
                print(f"  x Error: {e}\n")
                db.rollback()

        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
