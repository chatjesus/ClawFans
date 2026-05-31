# -*- coding: utf-8 -*-
"""
Stage 2 — Key frame image generation for manga drama scenes.

Generates one key frame per scene using local ComfyUI (SDXL),
reusing the existing image_service infrastructure.

Usage:
  python scripts/manga_frame_gen.py --char-id 53
  python scripts/manga_frame_gen.py --char-id 53 --episode 1 --provider comfyui
"""

import sys, os, asyncio, json, argparse, random, hashlib
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.platform == "win32":
    import ctypes; ctypes.windll.kernel32.SetConsoleOutputCP(65001)

BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from pathlib import Path
import httpx

COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")
OUTPUT_BASE = Path("uploads/manga")

NEGATIVE_PROMPT = (
    "worst quality, low quality, lowres, bad anatomy, bad hands, "
    "missing fingers, extra digits, deformed, blurry, watermark, text, "
    "signature, multiple people, split screen, panel layout, border, "
    "frame, ugly, censored, mosaic, "
    "nude, nudity, naked, exposed, nipples, genitals, explicit, nsfw, "
    "lingerie, underwear, revealing clothes, cleavage, upskirt"
)


async def _comfyui_available() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(f"{COMFYUI_URL}/system_stats")
            return r.status_code == 200
    except Exception:
        return False


async def _get_checkpoint() -> str:
    """Find best SDXL checkpoint in ComfyUI."""
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.get(f"{COMFYUI_URL}/object_info/CheckpointLoaderSimple")
        r.raise_for_status()
    names = r.json()["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
    preferred = ["noobai", "NoobAI", "illustrious", "pony", "animagine", "sdxl"]
    for pref in preferred:
        for n in names:
            if pref.lower() in n.lower():
                return n
    return names[0] if names else "model.safetensors"


def _build_workflow(positive: str, negative: str, checkpoint: str,
                    seed: int, width: int = 832, height: int = 1216) -> dict:
    """Standard txt2img workflow."""
    is_vpred = any(x in checkpoint.lower() for x in ["vpred", "v_pred", "v-pred"])
    cfg = 3.5 if is_vpred else 6.5
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "3": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": positive, "clip": ["1", 1]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
        "6": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0],
            "latent_image": ["3", 0], "seed": seed,
            "steps": 28, "cfg": cfg, "sampler_name": "euler_ancestral",
            "scheduler": "karras", "denoise": 1.0,
        }},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
        "8": {"class_type": "SaveImage", "inputs": {"filename_prefix": "manga", "images": ["7", 0]}},
    }


def _build_img2img_workflow(positive: str, negative: str, checkpoint: str,
                            ref_image_name: str, seed: int,
                            width: int = 832, height: int = 1216,
                            denoise: float = 0.65) -> dict:
    """img2img workflow: uses a reference image as the starting point.

    The reference image is VAE-encoded into latent space, then the KSampler
    partially denoises it guided by the scene prompt. This preserves the
    character's appearance from the reference while adapting pose/scene.
    """
    is_vpred = any(x in checkpoint.lower() for x in ["vpred", "v_pred", "v-pred"])
    cfg = 3.5 if is_vpred else 6.5
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": positive, "clip": ["1", 1]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
        "10": {"class_type": "LoadImage", "inputs": {"image": ref_image_name}},
        "11": {"class_type": "ImageScale", "inputs": {
            "image": ["10", 0], "width": width, "height": height,
            "upscale_method": "lanczos", "crop": "center",
        }},
        "12": {"class_type": "VAEEncode", "inputs": {"pixels": ["11", 0], "vae": ["1", 2]}},
        "6": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0],
            "latent_image": ["12", 0], "seed": seed,
            "steps": 28, "cfg": cfg, "sampler_name": "euler_ancestral",
            "scheduler": "karras", "denoise": denoise,
        }},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
        "8": {"class_type": "SaveImage", "inputs": {"filename_prefix": "manga", "images": ["7", 0]}},
    }


