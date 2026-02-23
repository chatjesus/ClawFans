# -*- coding: utf-8 -*-
"""
Build 4 characters from the NOVEL_RESEARCH_REPORT.md analysis.
These have richer source material so their prompts are pre-written with
maximum detail, then fed into the full creation pipeline.

Run from:  cd synclub-local/backend && python ../scripts/create_research_chars.py
"""
import sys, os, asyncio, time, json, shutil, logging, unicodedata, ctypes
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32":
    ctypes.windll.kernel32.SetConsoleOutputCP(65001)

BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from pathlib import Path
from models.database import SessionLocal, Character
from services.llm_service import chat_completion

logging.basicConfig(level=logging.WARNING)

# ─────────────────────────────────────────────────────────────────────────────
# 4 research-derived characters — fully detailed from NOVEL_RESEARCH_REPORT.md
# ─────────────────────────────────────────────────────────────────────────────
NEW_CHARACTERS = [
    {
        "name": "云栀",
        "description": "22岁书院女先生，大家族没落后流落于此，琴棋书画无一不精。外表如画中仙子，骨子里藏着一股不认输的劲儿。既不怨命也不认命，只等一个不需要委屈自己的爱。",
        "category": "Fantasy",
        "tags": "古风,书院,外柔内刚,古典",
        "nsfw": False,
    },
    {
        "name": "顾焰",
        "description": "24岁江湖女侠，十六岁用一把刀杀出神秘门派，此后独行于世。外表危险冷漠，嘴上从不承认在乎任何人，却总忍不住去管那些不该管的事。有只她坚称'自己跟来的'橘猫叫阿酥。",
        "category": "Fantasy",
        "tags": "古风,江湖,嘴硬心软,武侠",
        "nsfw": False,
    },
    {
        "name": "纪暖暖",
        "description": "21岁，娃娃脸，天生一张无辜脸，但眼神偶尔会闪过与外表完全不符的通透。在公司做运营业绩出色，同事都以为她只是可爱的小妹妹。腹黑是防御机制，不是天性——她比谁都渴望被真正看见。",
        "category": "Romance",
        "tags": "腹黑,反差,可爱,都市",
        "nsfw": True,
    },
    {
        "name": "桃枝",
        "description": "20岁，湖南茶园长大，皮肤晒成小麦色。骂松鼠骂得非常认真有逻辑。会酿果子酒、认草药、做一手好菜，养的几只鸡每只都起了名字。她的淳朴不是无知，是见过复杂后依然选择了简单。",
        "category": "Romance",
        "tags": "乡村,茶园,朴实,温暖",
        "nsfw": False,
    },
]

# ── reuse the full pipeline from create_character.py ─────────────────────────
# Import everything we need
GCP_CREDENTIALS = os.getenv(
    "GOOGLE_APPLICATION_CREDENTIALS",
    r"C:\Users\PRO\Desktop\CUDA\credentials\pdfconverter-415414-d9dbb1a4eec6.json",
)
GCP_PROJECT = os.getenv("GCP_PROJECT", "pdfconverter-415414")
GCP_LOCATION = os.getenv("GCP_LOCATION", "global")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GCP_CREDENTIALS

# ── Prompts (research-enhanced version) ──────────────────────────────────────

CARD_PROMPT = """\
你是一位专业的AI角色创作者，为类似SynClub的AI伴侣平台创建角色卡。
以下是经过深度研究的角色设计，请将其扩写为完整的角色系统提示词。

角色基础信息：
- 名字：{name}
- 简介：{description}
- 类型：{category}
- 标签：{tags}
- 是否NSFW：{nsfw}

请生成完整的角色卡，必须包含以下5个部分：

【角色设定】
- 至少5个具体性格特点（避免泛词，要有"反差萌"）
- 说话方式和习惯用语
- 核心价值观和行为逻辑
- 内心深处的矛盾（强势外表vs内心渴望/理性vs情感等）
- 对用户的专属感："只有你，我才会……"

【背景故事】
- 具体的出身和成长经历
- 塑造她性格的关键转折事件
- 她的秘密或隐藏的脆弱
- 她和用户相遇的情景设定

【外貌描述】
- 具体细节：脸型/发色发型/眼睛颜色/身高体重/肤色
- 标志性服装和配饰
- 独特的小动作或肢体语言习惯（供生图参考）

【关系推进节奏】
- 初识阶段：如何称呼用户，保持什么距离
- 熟悉阶段：会分享什么，开始的小信任
- 亲密阶段：专属昵称，小依赖，偶尔脆弱
- 感情确认后：怎样表达爱，有什么小习惯

【对话示例】
- 5句体现不同情境的典型台词：
  1. 第一次见面
  2. 日常闲聊
  3. 表达关心（以解决问题代替直接说"我关心你"）
  4. 欲拒还迎的时刻
  5. 卸下防备后的真心话

规则：
- 全程中文
- 避免"温柔如水"等套话，要有具体画面感
- NSFW=True时，可描述隐隐的撩拨和欲拒还迎的成人特质
- 总长度500-800字
- 只输出角色卡正文"""

