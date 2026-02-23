# -*- coding: utf-8 -*-
"""
regen_images.py — 对已有角色重新生成 ref 图（头像/背景）和 scene 图

用法：
  python scripts/regen_images.py --ids 49 50 52 53 54
  python scripts/regen_images.py --new   # 所有 sort_weight>=100 的角色
"""

import sys, os, asyncio, json, shutil, time, uuid
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.platform == "win32":
    import ctypes
    ctypes.windll.kernel32.SetConsoleOutputCP(65001)

BACKEND_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from pathlib import Path
from models.database import SessionLocal, Character
from services.llm_service import chat_completion as _chat_base

NSFW_MODEL = "huihui_ai/qwen2.5-abliterate:14b"
SAFE_MODEL = "qwen2.5:14b"
COMFYUI_URL = "http://127.0.0.1:8188"

async def llm(messages, temperature=0.8, max_tokens=900, nsfw=False):
    model = NSFW_MODEL if nsfw else SAFE_MODEL
    return await _chat_base(messages, temperature=temperature, max_tokens=max_tokens, model=model)

# ── Provider detection ─────────────────────────────────────────────────────────

async def _comfyui_available() -> bool:
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(f"{COMFYUI_URL}/system_stats")
            return r.status_code == 200
    except Exception:
        return False

_provider_cache: str | None = None

async def _get_provider() -> str:
    global _provider_cache
    if _provider_cache is None:
        if await _comfyui_available():
            _provider_cache = "comfyui"
            print("  [provider] ComfyUI detected — using local generation")
        else:
            _provider_cache = "gemini"
            print("  [provider] ComfyUI not running — using Gemini")
    return _provider_cache

# ── ComfyUI generation ─────────────────────────────────────────────────────────

async def _get_comfyui_checkpoint() -> str | None:
    import httpx
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.get(f"{COMFYUI_URL}/object_info/CheckpointLoaderSimple")
        info = r.json()
        ckpts = info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
        for pref in ["noobai", "NoobAI", "illustrious", "pony", "animagine", "sdxl"]:
            for name in ckpts:
                if pref.lower() in name.lower():
                    return name
        return ckpts[0] if ckpts else None

def _build_workflow(positive: str, negative: str, checkpoint: str, seed: int) -> dict:
    is_vpred = any(x in checkpoint.lower() for x in ["vpred", "v_pred", "v-pred"])
    cfg = 3.5 if is_vpred else 6.5
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "3": {"class_type": "EmptyLatentImage", "inputs": {"width": 832, "height": 1216, "batch_size": 1}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": positive, "clip": ["1", 1]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
        "6": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0],
            "latent_image": ["3", 0], "seed": seed,
            "steps": 28, "cfg": cfg, "sampler_name": "euler_ancestral",
            "scheduler": "karras", "denoise": 1.0,
        }},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
        "8": {"class_type": "SaveImage", "inputs": {"filename_prefix": "synclub", "images": ["7", 0]}},
    }

COMFYUI_NEGATIVE = (
    "worst quality, low quality, lowres, bad anatomy, bad hands, missing fingers, "
    "extra digits, deformed, blurry, watermark, text, signature, multiple people, "
    "split screen, panel layout, border, frame, ugly, censored, mosaic"
)

async def _gen_image_comfyui(prompt: str, save_path: Path, nsfw: bool = False) -> bool:
    import httpx
    try:
        checkpoint = await _get_comfyui_checkpoint()
        if not checkpoint:
            print("      x No checkpoint found in ComfyUI")
            return False
        positive = f"masterpiece, best quality, ultra-detailed, 1girl, solo, {prompt}"
        seed = int(time.time() * 1000) % (2 ** 32)
        workflow = _build_workflow(positive, COMFYUI_NEGATIVE, checkpoint, seed)
        client_id = uuid.uuid4().hex
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(f"{COMFYUI_URL}/prompt",
                             content=json.dumps({"prompt": workflow, "client_id": client_id}),
                             headers={"Content-Type": "application/json"})
            r.raise_for_status()
            prompt_id = r.json()["prompt_id"]
        # Poll for result
        start = time.time()
        while time.time() - start < 180:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.get(f"{COMFYUI_URL}/history/{prompt_id}")
                history = r.json()
                if prompt_id in history:
                    for node_out in history[prompt_id].get("outputs", {}).values():
                        if "images" in node_out:
                            img = node_out["images"][0]
                            params = {"filename": img["filename"], "subfolder": img.get("subfolder",""), "type": img.get("type","output")}
                            async with httpx.AsyncClient(timeout=30.0) as dl:
                                ri = await dl.get(f"{COMFYUI_URL}/view", params=params)
                                ri.raise_for_status()
                                save_path.parent.mkdir(parents=True, exist_ok=True)
                                save_path.write_bytes(ri.content)
                                print(f"      + {save_path.name}  ({len(ri.content)//1024} KB)")
                                return True
            await asyncio.sleep(3)
        print("      x ComfyUI timeout")
        return False
    except Exception as e:
        print(f"      x ComfyUI error: {e}")
        return False

