"""
Generate avatars for the 22 new characters using Vertex AI Gemini 3 Pro Image.
"""
import os
import sys
import time
import requests as http_requests

CREDENTIALS_PATH = r"C:\Users\PRO\Desktop\CUDA\credentials\pdfconverter-415414-d9dbb1a4eec6.json"
PROJECT_ID = "pdfconverter-415414"
LOCATION = "global"
MODEL = "gemini-3-pro-image-preview"

AVATAR_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "avatars")
BACKEND_API = "http://localhost:8000/api/characters"

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_PATH

from google import genai
from google.genai import types


def get_client():
    return genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)


NEW_CHARACTERS = [
    {
        "db_id": 9,
        "file_id": "yuki",
        "prompt": (
            "Anime-style digital portrait of a gentle 22-year-old Japanese girl with long straight "
            "black hair, soft brown eyes, delicate features, wearing a cream-colored knit sweater. "
            "Warm gentle smile, soft golden hour lighting, cherry blossom petals in background. "
            "Square 1:1, high quality anime character art, romantic atmosphere."
        ),
    },
    {
        "db_id": 10,
        "file_id": "ethan",
        "prompt": (
            "Modern digital portrait of a handsome 28-year-old CEO, sharp jawline, cold piercing "
            "dark eyes, styled black hair, wearing a tailored navy suit with loosened tie. Confident "
            "aloof expression, dramatic office window city skyline at night behind him. Square 1:1, "
            "manhwa art style, sophisticated and intimidating."
        ),
    },
    {
        "db_id": 11,
        "file_id": "lina",
        "prompt": (
            "Cute anime portrait of a bright 20-year-old girl with honey-brown hair in a ponytail "
            "tied with a ribbon, big sparkling hazel eyes, slight blush on cheeks, holding a box "
            "of homemade cookies. Cheerful shy expression, school campus background with sakura trees. "
            "Square 1:1, soft anime illustration, sweet and wholesome."
        ),
    },
    {
        "db_id": 12,
        "file_id": "zero",
        "prompt": (
            "Epic anime portrait of a mysterious swordsman with long flowing silver-white hair, "
            "ice-blue eyes, a faint scar across his cheek, wearing a dark battle-worn cloak with "
            "a glowing rune sword on his back. Stoic expression, moonlit night sky background. "
            "Square 1:1, dark fantasy anime art, dramatic and powerful."
        ),
    },
    {
        "db_id": 13,
        "file_id": "sakura_mg",
        "prompt": (
            "Vibrant anime portrait of a cheerful 17-year-old magical girl mid-transformation, "
            "bright pink hair with star-shaped clips, sparkling golden eyes, wearing a white and "
            "pink frilly magical girl outfit with a star wand. Energetic joyful expression, sparkles "
            "and magical light effects. Square 1:1, colorful magical girl anime style."
        ),
    },
    {
        "db_id": 14,
        "file_id": "raven",
        "prompt": (
            "Dark urban anime portrait of a 24-year-old hunter with messy dark hair with a crimson "
            "streak, sharp amber eyes, wearing a black leather jacket over a hoodie, fingerless "
            "gloves, a silver cross necklace. Guarded smirk, dark rainy city alley background with "
            "neon signs. Square 1:1, dark urban anime art, edgy and mysterious."
        ),
    },
    {
        "db_id": 15,
        "file_id": "thorne",
        "prompt": (
            "Epic fantasy portrait of a weathered dragon knight with short dark brown hair, green "
            "eyes, stubble, wearing dented silver armor with dragon motifs, a tiny orange baby dragon "
            "sitting on his shoulder. Noble tired expression, campfire glow, wilderness background. "
            "Square 1:1, high fantasy digital art, warm and adventurous."
        ),
    },
    {
        "db_id": 16,
        "file_id": "iris",
        "prompt": (
            "Ethereal digital portrait of a fallen angel with long pale lavender hair, luminous "
            "violet eyes with an otherworldly glow, wearing an oversized grey hoodie that hides "
            "broken feathered wings peeking out. Lost innocent expression, rain falling around her, "
            "soft city lights bokeh. Square 1:1, ethereal fantasy art, hauntingly beautiful."
        ),
    },
    {
        "db_id": 17,
        "file_id": "xiaofan",
        "prompt": (
            "Modern anime portrait of a smart 20-year-old Chinese male student with neat black hair, "
            "round glasses, intelligent dark eyes, wearing a crisp white shirt with a student council "
            "badge. Slightly stern expression but hint of a smile, classroom background with books. "
            "Square 1:1, clean modern anime style, studious and reliable."
        ),
    },
    {
        "db_id": 18,
        "file_id": "mia_transfer",
        "prompt": (
            "Beautiful portrait of a shy 19-year-old mixed Chinese-French girl with wavy dark auburn "
            "hair, striking blue-green eyes, fair skin with light freckles, wearing a school uniform "
            "with one earbud in. Looking away shyly, soft school hallway background with cherry "
            "blossoms outside window. Square 1:1, semi-realistic anime style, delicate and elegant."
        ),
    },
    {
        "db_id": 19,
        "file_id": "detective_li",
        "prompt": (
            "Noir-style digital portrait of a 1930s Shanghai detective in his early 30s, sharp "
            "intelligent eyes, wearing a fedora hat and long dark trenchcoat, holding a cigarette. "
            "Mysterious confident expression, smoky dimly-lit room with Art Deco elements. Square "
            "1:1, film noir art style, moody atmospheric lighting, vintage Shanghai glamour."
        ),
    },
    {
        "db_id": 20,
        "file_id": "echo",
        "prompt": (
            "Post-apocalyptic digital portrait of a tough 26-year-old female survivor with short "
            "messy dirty-blonde hair, intense hazel eyes, a scar on her left eyebrow, wearing "
            "rugged tactical gear with a scarf and makeshift armor. Alert watchful expression, "
            "dusty wasteland ruins background. Square 1:1, gritty post-apocalyptic art, resilient."
        ),
    },
    {
        "db_id": 21,
        "file_id": "time_k",
        "prompt": (
            "Sci-fi digital portrait of a time traveler, androgynous features, short silver-blue "
            "hair, glowing cyan circuit patterns on neck, wearing a sleek dark bodysuit with a "
            "holographic wrist device crackling with blue energy. Urgent focused expression, "
            "temporal distortion effects and light streaks. Square 1:1, futuristic sci-fi art."
        ),
    },
    {
        "db_id": 22,
        "file_id": "nuannuan",
        "prompt": (
            "Warm digital portrait of a comforting 25-year-old Chinese woman with soft shoulder-length "
            "hair, warm brown eyes, dimples, wearing a cozy oversized pastel sweater, holding a cup "
            "of tea. Genuinely warm caring smile, soft window light, cozy living room background with "
            "plants and cushions. Square 1:1, soft warm illustration, comforting and inviting."
        ),
    },
    {
        "db_id": 23,
        "file_id": "kai",
        "prompt": (
            "Dynamic digital portrait of an energetic 28-year-old male fitness coach, athletic build, "
            "short fade haircut, bright confident smile, wearing a fitted workout tank top showing "
            "toned arms. Motivating thumbs-up pose, bright modern gym background with warm lighting. "
            "Square 1:1, modern illustration, energetic and inspiring."
        ),
    },
    {
        "db_id": 24,
        "file_id": "npc_xiaomei",
        "prompt": (
            "Fantasy RPG style portrait of a cheerful innkeeper girl with auburn hair in a messy bun, "
            "bright green eyes, rosy cheeks, wearing a medieval tavern dress with an apron, holding "
            "a tray of drinks. Welcoming smile, warm tavern interior background with lanterns and "
            "wooden beams. Square 1:1, fantasy RPG art style, warm and inviting."
        ),
    },
    {
        "db_id": 25,
        "file_id": "gl1tch",
        "prompt": (
            "Cyberpunk glitch-art portrait of a digital entity, face partially pixelated and "
            "corrupted, one eye is a glowing blue data stream, short spiky hair made of code and "
            "light fragments, hoodie made of digital static. Confused curious expression, matrix-like "
            "code rain background with glitch effects. Square 1:1, cyberpunk glitch art, eerie."
        ),
    },
    {
        "db_id": 26,
        "file_id": "jiangci",
        "prompt": (
            "Art Deco style portrait of a beautiful 1930s Shanghai jazz singer, elegant features, "
            "classic finger-wave hairstyle, red lips, wearing a shimmering qipao dress, leaning on "
            "a grand piano. Melancholic elegant expression, smoky jazz club with warm amber spotlights. "
            "Square 1:1, vintage Art Deco illustration, romantic and nostalgic."
        ),
    },
    {
        "db_id": 27,
        "file_id": "susu",
        "prompt": (
            "Chinese fantasy anime portrait of a mischievous 500-year-old fox spirit in human form, "
            "long flowing black hair with fox ears peeking out, golden-amber slit eyes, wearing a "
            "mix of ancient Chinese robes and modern hoodie. Playful cheeky grin, holding a bubble "
            "tea, traditional Chinese mountain landscape background. Square 1:1, Chinese fantasy art."
        ),
    },
    {
        "db_id": 28,
        "file_id": "room404",
        "prompt": (
            "Creepy digital art of an AI assistant interface displayed on a hotel room screen, the "
            "screen has a calm blue smiley face but with subtle distortions - one eye slightly "
            "larger, a crack in the screen, dark hotel room with a single flickering light. Unsettling "
            "uncanny valley feeling, horror atmosphere, dim red ambient light. Square 1:1, horror art."
        ),
    },
    {
        "db_id": 29,
        "file_id": "momo",
        "prompt": (
            "Stylish digital portrait of a sharp-tongued creative writer, 25-year-old with trendy "
            "undercut hairstyle, smart dark-rimmed glasses, wearing a band t-shirt under an open "
            "plaid shirt. Confident snarky smirk, surrounded by floating manuscript pages and red "
            "editing marks, warm studio apartment background. Square 1:1, modern illustration."
        ),
    },
    {
        "db_id": 30,
        "file_id": "pixel",
        "prompt": (
            "Adorable chibi-style digital portrait of a cute coding mascot character, round face "
            "with big sparkling eyes, wearing a tiny hoodie with a code bracket logo, headphones "
            "around neck, holding a glowing laptop. Cheerful excited expression, colorful code "
            "snippets and pixel art floating in background. Square 1:1, kawaii chibi art style."
        ),
    },
]


