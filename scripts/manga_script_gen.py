# -*- coding: utf-8 -*-
"""
Stage 1 — LLM-based episode script generation for manga dramas.

Generates a structured JSON script with 6-8 scenes per episode,
including narration text, visual prompts, camera directions, and mood.

Usage:
  python scripts/manga_script_gen.py --char-id 53
  python scripts/manga_script_gen.py --char-id 53 --episode 2
"""

import sys, os, asyncio, json, argparse
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.platform == "win32":
    import ctypes; ctypes.windll.kernel32.SetConsoleOutputCP(65001)

BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from pathlib import Path
from models.database import SessionLocal, Character
from services.llm_service import chat_completion

NSFW_MODEL = "huihui_ai/qwen2.5-abliterate:14b"
SAFE_MODEL = "qwen2.5:14b"
FALLBACK_MODELS = ["qwen3:latest", "deepseek-r1:8b", "deepseek-r1:70b"]

OUTPUT_BASE = Path("uploads/manga")


async def llm(messages, temperature=0.8, max_tokens=2000, nsfw=False):
    preferred = [NSFW_MODEL, SAFE_MODEL] if nsfw else [SAFE_MODEL]
    for m in FALLBACK_MODELS:
        if m not in preferred:
            preferred.append(m)

    last_err = None
    for model in preferred:
        try:
            if model != preferred[0]:
                print(f"[Script] Fallback model → {model}")
            return await chat_completion(messages, temperature=temperature, max_tokens=max_tokens, model=model)
        except Exception as e:
            last_err = e
            if "not found" in str(e).lower():
                continue
            # Non "model not found" errors should bubble immediately.
            raise
    raise RuntimeError(f"No available LLM model among: {preferred}. Last error: {last_err}")


SCRIPT_SYSTEM_PROMPT = """\
你是一位专业的短剧编剧，擅长创作面向年轻人的都市情感短剧。
你需要为角色创作一集漫剧剧本，要求：

1. 每集包含 6-8 个场景
2. 每个场景有旁白台词（15-30字中文）、视觉描述、镜头指示、情绪氛围
3. 剧情需要有悬念、反转、情感钩子
4. 风格参考：活人感、真实感、"欲拒还迎"的张力
5. 视觉描述需要详细到可以直接用于图像生成（包含人物外貌、表情、服装、场景环境、光线）
6. 角色外貌描写要和角色设定一致

严格输出 JSON 格式，不要输出任何其他文字：
{
  "title": "剧集标题",
  "episode": 1,
  "character": {
    "name": "角色名",
    "appearance": "角色外貌特征概括（用于保持画面一致性）"
  },
  "scenes": [
    {
      "id": 0,
      "location": "场景地点",
      "time": "时间（如：深夜、黄昏、清晨）",
      "narration": "旁白/内心独白文字（15-30字中文）",
      "dialogue": "角色台词（如有，可为空）",
      "visual_prompt": "详细的画面描述，包含人物表情动作、服装、环境、光线、构图",
      "camera": "镜头类型：close-up / medium shot / wide shot / over-shoulder",
      "mood": "情绪氛围：warm / tense / romantic / melancholy / mysterious",
      "motion": "画面动态描述（如：头发被风吹起、手指轻触玻璃杯、缓缓转身）",
      "duration_sec": 4
    }
  ]
}"""


EPISODE_THEMES = [
    "初遇 —— 第一次见面，微妙的心动瞬间",
    "试探 —— 双方若有若无的靠近，暧昧升温",
    "冲突 —— 误解或外部压力导致的裂痕",
    "和解 —— 放下防备的一瞬间",
    "坦白 —— 情感爆发的高潮场景",
]


def _build_user_prompt(char: Character, episode: int = 1) -> str:
    theme = EPISODE_THEMES[(episode - 1) % len(EPISODE_THEMES)]
    return f"""请为以下角色创作第 {episode} 集漫剧剧本。

【角色信息】
- 姓名：{char.name}
- 标签：{char.tags or ''}
- 描述：{char.description or ''}
- 背景故事：{char.backstory or ''}
- 开场白：{char.greeting or ''}

【本集主题】{theme}

【要求】
- 6-8个场景，每个场景 3-5 秒
- 旁白用中文，画面描述用英文（便于图像生成）
- visual_prompt 必须包含角色外貌特征，且用英语 Danbooru 标签风格
- motion 描述动画方向，用简短英语
- 故事节奏：开头吸引注意 → 中间制造张力 → 结尾留下悬念

请直接输出 JSON："""


async def generate_script(char_id: int, episode: int = 1) -> dict:
    """Generate an episode script for a character, return parsed JSON."""
    db = SessionLocal()
    try:
        char = db.query(Character).filter(Character.id == char_id).first()
        if not char:
            raise ValueError(f"Character {char_id} not found")

        messages = [
            {"role": "system", "content": SCRIPT_SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(char, episode)},
        ]

        print(f"[Script] Generating episode {episode} for {char.name} (ID {char_id})...")
        raw = await llm(messages, temperature=0.85, max_tokens=3000, nsfw=True)

        # Extract JSON from response (handle markdown code blocks)
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            start = 1 if lines[0].startswith("```") else 0
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            raw = "\n".join(lines[start:end])

        script = json.loads(raw)

        # Validate structure
        assert "scenes" in script, "Missing 'scenes' in script"
        if not isinstance(script["scenes"], list) or not script["scenes"]:
            raise ValueError("Invalid script: 'scenes' must be a non-empty list")

        # Ensure each scene has required fields
        for i, scene in enumerate(script["scenes"]):
            scene.setdefault("id", i)
            scene.setdefault("duration_sec", 4)
            scene.setdefault("camera", "medium shot")
            scene.setdefault("mood", "warm")
            scene.setdefault("motion", "slight movement")
            scene.setdefault("dialogue", "")

        # Plan requires 6-8 scenes. Normalize count to keep pipeline stable.
        if len(script["scenes"]) < 6:
            last = script["scenes"][-1]
            for i in range(len(script["scenes"]), 6):
                cloned = dict(last)
                cloned["id"] = i
                cloned["narration"] = f"{last.get('narration', '她深吸一口气，故事还没有结束。')}"
                cloned["dialogue"] = last.get("dialogue", "")
                script["scenes"].append(cloned)
        elif len(script["scenes"]) > 8:
            script["scenes"] = script["scenes"][:8]

        # Save
        out_dir = OUTPUT_BASE / str(char_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"script_ep{episode}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(script, f, ensure_ascii=False, indent=2)

        print(f"[Script] Saved {len(script['scenes'])} scenes → {out_path}")
        return script
    finally:
        db.close()


async def main():
    parser = argparse.ArgumentParser(description="Generate manga drama script")
    parser.add_argument("--char-id", type=int, required=True)
    parser.add_argument("--episode", type=int, default=1)
    args = parser.parse_args()

    script = await generate_script(args.char_id, args.episode)
    print(f"\n=== {script.get('title', 'Untitled')} ===")
    for s in script["scenes"]:
        print(f"  Scene {s['id']}: [{s['camera']}] {s['narration']}")


if __name__ == "__main__":
    asyncio.run(main())
