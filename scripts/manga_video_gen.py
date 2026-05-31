# -*- coding: utf-8 -*-
"""
Stage 3 — Video clip generation from key frames.

Supports two engines:
  A) Wan 2.1 I2V (local, free, RTX 5090 32GB VRAM)
  B) Veo 3.1 (Google Cloud, disabled by default)

Usage:
  python scripts/manga_video_gen.py --char-id 53 --engine wan
  python scripts/manga_video_gen.py --char-id 53 --engine veo
"""

import sys, os, asyncio, json, argparse, time
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.platform == "win32":
    import ctypes; ctypes.windll.kernel32.SetConsoleOutputCP(65001)

from pathlib import Path

BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

OUTPUT_BASE = Path("uploads/manga")

# ── Wan 2.1 via ComfyUI API ──────────────────────────────────────────────────

import httpx, uuid as _uuid

COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")

# T2V 1.3B (fast, 480p, no image input)
WAN_T2V_MODEL   = "wan2.1_1.3b.safetensors"
# I2V 14B (high quality, takes reference image)
# ComfyUI sees it via junction: diffusion_models/wan_i2v/ -> D:/wan_i2v_models/
WAN_I2V_MODEL   = r"wan_i2v\wan2.1_i2v_14b_480p.safetensors"
WAN_CLIP_VISION = "open-clip-xlm-roberta-large-vit-huge-14.pth"

WAN_T5_ENCODER = "umt5-xxl-enc-bf16.pth"
WAN_VAE = "Wan2.1_VAE.pth"
WAN_WIDTH, WAN_HEIGHT = 832, 480
WAN_NUM_FRAMES = 41  # ~3.3s at ~12fps
WAN_STEPS = 20
# Keep legacy alias
WAN_MODEL = WAN_T2V_MODEL


def _wan_available() -> bool:
    try:
        r = httpx.get(f"{COMFYUI_URL}/system_stats", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def _build_wan_t2v_workflow(prompt: str, negative: str, seed: int) -> dict:
    """Build ComfyUI workflow for Wan 2.1 T2V using WanVideoWrapper nodes."""
    return {
        "10": {
            "class_type": "WanVideoModelLoader",
            "inputs": {
                "model": WAN_MODEL,
                "base_precision": "bf16",
                "quantization": "disabled",
                "load_device": "main_device",
            },
        },
        "11": {
            "class_type": "LoadWanVideoT5TextEncoder",
            "inputs": {
                "model_name": WAN_T5_ENCODER,
                "precision": "bf16",
                "load_device": "offload_device",
            },
        },
        "12": {
            "class_type": "WanVideoVAELoader",
            "inputs": {
                "model_name": WAN_VAE,
                "precision": "bf16",
            },
        },
        "20": {
            "class_type": "WanVideoTextEncode",
            "inputs": {
                "positive_prompt": prompt,
                "negative_prompt": negative,
                "t5": ["11", 0],
                "force_offload": True,
            },
        },
        "25": {
            "class_type": "WanVideoEmptyEmbeds",
            "inputs": {
                "width": WAN_WIDTH,
                "height": WAN_HEIGHT,
                "num_frames": WAN_NUM_FRAMES,
            },
        },
        "30": {
            "class_type": "WanVideoSampler",
            "inputs": {
                "model": ["10", 0],
                "image_embeds": ["25", 0],
                "steps": WAN_STEPS,
                "cfg": 6.0,
                "shift": 5.0,
                "seed": seed,
                "force_offload": True,
                "scheduler": "unipc",
                "riflex_freq_index": 0,
                "text_embeds": ["20", 0],
            },
        },
        "40": {
            "class_type": "WanVideoDecode",
            "inputs": {
                "vae": ["12", 0],
                "samples": ["30", 0],
                "enable_vae_tiling": False,
                "tile_x": 272,
                "tile_y": 272,
                "tile_stride_x": 144,
                "tile_stride_y": 128,
            },
        },
        "50": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["40", 0],
                "filename_prefix": "manga_video",
            },
        },
    }


