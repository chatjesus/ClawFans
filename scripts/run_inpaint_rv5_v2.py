"""
RV5.1 Inpainting V2 - Preserve original body proportions.
Strategy: 
  1. Extract body edges from original image as structural guide
  2. Pre-fill masked area with skin-toned body shape
  3. Inpaint with moderate strength to preserve structure
"""
import os
os.environ["HF_HUB_OFFLINE"] = "1"

import torch, json
import numpy as np
from PIL import Image, ImageFilter, ImageDraw
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


def get_skin_color(image_arr, seg):
    skin_mask = np.zeros_like(seg, dtype=bool)
    for cls in [1, 10, 11, 12, 13]:  # face, arms, legs
        skin_mask |= (seg == cls)
    if np.sum(skin_mask) < 100:
        return np.array([180, 150, 130])
    return np.median(image_arr[skin_mask], axis=0).astype(np.uint8)


def prefill_body_shape(image_arr, seg, clothing_mask):
    """Pre-fill clothing area with skin color while preserving body edges."""
    result = image_arr.copy()
    skin_color = get_skin_color(image_arr, seg)
    print(f"  Skin color: RGB({skin_color[0]},{skin_color[1]},{skin_color[2]})")

    gray = cv2.cvtColor(image_arr, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 30, 100)

    cloth_ys, cloth_xs = np.where(clothing_mask > 0)
    skin_ys, skin_xs = np.where(
        np.isin(seg, [1, 10, 11, 12, 13])
    )

    for i in range(len(cloth_ys)):
        cy, cx = cloth_ys[i], cloth_xs[i]
        if edges[cy, cx] > 0:
            continue

        if len(skin_ys) > 0:
            dists = np.abs(skin_ys - cy) + np.abs(skin_xs - cx)
            nearest = np.argsort(dists)[:10]
            chosen = nearest[np.random.randint(0, len(nearest))]
            sy, sx = skin_ys[chosen], skin_xs[chosen]
            jitter = np.random.randint(-3, 4, size=3).astype(np.int16)
            result[cy, cx] = np.clip(
                image_arr[sy, sx].astype(np.int16) + jitter, 0, 255
            ).astype(np.uint8)
        else:
            jitter = np.random.randint(-5, 6, size=3).astype(np.int16)
            result[cy, cx] = np.clip(
                skin_color.astype(np.int16) + jitter, 0, 255
            ).astype(np.uint8)

    result_blur = cv2.GaussianBlur(result, (5, 5), 0)
    mask_bool = clothing_mask > 0
    for c in range(3):
        result[:, :, c] = np.where(mask_bool, result_blur[:, :, c], result[:, :, c])

    return result


def load_pipeline():
    from diffusers import StableDiffusionInpaintPipeline, DDIMScheduler, AutoencoderKL, UNet2DConditionModel
    from transformers import CLIPTextModel, CLIPTokenizer
    from diffusers.pipelines.stable_diffusion.convert_from_ckpt import (
        convert_ldm_unet_checkpoint, convert_ldm_vae_checkpoint,
    )

    state_dict = load_file(MODEL_PATH)
    with open(os.path.join(SD_INP_DIR, "unet", "config.json"), "r") as f:
        unet_config = json.load(f)
    unet_config.setdefault("class_embed_type", None)
    unet_config.setdefault("addition_embed_type", None)
    unet_config.setdefault("addition_time_embed_dim", None)
    unet_config.setdefault("transformer_layers_per_block", 1)
    unet_config.setdefault("projection_class_embeddings_input_dim", None)

    converted_unet = convert_ldm_unet_checkpoint(state_dict, unet_config)
    unet = UNet2DConditionModel(**unet_config)
    unet.load_state_dict(converted_unet, strict=False)
    unet = unet.half().cuda()

    with open(os.path.join(VAE_DIR, "config.json"), "r") as f:
        vae_config = json.load(f)
    converted_vae = convert_ldm_vae_checkpoint(state_dict, vae_config)
    vae = AutoencoderKL(**vae_config)
    vae.load_state_dict(converted_vae, strict=False)
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


def main():
    print("=== RV5.1 V2: Proportion-Preserving Inpainting ===\n")

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

    print("[2] Pre-filling with body-shaped skin texture...")
    prefilled = prefill_body_shape(img_arr, seg, dilated)
    prefilled_img = Image.fromarray(prefilled)

    ys, xs = np.where(dilated > 0)
    pad = 80
    y1, y2 = max(0, ys.min() - pad), min(h, ys.max() + pad)
    x1, x2 = max(0, xs.min() - pad), min(w, xs.max() + pad)
    cw, ch = x2 - x1, y2 - y1

    crop_pre = prefilled_img.crop((x1, y1, x2, y2))
    crop_mask = Image.fromarray(dilated[y1:y2, x1:x2])

    scale = min(512 / cw, 768 / ch)
    nw = int(cw * scale) // 8 * 8
    nh = int(ch * scale) // 8 * 8
    nw, nh = max(nw, 256), max(nh, 256)

    crop_r = crop_pre.resize((nw, nh), Image.LANCZOS)
    mask_r = crop_mask.resize((nw, nh), Image.NEAREST)
    print(f"  Crop: {cw}x{ch} -> {nw}x{nh}")

    print("\n[3] Loading RV5.1...")
    pipe = load_pipeline()

    prompt = "photorealistic female body, natural bare skin, realistic skin texture, natural body proportions, soft lighting, professional photography, 8k"
    neg = "clothes, fabric, garment, dress, shirt, bikini, text, watermark, ugly, deformed, blurry, anime, cartoon, illustration, 3d, cgi, low quality, unnatural proportions, distorted body"

    strengths = [0.75, 0.80, 0.85]
    seeds = [42, 888, 2024]

    print(f"\n[4] Generating {len(strengths)} variants (body-preserving)...")
    for i, (strength, seed) in enumerate(zip(strengths, seeds)):
        with torch.inference_mode():
            result = pipe(
                prompt=prompt, negative_prompt=neg,
                image=crop_r, mask_image=mask_r,
                num_inference_steps=50, guidance_scale=7.0, strength=strength,
                generator=torch.Generator("cuda").manual_seed(seed),
            ).images[0]

        result_full = result.resize((cw, ch), Image.LANCZOS)
        output = img_arr.copy()
        result_np = np.array(result_full)
        local_mask = dilated[y1:y2, x1:x2]

        blend = np.array(Image.fromarray(local_mask).filter(ImageFilter.GaussianBlur(15)))
        alpha = blend.astype(float) / 255.0

        for c in range(3):
            orig = output[y1:y2, x1:x2, c].astype(float)
            inp = result_np[:, :, c].astype(float)
            output[y1:y2, x1:x2, c] = (orig * (1 - alpha) + inp * alpha).astype(np.uint8)

        path = os.path.join(OUTPUT_DIR, f"inpaint_rv5v2_{i+1}.png")
        Image.fromarray(output).save(path, quality=95)
        print(f"  [{i+1}] strength={strength}, seed={seed} -> {path}")

    print("\n[Done]")
    del pipe
    torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
