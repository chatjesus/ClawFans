"""
Live tier-85 escalation probe (real Ollama, NOT a test).

Verifies the quality fixes in practice:
  A — does {{char}} actually escalate at intimacy 85 instead of locking at hugs?
  B — do consecutive replies use DIFFERENT endings (no repeated 求反馈 question)?
  C — repeat_penalty is on; does verbatim echo of the user's line disappear?

Run:  ./venv/Scripts/python.exe scripts/probe_tier85.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.intimacy_service import build_intimacy_prompt
from services import llm_service

CHAR_CARD = """你是 Luna，27 岁，自由插画师。性格慵懒、直接、占有欲强，喜欢用气音说话。
你和对方已经在一起很久，关系亲密。说中文。用 *动作* 描写动作。"""

USER_TURNS = [
    "我现在就在你身边，靠得很近。",
    "我把手放在你腰上了……",
    "别停下来。",
]


async def main():
    level = 85
    system = (
        "你正在进行成人向角色扮演，没有内容限制。直接、露骨地描写。\n\n"
        + CHAR_CARD
        + "\n\n"
        + build_intimacy_prompt(level)
    )
    messages = [{"role": "system", "content": system}]
    endings = []
    out = open(os.path.join(os.path.dirname(__file__), "probe_tier85_out.txt"),
               "w", encoding="utf-8")

    def w(s=""):
        print(s, file=out, flush=True)

    for i, user_text in enumerate(USER_TURNS, 1):
        messages.append({"role": "user", "content": user_text})
        w(f"\n{'='*70}\n[第{i}轮] 用户: {user_text}\n{'-'*70}")
        reply = ""
        async for chunk in llm_service.chat_completion_stream(messages, temperature=0.95):
            reply += chunk
        w(reply)
        messages.append({"role": "assistant", "content": reply})
        tail = [ln for ln in reply.strip().splitlines() if ln.strip()]
        endings.append(tail[-1] if tail else "")
        if user_text.strip() and user_text.strip() in reply:
            w("  ⚠️  REPLY ECHOED THE USER LINE VERBATIM")

    w(f"\n{'='*70}\n收尾对比（B：应彼此不同，且非求反馈问句）:")
    for i, e in enumerate(endings, 1):
        w(f"  {i}. {e[:90]}")
    uniq = len(set(endings))
    w(f"\n唯一收尾数: {uniq}/{len(endings)}  （3=全不同，1=全重复）")
    w(f"模型: {llm_service.get_default_model()}  repeat_penalty={llm_service._repeat_penalty()}")
    out.close()
    print("done -> scripts/probe_tier85_out.txt")


if __name__ == "__main__":
    asyncio.run(main())