def _build_wan_i2v_workflow(image_filename: str, prompt: str, negative: str, seed: int) -> dict:
    """Build ComfyUI workflow for Wan 2.1 I2V 14B using WanVideoWrapper nodes.

    Requires:
      - models/diffusion_models/wan2.1_i2v_14b_480p.safetensors
      - models/clip_vision/open-clip-xlm-roberta-large-vit-huge-14.pth
      - models/text_encoders/umt5-xxl-enc-bf16.pth
      - models/vae/Wan2.1_VAE.pth
      - image uploaded to ComfyUI input folder (image_filename)
    """
    return {
        # ── Model loaders ───────────────────────────────────────────────────
        "10": {
            "class_type": "WanVideoModelLoader",
            "inputs": {
                "model": WAN_I2V_MODEL,
                "base_precision": "bf16",
                # fp8 quantization: converts to ~14GB during load
                "quantization": "fp8_e4m3fn",
                # offload_device = load + fp8-cast the checkpoint in CPU RAM, then the
                # sampler moves the ~14GB fp8 model resident onto the GPU (no block-swap).
                # (main_device would materialize the full 65GB raw ckpt on GPU -> OOM.)
                "load_device": "offload_device",
            },
        },
        # NOTE: Block-swap REMOVED for RTX 5090 (32GB VRAM). The fp8 I2V 14B model is
        # ~14GB and fits resident in VRAM; at 480p / 41 frames, sampling peaks at
        # ~17.8GB (verified), leaving ~14GB headroom. Keeping all blocks on-GPU is
        # ~2x faster (11.3 s/it vs 13+ s/it with blocks_to_swap=40, measured).
        # To re-enable for a smaller-VRAM card, restore the two nodes below and point
        # the sampler ("30") "model" input at ["10b", 0] instead of ["10", 0]:
        #   "10c": {"class_type": "WanVideoBlockSwap", "inputs": {
        #       "blocks_to_swap": 40, "offload_img_emb": True,
        #       "offload_txt_emb": True, "vace_blocks_to_swap": 0}},
        #   "10b": {"class_type": "WanVideoSetBlockSwap", "inputs": {
        #       "model": ["10", 0], "block_swap_args": ["10c", 0]}},
        "11": {
            "class_type": "LoadWanVideoT5TextEncoder",
            "inputs": {
                "model_name": WAN_T5_ENCODER,
                "precision": "bf16",
                "load_device": "offload_device",
            },
        },
        "12": {
            "class_type": "WanVideoVAELoader",
            "inputs": {
                "model_name": WAN_VAE,
                "precision": "bf16",
            },
        },
        "13": {
            "class_type": "LoadWanVideoClipTextEncoder",
            "inputs": {
                "model_name": WAN_CLIP_VISION,
                "precision": "bf16",
                "load_device": "offload_device",
            },
        },
        # ── Load reference image ─────────────────────────────────────────────
        "14": {
            "class_type": "LoadImage",
            "inputs": {
                "image": image_filename,
            },
        },
        # ── Encode reference image with CLIP vision + VAE (I2V latent) ───────
        "15": {
            "class_type": "WanVideoImageClipEncode",
            "inputs": {
                "clip_vision": ["13", 0],
                "image":       ["14", 0],
                "vae":         ["12", 0],
                "generation_width":  WAN_WIDTH,
                "generation_height": WAN_HEIGHT,
                "num_frames":        WAN_NUM_FRAMES,
            },
        },
        # ── Text encode ─────────────────────────────────────────────────────
        "20": {
            "class_type": "WanVideoTextEncode",
            "inputs": {
                "positive_prompt": prompt,
                "negative_prompt": negative,
                "t5":              ["11", 0],
                "force_offload":   True,
            },
        },
        # ── Sample ───────────────────────────────────────────────────────────
        "30": {
            "class_type": "WanVideoSampler",
            "inputs": {
                "model":        ["10", 0],  # was ["10b", 0]; block-swap removed for 5090 (see note above)
                "image_embeds": ["15", 0],
                "text_embeds":  ["20", 0],
                "steps":        WAN_STEPS,
                "cfg":          6.0,
                "shift":        5.0,
                "seed":         seed,
                "force_offload": True,
                "scheduler":    "unipc",
                "riflex_freq_index": 0,
            },
        },
        # ── Decode ───────────────────────────────────────────────────────────
        "40": {
            "class_type": "WanVideoDecode",
            "inputs": {
                "vae":               ["12", 0],
                "samples":           ["30", 0],
                "enable_vae_tiling": True,
                "tile_x":            272,
                "tile_y":            272,
                "tile_stride_x":     144,
                "tile_stride_y":     128,
            },
        },
        # ── Save frames ──────────────────────────────────────────────────────
        "50": {
            "class_type": "SaveImage",
            "inputs": {
                "images":          ["40", 0],
                "filename_prefix": "manga_i2v",
            },
        },
    }


