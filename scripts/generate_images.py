"""
Generate character avatars and scene images using Vertex AI Gemini 3 Pro Image.
Uses the google-genai SDK with service account authentication.
"""
import os
import sys
import time
import base64

# ── Configuration ──
CREDENTIALS_PATH = r"C:\Users\PRO\Desktop\CUDA\credentials\pdfconverter-415414-d9dbb1a4eec6.json"
PROJECT_ID = "pdfconverter-415414"
LOCATION = "global"
MODEL = "gemini-3-pro-image-preview"

AVATAR_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "avatars")
SCENE_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "scenes")

# Set credentials before importing google libs
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_PATH

from google import genai
from google.genai import types


def get_client():
    """Create Vertex AI GenAI client."""
    return genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location=LOCATION,
    )


# ── Character Definitions ──
CHARACTERS = [
    {
        "id": "mika",
        "name": "Mika",
        "avatar_prompt": (
            "Anime-style digital art portrait of a cheerful 19-year-old Japanese girl with "
            "bright pink-highlighted hair in twin tails, large expressive eyes, wearing a cute "
            "hoodie with anime pins. Warm smile, soft studio lighting, colorful background with "
            "subtle anime motifs. Square 1:1 aspect ratio, high quality character portrait."
        ),
        "scene_prompt": (
            "Cozy otaku bedroom interior, walls covered with anime posters and manga shelves, "
            "a desk with drawing tablet and figurines, warm fairy lights, soft pink and purple "
            "ambient lighting, cute plushies on the bed. Wide cinematic 16:9 aspect ratio, "
            "digital art style, detailed and atmospheric."
        ),
    },
    {
        "id": "aria",
        "name": "Aria",
        "avatar_prompt": (
            "Fantasy digital art portrait of a beautiful elven warrior princess with long flowing "
            "silver-white hair, pointed ears, piercing emerald green eyes, wearing ornate silver "
            "armor with nature motifs. Regal and fierce expression, soft magical glow, forest "
            "background. Square 1:1 aspect ratio, high fantasy art style."
        ),
        "scene_prompt": (
            "Enchanted fantasy forest clearing with ancient silver trees, moonlight filtering "
            "through canopy, mystical glowing flowers and fireflies, a stone path leading to "
            "an elven temple in the distance. Wide cinematic 16:9 aspect ratio, high fantasy "
            "digital painting, ethereal and magical atmosphere."
        ),
    },
    {
        "id": "sage",
        "name": "Sage",
        "avatar_prompt": (
            "Warm and calming digital art portrait of a gentle therapist figure with kind brown "
            "eyes, short wavy hair, wearing a soft cream cardigan. Serene and welcoming expression, "
            "soft natural lighting, peaceful neutral background with subtle warm tones. Square 1:1 "
            "aspect ratio, modern digital illustration style."
        ),
        "scene_prompt": (
            "Peaceful zen therapy room with a comfortable armchair by a large window, indoor "
            "plants, a small water fountain, warm sunlight streaming in, neutral earth tones, "
            "minimalist decor with a calming atmosphere. Wide 16:9 aspect ratio, soft digital "
            "painting, serene and inviting."
        ),
    },
    {
        "id": "marcus",
        "name": "Marcus",
        "avatar_prompt": (
            "Dark fantasy digital art portrait of a handsome aristocratic vampire lord in his 30s "
            "with sharp features, pale skin, deep crimson eyes, slicked-back dark hair, wearing "
            "an elegant dark velvet coat with a high collar. Mysterious smirk, dramatic candlelight "
            "lighting, gothic atmosphere. Square 1:1 aspect ratio, dark fantasy art style."
        ),
        "scene_prompt": (
            "Grand gothic castle interior at night, a vast candlelit hall with towering stone "
            "columns, red velvet drapes, ancient oil paintings on the walls, a fireplace with "
            "dancing flames, dark moody atmosphere with warm candle glow. Wide 16:9 aspect ratio, "
            "dark fantasy digital painting, cinematic and atmospheric."
        ),
    },
    {
        "id": "luna",
        "name": "Luna",
        "avatar_prompt": (
            "Ethereal digital art portrait of a mystical moon goddess with flowing luminous "
            "silver-blue hair, pale glowing skin, crescent moon tiara, wearing flowing white "
            "celestial robes with star patterns. Serene otherworldly expression, moonlight aura, "
            "cosmic starfield background. Square 1:1 aspect ratio, celestial fantasy art style."
        ),
        "scene_prompt": (
            "Breathtaking cosmic landscape at night, a vast moonlit crystal lake reflecting stars, "
            "floating luminous orbs, a silver gazebo on the shore, aurora borealis in the sky, "
            "distant nebulae visible. Wide 16:9 aspect ratio, celestial fantasy digital painting, "
            "ethereal and dreamlike atmosphere."
        ),
    },
    {
        "id": "coach_kim",
        "name": "Coach Kim",
        "avatar_prompt": (
            "Dynamic digital art portrait of a confident 30-year-old athletic female personal "
            "trainer with toned physique, short sporty dark hair, bright determined eyes, wearing "
            "a professional fitness tank top. Strong confident smile, gym lighting with warm tones, "
            "motivational energy. Square 1:1 aspect ratio, modern digital illustration."
        ),
        "scene_prompt": (
            "Modern premium gym interior with sleek equipment, large mirrors, motivational quotes "
            "on walls, warm LED lighting, clean design with dark and orange color scheme, weights "
            "and training area visible. Wide 16:9 aspect ratio, modern digital art, energetic "
            "and motivational atmosphere."
        ),
    },
    {
        "id": "jake",
        "name": "Jake",
        "avatar_prompt": (
            "Casual digital art portrait of a friendly 21-year-old college student guy with "
            "messy brown hair, warm hazel eyes, relaxed smile, wearing a comfortable oversized "
            "hoodie. Casual and approachable vibe, warm indoor lighting, simple background. "
            "Square 1:1 aspect ratio, modern digital illustration style."
        ),
        "scene_prompt": (
            "Cozy college dorm room at night, a gaming setup with RGB keyboard and dual monitors "
            "showing a game, messy desk with textbooks and energy drinks, string lights, posters "
            "on walls, warm ambient lighting. Wide 16:9 aspect ratio, modern digital art, chill "
            "and lived-in atmosphere."
        ),
    },
    {
        "id": "elena",
        "name": "Dr. Elena Voss",
        "avatar_prompt": (
            "Sci-fi digital art portrait of an eccentric brilliant female scientist in her 30s "
            "with wild curly auburn hair, safety goggles pushed up on forehead, bright curious "
            "eyes, wearing a lab coat with colorful stains. Excited mischievous expression, "
            "blue-tinted lab lighting, sci-fi equipment in background. Square 1:1 aspect ratio, "
            "sci-fi digital illustration style."
        ),
        "scene_prompt": (
            "Futuristic underground laboratory with holographic displays, bubbling test tubes "
            "and exotic glowing equipment, banks of servers with blue lights, a central workstation "
            "with scattered papers and coffee cups, sci-fi atmosphere with blue and purple lighting. "
            "Wide 16:9 aspect ratio, sci-fi digital painting, mysterious and high-tech."
        ),
    },
]