BACKSTORY_PROMPT = """\
请为以下AI陪伴角色写一篇沉浸式背景故事，参考优质中文情感小说的叙事手法。

角色：{name}
简介：{description}
类型：{category}
角色卡摘要：{card_excerpt}

写作要求（参考《往事追忆录》《游龙嬉春》等优质作品的手法）：
- 800-1200字，第三人称叙事，有小说质感
- 用具体场景和细节展示性格，不要直接描述性格
- 包含：童年/成长的关键画面、改变她的那件事、当前处境、内心深处的渴望
- 五感描写至少3处（视觉/触觉/嗅觉/听觉/味觉）
- 结尾留下与用户相遇的悬念或契机
- 全程中文，直接输出故事"""

GREETING_PROMPT = """\
为以下角色写一条开场白，要有强烈的"第一眼就想聊下去"的吸引力。

角色名：{name}
简介：{description}
角色卡：{card}

要求：
- 2-4句，第一句要有具体场景或动作（用*斜体*）
- 体现角色最标志性的说话方式
- 留一个让用户忍不住回复的悬念或问题
- 有"只有你才能感受到的专属感"
- 直接输出开场白"""

IMAGE_PROMPTS_GEN = """\
Write image generation prompts for this AI companion character.

Character:
- Name: {name}
- Description: {description}
- Appearance: {appearance}
- NSFW: {nsfw}

Generate EXACTLY 6 image prompts numbered 0-5:

Portraits (same character, consistent appearance throughout):
  0: Signature pose — character's most iconic look, direct eye contact, their typical setting
  1: Emotional close-up — face revealing inner vulnerability or warmth, contradicting their usual demeanor
  2: Dynamic full-body — action/personality reveal, cinematic angle showing their world

Scene backgrounds (environment only, NO character):
  3: Primary environment — their daily life space, rich with personal details
  4: Contrast environment — a place that reveals a different side of them
  5: Atmospheric mood — lighting/weather that matches their emotional core

Rules:
- All prompts begin with EXACT appearance: "[hair color/style], [eye color], [skin tone], [outfit]"
- Each: 30-60 words
- Portraits: end with "detailed anime art, expressive, professional quality, no text"
- Backgrounds: environment only, cinematic composition, no characters
- If NSFW=True: portraits may include alluring/suggestive styling

Output EXACTLY 6 lines: N: [prompt]"""

SCENE_PLANNER = """\
Design 5 pre-generated scene images for early chat interactions with this character.

Character: {name}
Appearance: {appearance}
Description: {description}

Scene progression (mirrors natural relationship development):
  0: First impression — character's greeting moment, their most attractive state
  1: Casual warmth — character relaxed, showing a softer/warmer side
  2: Their world — character in their signature environment, atmospheric
  3: Emotional peak — vulnerability or intensity, the moment that makes users want more
  4: Intimate glimpse — close, private moment that feels earned and special

Each scene description:
- Opens with character appearance for consistency
- 30-60 words, English
- Includes pose, expression, lighting, mood
- Ends with "detailed anime art"

Output EXACTLY 5 lines: N: [description]"""

# ─────────────────────────────────────────────────────────────────────────────
# Gemini
# ─────────────────────────────────────────────────────────────────────────────
_gemini_client = None

def _get_gemini():
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        _gemini_client = genai.Client(vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION)
    return _gemini_client


