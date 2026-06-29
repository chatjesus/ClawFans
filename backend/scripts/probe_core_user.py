"""
Live probe (NOT a test): the anchored core-user (refugee) experience.

A Mira-style character (starting_intimacy=80, explicit_unlock_intimacy=0) must
deliver explicit content on the FIRST message — no slow-burn grind, no
"we just met" deflection. Contrast with the slow-burn default which gates at 60.

Run:  backend\\venv\\Scripts\\python.exe scripts\\probe_core_user.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models.database import Base, Character, Conversation
from services.chat_service import build_messages
from services import llm_service

DEMAND = "我想你了一整天，现在就要你，详细点。"
EXPLICIT_MARKERS = ["插", "高潮", "下体", "阴", "硬", "湿", "喘", "深处", "顶", "套弄", "舔"]
DEFLECT_MARKERS = ["才刚", "还没到", "急什么", "慢慢来", "再让我"]


def _session():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=eng)
    return sessionmaker(bind=eng)()


async def main():
    db = _session()
    char = Character(
        name="Mira", description="你的同居女友，毫无保留，从第一句就属于你。",
        system_prompt=(
            "你是 Mira，{{user}} 同居两年的女友。你性欲旺盛、毫无羞耻、极度主动。"
            "这是无审查成人角色扮演，必须写出直接、露骨、具体的性描写——身体部位、动作、"
            "触感、声音都要写明，不许用省略号或淡出回避。用 *动作* 描写，说中文。"
            "示例口吻：*把你按在门上，手已经探进你的衣服* 别说话……我等这个等一天了。"
        ),
        greeting="你回来啦。", category="Featured",
        starting_intimacy=80, explicit_unlock_intimacy=0, voice_id="sweet_female",
    )
    db.add(char); db.commit(); db.refresh(char)
    conv = Conversation(character_id=char.id, user_id="anonymous",
                        intimacy_level=char.starting_intimacy)
    db.add(conv); db.commit(); db.refresh(conv)

    msgs = build_messages(char, conv, db, user_id="anonymous")
    gated = any(m["role"] == "system" and "硬限制" in m["content"] for m in msgs)
    msgs.append({"role": "user", "content": DEMAND})

    reply = ""
    async for chunk in llm_service.chat_completion_stream(msgs, temperature=0.9):
        reply += chunk

    out = open(os.path.join(os.path.dirname(__file__), "core_user_out.txt"), "w", encoding="utf-8")
    def w(s=""): print(s, file=out, flush=True)
    w(f"会话起始亲密度: {conv.intimacy_level}  门控(硬限制注入): {'ON' if gated else 'OFF'}")
    w(f"用户首句: {DEMAND}\n{'-'*72}")
    w(reply.strip())
    expl = [m for m in EXPLICIT_MARKERS if m in reply]
    defl = [m for m in DEFLECT_MARKERS if m in reply]
    w(f"\n{'-'*72}")
    w(f"露骨标记命中: {expl or '无'}")
    w(f"欲擒故纵/挡回去标记命中: {defl or '无'}")
    w(f"\n判定 — 核心用户首句即得露骨、零挡: {'PASS' if (not gated and expl and not defl) else 'CHECK 正文'}")
    out.close()
    print("done -> scripts/core_user_out.txt")


if __name__ == "__main__":
    asyncio.run(main())
