"""
RV5.1 V3: Frequency-separation approach for body-faithful inpainting.

Strategy:
  1. Inpaint at full strength -> good skin texture but wrong proportions
  2. Decompose both original and inpainted into low-freq (shape) + high-freq (detail)
  3. Combine: original shape + inpainted skin texture
  4. Color-correct to skin tone
"""
import os
os.environ["HF_HUB_OFFLINE"] = "1"

import torch, json
import numpy as np
from PIL import Image, ImageFilter
from safetensors.torch import load_file
import cv2

MODEL_PATH = r"D:\ComfyUI_Models\checkpoints\Realistic_Vision_V5.1_fp16-no-ema-inpainting.safetensors"
SD_INP_DIR = r"D:\ComfyUI_Models\CatVTON\stable-diffusion-inpainting"
VAE_DIR = r"D:\ComfyUI_Models\CatVTON\sd-vae-ft-mse"
HIRES_PATH = r"C:\Users\PRO\Desktop\CUDA\synclub-local\backend\uploads\manga\53\frame_4x_5s.png"
OUTPUT_DIR = r"C:\Users\PRO\Desktop\CUDA\synclub-local\backend\uploads\manga\53"


def generate_masks(image):
    os.environ.pop("TRANSFORMERS_OFFLINE", None)
    from transformers import AutoModelForSemanticSegmentation, AutoImageProcessor
    processor = AutoImageProcessor.from_pretrained("fashn-ai/fashn-human-parser", use_fast=False)
    model = AutoModelForSemanticSegmentation.from_pretrained("fashn-ai/fashn-human-parser").cuda().eval()
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.cuda() for k, v in inputs.items()}
    with torch.inference_mode():
        logits = model(**inputs).logits
        logits = torch.nn.functional.interpolate(logits, size=image.size[::-1], mode="bilinear", align_corners=False)
        seg = logits.argmax(dim=1)[0].cpu().numpy()
    del model
    torch.cuda.empty_cache()
    return seg


def load_pipeline():
    from diffusers import StableDiffusionInpaintPipeline, DDIMScheduler, AutoencoderKL, UNet2DConditionModel
    from transformers import CLIPTextModel, CLIPTokenizer
    from diffusers.pipelines.stable_diffusion.convert_from_ckpt import (
        convert_ldm_unet_checkpoint, convert_ldm_vae_checkpoint,
    )

    state_dict = load_file(MODEL_PATH)
    with open(os.path.join(SD_INP_DIR, "unet", "config.json"), "r") as f:
        unet_config = json.load(f)
    for k in ["class_embed_type", "addition_embed_type", "addition_time_embed_dim", "projection_class_embeddings_input_dim"]:
        unet_config.setdefault(k, None)
    unet_config.setdefault("transformer_layers_per_block", 1)

    unet = UNet2DConditionModel(**unet_config)
    unet.load_state_dict(convert_ldm_unet_checkpoint(state_dict, unet_config), strict=False)
    unet = unet.half().cuda()

    with open(os.path.join(VAE_DIR, "config.json"), "r") as f:
        vae_config = json.load(f)
    vae = AutoencoderKL(**vae_config)
    vae.load_state_dict(convert_ldm_vae_checkpoint(state_dict, vae_config), strict=False)
    vae = vae.half().cuda()

    os.environ.pop("TRANSFORMERS_OFFLINE", None)
    text_encoder = CLIPTextModel.from_pretrained(
        os.path.join(SD_INP_DIR, "text_encoder"), torch_dtype=torch.float16).cuda()
    tokenizer = CLIPTokenizer.from_pretrained(os.path.join(SD_INP_DIR, "tokenizer"))
    scheduler = DDIMScheduler.from_pretrained(os.path.join(SD_INP_DIR, "scheduler"))
    del state_dict
    torch.cuda.empty_cache()

    pipe = StableDiffusionInpaintPipeline(
        vae=vae, text_encoder=text_encoder, tokenizer=tokenizer,
        unet=unet, scheduler=scheduler,
        safety_checker=None, feature_extractor=None, requires_safety_checker=False,
    )
    pipe.enable_attention_slicing()
    return pipe


def frequency_separate(img_arr, sigma=15):
    """Split image into low-frequency (shape) and high-frequency (detail)."""
    low = cv2.GaussianBlur(img_arr.astype(np.float32), (0, 0), sigma)
    high = img_arr.astype(np.float32) - low
    return low, high