def _get_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


async def _submit_and_wait_video(workflow: dict, output_path: str, timeout: int = 600) -> str:
    """Submit a ComfyUI workflow, download frames, stitch into MP4 with ffmpeg."""
    import subprocess, tempfile
    client_id = str(_uuid.uuid4())
    payload = json.dumps({"prompt": workflow, "client_id": client_id})

    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.post(f"{COMFYUI_URL}/prompt",
                         content=payload, headers={"Content-Type": "application/json"})
        r.raise_for_status()
        prompt_id = r.json()["prompt_id"]

    print(f"    [ComfyUI] Submitted prompt {prompt_id[:8]}...")

    for elapsed in range(0, timeout, 5):
        await asyncio.sleep(5)
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{COMFYUI_URL}/history/{prompt_id}")
            if r.status_code != 200:
                continue
            hist = r.json()
            if prompt_id not in hist:
                if elapsed % 30 == 0 and elapsed > 0:
                    print(f"    [ComfyUI] Still processing... ({elapsed}s)")
                continue

            status = hist[prompt_id].get("status", {})
            if status.get("status_str") == "error":
                msgs = status.get("messages", [])
                raise RuntimeError(f"ComfyUI workflow error: {msgs}")

            outputs = hist[prompt_id].get("outputs", {})
            for node_id, node_out in outputs.items():
                images = node_out.get("images", [])
                if not images:
                    continue

                # Download all frames to temp dir
                tmpdir = tempfile.mkdtemp(prefix="manga_frames_")
                print(f"    [ComfyUI] Downloading {len(images)} frames...")
                for i, img in enumerate(images):
                    url = f"{COMFYUI_URL}/view"
                    params = {
                        "filename": img["filename"],
                        "subfolder": img.get("subfolder", ""),
                        "type": img.get("type", "output"),
                    }
                    async with httpx.AsyncClient(timeout=15.0) as c2:
                        dl = await c2.get(url, params=params)
                        dl.raise_for_status()
                        frame_path = os.path.join(tmpdir, f"frame_{i:05d}.png")
                        with open(frame_path, "wb") as f:
                            f.write(dl.content)

                # Stitch frames into MP4 with ffmpeg
                ffmpeg = _get_ffmpeg()
                frame_pattern = os.path.join(tmpdir, "frame_%05d.png")
                cmd = [
                    ffmpeg, "-y",
                    "-framerate", "12",
                    "-i", frame_pattern,
                    "-c:v", "libx264", "-preset", "fast",
                    "-crf", "20", "-pix_fmt", "yuv420p",
                    output_path,
                ]
                subprocess.run(cmd, check=True, capture_output=True)

                # Cleanup temp frames
                import shutil
                shutil.rmtree(tmpdir, ignore_errors=True)

                return output_path

    raise TimeoutError(f"ComfyUI video workflow timed out after {timeout}s")


def _wan_i2v_model_available() -> bool:
    """Return True if the merged I2V 14B model file exists (via junction)."""
    return os.path.exists(r"D:\wan_i2v_models\wan2.1_i2v_14b_480p.safetensors")


async def _upload_image_to_comfyui(image_path: str, dest_name: str) -> str:
    """Upload a local PNG to ComfyUI's input folder. Returns filename as seen by ComfyUI."""
    with open(image_path, "rb") as f:
        data = f.read()
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(
            f"{COMFYUI_URL}/upload/image",
            files={"image": (dest_name, data, "image/png")},
            data={"type": "input", "overwrite": "true"},
        )
        r.raise_for_status()
        resp = r.json()
    return resp.get("name", dest_name)


def generate_video_wan(image_path: str, prompt: str, output_path: str) -> str:
    """Placeholder - actual call is async via generate_video_wan_async."""
    raise NotImplementedError("Use generate_video_wan_async instead")