async def _submit_and_wait(workflow: dict, timeout: int = 180) -> bytes:
    """Submit a ComfyUI workflow and wait for the output image."""
    import uuid as _uuid
    client_id = str(_uuid.uuid4())
    payload = json.dumps({"prompt": workflow, "client_id": client_id})

    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.post(f"{COMFYUI_URL}/prompt",
                         content=payload, headers={"Content-Type": "application/json"})
        r.raise_for_status()
        prompt_id = r.json()["prompt_id"]

    # Poll for completion
    for _ in range(timeout // 2):
        await asyncio.sleep(2)
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{COMFYUI_URL}/history/{prompt_id}")
            if r.status_code != 200:
                continue
            hist = r.json()
            if prompt_id not in hist:
                continue
            outputs = hist[prompt_id].get("outputs", {})
            for node_id, node_out in outputs.items():
                images = node_out.get("images", [])
                if images:
                    img = images[0]
                    async with httpx.AsyncClient(timeout=10.0) as c2:
                        dl = await c2.get(f"{COMFYUI_URL}/view",
                                          params={"filename": img["filename"],
                                                  "subfolder": img.get("subfolder", ""),
                                                  "type": img.get("type", "output")})
                        dl.raise_for_status()
                        return dl.content

    raise TimeoutError(f"ComfyUI workflow {prompt_id} timed out after {timeout}s")


def _build_positive(visual_prompt: str, char_appearance: str) -> str:
    """Combine quality boosters + character appearance + scene visual prompt."""
    boosters = "masterpiece, best quality, ultra-detailed, 8k, anime, "
    appearance = char_appearance + ", " if char_appearance else ""
    return boosters + appearance + visual_prompt


async def _upload_ref_to_comfyui(char_id: int) -> str | None:
    """Upload the primary character reference image to ComfyUI's input folder."""
    refs_dir = Path("uploads/refs") / str(char_id)
    ref_path = refs_dir / "char_0.png"
    if not ref_path.exists():
        return None
    comfyui_name = f"char{char_id}_ref.png"
    async with httpx.AsyncClient(timeout=10.0) as c:
        with open(ref_path, "rb") as f:
            r = await c.post(
                f"{COMFYUI_URL}/upload/image",
                files={"image": (comfyui_name, f, "image/png")},
                data={"overwrite": "true"},
            )
            r.raise_for_status()
    print(f"[Frames] Uploaded reference → {comfyui_name}")
    return comfyui_name


async def generate_frames(char_id: int, episode: int = 1,
                          use_img2img: bool = True,
                          provider: str = "comfyui") -> list[str]:
    """Generate key frame images for all scenes in an episode script.

    When use_img2img=True (default), uses the character's reference image
    as the init image for img2img, preserving character appearance across
    all scene key frames.
    """
    script_path = OUTPUT_BASE / str(char_id) / f"script_ep{episode}.json"
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}. Run manga_script_gen.py first.")

    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    provider = provider.lower().strip()
    if provider not in {"comfyui"}:
        raise ValueError(f"Unknown provider: {provider}")

    comfy_available = await _comfyui_available()
    if not comfy_available:
        raise RuntimeError("ComfyUI is not running. Start local ComfyUI first.")

    checkpoint = None
    if provider == "comfyui":
        checkpoint = await _get_checkpoint()
        print(f"[Frames] Using checkpoint: {checkpoint}")

    # Upload reference image for img2img mode
    ref_name = None
    if use_img2img and provider == "comfyui":
        ref_name = await _upload_ref_to_comfyui(char_id)
        if ref_name:
            print(f"[Frames] img2img mode: character reference loaded")
        else:
            print(f"[Frames] No reference image found, falling back to txt2img")

    char_appearance = script.get("character", {}).get("appearance", "")
    scenes = script["scenes"]
    out_dir = OUTPUT_BASE / str(char_id)
    frame_paths = []

    # Deterministic base seed from char_id — all scenes share the same
    # character "noise DNA" so face/hair/body stay consistent.
    # Each scene adds a small offset (scene_id * 100) to allow minor
    # pose/expression variation while keeping identity locked.
    char_seed = int(hashlib.md5(str(char_id).encode()).hexdigest()[:8], 16) % (2**32)
    print(f"[Frames] Character seed: {char_seed} (deterministic from char_id={char_id})")

    for scene in scenes:
        sid = scene["id"]
        out_path = out_dir / f"frame_ep{episode}_s{sid}.png"

        if out_path.exists():
            print(f"  Scene {sid}: already exists, skipping")
            frame_paths.append(str(out_path))
            continue

        positive = _build_positive(scene.get("visual_prompt", ""), char_appearance)
        seed = (char_seed + sid * 100) % (2**32)

        print(f"  Scene {sid}: generating frame ({provider})...")
        try:
            if provider == "comfyui":
                if ref_name:
                    workflow = _build_img2img_workflow(
                        positive, NEGATIVE_PROMPT, checkpoint,
                        ref_name, seed, denoise=0.35,
                    )
                else:
                    workflow = _build_workflow(positive, NEGATIVE_PROMPT, checkpoint, seed)
                img_bytes = await _submit_and_wait(workflow, timeout=180)
                with open(out_path, "wb") as f:
                    f.write(img_bytes)
                saved_bytes = len(img_bytes)
            print(f"  Scene {sid}: saved → {out_path} ({saved_bytes} bytes)")
            frame_paths.append(str(out_path))
        except Exception as e:
            print(f"  Scene {sid}: FAILED — {e}")
            frame_paths.append("")

        await asyncio.sleep(1)

    return frame_paths


async def main():
    parser = argparse.ArgumentParser(description="Generate manga drama key frames")
    parser.add_argument("--char-id", type=int, required=True)
    parser.add_argument("--episode", type=int, default=1)
    parser.add_argument("--provider", choices=["comfyui"], default="comfyui")
    args = parser.parse_args()

    paths = await generate_frames(args.char_id, args.episode, provider=args.provider)
    print(f"\n[Frames] Generated {sum(1 for p in paths if p)} / {len(paths)} frames")


if __name__ == "__main__":
    asyncio.run(main())
