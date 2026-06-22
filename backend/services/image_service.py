"""
Image Generation Service — routes to Gemini 3.1 Flash Image (cloud) or ComfyUI (local).

Gemini 3.1 Flash Image: fast image generation via Vertex AI (cheaper than Pro).
ComfyUI + NoobAI XL: local anime-style generation (no cloud dependency).

Supports character reference images for visual consistency.
"""
import os
import re
import json
import time
import uuid
import base64
import logging
import asyncio
from enum import Enum
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")
BACKEND_DIR = Path(__file__).parent.parent
GENERATED_DIR = BACKEND_DIR / "uploads" / "generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)
SCENES_DIR = BACKEND_DIR / "uploads" / "scenes"
SCENES_DIR.mkdir(parents=True, exist_ok=True)
# Reference images for visual consistency: portraits and backgrounds per character
REFS_DIR = BACKEND_DIR / "uploads" / "refs"
REFS_DIR.mkdir(parents=True, exist_ok=True)

GCP_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
GCP_PROJECT = os.getenv("GCP_PROJECT", "pdfconverter-415414")
GCP_LOCATION = os.getenv("GCP_LOCATION", "global")

FRONTEND_PUBLIC = BACKEND_DIR.parent / "frontend" / "public"

# Match [IMG:] and [SCENE:N] tags, including optional surrounding roleplay asterisks (*..*)
IMG_TAG_PATTERN = re.compile(r"\*?\s*\[IMG:\s*(.+?)\]\s*\*?")
SCENE_TAG_PATTERN = re.compile(r"\*?\s*\[SCENE:\s*(\d+)\]\s*\*?")
# Also detect emoji-based image descriptions the LLM sometimes uses instead of [IMG:]
EMOJI_IMG_PATTERN = re.compile(r"[🖼📸🌄🎨]\s*([^\n\[]{15,200})")


class Provider(str, Enum):
    GEMINI = "gemini"
    COMFYUI = "comfyui"


# ── Provider health checks ──

async def _comfyui_available() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(f"{COMFYUI_URL}/system_stats")
            return r.status_code == 200
    except Exception:
        return False


_gemini_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GCP_CREDENTIALS
        from google import genai
        _gemini_client = genai.Client(
            vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION,
        )
    return _gemini_client


# ── Resolve character reference images ──

def _resolve_avatar_bytes(avatar_url: Optional[str]) -> Optional[bytes]:
    """Load the character's avatar image from local filesystem."""
    if not avatar_url:
        return None
    try:
        if avatar_url.startswith("/avatars/"):
            path = FRONTEND_PUBLIC / avatar_url.lstrip("/")
            if path.exists():
                return path.read_bytes()
        elif avatar_url.startswith("/uploads/"):
            path = BACKEND_DIR / avatar_url.lstrip("/")
            if path.exists():
                return path.read_bytes()
    except Exception as e:
        logger.debug(f"Could not load avatar {avatar_url}: {e}")
    return None


def get_char_ref_bytes(character_id: int) -> Optional[bytes]:
    """
    Load the primary character portrait reference image for use as generation reference.
    Tries uploads/refs/{char_id}/char_0.png first, falls back progressively.
    Returns bytes of the best available reference, or None.
    """
    ref_dir = REFS_DIR / str(character_id)
    for candidate in ["char_0.png", "char_0.jpg", "char_1.png", "char_1.jpg"]:
        p = ref_dir / candidate
        if p.exists():
            try:
                return p.read_bytes()
            except Exception as e:
                logger.debug(f"Could not read ref {p}: {e}")
    return None


def get_char_ref_urls(character_id: int) -> dict[str, str]:
    """
    Return all reference image URLs for a character.
    Keys: 'char_0', 'char_1', 'char_2', 'bg_0', 'bg_1', 'bg_2'
    Values: URL path like /uploads/refs/{char_id}/char_0.png
    """
    ref_dir = REFS_DIR / str(character_id)
    result = {}
    if not ref_dir.exists():
        return result
    for f in sorted(ref_dir.iterdir()):
        if f.suffix.lower() in (".png", ".jpg", ".jpeg"):
            key = f.stem  # e.g. 'char_0', 'bg_2'
            rel = f.relative_to(BACKEND_DIR)
            result[key] = f"/{rel.as_posix()}"
    return result