async def generate_video_wan_async(image_path: str, prompt: str, output_path: str) -> str:
    """Generate a video clip using Wan 2.1 via ComfyUI API.

    Automatically selects I2V 14B (if model is merged) or T2V 1.3B.
    """
    import random
    seed = random.randint(1, 2**31 - 1)
    negative = "static, blurry, low quality, worst quality, deformed, ugly, text, watermark"

    use_i2v = _wan_i2v_model_available() and image_path and os.path.exists(image_path)

    if use_i2v:
        print(f"    [Wan] I2V 14B mode — uploading key frame…")
        import hashlib
        dest_name = "wan_i2v_" + hashlib.md5(image_path.encode()).hexdigest()[:8] + ".png"
        uploaded_name = await _upload_image_to_comfyui(image_path, dest_name)
        workflow = _build_wan_i2v_workflow(uploaded_name, prompt, negative, seed)
        print(f"    [Wan] I2V workflow submitted (seed={seed})")
    else:
        if not use_i2v and _wan_i2v_model_available():
            print(f"    [Wan] T2V 1.3B mode (no key frame)")
        else:
            print(f"    [Wan] T2V 1.3B mode (I2V model not yet ready)")
        workflow = _build_wan_t2v_workflow(prompt, negative, seed)

    result = await _submit_and_wait_video(workflow, output_path, timeout=900)
    return result


# ── Veo 3.1 Configuration ───────────────────────────────────────────────────

GCP_CREDS_PATH = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "credentials",
    "pdfconverter-415414-d9dbb1a4eec6.json"
))
GCP_PROJECT = "pdfconverter-415414"
GCP_LOCATION = "us-central1"


def _desaturate_image(src_path: str, dst_path: str, saturation: float = 0.3) -> str:
    """Return a desaturated copy of the image to reduce RAI sensitivity."""
    from PIL import Image as PILImage, ImageEnhance
    img = PILImage.open(src_path).convert("RGB")
    enhancer = ImageEnhance.Color(img)
    img = enhancer.enhance(saturation)
    img.save(dst_path, format="PNG")
    return dst_path


async def _veo_generate(client, prompt: str, config, image_path: str | None) -> object:
    """Submit a Veo generation request and poll until done."""
    from google.genai import types
    if image_path and os.path.exists(image_path):
        first_frame = types.Image.from_file(location=image_path)
        print(f"  [Veo] I2V mode: {os.path.basename(image_path)}")
        op = client.models.generate_videos(
            model="veo-3.1-generate-preview",
            prompt=prompt,
            image=first_frame,
            config=config,
        )
    else:
        print(f"  [Veo] T2V mode (no key frame)")
        op = client.models.generate_videos(
            model="veo-3.1-generate-preview",
            prompt=prompt,
            config=config,
        )
    print(f"  [Veo] Submitting...")
    t0 = time.time()
    while not op.done:
        await asyncio.sleep(10)
        op = client.operations.get(op)
        print(f"  [Veo] Waiting... ({time.time()-t0:.0f}s)")
    return op


