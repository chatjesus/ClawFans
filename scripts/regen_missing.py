import os, time
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\PRO\Desktop\CUDA\credentials\pdfconverter-415414-d9dbb1a4eec6.json"
from google import genai
from google.genai import types
import requests

client = genai.Client(vertexai=True, project="pdfconverter-415414", location="global")
AVATAR_DIR = r"C:\Users\PRO\Desktop\CUDA\synclub-local\frontend\public\avatars"
API = "http://localhost:8000/api/characters"

tasks = [
    {
        "file_id": "yuki_v2",
        "db_id": 9,
        "prompt": (
            "High quality anime illustration, beautiful Japanese girl, 22 years old, "
            "long silky black hair flowing down, soft seductive brown eyes with long lashes, "
            "delicate features, wearing an off-shoulder cream knit sweater, "
            "gentle alluring smile, cherry blossoms outside window, warm golden light, "
            "intimate portrait composition, magazine cover quality, detailed illustration"
        ),
    },
    {
        "file_id": "mei",
        "db_id": None,
        "prompt": (
            "High quality anime illustration, cheerful idol girl, 20 years old, "
            "long twin-tailed bright orange hair with pastel gradient tips, "
            "large sparkling amber eyes, light freckles on nose, "
            "wearing a cute idol stage costume with ribbons and bows, "
            "dynamic energetic pose with microphone, stage lighting with spotlights, "
            "vibrant idol concert atmosphere, colorful and detailed anime art"
        ),
    },
]

for t in tasks:
    fid = t["file_id"]
    path = os.path.join(AVATAR_DIR, fid + ".png")
    print(f"Generating {fid}...")
    resp = client.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents=t["prompt"],
        config=types.GenerateContentConfig(response_modalities=["IMAGE"], temperature=1.0),
    )
    saved = False
    for part in resp.candidates[0].content.parts:
        if part.inline_data:
            with open(path, "wb") as f:
                f.write(part.inline_data.data)
            kb = len(part.inline_data.data) // 1024
            print(f"  Saved {kb}KB -> {fid}.png")
            saved = True
            if t["db_id"]:
                r = requests.put(f"{API}/{t['db_id']}", json={"avatar_url": f"/avatars/{fid}.png"}, timeout=5)
                print(f"  Updated DB id={t['db_id']} -> {r.status_code}")
    if not saved:
        for part in resp.candidates[0].content.parts:
            if part.text:
                print(f"  Filtered: {part.text[:100]}")
    time.sleep(3)

# Seed Mei into DB
mei_path = os.path.join(AVATAR_DIR, "mei.png")
if os.path.exists(mei_path):
    chars = requests.get(f"{API}/", timeout=5).json()
    if not any(c["name"] == "Mei" for c in chars):
        import random
        payload = {
            "name": "Mei",
            "description": "人气爱豆，台上光芒万丈，台下只有你能看到她卸下妆容后的真实笑容。",
            "system_prompt": (
                "You are Mei, a 20-year-old popular idol. In public you are bright, polished, and "
                "professional. With the user (your secret close friend), you completely relax — "
                "you complain about schedules, share snacks, geek out about your hobbies, and be "
                "genuinely yourself. You are cheerful, affectionate, and occasionally clingy. Stay in character."
            ),
            "greeting": "唔...终于结束今天的通告了。*偷偷发来消息* 你在吗？好想见你。今天好累...能陪我说说话吗？",
            "avatar_url": "/avatars/mei.png",
            "tags": "Romance,偶像,甜蜜",
            "category": "Romance",
            "is_public": True,
        }
        r = requests.post(f"{API}/", json=payload, timeout=5)
        if r.status_code == 201:
            cid = r.json()["id"]
            mc, sc = random.randint(200, 450), random.randint(30, 70)
            requests.put(f"{API}/{cid}", json={"message_count": mc, "star_count": sc}, timeout=5)
            print(f"Created Mei in DB (id={cid})")

print("Done!")
