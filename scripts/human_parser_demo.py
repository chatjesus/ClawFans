#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Human Parser Demo using fashn-human-parser
Academic research tool for clothing segmentation and body parsing
"""

import argparse
import os
import sys
import subprocess
import tempfile
from pathlib import Path

import torch
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

# Model info
MODEL_NAME = "fashn-ai/fashn-human-parser"

# 18 semantic classes
ID2LABEL = {
    0: "background", 1: "face", 2: "hair", 3: "top", 4: "dress",
    5: "skirt", 6: "pants", 7: "belt", 8: "bag", 9: "hat",
    10: "scarf", 11: "glasses", 12: "arms", 13: "hands",
    14: "legs", 15: "feet", 16: "torso", 17: "jewelry",
}

# Color map for visualization (18 distinct colors)
COLORS = [
    "#000000",  # background - black
    "#FFE4C4",  # face - bisque
    "#8B4513",  # hair - saddle brown
    "#FF0000",  # top - red
    "#FF69B4",  # dress - hot pink
    "#FFB6C1",  # skirt - light pink
    "#0000FF",  # pants - blue
    "#FFD700",  # belt - gold
    "#FFA500",  # bag - orange
    "#800080",  # hat - purple
    "#00CED1",  # scarf - dark turquoise
    "#32CD32",  # glasses - lime green
    "#FFC0CB",  # arms - pink
    "#FF6347",  # hands - tomato
    "#DDA0DD",  # legs - plum
    "#F0E68C",  # feet - khaki
    "#FF4500",  # torso - orange red
    "#00FF00",  # jewelry - lime
]


def _get_ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def extract_frame(video_path: str, time_sec: float = 2.0) -> str:
    """Extract a single frame from video at given timestamp."""
    ffmpeg = _get_ffmpeg()
    out = tempfile.mktemp(suffix=".png")
    subprocess.run(
        [ffmpeg, "-y", "-ss", str(time_sec), "-i", video_path,
         "-frames:v", "1", "-q:v", "1", out],
        check=True, capture_output=True,
    )
    return out


def load_model():
    """Load fashn-human-parser model and processor."""
    from transformers import AutoModelForSemanticSegmentation, AutoImageProcessor
    
    print(f"[Parser] Loading {MODEL_NAME}...")
    processor = AutoImageProcessor.from_pretrained(
        MODEL_NAME, 
        trust_remote_code=True,
        use_fast=False,
    )
    model = AutoModelForSemanticSegmentation.from_pretrained(
        MODEL_NAME,
        trust_remote_code=True,
    )
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device).eval()
    print(f"[Parser] Model loaded on {device}")
    
    return model, processor, device


@torch.inference_mode()
def parse_image(model, processor, device, image_path: str):
    """Parse image and return segmentation mask."""
    image = Image.open(image_path).convert("RGB")
    
    # Preprocess
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    
    # Inference
    outputs = model(**inputs)
    logits = outputs.logits
    
    # Upsample to original size
    upsampled_logits = torch.nn.functional.interpolate(
        logits,
        size=image.size[::-1],  # (H, W)
        mode="bilinear",
        align_corners=False,
    )
    
    # Get prediction
    pred_mask = upsampled_logits.argmax(dim=1)[0].cpu().numpy()
    
    return image, pred_mask


def create_visualization(image: Image.Image, mask: np.ndarray, output_path: str):
    """Create side-by-side visualization of original and parsed result."""
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    
    # Original image
    axes[0].imshow(image)
    axes[0].set_title("Original")
    axes[0].axis("off")
    
    # Segmentation mask with colors
    cmap = ListedColormap(COLORS)
    axes[1].imshow(mask, cmap=cmap, vmin=0, vmax=17)
    axes[1].set_title("Semantic Segmentation")
    axes[1].axis("off")
    
    # Overlay
    img_array = np.array(image)
    mask_rgb = np.zeros_like(img_array)
    for i, color in enumerate(COLORS):
        rgb = tuple(int(color.lstrip('#')[j:j+2], 16) for j in (0, 2, 4))
        mask_rgb[mask == i] = rgb
    
    alpha = 0.5
    overlay = (img_array * (1 - alpha) + mask_rgb * alpha).astype(np.uint8)
    axes[2].imshow(overlay)
    axes[2].set_title("Overlay")
    axes[2].axis("off")
    
    # Add legend
    legend_text = " | ".join([f"{k}: {v}" for k, v in ID2LABEL.items() if k > 0])
    fig.text(0.5, 0.02, legend_text, ha='center', fontsize=8, wrap=True)
    
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.15)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"[Parser] Visualization saved: {output_path}")


def extract_clothing_mask(mask: np.ndarray, clothing_classes: list = None) -> np.ndarray:
    """Extract clothing regions from mask.
    
    Args:
        mask: Segmentation mask
        clothing_classes: List of class IDs for clothing (default: top, dress, skirt)
    
    Returns:
        Binary mask for clothing regions
    """
    if clothing_classes is None:
        clothing_classes = [3, 4, 5]  # top, dress, skirt
    
    clothing_mask = np.zeros_like(mask)
    for cls in clothing_classes:
        clothing_mask[mask == cls] = 255
    
    return clothing_mask


def main():
    parser = argparse.ArgumentParser(description="Human Parser Demo")
    parser.add_argument("input", help="Input image or video path")
    parser.add_argument("--output", "-o", default="", help="Output directory")
    parser.add_argument("--frame-time", type=float, default=2.0, 
                        help="Timestamp to extract from video (seconds)")
    parser.add_argument("--classes", nargs="+", type=int, default=[3, 4, 5],
                        help="Class IDs to extract (default: 3 4 5 = top dress skirt)")
    args = parser.parse_args()
    
    # Determine input type
    is_video = args.input.lower().endswith((".mp4", ".avi", ".mov", ".mkv"))
    
    if is_video:
        print(f"[Parser] Extracting frame at t={args.frame_time}s from video...")
        frame_path = extract_frame(args.input, args.frame_time)
    else:
        frame_path = args.input
    
    # Load model
    model, processor, device = load_model()
    
    # Parse image
    print(f"[Parser] Analyzing image...")
    image, mask = parse_image(model, processor, device, frame_path)
    
    # Output directory
    if not args.output:
        if is_video:
            args.output = str(Path(args.input).parent)
        else:
            args.output = str(Path(args.input).parent)
    
    os.makedirs(args.output, exist_ok=True)
    
    # Save visualization
    base_name = Path(args.input).stem
    vis_path = os.path.join(args.output, f"{base_name}_parsed.png")
    create_visualization(image, mask, vis_path)
    
    # Save mask as image
    mask_img = Image.fromarray((mask * 255 // 17).astype(np.uint8))
    mask_path = os.path.join(args.output, f"{base_name}_mask.png")
    mask_img.save(mask_path)
    print(f"[Parser] Mask saved: {mask_path}")
    
    # Extract clothing mask
    clothing_mask = extract_clothing_mask(mask, args.classes)
    clothing_img = Image.fromarray(clothing_mask.astype(np.uint8))
    clothing_path = os.path.join(args.output, f"{base_name}_clothing.png")
    clothing_img.save(clothing_path)
    print(f"[Parser] Clothing mask saved: {clothing_path}")
    
    # Print statistics
    print("\n[Parser] Segmentation Statistics:")
    for class_id, label in ID2LABEL.items():
        pixels = np.sum(mask == class_id)
        pct = pixels / mask.size * 100
        if pct > 0.5:  # Only show significant regions
            print(f"  {label:12s}: {pixels:6d} px ({pct:5.2f}%)")
    
    # Cleanup temp file
    if is_video and frame_path != args.input:
        try:
            os.unlink(frame_path)
        except OSError:
            pass
    
    print(f"\n[Parser] Done! Results in: {args.output}")


if __name__ == "__main__":
    main()