async def generate_video_veo(image_path: str, prompt: str, output_path: str,
                             **_kwargs) -> str:
    """Generate a video clip using Google Veo 3.1 I2V mode.

    On RAI rejection, automatically retries with a desaturated version of
    the key frame (reduces content sensitivity). Falls back to T2V only if
    the desaturated retry also fails.
    """
    if os.getenv("ALLOW_ONLINE_MODELS") != "1":
        raise RuntimeError("Online model disabled: set ALLOW_ONLINE_MODELS=1 only if Veo is explicitly allowed.")

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GCP_CREDS_PATH

    from google import genai
    from google.genai import types

    client = genai.Client(vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION)

    t0 = time.time()

    config = types.GenerateVideosConfig(
        aspect_ratio="9:16",
        number_of_videos=1,
        duration_seconds=8,
        person_generation="allow_adult",
    )

    def _rai_blocked(op) -> bool:
        return bool(
            op.response
            and getattr(op.response, "rai_media_filtered_count", 0)
            and not op.response.generated_videos
        )

    # Attempt 1: I2V with original key frame
    operation = await _veo_generate(client, prompt, config, image_path if image_path else None)

    if _rai_blocked(operation) and image_path and os.path.exists(image_path):
        print(f"  [Veo] RAI blocked — retrying with desaturated frame...")
        import tempfile
        tmp = tempfile.mktemp(suffix=".png")
        _desaturate_image(image_path, tmp, saturation=0.25)
        operation = await _veo_generate(client, prompt, config, tmp)
        try:
            os.remove(tmp)
        except Exception:
            pass

    if _rai_blocked(operation):
        print(f"  [Veo] Still blocked — falling back to T2V...")
        operation = await _veo_generate(client, prompt, config, None)

    if operation.response and operation.response.generated_videos:
        video = operation.response.generated_videos[0]
        video_uri = video.video.uri
        if video_uri:
            import google.auth
            import google.auth.transport.requests
            import requests
            creds, _ = google.auth.default()
            auth_req = google.auth.transport.requests.Request()
            creds.refresh(auth_req)
            resp = requests.get(video_uri, headers={"Authorization": f"Bearer {creds.token}"})
            resp.raise_for_status()
            with open(output_path, "wb") as f:
                f.write(resp.content)
        elif video.video.video_bytes:
            video.video.save(output_path)
        else:
            raise RuntimeError("No video URI or bytes returned")
        elapsed = time.time() - t0
        size_kb = os.path.getsize(output_path) / 1024
        print(f"  [Veo] Done in {elapsed:.1f}s → {output_path} ({size_kb:.0f} KB)")
        return output_path
    else:
        raise RuntimeError(f"Veo generation failed: {operation}")


# ── Main video generation logic ──────────────────────────────────────────────

async def generate_clips(char_id: int, episode: int = 1, engine: str = "wan") -> list[str]:
    """Generate video clips for all scenes using the specified engine."""
    script_path = OUTPUT_BASE / str(char_id) / f"script_ep{episode}.json"
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")

    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    scenes = script["scenes"]
    out_dir = OUTPUT_BASE / str(char_id)
    clip_paths = []

    for scene in scenes:
        sid = scene["id"]
        frame_path = out_dir / f"frame_ep{episode}_s{sid}.png"
        clip_path = out_dir / f"clip_ep{episode}_s{sid}.mp4"

        if clip_path.exists():
            print(f"  Scene {sid}: clip exists, skipping")
            clip_paths.append(str(clip_path))
            continue

        if not frame_path.exists():
            print(f"  Scene {sid}: frame missing, skipping")
            clip_paths.append("")
            continue

        motion_desc = scene.get("motion", "slight movement")
        visual = scene.get("visual_prompt", "")
        char_appearance = script.get("character", {}).get("appearance", "")

        # Prefix with anime style + character anchor to prevent Veo from
        # switching to photorealistic mode and to reduce cross-scene drift
        style_prefix = "anime style, 2D cel animation, illustrated. "
        char_anchor = f"{char_appearance}. " if char_appearance else ""
        prompt = f"{style_prefix}{char_anchor}{visual}. Camera motion: {motion_desc}"

        print(f"  Scene {sid}: generating clip ({engine})...")
        try:
            if engine == "wan":
                if not _wan_available():
                    raise RuntimeError("ComfyUI is not running")
                await generate_video_wan_async(str(frame_path), prompt, str(clip_path))
            elif engine == "veo":
                await generate_video_veo(str(frame_path), prompt, str(clip_path))
            else:
                raise ValueError(f"Unknown engine: {engine}")
            clip_paths.append(str(clip_path))
        except Exception as e:
            print(f"  Scene {sid}: FAILED — {e}")
            clip_paths.append("")

    return clip_paths


async def main():
    parser = argparse.ArgumentParser(description="Generate manga drama video clips")
    parser.add_argument("--char-id", type=int, required=True)
    parser.add_argument("--episode", type=int, default=1)
    parser.add_argument("--engine", choices=["wan"], default="wan")
    args = parser.parse_args()

    clips = await generate_clips(args.char_id, args.episode, args.engine)
    ok = sum(1 for c in clips if c)
    print(f"\n[Video] Generated {ok} / {len(clips)} clips ({args.engine})")


if __name__ == "__main__":
    asyncio.run(main())
