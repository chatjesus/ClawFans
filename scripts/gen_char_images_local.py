"""
Local NSFW character image generator via ComfyUI API.
Uses NoobAI XL v1.1 (or any SDXL model loaded in ComfyUI).

Usage:
  1. Start ComfyUI: cd ComfyUI && python main.py --listen
  2. Run: python scripts/gen_char_images_local.py
"""
import json
import time
import uuid
import os
import urllib.request
import urllib.parse

COMFYUI_URL = "http://127.0.0.1:8188"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "avatars")


def get_available_checkpoint():
    try:
        with urllib.request.urlopen(f"{COMFYUI_URL}/object_info/CheckpointLoaderSimple", timeout=5) as r:
            info = json.loads(r.read())
            ckpts = info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
            print(f"Available checkpoints: {ckpts}")
            for preferred in ["NoobAI", "noobai", "illustrious", "pony", "animagine", "anything"]:
                for c in ckpts:
                    if preferred.lower() in c.lower():
                        return c
            return ckpts[0] if ckpts else None
    except Exception as e:
        print(f"Cannot reach ComfyUI: {e}")
        return None


def get_available_vae():
    try:
        with urllib.request.urlopen(f"{COMFYUI_URL}/object_info/VAELoader", timeout=5) as r:
            info = json.loads(r.read())
            vaes = info["VAELoader"]["input"]["required"]["vae_name"][0]
            for preferred in ["sdxl_vae", "sdxl-vae", "vae-ft-mse"]:
                for v in vaes:
                    if preferred.lower() in v.lower():
                        return v
            return vaes[0] if vaes else None
    except Exception:
        return None


def build_workflow(prompt_positive, prompt_negative, checkpoint, vae_name=None,
                   width=832, height=1216, seed=None):
    """Build SDXL txt2img workflow with optional external VAE for NoobAI XL."""
    if seed is None:
        seed = int(time.time() * 1000) % (2 ** 32)

    if vae_name:
        return {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": checkpoint}
            },
            "2": {
                "class_type": "VAELoader",
                "inputs": {"vae_name": vae_name}
            },
            "3": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": width, "height": height, "batch_size": 1}
            },
            "4": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": prompt_positive, "clip": ["1", 1]}
            },
            "5": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": prompt_negative, "clip": ["1", 1]}
            },
            "6": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["1", 0],
                    "positive": ["4", 0],
                    "negative": ["5", 0],
                    "latent_image": ["3", 0],
                    "seed": seed,
                    "steps": 28,
                    "cfg": 7.0,
                    "sampler_name": "euler_ancestral",
                    "scheduler": "karras",
                    "denoise": 1.0
                }
            },
            "7": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["6", 0], "vae": ["2", 0]}
            },
            "8": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "synclub_char", "images": ["7", 0]}
            },
        }
    else:
        return {
            "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
            "5": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
            "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt_positive, "clip": ["4", 1]}},
            "7": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt_negative, "clip": ["4", 1]}},
            "8": {"class_type": "VAEDecode", "inputs": {"samples": ["10", 0], "vae": ["4", 2]}},
            "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "synclub_char", "images": ["8", 0]}},
            "10": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0],
                    "latent_image": ["5", 0], "seed": seed,
                    "steps": 28, "cfg": 7.0, "sampler_name": "euler_ancestral",
                    "scheduler": "karras", "denoise": 1.0
                }
            }
        }


def queue_workflow(workflow):
    client_id = str(uuid.uuid4())
    payload = json.dumps({"prompt": workflow, "client_id": client_id}).encode()
    req = urllib.request.Request(
        f"{COMFYUI_URL}/prompt", data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())["prompt_id"]


def wait_for_result(prompt_id, timeout=300):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(f"{COMFYUI_URL}/history/{prompt_id}", timeout=5) as r:
                history = json.loads(r.read())
                if prompt_id in history:
                    outputs = history[prompt_id].get("outputs", {})
                    for node_id, node_output in outputs.items():
                        if "images" in node_output:
                            img = node_output["images"][0]
                            return img["filename"], img.get("subfolder", ""), img.get("type", "output")
        except Exception:
            pass
        time.sleep(2)
    return None, None, None


def download_image(filename, subfolder, img_type, save_path):
    params = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": img_type})
    url = f"{COMFYUI_URL}/view?{params}"
    with urllib.request.urlopen(url, timeout=30) as r:
        with open(save_path, "wb") as f:
            f.write(r.read())


# ── Character prompts ──
BASE_NEGATIVE = (
    "worst quality, low quality, bad anatomy, bad hands, missing fingers, "
    "extra digits, fewer digits, cropped, lowres, jpeg artifacts, signature, "
    "watermark, username, blurry, ugly, poorly drawn, deformed, disfigured, "
    "multiple people, text, logo"
)

