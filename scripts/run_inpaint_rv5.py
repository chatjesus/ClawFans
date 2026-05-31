"""
Realistic Vision V5.1 Inpainting with proper weight conversion.
Uses convert_ldm_unet_checkpoint from diffusers for correct key mapping.
"""
import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import torch
import numpy as np
from PIL import Image, ImageFilter
from safetensors.torch import load_file

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
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    clothing = np.zeros_like(seg, dtype=np.uint8)
    for cls in [3, 4, 5, 6]:
        clothing[seg == cls] = 255
    return clothing, seg


def load_pipeline():
    from diffusers import StableDiffusionInpaintPipeline, DDIMScheduler, AutoencoderKL, UNet2DConditionModel
    from transformers import CLIPTextModel, CLIPTokenizer
    from diffusers.pipelines.stable_diffusion.convert_from_ckpt import (
        convert_ldm_unet_checkpoint,
        convert_ldm_vae_checkpoint,
        convert_ldm_clip_checkpoint,
    )
    import json

    print("[Load] Checkpoint...")
    state_dict = load_file(MODEL_PATH)
    print(f"  Total keys: {len(state_dict)}")

    print("[Load] Converting UNet...")
    with open(os.path.join(SD_INP_DIR, "unet", "config.json"), "r") as f:
        unet_config = json.load(f)
    unet_config.setdefault("class_embed_type", None)
    unet_config.setdefault("addition_embed_type", None)
    unet_config.setdefault("addition_time_embed_dim", None)
    unet_config.setdefault("transformer_layers_per_block", 1)
    unet_config.setdefault("projection_class_embeddings_input_dim", None)
    converted_unet = convert_ldm_unet_checkpoint(state_dict, unet_config)
    unet = UNet2DConditionModel(**unet_config)
    m, u = unet.load_state_dict(converted_unet, strict=False)
    print(f"  UNet: missing={len(m)}, unexpected={len(u)}")
    unet = unet.half().cuda()

    print("[Load] Converting VAE...")
    with open(os.path.join(VAE_DIR, "config.json"), "r") as f:
        vae_config = json.load(f)
    converted_vae = convert_ldm_vae_checkpoint(state_dict, vae_config)
    vae = AutoencoderKL(**vae_config)
    m, u = vae.load_state_dict(converted_vae, strict=False)
    print(f"  VAE: missing={len(m)}, unexpected={len(u)}")
    vae = vae.half().cuda()

    print("[Load] Text encoder + tokenizer from local dir...")
    os.environ.pop("TRANSFORMERS_OFFLINE", None)
    text_encoder = CLIPTextModel.from_pretrained(
        os.path.join(SD_INP_DIR, "text_encoder"), torch_dtype=torch.float16)

    te_keys = {k: v for k, v in state_dict.items() if k.startswith("cond_stage_model.")}
    if te_keys:
        from diffusers.pipelines.stable_diffusion.convert_from_ckpt import convert_open_clip_checkpoint
        try:
            converted_te = convert_ldm_clip_checkpoint(state_dict)
            m, u = text_encoder.load_state_dict(converted_te, strict=False)
            print(f"  TE: missing={len(m)}, unexpected={len(u)}")
        except Exception as e:
            print(f"  TE conversion failed ({e}), using base weights")

    text_encoder = text_encoder.half().cuda()
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
    print("[Load] Done!")
    return pipe


def main():
    print("=== Realistic Vision V5.1 Inpainting ===\n")

    image = Image.open(HIRES_PATH).convert("RGB")
    w, h = image.size
    print(f"Input: {w}x{h}")

    print("[1] Parsing...")
    clothing, seg = generate_masks(image)
    dilated = np.array(Image.fromarray(clothing).filter(ImageFilter.MaxFilter(25)))
    ys, xs = np.where(dilated > 0)
    pad = 100
    y1, y2 = max(0, ys.min() - pad), min(h, ys.max() + pad)
    x1, x2 = max(0, xs.min() - pad), min(w, xs.max() + pad)

    crop = image.crop((x1, y1, x2, y2))
    crop_mask = Image.fromarray(dilated[y1:y2, x1:x2])
    cw, ch = crop.size

    scale = min(512 / cw, 768 / ch)
    nw = int(cw * scale) // 8 * 8
    nh = int(ch * scale) // 8 * 8
    nw, nh = max(nw, 256), max(nh, 256)
    crop_r = crop.resize((nw, nh), Image.LANCZOS)
    mask_r = crop_mask.resize((nw, nh), Image.NEAREST)
    print(f"  Inpaint: {nw}x{nh}")

    print("\n[2] Loading model...")
    pipe = load_pipeline()

    configs = [
        ("photorealistic nude female body, natural bare skin, realistic skin texture with pores, soft natural lighting, professional photography, 8k uhd", 42),
        ("realistic bare female torso and body, smooth natural skin, warm skin tones, photographic quality, studio photo", 888),
        ("beautiful nude female body, photorealistic bare skin, natural complexion, professional photography, high resolution", 2024),
    ]
    neg = "clothes, fabric, garment, dress, shirt, bikini, text, watermark, ugly, deformed, blurry, anime, cartoon, illustration, 3d, cgi, low quality"

    print(f"\n[3] Generating {len(configs)} variants...")
    for i, (prompt, seed) in enumerate(configs):
        with torch.inference_mode():
            result = pipe(
                prompt=prompt, negative_prompt=neg,
                image=crop_r, mask_image=mask_r,
                num_inference_steps=50, guidance_scale=7.5, strength=0.99,
                generator=torch.Generator("cuda").manual_seed(seed),
            ).images[0]

        result_full = result.resize((cw, ch), Image.LANCZOS)
        output = np.array(image).copy()
        result_np = np.array(result_full)
        local_mask = dilated[y1:y2, x1:x2]
        blend = np.array(Image.fromarray(local_mask).filter(ImageFilter.GaussianBlur(12)))
        alpha = blend.astype(float) / 255.0

        for c in range(3):
            orig = output[y1:y2, x1:x2, c].astype(float)
            inp = result_np[:, :, c].astype(float)
            output[y1:y2, x1:x2, c] = (orig * (1 - alpha) + inp * alpha).astype(np.uint8)

        path = os.path.join(OUTPUT_DIR, f"inpaint_rv5_{i+1}.png")
        Image.fromarray(output).save(path, quality=95)
        print(f"  [{i+1}] seed={seed} -> {path}")

    print("\n[Done]")
    del pipe
    torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