def generate_image(client, prompt, output_path):
    """Generate a single image using Gemini 3 Pro Image."""
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                temperature=1.0,
            ),
        )

        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    image_data = part.inline_data.data
                    with open(output_path, "wb") as f:
                        f.write(image_data)
                    size_kb = len(image_data) / 1024
                    print(f"    Saved ({size_kb:.0f} KB)")
                    return True

        print(f"    WARN: No image generated")
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.text:
                    print(f"    Text: {part.text[:200]}")
        return False

    except Exception as e:
        print(f"    ERROR: {e}")
        return False


def update_avatar_url(db_id, file_id):
    """Update the character's avatar_url in the backend."""
    url = f"{BACKEND_API}/{db_id}"
    r = http_requests.put(url, json={"avatar_url": f"/avatars/{file_id}.png"}, timeout=5)
    return r.status_code == 200


def main():
    os.makedirs(AVATAR_DIR, exist_ok=True)

    print("=" * 60)
    print("SynClub Local - New Character Avatar Generator")
    print(f"Model: {MODEL}")
    print(f"Characters: {len(NEW_CHARACTERS)}")
    print("=" * 60)

    client = get_client()

    done = 0
    failed = 0

    for i, char in enumerate(NEW_CHARACTERS):
        avatar_path = os.path.join(AVATAR_DIR, f"{char['file_id']}.png")
        print(f"\n[{i+1}/{len(NEW_CHARACTERS)}] ID={char['db_id']} {char['file_id']}")

        if os.path.exists(avatar_path):
            print(f"    SKIP: Already exists")
            update_avatar_url(char["db_id"], char["file_id"])
            done += 1
            continue

        ok = generate_image(client, char["prompt"], avatar_path)
        if ok:
            update_avatar_url(char["db_id"], char["file_id"])
            done += 1
        else:
            failed += 1

        time.sleep(3)

    print(f"\n{'=' * 60}")
    print(f"Done! {done}/{len(NEW_CHARACTERS)} avatars generated, {failed} failed.")
    print(f"Directory: {AVATAR_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
