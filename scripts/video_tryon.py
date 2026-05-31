#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video virtual try-on using CatVTON via ComfyUI API.

Steps:
  1. Extract key frame from video
  2. Generate clothing mask (upper body region)
  3. Call CatVTON to swap garment
  4. Apply to video frames using temporal consistency

Usage:
    python scripts/video_tryon.py input.mp4 garment.png [--output output_tryon.mp4]
"""

import argparse, os, sys, json, time, subprocess, tempfile, shutil, uuid
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def _get_ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")


def _extract_frame(video_path: str, time_sec: float = 2.0) -> str:
    """Extract a single frame from video at given timestamp."""
    ffmpeg = _get_ffmpeg()
    out = tempfile.mktemp(suffix=".png")
    subprocess.run(
        [ffmpeg, "-y", "-ss", str(time_sec), "-i", video_path,
         "-frames:v", "1", "-q:v", "1", out],
        check=True, capture_output=True,
    )
    return out


def _create_upper_body_mask(image_path: str) -> str:
    """Create a simple upper body mask (covers torso area).
    For production, use DensePose/SAM. This is a heuristic for demo."""
    img = Image.open(image_path)
    w, h = img.size

    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)

    # Upper body region heuristic: center 60% width, top 25%-65% height
    x1 = int(w * 0.20)
    x2 = int(w * 0.80)
    y1 = int(h * 0.20)
    y2 = int(h * 0.65)
    draw.rectangle([x1, y1, x2, y2], fill=255)

    out = tempfile.mktemp(suffix="_mask.png")
    mask.save(out)
    return out


async def _upload_to_comfyui(image_path: str, name: str) -> str:
    """Upload image to ComfyUI input folder."""
    import httpx
    with open(image_path, "rb") as f:
        data = f.read()
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(
            f"{COMFYUI_URL}/upload/image",
            files={"image": (name, data, "image/png")},
            data={"type": "input", "overwrite": "true"},
        )
        r.raise_for_status()
        return r.json().get("name", name)


def _build_catvton_workflow(person_name: str, mask_name: str, garment_name: str, seed: int) -> dict:
    """Build CatVTON workflow for ComfyUI."""
    return {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": person_name},
        },
        "2": {
            "class_type": "LoadImage",
            "inputs": {"image": mask_name},
        },
        "2b": {
            "class_type": "ImageToMask",
            "inputs": {"image": ["2", 0], "channel": "red"},
        },
        "3": {
            "class_type": "LoadImage",
            "inputs": {"image": garment_name},
        },
        "10": {
            "class_type": "CatVTONWrapper",
            "inputs": {
                "image": ["1", 0],
                "mask": ["2b", 0],
                "refer_image": ["3", 0],
                "mask_grow": 25,
                "mixed_precision": "bf16",
                "seed": seed,
                "steps": 50,
                "cfg": 2.5,
            },
        },
        "20": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["10", 0],
                "filename_prefix": "tryon_result",
            },
        },
    }


async def _submit_and_wait(workflow: dict, timeout: int = 300) -> list[dict]:
    """Submit workflow and wait for results. Returns list of output images."""
    import httpx
    client_id = str(uuid.uuid4())
    payload = json.dumps({"prompt": workflow, "client_id": client_id})

    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.post(
            f"{COMFYUI_URL}/prompt",
            content=payload,
            headers={"Content-Type": "application/json"},
        )
        r.raise_for_status()
        prompt_id = r.json()["prompt_id"]

    print(f"  [ComfyUI] Submitted prompt {prompt_id[:8]}...")

    for elapsed in range(0, timeout, 5):
        import asyncio
        await asyncio.sleep(5)
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{COMFYUI_URL}/history/{prompt_id}")
            if r.status_code != 200:
                continue
            hist = r.json()
            if prompt_id not in hist:
                if elapsed % 30 == 0 and elapsed > 0:
                    print(f"  [ComfyUI] Processing... ({elapsed}s)")
                continue

            status = hist[prompt_id].get("status", {})
            if status.get("status_str") == "error":
                msgs = status.get("messages", [])
                raise RuntimeError(f"Workflow error: {msgs}")

            outputs = hist[prompt_id].get("outputs", {})
            result_images = []
            for node_id, node_out in outputs.items():
                for img in node_out.get("images", []):
                    result_images.append(img)
            return result_images

    raise TimeoutError(f"Workflow timed out after {timeout}s")


async def _download_result(img_info: dict, dest_path: str):
    """Download result image from ComfyUI."""
    import httpx
    params = {
        "filename": img_info["filename"],
        "subfolder": img_info.get("subfolder", ""),
        "type": img_info.get("type", "output"),
    }
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(f"{COMFYUI_URL}/view", params=params)
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            f.write(r.content)


async def tryon_single_frame(person_path: str, garment_path: str, output_path: str, seed: int = 42):
    """Run CatVTON on a single frame."""
    print("[TryOn] Preparing inputs...")

    mask_path = _create_upper_body_mask(person_path)

    person_name = f"tryon_person_{uuid.uuid4().hex[:8]}.png"
    mask_name = f"tryon_mask_{uuid.uuid4().hex[:8]}.png"
    garment_name = f"tryon_garment_{uuid.uuid4().hex[:8]}.png"

    person_name = await _upload_to_comfyui(person_path, person_name)
    mask_name = await _upload_to_comfyui(mask_path, mask_name)
    garment_name = await _upload_to_comfyui(garment_path, garment_name)

    print(f"[TryOn] Running CatVTON (seed={seed})...")
    workflow = _build_catvton_workflow(person_name, mask_name, garment_name, seed)
    results = await _submit_and_wait(workflow, timeout=300)

    if not results:
        raise RuntimeError("No output images from CatVTON")

    await _download_result(results[0], output_path)
    print(f"[TryOn] Result saved: {output_path}")

    try:
        os.unlink(mask_path)
    except OSError:
        pass


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Input video or image")
    parser.add_argument("garment", help="Garment image to try on")
    parser.add_argument("--output", default="", help="Output path")
    parser.add_argument("--frame-time", type=float, default=2.0,
                        help="Timestamp (seconds) to extract frame from video")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if not args.output:
        base = Path(args.input)
        args.output = str(base.parent / f"{base.stem}_tryon.png")

    is_video = args.input.lower().endswith((".mp4", ".avi", ".mov", ".mkv"))

    if is_video:
        print(f"[TryOn] Extracting frame at t={args.frame_time}s...")
        frame_path = _extract_frame(args.input, args.frame_time)
        print(f"[TryOn] Frame: {frame_path}")
    else:
        frame_path = args.input

    await tryon_single_frame(frame_path, args.garment, args.output, args.seed)

    if is_video and frame_path != args.input:
        try:
            os.unlink(frame_path)
        except OSError:
            pass

    print(f"\n[TryOn] Done: {args.output}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