# ── GCP Gemini ────────────────────────────────────────────────────────────────
GCP_CREDENTIALS = os.getenv(
    "GOOGLE_APPLICATION_CREDENTIALS",
    r"C:\Users\PRO\Desktop\CUDA\credentials\pdfconverter-415414-d9dbb1a4eec6.json",
)
GCP_PROJECT  = os.getenv("GCP_PROJECT",  "pdfconverter-415414")
GCP_LOCATION = os.getenv("GCP_LOCATION", "global")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GCP_CREDENTIALS

_gemini_client = None
def _get_gemini():
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        _gemini_client = genai.Client(vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION)
    return _gemini_client

async def _gen_image_gemini(prompt: str, save_path: Path,
                            reference_bytes: bytes | None = None,
                            retries: int = 3) -> bool:
    from google.genai import types
    client = _get_gemini()
    for attempt in range(retries):
        try:
            if reference_bytes:
                contents = [
                    types.Part.from_bytes(data=reference_bytes, mime_type="image/png"),
                    types.Part.from_text(text=(
                        "Generate a new high-quality anime illustration of this EXACT same character "
                        "(keep face shape, hair color/style, eye color, body proportions IDENTICAL) "
                        f"in this new scene: {prompt}. "
                        "High quality anime art, vibrant colors. No text, no watermark."
                    )),
                ]
            else:
                contents = (
                    f"Generate a high-quality anime illustration: {prompt}. "
                    "High quality anime art, vibrant colors. No text, no watermark."
                )
            response = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-3-pro-image-preview",
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"], temperature=1.0,
                ),
            )
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    save_path.write_bytes(part.inline_data.data)
                    print(f"      + {save_path.name}  ({len(part.inline_data.data)//1024} KB)")
                    return True
            print(f"      x No image (attempt {attempt+1})")
        except Exception as e:
            print(f"      x Error attempt {attempt+1}: {e}")
            await asyncio.sleep(3 * (attempt + 1))
    return False

async def _gen_image(prompt: str, save_path: Path,
                     reference_bytes: bytes | None = None,
                     nsfw: bool = False,
                     retries: int = 3) -> bool:
    """Route to ComfyUI if available, else Gemini."""
    provider = await _get_provider()
    if provider == "comfyui":
        return await _gen_image_comfyui(prompt, save_path, nsfw=nsfw)
    else:
        return await _gen_image_gemini(prompt, save_path, reference_bytes=reference_bytes, retries=retries)

# ── Image prompt templates ─────────────────────────────────────────────────────

# ── Prompt templates ──────────────────────────────────────────────────────────
# SDXL (ComfyUI/NoobAI): short comma-separated Danbooru tags, no natural language
# Gemini: natural language English description

IMAGE_PROMPTS_GEN_GEMINI = """\
You are writing image generation prompts for an AI character.

Character:
- Name: {name}
- Description: {description}
- Appearance: {appearance}
- NSFW: {nsfw}

Generate EXACTLY 6 image prompts in English, numbered 0-5:

Portrait variations (SAME character, consistent appearance):
  0: Signature portrait — upper body, facing viewer, signature setting
  1: Emotional close-up — face & shoulders, expressive emotion
  2: Dynamic — 3/4 or full body, action/personality moment

Scene backgrounds (environment only, NO character):
  3: Primary environment — home/work, rich atmosphere
  4: Secondary location — contrasting mood
  5: Emotional scene — matching inner world (candlelight, moonlight, rain, etc.)

Rules:
- Portraits: start with EXACT appearance (e.g. "seductive anime girl, long black hair, violet eyes")
- CRITICAL COMPOSITION (ALL portraits): ONE person ONLY, centered, NO split screen, NO collage, NO panels, single shot
- Each prompt: 40-80 words
- Style suffix: "ecchi anime fanservice style, single character centered, no split screen, vibrant colors, no text, no watermark"
- NSFW=True: TARGET STYLE = anime pinup / ecchi fanservice. Requirements:
    * Portrait 0: [exact appearance], seductive anime girl, revealing outfit with deep V neckline or low-cut top,
      tight form-fitting clothes, slim waist showing, confident alluring smile, ecchi anime pinup style, vivid colors
    * Portrait 1: [exact appearance], close-up, sultry bedroom eyes, slightly parted lips, flushed cheeks,
      hair falling softly, seductive expression, warm soft lighting from below, ecchi anime style
    * Portrait 2: [exact appearance], full body, revealing fantasy/modern outfit showing midriff and thighs,
      sitting or leaning suggestively, gorgeous curves, legs visible, anime fanservice pinup pose, ecchi style
    * BANNED words: "tasteful", "elegant", "dignified"
- NSFW=False: expressive and charming, tasteful
- Backgrounds (3-5): environment only, atmospheric, NO character

Output EXACTLY 6 lines: N: [prompt]"""