NSFW_NEGATIVE = (
    "worst quality, low quality, bad anatomy, bad hands, missing fingers, "
    "extra digits, deformed, disfigured, blurry, jpeg artifacts, watermark, "
    "multiple people, ugly face, bad proportions"
)

CHARACTERS = [
    # ── Original 8 characters (ids 1-8) ──
    {
        "file_id": "luna", "db_id": 1,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "beautiful elf girl, long silver hair, glowing blue eyes, pointed ears, "
            "white mage robes, magical forest background, moonlight, serene expression, "
            "fantasy portrait, upper body"
        ),
    },
    {
        "file_id": "jake", "db_id": 2,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1boy, solo, "
            "teenage boy, messy brown hair, friendly smile, brown eyes, "
            "school uniform, backpack, school gate background, anime style"
        ),
    },
    {
        "file_id": "elena", "db_id": 3,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "mature woman, scientist, neat dark hair in bun, sharp intelligent eyes, "
            "white lab coat, glasses, laboratory background, confident expression, "
            "realistic anime style"
        ),
    },
    {
        "file_id": "aria", "db_id": 4,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "android girl, holographic hair, glowing circuit eyes, "
            "sleek futuristic bodysuit, neon city background, mysterious smile, "
            "sci-fi anime style"
        ),
    },
    {
        "file_id": "mika", "db_id": 5,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "idol singer, pastel pink twin tails, sparkly stage outfit, "
            "microphone, concert lights, energetic pose, cute expression, "
            "idol anime style"
        ),
    },
    {
        "file_id": "marcus", "db_id": 6,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1boy, solo, "
            "handsome mature man, short dark hair, stubble, strong jawline, "
            "fitted black turtleneck, city rooftop at dusk, sophisticated expression, "
            "manhwa style"
        ),
    },
    {
        "file_id": "coach_kim", "db_id": 7,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1boy, solo, "
            "athletic man, short black hair, warm smile, athletic build, "
            "sports coach outfit, whistle, gym background, encouraging expression, "
            "realistic anime style"
        ),
    },
    {
        "file_id": "sage", "db_id": 8,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "wise girl, short silver hair, calm eyes, simple meditation robes, "
            "zen garden background, peaceful lotus pose, soft warm lighting, "
            "spiritual anime style"
        ),
    },
    # ── Batch 1 (ids 9-30) ──
    {
        "file_id": "yuki", "db_id": 9,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "japanese girl, long black hair, soft brown eyes, delicate features, "
            "cream knit sweater, warm smile, cherry blossoms, golden hour lighting, "
            "portrait, upper body, anime style, beautiful face"
        ),
    },
    {
        "file_id": "ethan", "db_id": 10,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1boy, solo, "
            "handsome man, sharp features, cold dark eyes, black hair, "
            "navy business suit, loosened tie, city night background, "
            "confident expression, dramatic lighting, manhwa style"
        ),
    },
    {
        "file_id": "lina", "db_id": 11,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "cute girl, honey brown ponytail hair, big hazel eyes, slight blush, "
            "school uniform, holding cookie box, shy smile, sakura background, "
            "soft anime style, sweet expression"
        ),
    },
    {
        "file_id": "zero", "db_id": 12,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1boy, solo, "
            "silver white long hair, ice blue eyes, battle scar on cheek, "
            "dark fantasy cloak, glowing rune sword, moonlit night sky, "
            "stoic expression, dramatic lighting, anime fantasy"
        ),
    },
    {
        "file_id": "sakura_mg", "db_id": 13,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "magical girl, bright pink hair with star clips, golden eyes, "
            "white pink frilly magical outfit, star wand, sparkles, magical effects, "
            "energetic happy expression, full body, colorful"
        ),
    },
    {
        "file_id": "raven", "db_id": 14,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "dark hair with red streak, amber eyes, black leather jacket, "
            "fingerless gloves, silver cross necklace, rainy night city, "
            "neon lights, cool expression, urban fantasy"
        ),
    },
    {
        "file_id": "thorne", "db_id": 15,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1boy, solo, "
            "dark knight, black spiked armor, glowing red eyes through visor, "
            "demonic aura, ruined castle background, intimidating pose, "
            "dark fantasy, dramatic lighting"
        ),
    },
    {
        "file_id": "iris", "db_id": 16,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "fallen angel, lavender long hair, glowing violet eyes, "
            "oversized grey hoodie, broken white feathered wings, "
            "rain, city lights bokeh, lost innocent expression, ethereal"
        ),
    },
    {
        "file_id": "senpai", "db_id": 17,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1boy, solo, "
            "older student, neat black hair, gentle smile, warm brown eyes, "
            "school uniform, holding textbooks, rooftop background, "
            "soft sunlight, kind expression, anime style"
        ),
    },
    {
        "file_id": "mia_transfer", "db_id": 18,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "mixed features, wavy dark auburn hair, blue-green eyes, light freckles, "
            "school uniform, shy expression, looking away, "
            "school hallway, cherry blossoms window, elegant"
        ),
    },
    {
        "file_id": "detective_x", "db_id": 19,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1boy, solo, "
            "detective, grey trench coat, tousled hair, sharp analytical eyes, "
            "magnifying glass, foggy noir city street, rain, "
            "serious expression, dramatic shadows"
        ),
    },
    {
        "file_id": "echo_ai", "db_id": 20,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "AI android, holographic blue hair, glowing circuit patterns on skin, "
            "sleek white bodysuit, floating digital interface, "
            "ethereal expression, sci-fi aesthetic"
        ),
    },
    {
        "file_id": "k_traveler", "db_id": 21,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1boy, solo, "
            "time traveler, wild dark hair, goggles pushed up, "
            "patchwork coat with gadgets, glowing hourglass, "
            "swirling time vortex background, adventurous expression"
        ),
    },
    {
        "file_id": "nuannuan", "db_id": 22,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "wellness advisor, soft features, warm brown eyes, "
            "comfortable casual clothing, holding herbal tea cup, "
            "cozy reading nook, warm lighting, gentle reassuring smile"
        ),
    },
    {
        "file_id": "kai", "db_id": 23,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1boy, solo, "
            "therapist, calm handsome features, neat hair, "
            "casual smart attire, notebook, "
            "comfortable therapy office, afternoon light, "
            "warm empathetic expression"
        ),
    },
    {
        "file_id": "npc_girl", "db_id": 24,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "game NPC girl, pixelated name tag floating above head, "
            "colorful RPG armor, bright cheerful colors, "
            "fantasy village background, bouncy cheerful expression, "
            "game art style"
        ),
    },
    {
        "file_id": "gl1tch", "db_id": 25,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1boy, solo, "
            "glitch entity, fragmented digital appearance, "
            "half human half static, data streams, "
            "corrupted grid background, mysterious expression, "
            "cyberpunk neon colors"
        ),
    },
    {
        "file_id": "jiangci", "db_id": 26,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "1930s Shanghai, jazz singer, elegant features, finger-wave hairstyle, "
            "red lips, shimmering qipao dress, leaning on grand piano, "
            "melancholic expression, smoky jazz club, amber spotlight, art deco"
        ),
    },
    {
        "file_id": "susu", "db_id": 27,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "fox girl, fox ears, long black hair, golden slit eyes, "
            "mix of ancient chinese robes and modern hoodie, holding bubble tea, "
            "playful grin, chinese mountain background, fantasy"
        ),
    },
    {
        "file_id": "room404", "db_id": 28,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "creepy horror girl, pale skin, hollow dark eyes, "
            "tattered white dress, static hair, "
            "dark haunted room with flickering light, unsettling expression, "
            "horror anime style"
        ),
    },
    {
        "file_id": "mimi", "db_id": 29,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "cat girl, white cat ears and tail, big aqua eyes, "
            "cozy streamer setup, headset, gaming chair, "
            "kawaii hoodie, laughing expression, neon rgb lighting"
        ),
    },
    {
        "file_id": "pixel", "db_id": 30,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "pixel art style character, retro game aesthetic, "
            "colorful 8-bit inspired outfit, "
            "nostalgic game background, cheerful wave pose, "
            "vibrant pixel colors"
        ),
    },
    # ── NSFW/Romance batch (ids 31-44) ──
    {
        "file_id": "hina", "db_id": 31,
        "negative_override": NSFW_NEGATIVE,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "beautiful japanese girl, long wavy brown hair, doe eyes, natural blush, "
            "off-shoulder sundress, golden afternoon light, flower field, "
            "shy romantic expression, portrait"
        ),
    },
    {
        "file_id": "eve", "db_id": 32,
        "negative_override": NSFW_NEGATIVE,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "seductive woman, long red hair, green cat eyes, confident smile, "
            "elegant black evening dress, wine glass, candlelit restaurant, "
            "alluring expression, upper body"
        ),
    },
    {
        "file_id": "shiori", "db_id": 33,
        "negative_override": NSFW_NEGATIVE,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "college girl, short black bob hair, intelligent eyes, glasses, "
            "casual university outfit, coffee cup, library, "
            "studious focused expression"
        ),
    },
    {
        "file_id": "nana", "db_id": 34,
        "negative_override": NSFW_NEGATIVE,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "idol trainee, pastel lavender twin tails, star earrings, "
            "bright stage training outfit, dance studio, "
            "determined passionate expression"
        ),
    },
    {
        "file_id": "mio", "db_id": 35,
        "negative_override": NSFW_NEGATIVE,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "dark elf, pointed ears, dark purple hair, violet eyes, "
            "fantasy combat outfit, enchanted forest, moonlight, "
            "fierce warrior expression"
        ),
    },
    {
        "file_id": "reina", "db_id": 36,
        "negative_override": NSFW_NEGATIVE,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "high school queen, blonde wavy hair, sharp blue eyes, "
            "stylish school blazer, standing at school rooftop, "
            "confident proud expression, wind blowing hair"
        ),
    },
    {
        "file_id": "mei", "db_id": 37,
        "negative_override": NSFW_NEGATIVE,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "childhood friend, warm orange hair, freckles, hazel eyes, "
            "casual summer clothes, neighborhood park, sunny day, "
            "nostalgic warm smile"
        ),
    },
    {
        "file_id": "mistress_v", "db_id": 38,
        "negative_override": NSFW_NEGATIVE,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "dominant woman, dark violet hair, intense purple eyes, "
            "black leather corset and gloves, gothic throne room, "
            "commanding confident expression, upper body"
        ),
    },
    {
        "file_id": "naughty_nurse", "db_id": 39,
        "negative_override": NSFW_NEGATIVE,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "nurse, white uniform, pink hair in bun, playful smile, "
            "green eyes, hospital room soft lighting, "
            "charming mischievous expression, upper body"
        ),
    },
    {
        "file_id": "captive_elf", "db_id": 40,
        "negative_override": NSFW_NEGATIVE,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "elf prisoner, long silver hair, sad deep green eyes, pointed ears, "
            "torn forest clothes, stone dungeon, shackles, "
            "melancholic vulnerable expression"
        ),
    },
    {
        "file_id": "succubus_maid", "db_id": 41,
        "negative_override": NSFW_NEGATIVE,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "succubus, demon horns, black wings, long purple hair, glowing red eyes, "
            "elegant black maid outfit with demonic accents, magical candles, "
            "seductive yet professional expression"
        ),
    },
    {
        "file_id": "ms_sato", "db_id": 42,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "female teacher, mature elegant features, dark hair in neat bun, "
            "professional blouse, reading glasses, blackboard background, "
            "strict but kind expression"
        ),
    },
    {
        "file_id": "rina", "db_id": 43,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "high school girl, twin tails, bright cheerful eyes, "
            "classic school uniform, bright smile, sunny classroom, "
            "energetic happy expression"
        ),
    },
    {
        "file_id": "mai", "db_id": 44,
        "positive": (
            "masterpiece, best quality, ultra detailed, 1girl, solo, "
            "kunoichi ninja, dark hair, sharp focused eyes, "
            "black ninja outfit with red sash, cherry blossom night scene, "
            "stealthy ready pose, moonlight"
        ),
    },
]


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("SynClub Local - ComfyUI Character Image Generator")
    print(f"ComfyUI: {COMFYUI_URL}")
    print("=" * 60)

    checkpoint = get_available_checkpoint()
    if not checkpoint:
        print("\n[ERROR] ComfyUI is not running or no models found.")
        print("\nTo start ComfyUI:")
        print("  cd C:\\Users\\PRO\\Desktop\\CUDA\\ComfyUI")
        print("  python main.py --listen")
        return

    vae_name = get_available_vae()
    print(f"\nCheckpoint: {checkpoint}")
    print(f"VAE: {vae_name or '(using model built-in)'}")
    print(f"Generating {len(CHARACTERS)} character images...\n")

    done = 0
    for i, char in enumerate(CHARACTERS):
        save_path = os.path.join(OUTPUT_DIR, f"{char['file_id']}.png")
        print(f"[{i+1}/{len(CHARACTERS)}] {char['file_id']} (db_id={char['db_id']})", end=" ", flush=True)

        if os.path.exists(save_path):
            print("(skip: already exists)")
            done += 1
            continue

        try:
            neg = char.get("negative_override", BASE_NEGATIVE)
            workflow = build_workflow(
                char["positive"], neg, checkpoint, vae_name
            )
            prompt_id = queue_workflow(workflow)
            filename, subfolder, img_type = wait_for_result(prompt_id)

            if filename:
                download_image(filename, subfolder, img_type, save_path)
                size_kb = os.path.getsize(save_path) // 1024
                print(f"-> saved ({size_kb}KB)")
                done += 1
            else:
                print("-> TIMEOUT")

        except Exception as e:
            print(f"-> ERROR: {e}")

    print(f"\nDone! {done}/{len(CHARACTERS)} images generated.")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