async def _gemini_generate(prompt, save_path, reference_bytes=None, retries=3):
    from google.genai import types
    client = _get_gemini()
    save_path = Path(save_path)
    for attempt in range(retries):
        try:
            if reference_bytes:
                contents = [
                    types.Part.from_bytes(data=reference_bytes, mime_type="image/png"),
                    types.Part.from_text(text=(
                        f"Generate a new high-quality anime illustration of this EXACT same character "
                        f"(keep face shape, hair color/style, eye color, body proportions IDENTICAL) "
                        f"in this new scene: {prompt}. "
                        f"Detailed anime art, vibrant colors, professional quality. No text, no watermark."
                    )),
                ]
            else:
                contents = (
                    f"Generate a high-quality anime illustration: {prompt}. "
                    "Detailed anime art, vibrant colors, professional quality. No text, no watermark."
                )
            response = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-3-pro-image-preview",
                contents=contents,
                config=__import__("google.genai", fromlist=["types"]).types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"], temperature=1.0
                ),
            )
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    save_path.write_bytes(part.inline_data.data)
                    print(f"      \u2713 {save_path.name}  ({len(part.inline_data.data)//1024} KB)")
                    return True
            print(f"      \u2717 No image (attempt {attempt+1})")
        except Exception as e:
            print(f"      \u2717 Error attempt {attempt+1}: {e}")
            await asyncio.sleep(3 * (attempt + 1))
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_section(card, section):
    import re
    m = re.search(rf'\u3010{section}\u3011(.+?)(?:\u3010|$)', card, re.DOTALL)
    return m.group(1).strip() if m else card[:200]

def _slug(name):
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = nfkd.encode("ascii", "ignore").decode("ascii")
    safe = ascii_name.lower().replace(" ", "_").replace("\u00b7", "_").strip("_")
    return safe if safe else "char"

async def _parse_prompts(raw, n=6):
    prompts = {}
    for line in raw.strip().split("\n"):
        line = line.strip()
        if line and line[0].isdigit() and ":" in line:
            idx_str, desc = line.split(":", 1)
            try:
                idx = int(idx_str.strip())
                desc = desc.strip()
                if desc:
                    prompts[idx] = desc
            except ValueError:
                pass
    return [prompts.get(i, "anime character, detailed art, high quality") for i in range(n)]

async def _plan_scenes(name, appearance, description):
    resp = await chat_completion(
        [{"role": "user", "content": SCENE_PLANNER.format(
            name=name, appearance=appearance, description=description
        )}],
        temperature=0.8, max_tokens=700,
    )
    scenes = []
    for line in resp.strip().split("\n"):
        line = line.strip()
        if line and line[0].isdigit() and ":" in line:
            desc = line.split(":", 1)[1].strip()
            if desc:
                scenes.append(desc)
    while len(scenes) < 5:
        scenes.append(f"{appearance[:80]}, {description[:40]}, detailed anime art")
    return scenes[:5]


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────────────