IMAGE_PROMPTS_GEN_SDXL = """\
You are writing Danbooru-style tag prompts for Stable Diffusion XL (NoobAI/Illustrious).
CRITICAL: ALL output must be ENGLISH ONLY. Translate everything — NO Chinese, NO Japanese.
Output SHORT comma-separated English tags only — NO sentences, NO natural language.

Character (translate ALL details to English tags):
- Name: {name}
- Description: {description}
- Appearance: {appearance}
- NSFW: {nsfw}

CRITICAL: ALL tags must be ENGLISH ONLY. Translate any Chinese/Japanese appearance details to English.
Example: "黑色长发" → "long black hair", "大眼睛" → "large eyes", "上海白领" → "office lady"

Generate EXACTLY 6 tag prompts numbered 0-5 — ALL IN ENGLISH:

Portraits 0-2 (character only, ONE girl, solo):
  0: NSFW=True → cowboy shot (thighs to head), facing viewer, busty figure on display
     NSFW=False → upper body, facing viewer, friendly expression
  1: Close-up face and shoulders, expressive emotional look
  2: Full body or 3/4 body, showing complete figure and outfit

Backgrounds 3-5 (environment only, NO character):
  3: Primary setting (bedroom / café / office / etc.)
  4: Secondary location
  5: Atmospheric scene (night / rain / candlelight)

Rules for NSFW=True portraits — MANDATORY:
  - ALWAYS use cowboy shot for portrait 0 (shows legs AND cleavage)
  - MUST include ALL of: {nsfw_portrait_tags}
  - Outfit: MUST be revealing — low-cut blouse, mini skirt, lingerie, or bikini
  - NEVER use: suit, formal wear, modest, fully clothed, office suit
  - Expression: seductive smile, bedroom eyes, blush, parted lips
  - Lighting: soft warm lighting, ambient glow

Rules for NSFW=False:
  - Outfit: school uniform, casual wear, maid outfit, cute dress
  - Expression: smile, happy, gentle

Quality tags already added externally — do NOT include: masterpiece, best quality, 1girl, solo

Output EXACTLY 6 lines, ALL ENGLISH: N: tag1, tag2, tag3, ..."""


SCENE_PLANNER_GEMINI = """\
Design 5 pre-generated scene images for an AI companion chat.

Character: {name}
Appearance: {appearance}
Description: {description}
NSFW: {nsfw}

Scene progression:
  0: First impression — character in signature setting, attractive and intriguing
  1: Flirty/playful — showing charm and allure
  2: Atmospheric wide shot — their world, mood-setting
  3: Personality reveal — expressive pose showing who they really are
  4: Intimate/sensual — close, personal, emotionally and physically charged

Rules:
- Start each with character appearance (hair, eyes, outfit)
- Include pose, expression, setting, lighting, emotional atmosphere
- NSFW=True: Be visually alluring. Use "revealing outfit", "seductive pose",
  "soft candlelight", "intimate atmosphere", "sensual expression", "ecchi anime style".
  Scenes 1 and 4 especially should be suggestive and show attractive figure
- 30-70 words each in English
- End each with: "high quality anime art"

Output EXACTLY 5 lines: N: [description]"""


SCENE_PLANNER_SDXL = """\
Write 5 Danbooru-style English tag prompts for Stable Diffusion XL chat scenes.
CRITICAL: ALL output must be ENGLISH ONLY — translate any non-English text to English tags.
Output SHORT comma-separated English tags — NO sentences, NO Chinese, NO Japanese.

Character: {name}
Appearance (translate to English tags): {appearance}
NSFW: {nsfw}

Scene progression:
  0: First impression — signature setting, attractive
  1: Flirty/playful — charm and allure
  2: Atmospheric — character in their world
  3: Personality reveal — expressive pose
  4: Intimate/sensual — close and personal

NSFW=True scene tags to include:
  {nsfw_portrait_tags}, intimate lighting, soft glow, sensual pose, seductive expression, bedroom eyes

Quality tags already added — do NOT repeat: masterpiece, best quality, 1girl, solo

Output EXACTLY 5 lines, ALL ENGLISH: N: tag1, tag2, ..."""


