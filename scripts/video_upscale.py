#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video 4x super-resolution using Real-ESRGAN via spandrel + PyTorch.

Extracts frames → upscales each with GPU → re-encodes to H.264 MP4.
No basicsr/realesrgan pip packages needed — just spandrel + torch.

Usage:
    python scripts/video_upscale.py input.mp4 [--output output_4x.mp4] [--scale 4]
"""

import argparse, os, sys, time, subprocess, tempfile, shutil
from pathlib import Path

import torch
import numpy as np
from PIL import Image


def _get_ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def _extract_frames(video_path: str, out_dir: str, ffmpeg: str) -> tuple[int, str]:
    """Extract all frames from video. Returns (frame_count, fps_string)."""
    # Get fps
    r = subprocess.run(
        [ffmpeg, "-i", video_path],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    fps = "24"
    for line in r.stderr.split("\n"):
        if "Stream" in line and "Video:" in line:
            import re
            m = re.search(r"(\d+(?:\.\d+)?)\s*fps", line)
            if m:
                fps = m.group(1)
            break

    pattern = os.path.join(out_dir, "frame_%06d.png")
    subprocess.run(
        [ffmpeg, "-y", "-i", video_path, "-q:v", "1", pattern],
        check=True, capture_output=True,
    )
    frames = sorted(Path(out_dir).glob("frame_*.png"))
    return len(frames), fps


def _load_upscale_model(model_path: str, device: torch.device):
    """Load upscale model using spandrel (supports ESRGAN, SwinIR, etc.)."""
    from spandrel import ModelLoader
    model = ModelLoader().load_from_file(model_path)
    model = model.to(device).eval()
    return model


@torch.inference_mode()
def _upscale_frame(model, img_path: str, out_path: str, device: torch.device, tile_size: int = 512):
    """Upscale a single frame with optional tiling for VRAM management."""
    img = Image.open(img_path).convert("RGB")
    img_np = np.array(img).astype(np.float32) / 255.0
    img_tensor = torch.from_numpy(img_np).permute(2, 0, 1).unsqueeze(0).to(device)

    h, w = img_tensor.shape[2], img_tensor.shape[3]

    if h * w <= tile_size * tile_size:
        out_tensor = model(img_tensor)
    else:
        out_tensor = _tiled_upscale(model, img_tensor, tile_size)

    out_np = out_tensor.squeeze(0).permute(1, 2, 0).clamp(0, 1).cpu().numpy()
    out_img = Image.fromarray((out_np * 255).astype(np.uint8))
    out_img.save(out_path)


def _tiled_upscale(model, img_tensor: torch.Tensor, tile_size: int = 512, overlap: int = 32) -> torch.Tensor:
    """Process large images in tiles to avoid OOM."""
    scale = 4
    _, c, h, w = img_tensor.shape
    out_h, out_w = h * scale, w * scale
    output = torch.zeros(1, c, out_h, out_w, device=img_tensor.device)
    weights = torch.zeros(1, 1, out_h, out_w, device=img_tensor.device)

    for y in range(0, h, tile_size - overlap):
        for x in range(0, w, tile_size - overlap):
            y_end = min(y + tile_size, h)
            x_end = min(x + tile_size, w)
            tile = img_tensor[:, :, y:y_end, x:x_end]

            with torch.no_grad():
                tile_out = model(tile)

            oy, ox = y * scale, x * scale
            oh, ow = tile_out.shape[2], tile_out.shape[3]
            output[:, :, oy:oy+oh, ox:ox+ow] += tile_out
            weights[:, :, oy:oy+oh, ox:ox+ow] += 1

    output /= weights.clamp(min=1)
    return output


def upscale_video(input_path: str, output_path: str, model_path: str, scale: int = 4):
    ffmpeg = _get_ffmpeg()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print(f"[Upscale] Loading model: {os.path.basename(model_path)}")
    model = _load_upscale_model(model_path, device)
    print(f"[Upscale] Device: {device}")

    tmp_in = tempfile.mkdtemp(prefix="upscale_in_")
    tmp_out = tempfile.mkdtemp(prefix="upscale_out_")

    try:
        print(f"[Upscale] Extracting frames...")
        n_frames, fps = _extract_frames(input_path, tmp_in, ffmpeg)
        print(f"[Upscale] {n_frames} frames at {fps} fps")

        t0 = time.time()
        for i, frame_path in enumerate(sorted(Path(tmp_in).glob("frame_*.png"))):
            out_frame = os.path.join(tmp_out, frame_path.name)
            _upscale_frame(model, str(frame_path), out_frame, device, tile_size=512)
            elapsed = time.time() - t0
            fps_proc = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (n_frames - i - 1) / fps_proc if fps_proc > 0 else 0
            print(f"\r[Upscale] Frame {i+1}/{n_frames}  {fps_proc:.1f} fps  ETA {eta:.0f}s", end="", flush=True)

        print()

        # Check upscaled resolution
        sample = Image.open(os.path.join(tmp_out, "frame_000001.png"))
        print(f"[Upscale] Output resolution: {sample.width}x{sample.height}")

        # Re-encode with audio from original
        pattern = os.path.join(tmp_out, "frame_%06d.png")
        cmd = [
            ffmpeg, "-y",
            "-framerate", fps,
            "-i", pattern,
            "-i", input_path,
            "-map", "0:v", "-map", "1:a?",
            "-c:v", "libx264", "-preset", "slow", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            output_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)

        size = os.path.getsize(output_path) / 1e6
        total_time = time.time() - t0
        print(f"[Upscale] Done in {total_time:.0f}s -> {output_path} ({size:.1f} MB)")

    finally:
        shutil.rmtree(tmp_in, ignore_errors=True)
        shutil.rmtree(tmp_out, ignore_errors=True)
        del model
        torch.cuda.empty_cache()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Input video path")
    parser.add_argument("--output", default="", help="Output path (default: input_4x.mp4)")
    parser.add_argument("--model", default=r"C:\Users\PRO\Desktop\CUDA\ComfyUI\models\upscale_models\RealESRGAN_x4plus.pth")
    parser.add_argument("--scale", type=int, default=4)
    args = parser.parse_args()

    if not args.output:
        base = Path(args.input)
        args.output = str(base.parent / f"{base.stem}_{args.scale}x{base.suffix}")

    upscale_video(args.input, args.output, args.model, args.scale)
