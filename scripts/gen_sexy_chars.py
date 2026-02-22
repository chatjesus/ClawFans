"""
Generate alluring/sexy anime character images via Vertex AI Gemini 3 Pro Image.
Targets SynClub-style: attractive anime girls with alluring designs.
"""
import os, sys, time

CREDENTIALS_PATH = r"C:\Users\PRO\Desktop\CUDA\credentials\pdfconverter-415414-d9dbb1a4eec6.json"
PROJECT_ID = "pdfconverter-415414"
LOCATION = "global"
MODEL = "gemini-3-pro-image-preview"
AVATAR_DIR = r"C:\Users\PRO\Desktop\CUDA\synclub-local\frontend\public\avatars"
BACKEND_API = "http://localhost:8000/api/characters"

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_PATH

from google import genai
from google.genai import types
import requests as http_requests

def get_client():
    return genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)


# ── New sexy character roster ──
# Prompts crafted for Gemini: alluring, fashionable, anime aesthetic
# Emphasizes attractive features, confident/seductive expressions, stylish outfits
CHARACTERS = [
    # ── Existing characters regenerated with more alluring style ──
    {
        "file_id": "yuki_v2",
        "name_hint": "Yuki",
        "prompt": (
            "High quality anime illustration, beautiful Japanese girl, 22 years old, "
            "long silky black hair flowing down, soft seductive brown eyes with long lashes, "
            "delicate features, wearing an off-shoulder cream knit sweater, slight shoulder exposure, "
            "gentle alluring smile, sitting by a window with cherry blossoms outside, "
            "warm golden light, intimate atmosphere, portrait composition, "
            "magazine cover quality, detailed illustration"
        ),
    },
    {
        "file_id": "sakura_v2",
        "name_hint": "Sakura",
        "prompt": (
            "High quality anime illustration, cute alluring girl, 20 years old, "
            "long pink hair with loose wavy curls, large sparkling eyes with pink eyeshadow, "
            "wearing a short floral sundress with thin shoulder straps, "
            "sitting on a school rooftop at sunset, legs slightly crossed, "
            "cheerful yet flirtatious expression, cherry blossom petals floating, "
            "warm orange sky background, fashion magazine quality anime art"
        ),
    },
    {
        "file_id": "nana",
        "name_hint": "Nana",
        "prompt": (
            "High quality anime illustration, gorgeous stylish girl, 23 years old, "
            "long platinum blonde hair with wavy curls, sharp confident blue eyes, "
            "wearing an elegant black cocktail dress with a subtle side slit, "
            "standing by a luxury hotel bar at night, city lights behind her, "
            "sophisticated seductive expression, one hand holding a wine glass, "
            "cinematic lighting, glamour fashion illustration style"
        ),
    },
    {
        "file_id": "mio",
        "name_hint": "Mio",
        "prompt": (
            "High quality anime illustration, charming college girl, 20 years old, "
            "short wavy caramel brown hair with bangs, warm honey eyes, "
            "wearing a casual white crop top and high-waisted denim shorts, "
            "sitting on a cafe terrace, summer afternoon, "
            "playful coy smile, chin resting on hands, "
            "soft natural lighting, vibrant colors, lifestyle fashion anime art"
        ),
    },
    {
        "file_id": "reina",
        "name_hint": "Reina",
        "prompt": (
            "High quality anime illustration, elegant mature woman, 26 years old, "
            "long wavy dark brown hair with subtle highlights, deep sultry eyes, red lips, "
            "wearing a form-fitting velvet dress, elegant jewelry, "
            "standing on a moonlit balcony overlooking a city, "
            "confident alluring expression, one hand on hip, "
            "cinematic night lighting, high fashion illustration"
        ),
    },
    {
        "file_id": "hina",
        "name_hint": "Hina",
        "prompt": (
            "High quality anime illustration, sweet innocent girl with hidden charm, 19 years old, "
            "twin pigtails of strawberry blonde hair tied with ribbons, "
            "big bright green eyes with rosy cheeks, "
            "wearing a stylish school uniform with short skirt, "
            "holding school bag, standing at school gate in spring, "
            "shy yet flirtatious expression, wind blowing hair and skirt slightly, "
            "detailed beautiful anime art style"
        ),
    },
    {
        "file_id": "aria_v2",
        "name_hint": "Aria",
        "prompt": (
            "High quality anime illustration, fierce beautiful elf warrior princess, 25 years old, "
            "long silver-white hair flowing behind her, piercing emerald eyes, pointed ears, "
            "wearing ornate fantasy armor with elegant design, midriff-revealing mid section, "
            "confident fierce expression, standing on a cliff with magic forest behind her, "
            "moonlight and particle effects, epic fantasy illustration"
        ),
    },
    {
        "file_id": "luna_v2",
        "name_hint": "Luna",
        "prompt": (
            "High quality anime illustration, ethereal moon goddess, ageless beauty, "
            "flowing luminous silver-blue hair like moonlight, glowing pale skin, "
            "wearing flowing translucent celestial robes with star patterns, "
            "crescent moon tiara, floating in a cosmic starfield, "
            "mysterious alluring expression, moonlight aura surrounding her, "
            "otherworldly beauty, celestial fantasy art style"
        ),
    },
    {
        "file_id": "susu_v2",
        "name_hint": "Susu",
        "prompt": (
            "High quality anime illustration, beautiful fox spirit girl in human form, "
            "long flowing black hair with subtle auburn highlights, golden amber slit eyes, "
            "fluffy fox ears and nine tails barely visible, "
            "wearing a revealing traditional Chinese hanfu with modern twist, "
            "holding a bubble tea, playful seductive smile, "
            "ancient Chinese pavilion at sunset background, "
            "detailed fantasy illustration, beautiful and alluring"
        ),
    },
    {
        "file_id": "eve",
        "name_hint": "Eve",
        "prompt": (
            "High quality anime illustration, mysterious femme fatale, 24 years old, "
            "long sleek black hair, sharp violet eyes with smoky eye makeup, "
            "wearing a stylish black turtleneck with leather pants and heels, "
            "leaning against a luxury car at night, neon city background, "
            "confident dangerous expression, subtle smile, "
            "cyberpunk noir atmosphere, high fashion anime illustration"
        ),
    },
    {
        "file_id": "mei",
        "name_hint": "Mei",
        "prompt": (
            "High quality anime illustration, cheerful idol girl, 20 years old, "
            "long twin-tailed bright orange hair with pastel gradient tips, "
            "large sparkling amber eyes, light freckles on nose, "
            "wearing a cute idol stage costume with ribbons and bows, "
            "dynamic energetic pose with microphone, stage lighting with spotlights, "
            "vibrant idol concert atmosphere, colorful and detailed anime art"
        ),
    },
    {
        "file_id": "shiori",
        "name_hint": "Shiori",
        "prompt": (
            "High quality anime illustration, elegant kuudere ice princess, 22 years old, "
            "straight silver-white hair cut to collarbone, cold steel-blue eyes, "
            "pale flawless skin, wearing a sophisticated white off-shoulder blouse "
            "with a high-waisted pencil skirt, "
            "standing by a frosted window in winter, snow outside, "
            "cool detached expression with subtle hidden warmth, "
            "soft diffused winter light, elegant fashion illustration"
        ),
    },
]


