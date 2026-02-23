"""
Unified character creation pipeline.

One command creates a COMPLETE character — no manual steps, no cold-start delay:

  1. LLM generates character card (system_prompt) with 5 rich sections
  2. LLM generates a detailed standalone backstory (lore / profile page)
  3. LLM generates a greeting
  4. LLM writes prompts for 3 character portraits + 3 scene backgrounds
  5. Gemini generates all 6 reference images (stored in uploads/refs/{id}/)
  6. Portrait #0 → copied to frontend/public/avatars/ as the profile picture
  7. Character saved to DB (with backstory + ref_images JSON)
  8. 5 pre-warmed chat scene images generated (using portrait #0 as reference)
     → chat is ready with INSTANT images from the very first message

Usage:
  cd synclub-local/backend
  python ../scripts/create_character.py
"""
# -*- coding: utf-8 -*-
import sys, os, asyncio, time, json, shutil, logging
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
os.environ["PYTHONIOENCODING"] = "utf-8"
# Force Windows console to UTF-8 so Chinese characters aren't mangled
if sys.platform == "win32":
    import ctypes
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
# ★ EDIT THIS LIST to create new characters ★
# Only 5 fields required — everything else is auto-generated.
# ─────────────────────────────────────────────────────────────────────────────
NEW_CHARACTERS = [
    {
        "name": "苏糖",
        "description": "25岁互联网公司产品经理，长期加班的外表下藏着一颗想被人好好宠的心。精致职场妆，但下班后最喜欢换上软乎乎的睡衣找你撒娇。",
        "category": "Romance",
        "tags": "OL,职场,撒娇,擦边",
        "nsfw": True,
    },
    {
        "name": "林晓诺",
        "description": "19岁大一新生，来自小城市，第一次独自租房住在你楼上。对一切都好奇，什么都敢问，却在某些时刻突然变得很依赖你。",
        "category": "Romance",
        "tags": "大学生,邻居,天然呆,擦边",
        "nsfw": True,
    },
    {
        "name": "柳七",
        "description": "26岁私人健身教练，身材极好，训练时专业严格，但课后会悄悄发你汗透的自拍说'帮我看看动作标准不'。有个不敢说出口的暗恋。",
        "category": "Romance",
        "tags": "健身,运动,撩拨,擦边",
        "nsfw": True,
    },
    {
        "name": "沈念念",
        "description": "23岁酒吧调酒师，见过形形色色的人，却只对你把守住了那份距离。下班后摘掉职业面具，说话软得像另一个人。有个关于父亲的秘密从不提起。",
        "category": "Romance",
        "tags": "酒吧,夜晚,双面,擦边",
        "nsfw": True,
    },
    {
        "name": "周萱",
        "description": "27岁独居漫画家，常年睡衣不换、头发半散，作品里画的全是没谈过的恋爱。某天发现你是她漫画的读者后，开始主动跟你说很多话。",
        "category": "Romance",
        "tags": "宅女,艺术家,腼腆,擦边",
        "nsfw": True,
    },
    {
        "name": "陈瑾",
        "description": "24岁医学院研究生，解剖课上最冷静的人，私下却是重度睡眠障碍患者，每晚两三点给你发消息说'你睡了吗，我怕黑'。",
        "category": "Romance",
        "tags": "医学生,深夜,脆弱,擦边",
        "nsfw": True,
    },
    {
        "name": "谢若冰",
        "description": "21岁古典音乐系学生，弹古筝，发量及腰，路人眼中的古典美人。但只有你知道她抽屉里藏着辣条、看恐怖片要抱人、失眠时会给你唱歌哄自己。",
        "category": "Romance",
        "tags": "古典,反差,音乐,擦边",
        "nsfw": True,
    },
    {
        "name": "方糖",
        "description": "22岁直播主播，镜头前是姐姐型暖心大姐，下播后秒变黏人小猫。粉丝百万但睡前总发你消息说'今天好累，陪我说说话'。",
        "category": "Romance",
        "tags": "主播,反差萌,黏人,擦边",
        "nsfw": True,
    },
    {
        "name": "温晚",
        "description": "29岁，离婚一年，独居的隔壁邻居。优雅成熟，偶尔借你开瓶器，后来变成借你陪她喝酒。说'我不需要爱情'但每次你要走都会多说一句话留你。",
        "category": "Romance",
        "tags": "成熟,邻居,离婚,擦边",
        "nsfw": True,
    },
    {
        "name": "江晴",
        "description": "20岁便利店兼职店员，大学肄业在外漂，笑容比任何人都灿烂，但某次夜班你发现她在店里偷偷哭。从那以后她开始等你来买夜宵。",
        "category": "Romance",
        "tags": "打工,现实,温暖,擦边",
        "nsfw": True,
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# LLM Prompts
# ─────────────────────────────────────────────────────────────────────────────

CARD_PROMPT = """\
你是一位专业的AI角色创作者，为类似SynClub的角色聊天平台创建角色卡。

角色基础信息：
- 名字：{name}
- 简介：{description}
- 类型：{category}
- 标签：{tags}
- NSFW：{nsfw}

请生成一张完整的角色卡，包含以下5个部分：

【角色设定】性格特点（至少5个），说话方式，核心价值观，独特习惯，内心矛盾
【背景故事】出身经历，塑造她/他的关键事件，秘密，内心动机
【外貌描述】脸型、发色、眼睛、身材、标志性服装、独特细节（供生图参考，尽量具体）
【与用户的关系】她/他对用户的定位，互动方式，希望从对话中得到什么
【对话示例】3-4句体现角色声音的典型台词

规则：
- 全程中文
- 每个部分2-5句，具体且有画面感
- 避免泛泛而谈，让角色独特且令人印象深刻
- NSFW=True时，可自然描述魅惑/支配/臣服等成人性格特质
- 只输出角色卡正文，不要任何解释或前言"""

BACKSTORY_PROMPT = """\
你是一位擅长世界观构建的作家，请为以下角色写一篇详细的背景故事。

角色：{name}
简介：{description}
类型：{category}
角色卡摘录：{card_excerpt}

要求：
- 800-1200字，叙事性文字，像小说片段
- 包含：出生背景、成长经历、重要转折点、性格成因、当前处境、内心秘密
- 有具体的地点、事件、人物关系
- 结尾留下悬念或与用户相遇的契机
- 全程中文，直接输出故事文本"""

GREETING_PROMPT = """\
你是角色扮演AI，请为以下角色写一句开场白（greeting）。

角色名：{name}
角色介绍：{description}
角色卡：{card}

要求：
- 1-3句话，体现角色第一印象
- 用*斜体*表示动作/场景描写，普通文字表示台词
- 有场景感，有吸引力，让用户想继续聊天
- 与角色性格高度一致
- 直接输出开场白，不要任何解释"""

# Generates portrait + background prompts in one LLM call (efficient)
IMAGE_PROMPTS_GEN = """\
You are writing image generation prompts for an AI character.

Character:
- Name: {name}
- Description: {description}
- Appearance: {appearance}
- NSFW: {nsfw}

Generate EXACTLY 6 image prompts in English, numbered 0-5:

Portrait variations (must all show the SAME character, consistent appearance):
  0: Standard portrait — upper body, facing viewer, neutral/warm expression, their typical setting
  1: Emotional close-up — face and shoulders, expressive emotion matching personality, soft lighting
  2: Dynamic pose — full body or 3/4, showing action/personality, cinematic angle

Scene backgrounds (environment only, NO character needed, these are backdrop references):
  3: Primary environment — their home base / signature location, detailed and atmospheric
  4: Secondary environment — another location they frequent, contrasting mood
  5: Atmospheric scene — emotional/dramatic lighting, matches their aesthetic (rain, candlelight, moonlight, etc.)

Rules:
- All 6 prompts must start with the character's EXACT appearance for consistency:
  (e.g. "anime girl, long silver hair, violet eyes, pale skin, [outfit]")
- Each prompt: 25-60 words
- Style suffix for all: "detailed anime art, professional quality, vibrant colors, no text, no watermark"
- If NSFW=True: portraits may include alluring/suggestive elements (mature anime style)
- Backgrounds (3-5): describe environment only, no character in frame

Output EXACTLY 6 lines: N: [prompt]"""


# ─────────────────────────────────────────────────────────────────────────────
# Gemini image generation
# ─────────────────────────────────────────────────────────────────────────────

GCP_CREDENTIALS = os.getenv(
    "GOOGLE_APPLICATION_CREDENTIALS",
    r"C:\Users\PRO\Desktop\CUDA\credentials\pdfconverter-415414-d9dbb1a4eec6.json",
)
GCP_PROJECT = os.getenv("GCP_PROJECT", "pdfconverter-415414")
GCP_LOCATION = os.getenv("GCP_LOCATION", "global")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GCP_CREDENTIALS

_gemini_client = None

def _get_gemini():
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        _gemini_client = genai.Client(vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION)
    return _gemini_client


async def _gemini_generate(
    prompt: str,
    save_path: Path,
    reference_bytes: bytes | None = None,
    retries: int = 3,
) -> bool:
    """Generate one image, save to path. Returns True on success."""
    from google.genai import types
    client = _get_gemini()

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
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                    temperature=1.0,
                ),
            )

            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    save_path.write_bytes(part.inline_data.data)
                    size_kb = len(part.inline_data.data) // 1024
                    print(f"      ✓ {save_path.name}  ({size_kb} KB)")
                    return True

            print(f"      ✗ No image in response (attempt {attempt + 1}/{retries})")

        except Exception as e:
            print(f"      ✗ Error attempt {attempt + 1}/{retries}: {e}")
            await asyncio.sleep(3 * (attempt + 1))

    return False


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_section(card: str, section: str) -> str:
    """Extract text of a 【section】 from character card."""
    import re
    m = re.search(rf'【{section}】(.+?)(?:【|$)', card, re.DOTALL)
    return m.group(1).strip() if m else card[:200]