def skin_color_transfer(original_crop, inpainted_crop, mask, seg_crop):
    """Transfer skin appearance from inpainted to original body structure."""
    h, w = mask.shape
    orig = original_crop.astype(np.float32)
    inp = inpainted_crop.astype(np.float32)
    mask_f = mask.astype(np.float32) / 255.0

    skin_in_seg = np.zeros_like(seg_crop, dtype=bool)
    for cls in [1, 10, 11, 12, 13]:
        skin_in_seg |= (seg_crop == cls)
    skin_ref = orig[skin_in_seg] if np.sum(skin_in_seg) > 50 else orig[mask > 0]
    target_mean = np.mean(skin_ref, axis=0)
    target_std = np.std(skin_ref, axis=0) + 1e-6

    orig_low, orig_high = frequency_separate(orig, sigma=20)
    inp_low, inp_high = frequency_separate(inp, sigma=20)

    result = np.zeros_like(orig)
    for c in range(3):
        structure = orig_low[:, :, c]

        cloth_region = mask > 0
        cloth_mean = np.mean(structure[cloth_region]) if np.sum(cloth_region) > 0 else 128
        skin_mean_val = target_mean[c]
        shift = skin_mean_val - cloth_mean

        adjusted_structure = structure.copy()
        adjusted_structure[cloth_region] += shift * 0.7

        detail = inp_high[:, :, c]

        combined = adjusted_structure + detail * 0.8
        result[:, :, c] = combined

    result = np.clip(result, 0, 255).astype(np.uint8)

    orig_lab = cv2.cvtColor(orig.astype(np.uint8), cv2.COLOR_RGB2LAB).astype(np.float32)
    result_lab = cv2.cvtColor(result, cv2.COLOR_RGB2LAB).astype(np.float32)

    inp_colors = inp[mask > 0]
    if len(inp_colors) > 0:
        inp_crop_lab = cv2.cvtColor(inp.astype(np.uint8), cv2.COLOR_RGB2LAB).astype(np.float32)
        for ch in [1, 2]:  # a, b channels
            result_lab[:, :, ch] = np.where(
                mask > 0,
                inp_crop_lab[:, :, ch] * 0.7 + orig_lab[:, :, ch] * 0.3,
                result_lab[:, :, ch]
            )

    result = cv2.cvtColor(np.clip(result_lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB)
    return result


def main():
    print("=== RV5.1 V3: Body-Faithful Frequency Separation ===\n")

    image = Image.open(HIRES_PATH).convert("RGB")
    w, h = image.size
    img_arr = np.array(image)
    print(f"Input: {w}x{h}")

    print("[1] Human parsing...")
    seg = generate_masks(image)
    clothing_mask = np.zeros_like(seg, dtype=np.uint8)
    for cls in [3, 4, 5, 6]:
        clothing_mask[seg == cls] = 255
    dilated = np.array(Image.fromarray(clothing_mask).filter(ImageFilter.MaxFilter(21)))

    ys, xs = np.where(dilated > 0)
    pad = 80
    y1, y2 = max(0, ys.min() - pad), min(h, ys.max() + pad)
    x1, x2 = max(0, xs.min() - pad), min(w, xs.max() + pad)
    cw, ch_ = x2 - x1, y2 - y1

    crop_orig = img_arr[y1:y2, x1:x2].copy()
    crop_mask = dilated[y1:y2, x1:x2]
    crop_seg = seg[y1:y2, x1:x2]

    scale = min(512 / cw, 768 / ch_)
    nw = int(cw * scale) // 8 * 8
    nh = int(ch_ * scale) // 8 * 8
    nw, nh = max(nw, 256), max(nh, 256)

    crop_img = Image.fromarray(crop_orig).resize((nw, nh), Image.LANCZOS)
    mask_img = Image.fromarray(crop_mask).resize((nw, nh), Image.NEAREST)
    print(f"  Crop: {cw}x{ch_} -> inpaint at {nw}x{nh}")

    print("\n[2] Loading RV5.1...")
    pipe = load_pipeline()

    prompt = "photorealistic nude female body, natural bare skin, realistic skin texture with pores, soft natural lighting, professional photography, 8k uhd"
    neg = "clothes, fabric, garment, dress, shirt, bikini, text, watermark, ugly, deformed, blurry, anime, cartoon, illustration, 3d, cgi, low quality"

    seeds = [42, 888, 2024]
    print(f"\n[3] Inpainting {len(seeds)} seeds at full strength...")

    for idx, seed in enumerate(seeds):
        with torch.inference_mode():
            result_small = pipe(
                prompt=prompt, negative_prompt=neg,
                image=crop_img, mask_image=mask_img,
                num_inference_steps=50, guidance_scale=7.5, strength=0.99,
                generator=torch.Generator("cuda").manual_seed(seed),
            ).images[0]

        inpainted_crop = np.array(result_small.resize((cw, ch_), Image.LANCZOS))

        print(f"\n[4-{idx+1}] Frequency separation + body structure transfer (seed={seed})...")
        merged = skin_color_transfer(crop_orig, inpainted_crop, crop_mask, crop_seg)

        blend_mask = cv2.GaussianBlur(crop_mask.astype(np.float32), (0, 0), 12) / 255.0
        output = img_arr.copy()
        for c in range(3):
            orig_ch = output[y1:y2, x1:x2, c].astype(np.float32)
            merged_ch = merged[:, :, c].astype(np.float32)
            output[y1:y2, x1:x2, c] = (
                orig_ch * (1 - blend_mask) + merged_ch * blend_mask
            ).astype(np.uint8)

        path = os.path.join(OUTPUT_DIR, f"inpaint_rv5v3_{idx+1}.png")
        Image.fromarray(output).save(path, quality=95)
        print(f"  -> {path}")

    print("\n[Done]")
    del pipe
    torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