# ── Gemini 3 Pro Image generation ──

async def generate_image_gemini(
    prompt: str,
    reference_image: Optional[bytes] = None,
    output_dir: Optional[Path] = None,
    filename_prefix: str = "",
) -> Optional[str]:
    """Generate an image via Gemini 3.1 Flash Image with optional character reference."""
    try:
        client = _get_gemini_client()
        from google.genai import types

        save_dir = output_dir or GENERATED_DIR

        if reference_image:
            contents = [
                types.Part.from_bytes(data=reference_image, mime_type="image/png"),
                types.Part.from_text(
                    text=f"Generate a new illustration of this EXACT same character "
                    f"(keep their face, hair, eyes, body proportions identical) "
                    f"in the following scene: {prompt}. "
                    f"Style: detailed anime art, vibrant colors, professional quality. "
                    f"No text, no watermark. Keep character consistency with the reference image."
                ),
            ]
        else:
            contents = (
                f"Generate a high-quality anime illustration: {prompt}. "
                "Style: detailed anime art, vibrant colors, professional quality. "
                "No text, no watermark."
            )

        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-3.1-flash-image-preview",
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
                temperature=1.0,
            ),
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                ext = part.inline_data.mime_type.split("/")[-1]
                if ext == "jpeg":
                    ext = "jpg"
                fname = f"{filename_prefix}{uuid.uuid4().hex[:12]}.{ext}"
                filepath = save_dir / fname
                filepath.write_bytes(part.inline_data.data)
                logger.info(f"Gemini image saved: {filepath}")
                rel = filepath.relative_to(BACKEND_DIR)
                return f"/{rel.as_posix()}"

        logger.warning("Gemini returned no image parts")
        return None
    except Exception as e:
        logger.error(f"Gemini image generation failed: {e}")
        return None


# ── ComfyUI local generation ──

# Negative prompt tuned for NoobAI XL / Illustrious XL / Pony
_COMFYUI_NEGATIVE_BASE = (
    "worst quality, low quality, lowres, bad anatomy, bad hands, missing fingers, "
    "extra digits, deformed, blurry, watermark, text, signature, multiple people, "
    "split screen, panel layout, border, frame, multiple views, ugly, censored, mosaic"
)
# Extra negatives for NSFW — block conservative/modest outputs
_COMFYUI_NEGATIVE_NSFW_EXTRA = (
    ", flat chest, small breasts, fully clothed, conservative outfit, formal suit, "
    "modest, covered up, turtleneck, thick clothing"
)
_COMFYUI_NEGATIVE = _COMFYUI_NEGATIVE_BASE


def _build_sdxl_positive(prompt: str, nsfw: bool = False) -> str:
    """
    Prefix natural-language prompt with quality/style booster tags for NoobAI XL.
    For NSFW: prepend ecchi/fanservice style boosters to ensure sexy output.
    """
    if nsfw:
        boosters = (
            "masterpiece, best quality, ultra-detailed, 8k, "
            "1girl, solo, "
            "ecchi, fanservice, sexy, alluring, "
        )
    else:
        boosters = (
            "masterpiece, best quality, ultra-detailed, 8k, "
            "1girl, solo, "
        )
    return boosters + prompt


async def generate_image_comfyui(prompt: str, nsfw: bool = False) -> Optional[str]:
    """Generate an image via local ComfyUI, return URL path."""
    try:
        checkpoint = await _get_comfyui_checkpoint()
        if not checkpoint:
            return None
        vae = await _get_comfyui_vae()

        positive = _build_sdxl_positive(prompt, nsfw=nsfw)
        negative = _COMFYUI_NEGATIVE_BASE + (_COMFYUI_NEGATIVE_NSFW_EXTRA if nsfw else "")
        seed = int(time.time() * 1000) % (2 ** 32)
        workflow = _build_comfyui_workflow(positive, negative, checkpoint, vae, seed=seed, nsfw=nsfw)

        client_id = uuid.uuid4().hex
        payload = json.dumps({"prompt": workflow, "client_id": client_id})

        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(
                f"{COMFYUI_URL}/prompt",
                content=payload,
                headers={"Content-Type": "application/json"},
            )
            r.raise_for_status()
            prompt_id = r.json()["prompt_id"]

        filename, subfolder, img_type = await _wait_comfyui_result(prompt_id)
        if not filename:
            return None

        async with httpx.AsyncClient(timeout=30.0) as c:
            params = {"filename": filename, "subfolder": subfolder, "type": img_type}
            r = await c.get(f"{COMFYUI_URL}/view", params=params)
            r.raise_for_status()

            local_name = f"{uuid.uuid4().hex[:12]}.png"
            filepath = GENERATED_DIR / local_name
            filepath.write_bytes(r.content)
            logger.info(f"ComfyUI image saved: {filepath}")
            return f"/uploads/generated/{local_name}"

    except Exception as e:
        logger.error(f"ComfyUI image generation failed: {e}")
        return None