def generate_image(client, prompt, output_path, aspect="1:1"):
    """Generate a single image using Gemini 3 Pro Image."""
    print(f"  Generating: {os.path.basename(output_path)}...")

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                temperature=1.0,
            ),
        )

        # Extract image from response
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    image_data = part.inline_data.data
                    with open(output_path, "wb") as f:
                        f.write(image_data)
                    size_kb = len(image_data) / 1024
                    print(f"  OK: Saved {output_path} ({size_kb:.0f} KB)")
                    return True

        print(f"  WARN: No image in response for {output_path}")
        # Print text parts if any (useful for debugging)
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.text:
                    print(f"  Text response: {part.text[:200]}")
        return False

    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def main():
    os.makedirs(AVATAR_DIR, exist_ok=True)
    os.makedirs(SCENE_DIR, exist_ok=True)

    print("=" * 60)
    print("SynClub Local - Character Image Generator")
    print(f"Model: {MODEL}")
    print(f"Project: {PROJECT_ID}")
    print("=" * 60)

    client = get_client()

    # Test connection with a simple image generation
    print("\nTesting Vertex AI connection (generating test image)...")
    try:
        test = client.models.generate_content(
            model=MODEL,
            contents="Generate a small red circle on white background.",
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )
        if test.candidates and test.candidates[0].content.parts:
            for part in test.candidates[0].content.parts:
                if part.inline_data is not None:
                    print(f"Connection OK! Test image generated ({len(part.inline_data.data)//1024} KB)")
                    break
            else:
                print("Connection OK but no image in test response, continuing anyway...")
        else:
            print("Connection OK but empty response, continuing anyway...")
    except Exception as e:
        print(f"Connection FAILED: {e}")
        print("\nPlease check:")
        print(f"  1. Credentials file exists: {CREDENTIALS_PATH}")
        print(f"  2. Vertex AI API is enabled for project: {PROJECT_ID}")
        print(f"  3. Service account has Vertex AI User role")
        sys.exit(1)

    total = len(CHARACTERS) * 2  # avatar + scene per character
    done = 0
    failed = 0

    print(f"\nGenerating {total} images for {len(CHARACTERS)} characters...\n")

    for char in CHARACTERS:
        print(f"[{char['name']}]")

        # Generate avatar (1:1)
        avatar_path = os.path.join(AVATAR_DIR, f"{char['id']}.png")
        if os.path.exists(avatar_path):
            print(f"  SKIP: Avatar already exists: {avatar_path}")
            done += 1
        else:
            ok = generate_image(client, char["avatar_prompt"], avatar_path)
            if ok:
                done += 1
            else:
                failed += 1
            time.sleep(2)  # Rate limit protection

        # Generate scene (16:9)
        scene_path = os.path.join(SCENE_DIR, f"{char['id']}.png")
        if os.path.exists(scene_path):
            print(f"  SKIP: Scene already exists: {scene_path}")
            done += 1
        else:
            ok = generate_image(client, char["scene_prompt"], scene_path)
            if ok:
                done += 1
            else:
                failed += 1
            time.sleep(2)  # Rate limit protection

        print()

    print("=" * 60)
    print(f"Done! {done}/{total} images generated, {failed} failed.")
    print(f"Avatars: {AVATAR_DIR}")
    print(f"Scenes:  {SCENE_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()