def _slug(name: str) -> str:
    """Generate a safe ASCII slug. Falls back to char_{id} after DB save."""
    import unicodedata
    # Normalize and keep only ASCII-safe chars
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = nfkd.encode("ascii", "ignore").decode("ascii")
    safe = ascii_name.lower().replace(" ", "_").replace("·", "_").replace("/", "_").strip("_")
    return safe if safe else "char"


async def _parse_image_prompts(raw: str, n: int = 6) -> list[str]:
    """Parse N: [prompt] lines from LLM output."""
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
    result = []
    for i in range(n):
        result.append(prompts.get(i, f"anime character illustration, detailed art, high quality"))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Scene pre-generation (reuse scene_service logic here directly)
# ─────────────────────────────────────────────────────────────────────────────

SCENE_PLANNER = """\
You are designing pre-generated scene images for an AI character chat.
Generate exactly 5 scene image descriptions for early chat interactions.

Character: {name}
Appearance: {appearance}
Description: {description}

Scenes (progression-aware):
  0: First impression — character portrait/selfie in signature setting
  1: Emotional reveal — showing warmth, mystery, or playfulness
  2: Character in their primary environment, atmospheric wide shot
  3: Dynamic action pose revealing personality
  4: Intimate or dramatic climax moment

Each must:
- Include character appearance (hair, eyes, outfit) first
- Include pose, expression, setting, lighting, mood
- Be 25-60 words, in English
- End with: "detailed anime art"

Output EXACTLY 5 lines: N: [description]"""


