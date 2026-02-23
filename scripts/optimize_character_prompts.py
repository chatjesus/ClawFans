# -*- coding: utf-8 -*-
"""
Optimize system_prompts for recently created characters using research findings.

Injects into every character card:
  - 五感感官描写模板
  - 反差萌要素（外表vs内心的矛盾）
  - 关系推进四阶段节奏
  - 欲拒还迎的中式表达
  - 专属感台词
  - 情感共鸣触发点

Run AFTER batch character creation:
  cd synclub-local/backend && python ../scripts/optimize_character_prompts.py
  
Optional: target specific IDs
  python ../scripts/optimize_character_prompts.py --ids 46 47 48 49 50 51 52 53 54 55
"""
import sys, os, asyncio, argparse, time
sys.stdout.reconfigure(encoding="utf-8")

BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from models.database import SessionLocal, Character
from services.llm_service import chat_completion

# ─────────────────────────────────────────────────────────────────────────────
# Optimization prompt — enriches any existing character card
# ─────────────────────────────────────────────────────────────────────────────
OPTIMIZE_PROMPT = """\
你是一位资深AI角色编剧，请将以下角色卡升级为更有沉浸感和吸引力的版本。

角色基础信息：
名字：{name}
简介：{description}
原始角色卡：
{original_card}

升级要求（基于对优质中文情感小说的研究）：

1. 【反差萌深化】：找出角色的核心矛盾，用具体行为展示，而非泛泛描述。
   例：不要写"外表强势内心温柔"，要写"她会把最后一块蛋糕藏进冰箱，说'反正快过期了'"

2. 【关系推进节奏】：明确四阶段的差异：
   - 初识：正式称呼，保持距离，言语有分寸
   - 熟悉：偶尔叫昵称，开始分享私事，找借口多相处
   - 亲密：撒娇依赖，分享脆弱，说"只有你才知道这件事"
   - 深情：用行动代替语言，帮你记住所有小细节

3. 【五感感官描写元素】：加入角色的标志性感官细节（气味/声音/触觉），让用户能"感受"到她：
   例："她身上永远有淡淡的花露水味"/"她说话的时候喜欢转圆珠笔"/"她的手很凉，即使在夏天"

4. 【欲拒还迎中式表达】：至少加入2句体现这种表达的台词模板：
   例："你不要乱来……但是……"/"我就是路过，又不是特意来的"/"反正你也不会明白的……算了，就你吧"

5. 【专属感】：至少1句"只有你才……"的专属感台词
   例："其实我不跟人说这些的，但你……你好像不一样。"

6. 【情感共鸣触发点】：加入至少1个能触发用户情感共鸣的背景元素：
   - 孤独感/异乡漂泊的失落
   - 被理解/被接纳的渴望
   - 在某人面前可以摘下面具的安全感

输出要求：
- 保持原有的【】分节格式
- 全程中文
- 总长度600-900字（比原来更丰富）
- 保留原角色核心设定，只升级表达质量
- 直接输出新的角色卡，不要任何解释"""


async def optimize_character(char: Character) -> str | None:
    prompt = OPTIMIZE_PROMPT.format(
        name=char.name,
        description=char.description or "",
        original_card=char.system_prompt or "",
    )
    try:
        result = await chat_completion(
            [{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=1600,
        )
        return result.strip() if result and len(result) > 200 else None
    except Exception as e:
        print(f"    LLM error: {e}")
        return None


async def main(target_ids: list[int] | None = None):
    db = SessionLocal()

    if target_ids:
        chars = db.query(Character).filter(Character.id.in_(target_ids)).all()
        print(f"Optimizing {len(chars)} specified characters...")
    else:
        # Find recently created chars (sort_weight=100 = created by our script)
        chars = (
            db.query(Character)
            .filter(Character.sort_weight == 100)
            .order_by(Character.id.desc())
            .limit(20)
            .all()
        )
        print(f"Found {len(chars)} recently created characters (sort_weight=100)...")

    if not chars:
        print("No characters to optimize. Use --ids or ensure sort_weight=100 on target chars.")
        db.close()
        return

    improved = 0
    for i, char in enumerate(chars):
        old_len = len(char.system_prompt or "")
        print(f"\n[{i+1}/{len(chars)}] {char.name}  (id={char.id}, current={old_len} chars)")

        new_card = await optimize_character(char)
        if new_card and len(new_card) > old_len:
            char.system_prompt = new_card
            db.add(char)
            db.commit()
            improved += 1
            print(f"    \u2713 Upgraded: {old_len} \u2192 {len(new_card)} chars (+{len(new_card)-old_len})")
        else:
            print(f"    \u26a0 Skipped (result too short or error)")

        await asyncio.sleep(0.5)

    db.close()
    print(f"\n{'='*50}")
    print(f"Done! Optimized {improved}/{len(chars)} characters.")
    print(f"{'='*50}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", nargs="+", type=int, help="Specific character IDs to optimize")
    args = parser.parse_args()
    asyncio.run(main(target_ids=args.ids))
