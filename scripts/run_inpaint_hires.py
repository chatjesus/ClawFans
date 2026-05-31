"""
High-res inpainting: Use 4x upscaled frame, crop body region to SD1.5 optimal 512x768.
"""
import os, torch
import numpy as np
from PIL import Image, ImageFilter

MODEL_DIR = r"D:\ComfyUI_Models\CatVTON\stable-diffusion-inpainting"
VAE_DIR = r"D:\ComfyUI_Models\CatVTON\sd-vae-ft-mse"
HIRES_PATH = r"C:\Users\PRO\Desktop\CUDA\synclub-local\backend\uploads\manga\53\frame_4x_5s.png"
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
    clothing = np.zeros_like(seg, dtype=np.uint8)
    for cls in [3, 4, 5, 6]:
        clothing[seg == cls] = 255
    skin = np.zeros_like(seg, dtype=bool)
    for cls in [1, 10, 11, 12, 13]:
        skin |= (seg == cls)
    return clothing, skin, seg


def load_pipeline():
    from diffusers import StableDiffusionInpaintPipeline, DDIMScheduler, AutoencoderKL
    from transformers import CLIPTextModel, CLIPTokenizer
    from diffusers import UNet2DConditionModel

    pipe = StableDiffusionInpaintPipeline(
        vae=AutoencoderKL.from_pretrained(VAE_DIR, torch_dtype=torch.float16),
        text_encoder=CLIPTextModel.from_pretrained(
            os.path.join(MODEL_DIR, "text_encoder"), torch_dtype=torch.float16),
        tokenizer=CLIPTokenizer.from_pretrained(os.path.join(MODEL_DIR, "tokenizer")),
        unet=UNet2DConditionModel.from_pretrained(
            os.path.join(MODEL_DIR, "unet"), torch_dtype=torch.float16),
        scheduler=DDIMScheduler.from_pretrained(os.path.join(MODEL_DIR, "scheduler")),
        safety_checker=None, feature_extractor=None, requires_safety_checker=False,
    )
    pipe = pipe.to("cuda")
    pipe.enable_attention_slicing()
    return pipe


def main():
    print("=== High-Res Crop Inpainting ===\n")

    image = Image.open(HIRES_PATH).convert("RGB")
    w, h = image.size
    print(f"Input: {w}x{h}")

    print("[1] Parsing...")
    clothing, skin_mask, seg = generate_masks(image)
    dilated = np.array(Image.fromarray(clothing).filter(ImageFilter.MaxFilter(25)))

    ys, xs = np.where(dilated > 0)
    if len(ys) == 0:
        print("No clothing found!")
        return

    pad = 100
    y1 = max(0, ys.min() - pad)
    y2 = min(h, ys.max() + pad)
    x1 = max(0, xs.min() - pad)
    x2 = min(w, xs.max() + pad)
    print(f"  Clothing region: ({x1},{y1})-({x2},{y2}), size {x2-x1}x{y2-y1}")

    crop = image.crop((x1, y1, x2, y2))
    crop_mask = Image.fromarray(dilated[y1:y2, x1:x2])

    target_w, target_h = 512, 768
    cw, ch = crop.size
    scale = min(target_w / cw, target_h / ch)
    nw = int(cw * scale) // 8 * 8
    nh = int(ch * scale) // 8 * 8
    nw = max(nw, 256)
    nh = max(nh, 256)
    print(f"  Inpaint size: {nw}x{nh}")

    crop_r = crop.resize((nw, nh), Image.LANCZOS)
    mask_r = crop_mask.resize((nw, nh), Image.NEAREST)

    print("[2] Loading pipeline...")
    pipe = load_pipeline()

    prompts_seeds = [
        ("photorealistic nude female body, bare skin, natural skin texture, detailed skin pores, natural lighting, high resolution photograph, professional photography", 42),
        ("realistic bare female torso, smooth skin, natural body, photographic quality, skin detail, warm lighting", 888),
        ("naked female body, photorealistic skin, natural complexion, professional photo, studio quality", 2024),
    ]

    neg = "clothes, fabric, garment, clothing, dress, shirt, text, watermark, ugly, deformed, blurry, anime, cartoon, illustration, painting, 3d, cgi, artificial"

    print(f"[3] Running {len(prompts_seeds)} variations...")
    for i, (prompt, seed) in enumerate(prompts_seeds):
        with torch.inference_mode():
            result = pipe(
                prompt=prompt,
                negative_prompt=neg,
                image=crop_r,
                mask_image=mask_r,
                num_inference_steps=50,
                guidance_scale=7.5,
                strength=0.99,
                generator=torch.Generator("cuda").manual_seed(seed),
            ).images[0]

        result_full = result.resize((cw, ch), Image.LANCZOS)

        output = np.array(image).copy()
        result_np = np.array(result_full)
        local_mask = dilated[y1:y2, x1:x2]
        blend = np.array(Image.fromarray(local_mask).filter(ImageFilter.GaussianBlur(10)))
        alpha = blend.astype(float) / 255.0

        for c in range(3):
            orig = output[y1:y2, x1:x2, c].astype(float)
            inp = result_np[:, :, c].astype(float)
            output[y1:y2, x1:x2, c] = (orig * (1 - alpha) + inp * alpha).astype(np.uint8)

        out_path = os.path.join(OUTPUT_DIR, f"inpaint_hires_{i+1}.png")
        Image.fromarray(output).save(out_path, quality=95)
        print(f"  [{i+1}] seed={seed} -> {out_path}")

    print("\n[Done]")
    del pipe
    torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
