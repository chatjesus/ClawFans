"""
V3: Pre-fill with real skin texture from the image, then refine with low-strength inpainting.
This preserves photorealism much better than generating from scratch.
"""
import os, torch
import numpy as np
from PIL import Image, ImageFilter
from scipy.ndimage import binary_dilation

MODEL_DIR = r"D:\ComfyUI_Models\CatVTON\stable-diffusion-inpainting"
VAE_DIR = r"D:\ComfyUI_Models\CatVTON\sd-vae-ft-mse"
IMAGE_PATH = r"C:\Users\PRO\Desktop\CUDA\synclub-local\backend\uploads\manga\53\thumb_a163_5s.png"
OUTPUT_DIR = r"C:\Users\PRO\Desktop\CUDA\synclub-local\backend\uploads\manga\53"


def generate_masks(image):
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

    clothing_mask = np.zeros_like(seg, dtype=np.uint8)
    for cls in [3, 4, 5, 6]:
        clothing_mask[seg == cls] = 255

    skin_mask = np.zeros_like(seg, dtype=bool)
    for cls in [1, 10, 11, 12, 13]:  # face, arms, legs
        skin_mask |= (seg == cls)

    return clothing_mask, skin_mask, seg


def prefill_with_skin(image_arr, clothing_mask, skin_mask):
    """Fill clothing area with skin texture sampled from exposed skin."""
    h, w, c = image_arr.shape
    result = image_arr.copy()

    skin_pixels = image_arr[skin_mask]
    if len(skin_pixels) < 50:
        median_color = np.array([180, 150, 130], dtype=np.uint8)
    else:
        median_color = np.median(skin_pixels, axis=0).astype(np.uint8)

    cloth_ys, cloth_xs = np.where(clothing_mask > 0)
    if len(cloth_ys) == 0:
        return result

    skin_ys, skin_xs = np.where(skin_mask)

    for i in range(len(cloth_ys)):
        cy, cx = cloth_ys[i], cloth_xs[i]
        if len(skin_ys) > 0:
            dists = (skin_ys - cy) ** 2 + (skin_xs - cx) ** 2
            nearest_indices = np.argsort(dists)[:20]
            chosen = nearest_indices[np.random.randint(0, len(nearest_indices))]
            sy, sx = skin_ys[chosen], skin_xs[chosen]
            jitter = np.random.randint(-2, 3, size=3).astype(np.int16)
            pixel = np.clip(image_arr[sy, sx].astype(np.int16) + jitter, 0, 255).astype(np.uint8)
            result[cy, cx] = pixel
        else:
            jitter = np.random.randint(-5, 6, size=3).astype(np.int16)
            result[cy, cx] = np.clip(median_color.astype(np.int16) + jitter, 0, 255).astype(np.uint8)

    return result


def load_pipeline():
    from diffusers import StableDiffusionInpaintPipeline, DDIMScheduler, AutoencoderKL
    from transformers import CLIPTextModel, CLIPTokenizer
    from diffusers import UNet2DConditionModel

    scheduler = DDIMScheduler.from_pretrained(os.path.join(MODEL_DIR, "scheduler"))
    tokenizer = CLIPTokenizer.from_pretrained(os.path.join(MODEL_DIR, "tokenizer"))
    text_encoder = CLIPTextModel.from_pretrained(
        os.path.join(MODEL_DIR, "text_encoder"), torch_dtype=torch.float16)
    unet = UNet2DConditionModel.from_pretrained(
        os.path.join(MODEL_DIR, "unet"), torch_dtype=torch.float16)
    vae = AutoencoderKL.from_pretrained(VAE_DIR, torch_dtype=torch.float16)

    pipe = StableDiffusionInpaintPipeline(
        vae=vae, text_encoder=text_encoder, tokenizer=tokenizer,
        unet=unet, scheduler=scheduler,
        safety_checker=None, feature_extractor=None, requires_safety_checker=False,
    )
    pipe = pipe.to("cuda")
    pipe.enable_attention_slicing()
    return pipe


def run_inpainting(pipe, prefilled, mask_pil, seed, strength=0.75, steps=50):
    w, h = prefilled.size
    nw = (w // 8) * 8
    nh = (h // 8) * 8
    img_r = prefilled.resize((nw, nh), Image.LANCZOS)
    mask_r = mask_pil.resize((nw, nh), Image.NEAREST)

    with torch.inference_mode():
        result = pipe(
            prompt="realistic human skin, smooth natural skin texture, photorealistic photo, detailed pores, natural body, high quality",
            negative_prompt="clothes, fabric, garment, text, watermark, ugly, deformed, blurry, anime, cartoon, illustration, painting, 3d render, artificial",
            image=img_r,
            mask_image=mask_r,
            num_inference_steps=steps,
            guidance_scale=7.5,
            strength=strength,
            generator=torch.Generator("cuda").manual_seed(seed),
        ).images[0]

    return result.resize((w, h), Image.LANCZOS)


def main():
    print("=== V3: Skin Prefill + Low-Strength Inpainting ===\n")

    image = Image.open(IMAGE_PATH).convert("RGB")
    print(f"Input: {image.size[0]}x{image.size[1]}")

    print("[1] Human parsing...")
    clothing_mask, skin_mask, seg = generate_masks(image)
    cloth_pct = np.sum(clothing_mask > 0) / clothing_mask.size * 100
    skin_pct = np.sum(skin_mask) / skin_mask.size * 100
    print(f"  Clothing: {cloth_pct:.1f}%, Skin: {skin_pct:.1f}%")

    dilated = np.array(Image.fromarray(clothing_mask).filter(ImageFilter.MaxFilter(15)))
    mask_pil = Image.fromarray(dilated)

    print("[2] Pre-filling with skin texture...")
    img_arr = np.array(image)
    prefilled = prefill_with_skin(img_arr, dilated, skin_mask)
    prefilled_img = Image.fromarray(prefilled)
    prefilled_img.save(os.path.join(OUTPUT_DIR, "prefilled.png"))
    print("  Saved prefilled.png")

    print("[3] Loading SD 1.5 inpainting...")
    pipe = load_pipeline()

    configs = [
        (42, 0.6, 50),
        (123, 0.65, 50),
        (777, 0.55, 50),
        (42, 0.7, 40),
    ]

    print(f"[4] Running {len(configs)} variations...")
    for i, (seed, strength, steps) in enumerate(configs):
        print(f"  Config {i+1}: seed={seed}, strength={strength}, steps={steps}")
        result = run_inpainting(pipe, prefilled_img, mask_pil, seed, strength, steps)

        blend_mask = mask_pil.filter(ImageFilter.GaussianBlur(radius=8))
        blend_arr = np.array(blend_mask).astype(float) / 255.0
        orig = np.array(image).astype(float)
        res = np.array(result).astype(float)
        blended = orig * (1 - blend_arr[:, :, None]) + res * blend_arr[:, :, None]
        final = Image.fromarray(blended.astype(np.uint8))

        path = os.path.join(OUTPUT_DIR, f"inpaint_v3_{i+1}.png")
        final.save(path, quality=95)
        print(f"    -> {path}")

    print("\n[Done] Generated 4 variants - pick the best!")

    del pipe
    torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