# Ecchi/fanservice style — suggestive body appeal, NOT fully nude
# Key: cowboy shot shows both cleavage AND legs; slim waist + wide hips = hourglass figure
NSFW_PORTRAIT_TAGS_SDXL = (
    "large breasts, huge breasts, busty, cleavage, low-cut dress, revealing outfit, "
    "slim waist, wide hips, long legs, bare thighs, cowboy shot, "
    "seductive smile, bedroom eyes, alluring pose, ecchi, fanservice"
)
NSFW_PORTRAIT_TAGS_GEMINI = (
    "alluring, sensual, voluptuous figure, large breasts with cleavage, "
    "slim waist, wide hips, long bare legs, revealing outfit, seductive smile"
)


def _get_prompt_template(provider: str, nsfw: bool, for_scenes: bool = False) -> str:
    if provider == "comfyui":
        return SCENE_PLANNER_SDXL if for_scenes else IMAGE_PROMPTS_GEN_SDXL
    else:
        return SCENE_PLANNER_GEMINI if for_scenes else IMAGE_PROMPTS_GEN_GEMINI


def _get_nsfw_tags(provider: str) -> str:
    return NSFW_PORTRAIT_TAGS_SDXL if provider == "comfyui" else NSFW_PORTRAIT_TAGS_GEMINI


def _extract_section(card: str, section: str) -> str:
    import re
    m = re.search(rf'【{section}】(.+?)(?:【|$)', card, re.DOTALL)
    return m.group(1).strip() if m else card[:300]


async def _parse_prompts(raw: str, n: int) -> list[str]:
    prompts = {}
    for line in raw.strip().split("\n"):
        line = line.strip()
        if line and line[0].isdigit() and ":" in line:
            idx_str, desc = line.split(":", 1)
            try:
                idx = int(idx_str.strip())
                if desc.strip():
                    prompts[idx] = desc.strip()
            except ValueError:
                pass
    return [prompts.get(i, "anime character illustration, high quality art") for i in range(n)]