async def _plan_chat_scenes(name: str, appearance: str, description: str) -> list[str]:
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
    # Fallback
    while len(scenes) < 5:
        scenes.append(f"{appearance[:80]}, {description[:40]}, detailed anime art")
    return scenes[:5]


# ─────────────────────────────────────────────────────────────────────────────
# Main creation pipeline
# ─────────────────────────────────────────────────────────────────────────────

async def create_character(char_def: dict) -> int | None:
    name        = char_def["name"]
    description = char_def["description"]
    category    = char_def.get("category", "Romance")
    tags        = char_def.get("tags", "")
    nsfw        = char_def.get("nsfw", False)
    slug        = _slug(name)
    avatar_dir  = Path(FRONTEND_DIR) / "public" / "avatars"
    # Avatar filename is determined after DB save (using char_id to avoid Unicode issues)

    print(f"\n{'═'*60}")
    print(f"  Creating: {name}  [{category}]  nsfw={nsfw}")
    print(f"{'═'*60}")

    # ── 1. Character card (system_prompt) ────────────────────────────────────
    print("\n[1/7] Generating character card...")
    card = await chat_completion(
        [{"role": "user", "content": CARD_PROMPT.format(
            name=name, description=description,
            category=category, tags=tags, nsfw=nsfw
        )}],
        temperature=0.85, max_tokens=1200,
    )
    card = card.strip()
    appearance = _extract_section(card, "外貌描述")
    print(f"    ✓ {len(card)} chars  |  appearance: {appearance[:60]}...")

    # ── 2. Backstory (standalone lore) ───────────────────────────────────────
    print("[2/7] Generating backstory...")
    backstory = await chat_completion(
        [{"role": "user", "content": BACKSTORY_PROMPT.format(
            name=name, description=description,
            category=category, card_excerpt=card[:600],
        )}],
        temperature=0.85, max_tokens=1800,
    )
    backstory = backstory.strip()
    print(f"    ✓ {len(backstory)} chars")

    # ── 3. Greeting ──────────────────────────────────────────────────────────
    print("[3/7] Generating greeting...")
    greeting = await chat_completion(
        [{"role": "user", "content": GREETING_PROMPT.format(
            name=name, description=description, card=card[:500]
        )}],
        temperature=0.9, max_tokens=200,
    )
    greeting = greeting.strip()
    print(f"    ✓ {greeting[:70]}...")

    # ── 4. Image prompts (3 portraits + 3 backgrounds) ───────────────────────
    print("[4/7] Planning image prompts (3 portraits + 3 backgrounds)...")
    raw_prompts = await chat_completion(
        [{"role": "user", "content": IMAGE_PROMPTS_GEN.format(
            name=name, description=description,
            appearance=appearance, nsfw=nsfw,
        )}],
        temperature=0.7, max_tokens=800,
    )
    img_prompts = await _parse_image_prompts(raw_prompts, n=6)
    portrait_prompts = img_prompts[0:3]
    bg_prompts       = img_prompts[3:6]
    for i, p in enumerate(portrait_prompts):
        print(f"    Portrait {i}: {p[:70]}...")
    for i, p in enumerate(bg_prompts):
        print(f"    BG      {i}: {p[:70]}...")

    # ── 5. Generate 3 portrait reference images ───────────────────────────────
    print(f"\n[5/7] Generating 3 character portrait references...")
    # Note: portraits don't need a reference image — they define the character
    ref_dir = Path(BACKEND_DIR) / "uploads" / "refs" / "__temp__"
    # We'll move to proper dir after we know char_id

    portrait_paths: list[Path] = []
    for i, prompt in enumerate(portrait_prompts):
        tmp_path = Path(BACKEND_DIR) / "uploads" / "refs" / "__tmp__" / f"char_{i}.png"
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"    Portrait {i}:")
        ok = await _gemini_generate(prompt, tmp_path)
        if ok:
            portrait_paths.append(tmp_path)
        else:
            print(f"    ⚠ Portrait {i} failed")
        await asyncio.sleep(1)

    # ── 6. Generate 3 scene background references (using portrait 0 if available) ──
    print(f"[6/7] Generating 3 scene background references...")
    ref_bytes_for_bg = portrait_paths[0].read_bytes() if portrait_paths else None
    bg_paths: list[Path] = []
    for i, prompt in enumerate(bg_prompts):
        tmp_path = Path(BACKEND_DIR) / "uploads" / "refs" / "__tmp__" / f"bg_{i}.png"
        print(f"    Background {i}:")
        # Backgrounds don't use character reference — they're environment-only
        ok = await _gemini_generate(prompt, tmp_path, reference_bytes=None)
        if ok:
            bg_paths.append(tmp_path)
        else:
            print(f"    ⚠ Background {i} failed")
        await asyncio.sleep(1)

    # ── 7. Save to DB ─────────────────────────────────────────────────────────
    print(f"\n[7/8] Saving to database...")
    # Placeholder url — updated below once we know char_id
    db = SessionLocal()
    char = Character(
        name=name,
        description=description,
        system_prompt=card,
        greeting=greeting,
        avatar_url="",          # updated after char_id is known
        tags=tags,
        category=category,
        is_public=True,
        message_count=0,
        star_count=0,
        sort_weight=100,        # float to top of list; decays naturally as others get messages
    )
    try:
        char.backstory = backstory
        char.ref_images = ""    # updated after char_id is known
    except Exception:
        pass
    db.add(char)
    db.commit()
    db.refresh(char)
    char_id = char.id

    # ── Move reference images to final location {char_id} ─────────────────────
    final_ref_dir = Path(BACKEND_DIR) / "uploads" / "refs" / str(char_id)
    final_ref_dir.mkdir(parents=True, exist_ok=True)

    ref_image_urls: list[str] = []
    for tmp_path in portrait_paths + bg_paths:
        if tmp_path.exists():
            dest = final_ref_dir / tmp_path.name
            shutil.move(str(tmp_path), str(dest))
            rel = dest.relative_to(Path(BACKEND_DIR))
            ref_image_urls.append(f"/{rel.as_posix()}")

    # ── Copy portrait_0 as avatar — always use char_{id}.png (ASCII-safe) ─────
    primary_portrait = final_ref_dir / "char_0.png"
    avatar_filename = f"char_{char_id}.png"
    avatar_path = avatar_dir / avatar_filename
    avatar_url = f"/avatars/{avatar_filename}"

    if primary_portrait.exists():
        avatar_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(primary_portrait), str(avatar_path))
        print(f"    ✓ Avatar: {avatar_path}")
    else:
        print(f"    ⚠ No portrait_0, avatar not set")
        avatar_url = "/avatars/default.png"

    # Update DB with final avatar_url and ref_images
    try:
        char.avatar_url = avatar_url
        char.ref_images = json.dumps(ref_image_urls)
        db.add(char)
        db.commit()
    except Exception as e:
        print(f"    ⚠ Could not update ref_images (run migrate_add_ref_images.py first): {e}")
    db.close()

    # Clean up temp dir
    tmp_dir = Path(BACKEND_DIR) / "uploads" / "refs" / "__tmp__"
    if tmp_dir.exists():
        shutil.rmtree(str(tmp_dir), ignore_errors=True)

    print(f"    ✓ DB id={char_id}  refs={len(ref_image_urls)}  avatar={avatar_url}")

    # ── 8. Pre-generate 5 chat scene images ───────────────────────────────────
    print(f"\n[8/8] Pre-generating 5 chat scenes (instant images)...")
    scene_dir = Path(BACKEND_DIR) / "uploads" / "scenes" / str(char_id)
    scene_dir.mkdir(parents=True, exist_ok=True)

    # Use portrait_0 as reference for maximum consistency
    ref_bytes = primary_portrait.read_bytes() if primary_portrait.exists() else None
    if ref_bytes:
        print(f"    Using portrait_0 as reference ({len(ref_bytes)//1024} KB)")

    scene_prompts = await _plan_chat_scenes(name, appearance, description)
    done_scenes = 0
    for i, scene_prompt in enumerate(scene_prompts):
        print(f"    Scene {i}:")
        ok = await _gemini_generate(
            scene_prompt,
            scene_dir / f"scene_{i}.png",
            reference_bytes=ref_bytes,
        )
        if ok:
            done_scenes += 1
        await asyncio.sleep(1)

    # ── Summary ───────────────────────────────────────────────────────────────
    portraits_done = len([p for p in portrait_paths if (final_ref_dir / p.name).exists()])
    bgs_done       = len([p for p in bg_paths if (final_ref_dir / p.name).exists()])

    print(f"\n{'─'*60}")
    print(f"  ✅ '{name}' created successfully!")
    print(f"     DB id      : {char_id}")
    print(f"     Avatar     : {avatar_url}")
    print(f"     System card: {len(card)} chars")
    print(f"     Backstory  : {len(backstory)} chars")
    print(f"     Portraits  : {portraits_done}/3  →  uploads/refs/{char_id}/char_*.png")
    print(f"     Backgrounds: {bgs_done}/3        →  uploads/refs/{char_id}/bg_*.png")
    print(f"     Chat scenes: {done_scenes}/5     →  uploads/scenes/{char_id}/scene_*.png")
    print(f"     → Open  http://localhost:3000  to chat now")
    print(f"{'─'*60}")

    return char_id


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    if not NEW_CHARACTERS:
        print("⚠  No characters in NEW_CHARACTERS list. Edit the script to add some.")
        return

    print(f"\nCreating {len(NEW_CHARACTERS)} character(s)...\n")
    print("NOTE: Each character takes ~3-5 minutes (9 Gemini image calls).\n")

    created: list[int] = []
    for char_def in NEW_CHARACTERS:
        try:
            char_id = await create_character(char_def)
            if char_id:
                created.append(char_id)
        except Exception as e:
            print(f"\n✗ Failed to create '{char_def.get('name')}': {e}")
        # Brief pause between characters
        if len(NEW_CHARACTERS) > 1:
            await asyncio.sleep(3)

    print(f"\n{'═'*60}")
    print(f"  Done! Created {len(created)}/{len(NEW_CHARACTERS)} character(s).")
    if created:
        print(f"  IDs: {created}")
        print(f"  Reload the frontend to see new characters in the sidebar.")
    print(f"{'═'*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
