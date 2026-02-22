"""
Final attempt for Rina (Gyaru) and adding a Bunny Girl.
"""
import os, time, random
import requests
from google import genai
from google.genai import types

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\PRO\Desktop\CUDA\credentials\pdfconverter-415414-d9dbb1a4eec6.json"
client = genai.Client(vertexai=True, project="pdfconverter-415414", location="global")

API = "http://localhost:8000/api/characters"
AVATAR_DIR = r"C:\Users\PRO\Desktop\CUDA\synclub-local\frontend\public\avatars"

CHARACTERS = [
    {
        "file_id": "gyaru_rina_final",
        "name": "Rina",
        "prompt": (
            "High quality anime illustration, gyaru fashion high school girl, "
            "tanned skin, blonde hair with pink streaks, heavy makeup, "
            "wearing a beige cardigan over school uniform, plaid skirt, "
            "holding a bubble tea, winking at viewer, playful expression, "
            "shibuya crossing background, vibrant city lights, "
            "detailed anime art style, trendy and cute"
        ),
        "desc": "涩谷街头的时尚辣妹，看起来很不好惹，其实很单纯。",
        "tags": "NSFW,Gyaru,Fashion",
        "category": "School"
    },
    {
        "file_id": "bunny_girl_senpai",
        "name": "Mai",
        "prompt": (
            "High quality anime illustration, beautiful girl in bunny suit, "
            "black leotard, bunny ears, fishnet tights, cuffs and collar, "
            "long black hair, embarrassed blushing expression, covering chest with arm, "
            "looking away shyly, stage curtain background, spotlight, "
            "soft lighting, detailed anime art style"
        ),
        "desc": "兼职穿成兔女郎的学姐，被你发现了...",
        "tags": "NSFW,Bunny,Senpai",
        "category": "Roleplay"
    }
]

def main():
    print("Generating final batch...")
    for char in CHARACTERS:
        print(f"\nGenerating: {char['name']}...")
        path = os.path.join(AVATAR_DIR, char['file_id'] + ".png")
        
        try:
            resp = client.models.generate_content(
                model="gemini-3-pro-image-preview",
                contents=char['prompt'],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"], 
                    temperature=1.0,
                    safety_settings=[
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                            threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH
                        )
                    ]
                ),
            )
            
            if resp.candidates:
                for part in resp.candidates[0].content.parts:
                    if part.inline_data:
                        with open(path, "wb") as f:
                            f.write(part.inline_data.data)
                        print(f"  [OK] Saved -> {char['file_id']}.png")
                        
                        # Add to DB
                        payload = {
                            "name": char["name"],
                            "description": char["desc"],
                            "system_prompt": f"You are {char['name']}. {char['desc']} Stay in character.",
                            "greeting": f"Oh... you saw me? *Blushes*",
                            "avatar_url": f"/avatars/{char['file_id']}.png",
                            "tags": char["tags"],
                            "category": char["category"],
                            "is_public": True
                        }
                        r = requests.post(f"{API}/", json=payload)
                        if r.status_code == 201:
                            cid = r.json()["id"]
                            requests.put(f"{API}/{cid}", json={"message_count": random.randint(100,900), "star_count": random.randint(50,200)})
                            print(f"  [DB] Added ID={cid}")
                        break
            else:
                print("  [BLOCKED]")

        except Exception as e:
            print(f"  [ERROR] {e}")
        
        time.sleep(3)

if __name__ == "__main__":
    main()