async def _get_comfyui_checkpoint() -> Optional[str]:
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.get(f"{COMFYUI_URL}/object_info/CheckpointLoaderSimple")
        info = r.json()
        ckpts = info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
        for pref in ["NoobAI", "noobai", "illustrious", "pony", "animagine"]:
            for name in ckpts:
                if pref.lower() in name.lower():
                    return name
        return ckpts[0] if ckpts else None


async def _get_comfyui_vae() -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{COMFYUI_URL}/object_info/VAELoader")
            info = r.json()
            vaes = info["VAELoader"]["input"]["required"]["vae_name"][0]
            for pref in ["sdxl_vae", "sdxl-vae"]:
                for v in vaes:
                    if pref.lower() in v.lower():
                        return v
            return None
    except Exception:
        return None


def _build_comfyui_workflow(positive, negative, checkpoint, vae=None, seed=42, nsfw=False):
    # NoobAI XL vpred uses cfg=3-5; regular SDXL uses cfg=7; Pony uses cfg=6
    is_vpred = any(x in checkpoint.lower() for x in ["vpred", "v_pred", "v-pred"])
    cfg = 3.5 if is_vpred else 6.5
    # Portrait: 832x1216 is the SDXL optimal portrait resolution
    width, height = 832, 1216
    base = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "3": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": positive, "clip": ["1", 1]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
        "6": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0],
                "latent_image": ["3", 0], "seed": seed,
                "steps": 28, "cfg": cfg, "sampler_name": "euler_ancestral",
                "scheduler": "karras", "denoise": 1.0,
            },
        },
    }
    if vae:
        base["2"] = {"class_type": "VAELoader", "inputs": {"vae_name": vae}}
        base["7"] = {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["2", 0]}}
    else:
        base["7"] = {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}}
    base["8"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": "synclub", "images": ["7", 0]}}
    return base


async def _wait_comfyui_result(prompt_id: str, timeout: int = 120):
    start = time.time()
    while time.time() - start < timeout:
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.get(f"{COMFYUI_URL}/history/{prompt_id}")
                history = r.json()
                if prompt_id in history:
                    outputs = history[prompt_id].get("outputs", {})
                    for node_output in outputs.values():
                        if "images" in node_output:
                            img = node_output["images"][0]
                            return img["filename"], img.get("subfolder", ""), img.get("type", "output")
        except Exception:
            pass
        await asyncio.sleep(2)
    return None, None, None


# ── Public API ──

async def detect_provider() -> Optional[Provider]:
    """Auto-detect best available provider. Prefer ComfyUI for speed + no cost."""
    if await _comfyui_available():
        return Provider.COMFYUI
    try:
        _get_gemini_client()
        return Provider.GEMINI
    except Exception:
        return None


async def generate_image(
    prompt: str,
    provider: Optional[Provider] = None,
    avatar_url: Optional[str] = None,
    character_id: Optional[int] = None,
    nsfw: bool = False,
) -> Optional[str]:
    """
    Generate an image from a text prompt with optional character reference.
    Prefers uploads/refs/{char_id}/char_0.png over avatar_url for better consistency.
    Returns the URL path (e.g. /uploads/generated/xxx.png) or None on failure.
    """
    if provider is None:
        provider = await detect_provider()

    if provider is None:
        logger.warning("No image generation provider available")
        return None

    logger.info(f"Generating image via {provider.value} (nsfw={nsfw}): {prompt[:80]}...")

    # Prefer dedicated reference portrait over plain avatar thumbnail
    ref_bytes: Optional[bytes] = None
    if character_id is not None:
        ref_bytes = get_char_ref_bytes(character_id)
        if ref_bytes:
            logger.info(f"Using char ref portrait for id={character_id} ({len(ref_bytes)//1024}KB)")
    if ref_bytes is None and avatar_url:
        ref_bytes = _resolve_avatar_bytes(avatar_url)
        if ref_bytes:
            logger.info(f"Using avatar fallback: {avatar_url} ({len(ref_bytes)//1024}KB)")

    if provider == Provider.COMFYUI:
        return await generate_image_comfyui(prompt, nsfw=nsfw)
    else:
        return await generate_image_gemini(prompt, reference_image=ref_bytes)


def extract_image_tags(text: str) -> list[str]:
    """Extract all [IMG: description] tags AND emoji-based image descriptions from text."""
    tags = IMG_TAG_PATTERN.findall(text)
    # Also catch LLM emoji-format: 🖼 description (common model fallback)
    emoji_tags = EMOJI_IMG_PATTERN.findall(text)
    for desc in emoji_tags:
        desc = desc.strip().rstrip("。.！!，,")
        if desc and desc not in tags:
            tags.append(desc)
    return tags


def extract_scene_tags(text: str) -> list[int]:
    """Extract all [SCENE: n] tag indices from text."""
    return [int(m) for m in SCENE_TAG_PATTERN.findall(text)]


def strip_image_tags(text: str) -> str:
    """Remove [IMG: ...], [SCENE: n] tags and emoji image descriptions from text."""
    text = IMG_TAG_PATTERN.sub("", text)
    text = SCENE_TAG_PATTERN.sub("", text)
    text = EMOJI_IMG_PATTERN.sub("", text)
    return text.strip()


def replace_image_tags(text: str, tag_to_url: dict[str, str]) -> str:
    """Replace [IMG: desc] tags and emoji descriptions with markdown image syntax."""
    def _replacer(match):
        desc = match.group(1)
        url = tag_to_url.get(desc)
        if url:
            return f"\n![{desc}]({url})\n"
        return match.group(0)

    text = IMG_TAG_PATTERN.sub(_replacer, text)

    # Also replace emoji-based descriptions
    def _emoji_replacer(match):
        desc = match.group(1).strip().rstrip("。.！!，,")
        url = tag_to_url.get(desc)
        if url:
            return f"\n![{desc}]({url})\n"
        return match.group(0)

    text = EMOJI_IMG_PATTERN.sub(_emoji_replacer, text)
    return text


def replace_scene_tags(text: str, idx_to_url: dict[int, str]) -> str:
    """Replace [SCENE: n] tags with markdown image syntax."""
    def _replacer(match):
        idx = int(match.group(1))
        url = idx_to_url.get(idx)
        if url:
            return f"\n![scene {idx}]({url})\n"
        return match.group(0)
    return SCENE_TAG_PATTERN.sub(_replacer, text)


# ── Scene pre-generation ──

def get_scene_dir(character_id: int) -> Path:
    d = SCENES_DIR / str(character_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_pregenerated_scenes(character_id: int) -> dict[int, str]:
    """Return {index: url_path} of existing pre-generated scenes."""
    scene_dir = get_scene_dir(character_id)
    scenes = {}
    for f in sorted(scene_dir.glob("scene_*.png")):
        try:
            idx = int(f.stem.split("_")[1])
            rel = f.relative_to(BACKEND_DIR)
            scenes[idx] = f"/{rel.as_posix()}"
        except (ValueError, IndexError):
            continue
    # Also check jpg
    for f in sorted(scene_dir.glob("scene_*.jpg")):
        try:
            idx = int(f.stem.split("_")[1])
            rel = f.relative_to(BACKEND_DIR)
            scenes[idx] = f"/{rel.as_posix()}"
        except (ValueError, IndexError):
            continue
    return scenes


def scenes_ready(character_id: int, expected: int = 5) -> bool:
    return len(get_pregenerated_scenes(character_id)) >= expected
