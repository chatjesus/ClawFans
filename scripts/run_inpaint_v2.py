"""
High-quality clothing inpainting using crop-inpaint-paste approach.
Processes at SD 1.5's optimal 512x512 resolution for best quality.
Uses high-res 4x upscaled frame for more detail.
"""
import os, sys, torch
import numpy as np
from PIL import Image, ImageFilter, ImageDraw

MODEL_DIR = r"D:\ComfyUI_Models\CatVTON\stable-diffusion-inpainting"
VAE_DIR = r"D:\ComfyUI_Models\CatVTON\sd-vae-ft-mse"
IMAGE_PATH = r"C:\Users\PRO\Desktop\CUDA\synclub-local\backend\uploads\manga\53\thumb_a163_5s.png"
OUTPUT_DIR = r"C:\Users\PRO\Desktop\CUDA\synclub-local\backend\uploads\manga\53"


def generate_clothing_mask(image):
    """Generate precise clothing mask using human parser."""
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

    # Classes: 3=upper-clothes, 4=dress, 5=skirt, 6=pants, 7=belt
    mask = np.zeros_like(seg, dtype=np.uint8)
    for cls in [3, 4, 5, 6]:
        mask[seg == cls] = 255
    return mask, seg


def get_skin_color(image, seg):
    """Extract average skin color from exposed skin areas (face, arms, legs)."""
    img_arr = np.array(image)
    # Skin classes: 1=face, 10=left-arm, 11=right-arm, 12=left-leg, 13=right-leg
    skin_mask = np.zeros_like(seg, dtype=bool)
    for cls in [1, 10, 11, 12, 13]:
        skin_mask |= (seg == cls)
    if np.sum(skin_mask) < 100:
        return (200, 170, 150)
    skin_pixels = img_arr[skin_mask]
    return tuple(np.median(skin_pixels, axis=0).astype(int))


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


def crop_inpaint_paste(pipe, image, mask_arr, seg, seed=42):
    """
    Crop regions around clothing, inpaint at 512x512, paste back.
    This gives much better quality than full-image inpainting.
    """
    w, h = image.size
    img_arr = np.array(image)
    skin_color = get_skin_color(image, seg)
    print(f"  Skin color reference: RGB{skin_color}")

    mask_dilated = Image.fromarray(mask_arr).filter(ImageFilter.MaxFilter(15))
    mask_np = np.array(mask_dilated)

    ys, xs = np.where(mask_np > 0)
    if len(ys) == 0:
        print("  No clothing detected!")
        return image

    y_min, y_max = ys.min(), ys.max()
    x_min, x_max = xs.min(), xs.max()
    print(f"  Clothing bbox: ({x_min},{y_min}) - ({x_max},{y_max})")

    padding = 64
    crop_x1 = max(0, x_min - padding)
    crop_y1 = max(0, y_min - padding)
    crop_x2 = min(w, x_max + padding)
    crop_y2 = min(h, y_max + padding)

    crop_w = crop_x2 - crop_x1
    crop_h = crop_y2 - crop_y1
    print(f"  Crop region: {crop_w}x{crop_h}")

    crop_img = image.crop((crop_x1, crop_y1, crop_x2, crop_y2))
    crop_mask = Image.fromarray(mask_np[crop_y1:crop_y2, crop_x1:crop_x2])

    target_size = 512
    scale = target_size / max(crop_w, crop_h)
    new_w = int(crop_w * scale) // 8 * 8
    new_h = int(crop_h * scale) // 8 * 8
    new_w = max(new_w, 256)
    new_h = max(new_h, 256)

    crop_resized = crop_img.resize((new_w, new_h), Image.LANCZOS)
    mask_resized = crop_mask.resize((new_w, new_h), Image.NEAREST)
    print(f"  Inpainting at {new_w}x{new_h}...")

    prompts = [
        "photorealistic bare skin, natural human body, smooth skin texture, realistic photograph, high quality, natural lighting, detailed skin pores",
    ]
    neg = "clothes, fabric, garment, text, watermark, ugly, deformed, blurry, anime, cartoon, drawing, illustration, painting, 3d render, cgi"

    best_result = None
    best_score = float("-inf")

    for attempt, prompt in enumerate(prompts):
        for s in [seed, seed + 100, seed + 200]:
            with torch.inference_mode():
                result = pipe(
                    prompt=prompt,
                    negative_prompt=neg,
                    image=crop_resized,
                    mask_image=mask_resized,
                    num_inference_steps=50,
                    guidance_scale=8.0,
                    strength=0.99,
                    generator=torch.Generator("cuda").manual_seed(s),
                ).images[0]

            result_arr = np.array(result)
            mask_eval = np.array(mask_resized)
            if result_arr.shape[:2] != mask_eval.shape[:2]:
                mask_eval = np.array(crop_mask.resize((result_arr.shape[1], result_arr.shape[0]), Image.NEAREST))
            mask_bool = mask_eval > 0
            inpainted_region = result_arr[mask_bool]
            if len(inpainted_region) > 0:
                avg_color = np.mean(inpainted_region, axis=0)
                target = np.array(skin_color)
                color_dist = np.linalg.norm(avg_color - target)
                score = -color_dist
                print(f"    Seed {s}: avg RGB=({avg_color[0]:.0f},{avg_color[1]:.0f},{avg_color[2]:.0f}), dist={color_dist:.1f}")
                if score > best_score:
                    best_score = score
                    best_result = result

    result_fullsize = best_result.resize((crop_w, crop_h), Image.LANCZOS)

    output = img_arr.copy()
    result_np = np.array(result_fullsize)
    local_mask = mask_np[crop_y1:crop_y2, crop_x1:crop_x2]

    feather = ImageFilter.GaussianBlur(radius=5)
    blend_mask = Image.fromarray(local_mask).filter(feather)
    blend_arr = np.array(blend_mask).astype(float) / 255.0

    for c in range(3):
        region = output[crop_y1:crop_y2, crop_x1:crop_x2, c].astype(float)
        inpainted = result_np[:, :, c].astype(float)
        output[crop_y1:crop_y2, crop_x1:crop_x2, c] = (
            region * (1 - blend_arr) + inpainted * blend_arr
        ).astype(np.uint8)

    return Image.fromarray(output)


def main():
    print("=== High-Quality Clothing Inpainting (Crop-Paste) ===\n")

    image = Image.open(IMAGE_PATH).convert("RGB")
    print(f"Input: {IMAGE_PATH} ({image.size[0]}x{image.size[1]})")

    print("\n[Step 1] Human parsing...")
    mask_arr, seg = generate_clothing_mask(image)
    coverage = np.sum(mask_arr > 0) / mask_arr.size * 100
    print(f"  Clothing mask: {coverage:.1f}% coverage")

    print("\n[Step 2] Loading SD 1.5 inpainting...")
    pipe = load_pipeline()

    print("\n[Step 3] Crop-inpaint-paste (3 seeds, pick best)...")
    result = crop_inpaint_paste(pipe, image, mask_arr, seg, seed=42)

    out_path = os.path.join(OUTPUT_DIR, "inpaint_hq.png")
    result.save(out_path, quality=95)
    print(f"\n[Done] {out_path}")

    del pipe
    torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