async def regen_char_images(char: Character, skip_refs: bool = False, skip_scenes: bool = False, force_nsfw: bool = False):
    name = char.name
    desc = char.description or ""
    tags = char.tags or ""
    appearance = _extract_section(char.system_prompt or "", "外貌描述")
    if not appearance or len(appearance) < 20:
        appearance = desc[:200]

    # Detect nsfw
    cat_nsfw = (char.category or "") in ["NSFW", "Romance", "Roleplay", "Drama", "Fantasy"]
    tag_nsfw = any(kw in tags for kw in ["NSFW","nsfw","擦边","成人","SM","Bondage"])
    nsfw = force_nsfw or cat_nsfw or tag_nsfw

    provider = await _get_provider()
    print(f"\n[{char.id}] {name}  nsfw={nsfw}  provider={provider}")
    print(f"  appearance: {appearance[:80]}...")

    avatar_dir    = Path(FRONTEND_DIR) / "public" / "avatars"
    final_ref_dir = Path(BACKEND_DIR) / "uploads" / "refs" / str(char.id)
    scene_dir     = Path(BACKEND_DIR) / "uploads" / "scenes" / str(char.id)

    # ── 1. Re-generate 6 ref images ───────────────────────────────────────────
    if not skip_refs:
        print("  Generating image prompts...")
        tpl = _get_prompt_template(provider, nsfw, for_scenes=False)
        nsfw_tags = _get_nsfw_tags(provider)
        raw = await llm(
            [{"role": "user", "content": tpl.format(
                name=name, description=desc, appearance=appearance, nsfw=nsfw,
                nsfw_portrait_tags=nsfw_tags if nsfw else "",
            )}],
            temperature=0.8, max_tokens=900, nsfw=nsfw,
        )
        img_prompts = await _parse_prompts(raw, 6)
        portrait_prompts = img_prompts[0:3]
        bg_prompts       = img_prompts[3:6]

        for i, p in enumerate(portrait_prompts):
            print(f"  Portrait {i}: {p[:80]}...")
        for i, p in enumerate(bg_prompts):
            print(f"  BG      {i}: {p[:80]}...")

        # Backup old refs
        if final_ref_dir.exists():
            backup = final_ref_dir.parent / f"{char.id}_backup"
            if backup.exists():
                shutil.rmtree(str(backup))
            shutil.copytree(str(final_ref_dir), str(backup))

        # Generate portraits
        print("  Generating 3 portraits...")
        portrait_paths = []
        tmp_dir = Path(BACKEND_DIR) / "uploads" / "refs" / "__tmp_regen__"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        for i, prompt in enumerate(portrait_prompts):
            p = tmp_dir / f"char_{i}.png"
            print(f"    Portrait {i}:")
            ok = await _gen_image(prompt, p, nsfw=nsfw)
            if ok:
                portrait_paths.append(p)
            await asyncio.sleep(0.5 if provider == "comfyui" else 1)

        # Generate backgrounds
        print("  Generating 3 backgrounds...")
        bg_paths = []
        for i, prompt in enumerate(bg_prompts):
            p = tmp_dir / f"bg_{i}.png"
            print(f"    BG {i}:")
            ok = await _gen_image(prompt, p, nsfw=False)
            if ok:
                bg_paths.append(p)
            await asyncio.sleep(0.5 if provider == "comfyui" else 1)

        # Move to final location
        final_ref_dir.mkdir(parents=True, exist_ok=True)
        ref_urls = []
        for tp in portrait_paths + bg_paths:
            if tp.exists():
                dest = final_ref_dir / tp.name
                shutil.move(str(tp), str(dest))
                rel = dest.relative_to(Path(BACKEND_DIR))
                ref_urls.append(f"/{rel.as_posix()}")
        shutil.rmtree(str(tmp_dir), ignore_errors=True)

        # Update avatar — use timestamp suffix to bust browser cache
        primary = final_ref_dir / "char_0.png"
        ts = int(time.time())
        avatar_fn = f"char_{char.id}_{ts}.png"
        if primary.exists():
            avatar_dir.mkdir(parents=True, exist_ok=True)
            old_url = char.avatar_url or ""
            if old_url and old_url != f"/avatars/{avatar_fn}":
                old_path = avatar_dir / old_url.split("/")[-1]
                if old_path.exists():
                    old_path.unlink(missing_ok=True)
            shutil.copy2(str(primary), str(avatar_dir / avatar_fn))
            char.avatar_url = f"/avatars/{avatar_fn}"
            print(f"  Avatar updated: {char.avatar_url}")

        if ref_urls:
            try:
                char.ref_images = json.dumps(ref_urls)
            except Exception:
                pass

    # ── 2. Re-generate 5 scene images ─────────────────────────────────────────
    if not skip_scenes:
        print("  Planning scene prompts...")
        tpl_s = _get_prompt_template(provider, nsfw, for_scenes=True)
        nsfw_tags = _get_nsfw_tags(provider)
        raw_scenes = await llm(
            [{"role": "user", "content": tpl_s.format(
                name=name, appearance=appearance, description=desc, nsfw=nsfw,
                nsfw_portrait_tags=nsfw_tags if nsfw else "",
            )}],
            temperature=0.8, max_tokens=900, nsfw=nsfw,
        )
        scene_prompts = await _parse_prompts(raw_scenes, 5)

        # Use new portrait_0 as reference (Gemini only — ComfyUI doesn't use reference)
        primary = final_ref_dir / "char_0.png"
        ref_bytes = primary.read_bytes() if (primary.exists() and provider != "comfyui") else None

        scene_dir.mkdir(parents=True, exist_ok=True)
        print("  Generating 5 chat scenes...")
        for i, sp in enumerate(scene_prompts):
            print(f"    Scene {i}: {sp[:70]}...")
            await _gen_image(sp, scene_dir / f"scene_{i}.png", reference_bytes=ref_bytes, nsfw=nsfw)
            await asyncio.sleep(0.5 if provider == "comfyui" else 1)


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", nargs="*", type=int)
    parser.add_argument("--new", action="store_true", help="All sort_weight>=100 chars")
    parser.add_argument("--skip-refs", action="store_true")
    parser.add_argument("--skip-scenes", action="store_true")
    parser.add_argument("--force-nsfw", action="store_true", help="Force NSFW mode for all chars")
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

    print(f"Re-generating images for {len(chars)} characters... force_nsfw={args.force_nsfw}")
    for char in chars:
        try:
            await regen_char_images(
                char,
                skip_refs=args.skip_refs,
                skip_scenes=args.skip_scenes,
                force_nsfw=args.force_nsfw,
            )
            db.commit()
        except Exception as e:
            print(f"  ERROR {char.name}: {e}")
            db.rollback()
        await asyncio.sleep(2)

    db.close()
    print("\nDone. Refresh frontend to see updated images.")


if __name__ == "__main__":
    asyncio.run(main())