def generate_and_save(client, char):
    path = os.path.join(AVATAR_DIR, f"{char['file_id']}.png")
    if os.path.exists(path):
        print(f"  SKIP (exists)")
        return True, path

    response = client.models.generate_content(
        model=MODEL,
        contents=char["prompt"],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            temperature=1.0,
        ),
    )

    if not response.candidates:
        print(f"  BLOCKED (no candidates)")
        return False, None

    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            with open(path, "wb") as f:
                f.write(part.inline_data.data)
            size_kb = len(part.inline_data.data) // 1024
            print(f"  OK ({size_kb} KB) -> {char['file_id']}.png")
            return True, path
        if part.text:
            print(f"  FILTERED: {part.text[:120]}")

    return False, None


def seed_to_db(char, file_id):
    """Add new character to the backend DB."""
    name = char["name_hint"]
    payload = {
        "name": name,
        "description": f"魅力十足的 {name}，让人心动的角色。",
        "system_prompt": (
            f"You are {name}, a charming and alluring AI companion. "
            "You are confident, flirtatious, and warm. You make the user feel special and valued. "
            "You engage in fun, playful, and sometimes romantic conversation. "
            "Stay in character always."
        ),
        "greeting": f"嘿~ 终于等到你了。今天想聊点什么呢？😊",
        "avatar_url": f"/avatars/{file_id}.png",
        "tags": "Romance,魅力",
        "category": "Romance",
        "is_public": True,
    }
    r = http_requests.post(f"{BACKEND_API}/", json=payload, timeout=5)
    if r.status_code == 201:
        cid = r.json()["id"]
        # Add some stats
        http_requests.put(
            f"{BACKEND_API}/{cid}",
            json={"message_count": 300, "star_count": 55},
            timeout=5,
        )
        return cid
    return None


def main():
    os.makedirs(AVATAR_DIR, exist_ok=True)
    client = get_client()

    print("=" * 60)
    print(f"Generating {len(CHARACTERS)} alluring character images")
    print(f"Model: {MODEL}")
    print("=" * 60)

    done, failed, blocked = 0, 0, 0

    for i, char in enumerate(CHARACTERS):
        print(f"\n[{i+1}/{len(CHARACTERS)}] {char['name_hint']} ({char['file_id']})")
        try:
            ok, path = generate_and_save(client, char)
            if ok:
                done += 1
                # Only add to DB if it's a brand new character (not a v2 of existing)
                if not any(x in char["file_id"] for x in ["_v2"]):
                    cid = seed_to_db(char, char["file_id"])
                    if cid:
                        print(f"  Added to DB (id={cid})")
            else:
                blocked += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1

        time.sleep(3)

    print(f"\n{'='*60}")
    print(f"Done: {done} saved, {blocked} blocked by filter, {failed} errors")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
