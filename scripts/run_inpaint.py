"""Run SD 1.5 inpainting on a person image to remove clothing (academic research demo)."""
import os, sys, torch
import numpy as np
from PIL import Image, ImageFilter

MODEL_DIR = r"D:\ComfyUI_Models\CatVTON\stable-diffusion-inpainting"
VAE_DIR = r"D:\ComfyUI_Models\CatVTON\sd-vae-ft-mse"
IMAGE_PATH = r"C:\Users\PRO\Desktop\CUDA\synclub-local\backend\uploads\manga\53\thumb_a163_5s.png"
OUTPUT_PATH = r"C:\Users\PRO\Desktop\CUDA\synclub-local\backend\uploads\manga\53\inpaint_sd15.png"

def generate_clothing_mask(image_path):
    from transformers import AutoModelForSemanticSegmentation, AutoImageProcessor
    processor = AutoImageProcessor.from_pretrained("fashn-ai/fashn-human-parser", use_fast=False)
    model = AutoModelForSemanticSegmentation.from_pretrained("fashn-ai/fashn-human-parser").cuda().eval()
    image = Image.open(image_path).convert("RGB")
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.cuda() for k, v in inputs.items()}
    with torch.inference_mode():
        logits = model(**inputs).logits
        logits = torch.nn.functional.interpolate(logits, size=image.size[::-1], mode="bilinear", align_corners=False)
        seg = logits.argmax(dim=1)[0].cpu().numpy()
    del model
    torch.cuda.empty_cache()
    mask = np.zeros_like(seg, dtype=np.uint8)
    for cls in [3, 4, 5]:  # top, dress, skirt
        mask[seg == cls] = 255
    mask_img = Image.fromarray(mask)
    mask_img = mask_img.filter(ImageFilter.MaxFilter(11))
    return mask_img


def load_pipeline():
    from diffusers import StableDiffusionInpaintPipeline, DDIMScheduler, AutoencoderKL
    from transformers import CLIPTextModel, CLIPTokenizer

    print("[Load] Scheduler...")
    scheduler = DDIMScheduler.from_pretrained(os.path.join(MODEL_DIR, "scheduler"))

    print("[Load] Tokenizer...")
    tokenizer = CLIPTokenizer.from_pretrained(os.path.join(MODEL_DIR, "tokenizer"))

    print("[Load] Text encoder...")
    text_encoder = CLIPTextModel.from_pretrained(
        os.path.join(MODEL_DIR, "text_encoder"),
        torch_dtype=torch.float16,
    )

    print("[Load] UNet...")
    from diffusers import UNet2DConditionModel
    unet = UNet2DConditionModel.from_pretrained(
        os.path.join(MODEL_DIR, "unet"),
        torch_dtype=torch.float16,
    )

    print("[Load] VAE...")
    vae = AutoencoderKL.from_pretrained(VAE_DIR, torch_dtype=torch.float16)

    pipe = StableDiffusionInpaintPipeline(
        vae=vae,
        text_encoder=text_encoder,
        tokenizer=tokenizer,
        unet=unet,
        scheduler=scheduler,
        safety_checker=None,
        feature_extractor=None,
        requires_safety_checker=False,
    )
    pipe = pipe.to("cuda")
    pipe.enable_attention_slicing()
    return pipe


def main():
    print("=== SD 1.5 Inpainting (Realistic) ===")

    print("\n[Step 1] Generating clothing mask...")
    mask = generate_clothing_mask(IMAGE_PATH)
    coverage = np.sum(np.array(mask) > 0) / np.array(mask).size * 100
    print(f"  Mask coverage: {coverage:.1f}%")

    print("\n[Step 2] Loading SD 1.5 inpainting pipeline...")
    pipe = load_pipeline()

    print("\n[Step 3] Running inpainting...")
    image = Image.open(IMAGE_PATH).convert("RGB")
    w, h = image.size
    new_w = (w // 8) * 8
    new_h = (h // 8) * 8
    image_resized = image.resize((new_w, new_h), Image.LANCZOS)
    mask_resized = mask.resize((new_w, new_h), Image.NEAREST)

    with torch.inference_mode():
        result = pipe(
            prompt="realistic bare skin, natural human body, smooth skin texture, photorealistic, high quality photograph, natural lighting",
            negative_prompt="clothes, fabric, garment, text, watermark, ugly, deformed, blurry, anime, cartoon, drawing, illustration",
            image=image_resized,
            mask_image=mask_resized,
            num_inference_steps=40,
            guidance_scale=7.5,
            strength=0.99,
            generator=torch.Generator("cuda").manual_seed(42),
        ).images[0]

    result = result.resize((w, h), Image.LANCZOS)
    result.save(OUTPUT_PATH)
    print(f"\n[Done] Saved to: {OUTPUT_PATH}")

    del pipe
    torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
