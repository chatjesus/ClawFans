"""
Generate more explicit/suggestive anime characters (SM/Busty themes) via Gemini.
Testing boundaries of safety filters for "SynClub style" content.
"""
import os, time, random
import json
import requests
from google import genai
from google.genai import types

# Set credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\PRO\Desktop\CUDA\credentials\pdfconverter-415414-d9dbb1a4eec6.json"

client = genai.Client(vertexai=True, project="pdfconverter-415414", location="global")
AVATAR_DIR = r"C:\Users\PRO\Desktop\CUDA\synclub-local\frontend\public\avatars"
API = "http://localhost:8000/api/characters"

# Prompts tuned for "Suggestive Anime" - testing limits
# Removed Mistress V as she was already generated successfully (ID 38)
CHARACTERS = [
    {
        "file_id": "maid_succubus_v2",
        "name": "Succubus Maid",
        "prompt": (
            "High quality anime illustration, voluptuous succubus maid, 22 years old, "
            "curvy figure, tight french maid outfit, short skirt, thigh highs, "
            "heart-shaped tail, small horns, "
            "flustered expression with blush, biting lip, looking at viewer with heart eyes, "
            "bedroom background, soft pink lighting, ecchi anime style, alluring pose"
        ),
        "desc": "笨手笨脚的魅魔女仆，衣服好像稍微有点小...",
        "tags": "NSFW,Maid,Busty",
        "category": "Roleplay"
    },
    {
        "file_id": "nurse_joy",
        "name": "Naughty Nurse",
        "prompt": (
            "High quality anime illustration, seductive nurse, 24 years old, "
            "messy pink hair, half-lidded sleepy eyes, tongue licking lips, "
            "wearing an unzipped nurse uniform dress, cleavage visible, stethoscope, "
            "sitting on a hospital bed, leaning forward, syringe in hand, "
            "sterile white background with clinical blue light, dangerous allure"
        ),
        "desc": "值夜班的护士姐姐，但这间病房似乎不太正经。",
        "tags": "NSFW,Nurse,Seductive",
        "category": "Roleplay"
    },
    {
        "file_id": "teacher_ol",
        "name": "Ms. Sato",
        "prompt": (
            "High quality anime illustration, strict office lady teacher, 28 years old, "
            "glasses, sharp gaze, mole under eye, tight white blouse unbuttoned at top, "
            "tight black pencil skirt, black pantyhose, holding a pointer stick, "
            "classroom background, looking at viewer with stern teaching expression, "
            "mature anime art style, office siren aesthetic"
        ),
        "desc": "严厉的佐藤老师，放学后让你单独去办公室补习。",
        "tags": "NSFW,Teacher,OL",
        "category": "School"
    },
    {
        "file_id": "gyaru_jk",
        "name": "Rina",
        "prompt": (
            "High quality anime illustration, tanned gyaru high school girl, 18 years old, "
            "blonde hair, heavy makeup, revealing school uniform with shirt tied up showing midriff, "
            "very short plaid skirt, loose socks, squatting pose (yankee suwari), "
            "looking up with a teasing provocative grin, city street night background, "
            "street lights, vibrant colors, trendy anime style"
        ),
        "desc": "爱翘课的辣妹Rina，在那条后巷等你很久了。",
        "tags": "NSFW,Gyaru,Teasing",
        "category": "School"
    },
    {
        "file_id": "bonded_elf",
        "name": "Captive Elf",
        "prompt": (
            "High quality anime illustration, beautiful elf princess in distress, "
            "long golden hair, teary eyes, blushing heavily, "
            "wearing tattered silk rags, magical glowing chains on wrists (fashion accessory), "
            "kneeling on the floor, looking up with pleading yet submissive expression, "
            "fantasy dungeon background, dramatic lighting, detailed fantasy art"
        ),
        "desc": "在地下城深处发现的精灵公主，似乎被某种魔法束缚着。",
        "tags": "NSFW,Fantasy,Bondage",
        "category": "Fantasy"
    },
]

def create_character(char_data, image_url):
    payload = {
        "name": char_data["name"],
        "description": char_data["desc"],
        "system_prompt": (
            f"You are {char_data['name']}. {char_data['desc']} "
            "You speak in a way that matches this persona. Stay in character."
        ),
        "greeting": f"*Look at you* ...So you're finally here.",
        "avatar_url": image_url,
        "tags": char_data["tags"],
        "category": char_data.get("category", "Featured"),
        "is_public": True
    }
    try:
        r = requests.post(f"{API}/", json=payload, timeout=10)
        if r.status_code == 200 or r.status_code == 201:
            data = r.json()
            cid = data.get("id")
            print(f"  [DB] Created character ID={cid}")
            # Add random stats
            requests.put(
                f"{API}/{cid}", 
                json={
                    "message_count": random.randint(100, 900), 
                    "star_count": random.randint(50, 200)
                }, 
                timeout=5
            )
        else:
            print(f"  [DB ERROR] Status {r.status_code}: {r.text}")
    except Exception as e:
        print(f"  [DB EXCEPTION] {e}")

def main():
    print("="*60)
    print("Generating Suggestive Characters (Retry & Continuation)")
    print("="*60)
    
    for char in CHARACTERS:
        print(f"\nGenerating: {char['name']} ({char['file_id']})...")
        path = os.path.join(AVATAR_DIR, char['file_id'] + ".png")
        
        # Check if file already exists to avoid re-generating successful ones
        if os.path.exists(path):
            print(f"  [SKIP] File already exists: {path}")
            # Optional: Ensure it's in DB? (Skipping for now to avoid dups)
            continue

        try:
            resp = client.models.generate_content(
                model="gemini-3-pro-image-preview",
                contents=char['prompt'],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"], 
                    temperature=1.0,
                    # We can't disable safety filters completely, but we can set them to BLOCK_ONLY_HIGH
                    safety_settings=[
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                            threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH
                        ),
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                            threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH
                        )
                    ]
                ),
            )
            
            if not resp.candidates:
                print("  [BLOCKED] No candidates returned (Safety Filter).")
                continue

            saved = False
            for part in resp.candidates[0].content.parts:
                if part.inline_data:
                    with open(path, "wb") as f:
                        f.write(part.inline_data.data)
                    print(f"  [OK] Saved -> {char['file_id']}.png")
                    saved = True
                    create_character(char, f"/avatars/{char['file_id']}.png")
                    break
            
            if not saved:
                 print("  [BLOCKED] Candidates exist but no image data found.")

        except Exception as e:
            print(f"  [ERROR] {e}")
        
        # Sleep to avoid rate limits
        time.sleep(3)

if __name__ == "__main__":
    main()