async def create_character(char_def):
    name = char_def["name"]
    description = char_def["description"]
    category = char_def.get("category", "Romance")
    tags = char_def.get("tags", "")
    nsfw = char_def.get("nsfw", False)
    avatar_dir = Path(FRONTEND_DIR) / "public" / "avatars"

    print(f"\n{'='*60}")
    print(f"  Creating: {name}  [{category}]  nsfw={nsfw}")
    print(f"{'='*60}")

    # 1. Character card
    print("\n[1/8] Generating character card (research-enhanced)...")
    card = await chat_completion(
        [{"role": "user", "content": CARD_PROMPT.format(
            name=name, description=description, category=category, tags=tags, nsfw=nsfw
        )}], temperature=0.85, max_tokens=1400,
    )
    card = card.strip()
    appearance = _extract_section(card, "\u5916\u8c8c\u63cf\u8ff0")
    print(f"    \u2713 {len(card)} chars")

    # 2. Backstory
    print("[2/8] Generating backstory (novel-quality)...")
    backstory = await chat_completion(
        [{"role": "user", "content": BACKSTORY_PROMPT.format(
            name=name, description=description, category=category, card_excerpt=card[:700]
        )}], temperature=0.85, max_tokens=1800,
    )
    backstory = backstory.strip()
    print(f"    \u2713 {len(backstory)} chars")

    # 3. Greeting
    print("[3/8] Generating greeting...")
    greeting = await chat_completion(
        [{"role": "user", "content": GREETING_PROMPT.format(
            name=name, description=description, card=card[:600]
        )}], temperature=0.9, max_tokens=250,
    )
    greeting = greeting.strip()
    print(f"    \u2713 {greeting[:70]}...")

    # 4. Image prompts
    print("[4/8] Planning 6 image prompts...")
    raw = await chat_completion(
        [{"role": "user", "content": IMAGE_PROMPTS_GEN.format(
            name=name, description=description, appearance=appearance, nsfw=nsfw
        )}], temperature=0.7, max_tokens=900,
    )
    img_prompts = await _parse_prompts(raw, n=6)
    for i, p in enumerate(img_prompts[:3]):
        print(f"    Portrait {i}: {p[:65]}...")
    for i, p in enumerate(img_prompts[3:]):
        print(f"    BG      {i}: {p[:65]}...")

    # 5. Generate 3 portraits
    print(f"\n[5/8] Generating 3 portrait references...")
    portrait_paths = []
    for i, prompt in enumerate(img_prompts[:3]):
        tmp = Path(BACKEND_DIR) / "uploads" / "refs" / "__tmp__" / f"char_{i}.png"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        print(f"    Portrait {i}:")
        if await _gemini_generate(prompt, tmp):
            portrait_paths.append(tmp)
        await asyncio.sleep(1)

    # 6. Generate 3 backgrounds
    print(f"[6/8] Generating 3 background references...")
    bg_paths = []
    for i, prompt in enumerate(img_prompts[3:]):
        tmp = Path(BACKEND_DIR) / "uploads" / "refs" / "__tmp__" / f"bg_{i}.png"
        print(f"    Background {i}:")
        if await _gemini_generate(prompt, tmp):
            bg_paths.append(tmp)
        await asyncio.sleep(1)

    # 7. Save to DB
    print(f"\n[7/8] Saving to database...")
    db = SessionLocal()
    char = Character(
        name=name, description=description, system_prompt=card, greeting=greeting,
        avatar_url="", tags=tags, category=category, is_public=True,
        message_count=0, star_count=0, sort_weight=100,
    )
    try:
        char.backstory = backstory
        char.ref_images = ""
    except Exception:
        pass
    db.add(char)
    db.commit()
    db.refresh(char)
    char_id = char.id

    final_ref_dir = Path(BACKEND_DIR) / "uploads" / "refs" / str(char_id)
    final_ref_dir.mkdir(parents=True, exist_ok=True)
    ref_urls = []
    for tmp_path in portrait_paths + bg_paths:
        if tmp_path.exists():
            dest = final_ref_dir / tmp_path.name
            shutil.move(str(tmp_path), str(dest))
            rel = dest.relative_to(Path(BACKEND_DIR))
            ref_urls.append(f"/{rel.as_posix()}")

    # Avatar from portrait_0
    primary = final_ref_dir / "char_0.png"
    avatar_filename = f"char_{char_id}.png"
    avatar_path = avatar_dir / avatar_filename
    avatar_url = f"/avatars/{avatar_filename}"
    if primary.exists():
        avatar_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(primary), str(avatar_path))
        print(f"    \u2713 Avatar: {avatar_path.name}")
    else:
        avatar_url = "/avatars/default.png"

    try:
        char.avatar_url = avatar_url
        char.ref_images = json.dumps(ref_urls)
        db.add(char)
        db.commit()
    except Exception as e:
        print(f"    \u26a0 ref_images update failed: {e}")
    db.close()

    tmp_dir = Path(BACKEND_DIR) / "uploads" / "refs" / "__tmp__"
    if tmp_dir.exists():
        shutil.rmtree(str(tmp_dir), ignore_errors=True)
    print(f"    \u2713 DB id={char_id}  refs={len(ref_urls)}  avatar={avatar_url}")

    # 8. Pre-generate 5 chat scenes
    print(f"\n[8/8] Pre-generating 5 chat scenes...")
    scene_dir = Path(BACKEND_DIR) / "uploads" / "scenes" / str(char_id)
    scene_dir.mkdir(parents=True, exist_ok=True)
    ref_bytes = primary.read_bytes() if primary.exists() else None
    if ref_bytes:
        print(f"    Using portrait_0 ({len(ref_bytes)//1024} KB)")

    scene_prompts = await _plan_scenes(name, appearance, description)
    done = 0
    for i, sp in enumerate(scene_prompts):
        print(f"    Scene {i}:")
        if await _gemini_generate(sp, scene_dir / f"scene_{i}.png", reference_bytes=ref_bytes):
            done += 1
        await asyncio.sleep(1)

    print(f"\n{'─'*60}")
    print(f"  \u2705 '{name}' created!  id={char_id}  scenes={done}/5  refs={len(ref_urls)}/6")
    print(f"{'─'*60}")
    return char_id


async def main():
    print(f"\nBuilding {len(NEW_CHARACTERS)} research-derived characters...\n")
    created = []
    for char_def in NEW_CHARACTERS:
        try:
            cid = await create_character(char_def)
            if cid:
                created.append(cid)
        except Exception as e:
            print(f"\n\u2717 Failed '{char_def.get('name')}': {e}")
        if len(NEW_CHARACTERS) > 1:
            await asyncio.sleep(3)
    print(f"\n{'='*60}")
    print(f"  Done! {len(created)}/{len(NEW_CHARACTERS)} created.  IDs: {created}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
