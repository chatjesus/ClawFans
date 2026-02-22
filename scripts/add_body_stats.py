"""
Add physical body stats to each character's system_prompt using Qwen 2.5 14B.
Appends: Height, Weight, Bust/Waist/Hip (三围), Blood Type, Birthday, Hobbies.
"""
import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

API_URL = "http://localhost:8000/api/characters"
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:14b"

TARGET_IDS = [
    38, 39, 40, 41, 42, 43, 44,  # New NSFW batch
    9, 10, 11, 34, 36, 37,        # Romance
    4, 19, 21,                    # Roleplay
    12, 14,                       # Anime
    17, 18,                       # School
    31, 32, 33, 35,               # Extra Romance
    5, 6, 7, 8,                   # Featured
]

def call_qwen(prompt):
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.7, "num_ctx": 2048}
    }
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=60)
        r.raise_for_status()
        return r.json().get("response", "")
    except Exception as e:
        print(f"  [OLLAMA ERROR] {e}")
        return None

def generate_body_stats(char):
    prompt = f"""You are a character designer for an adult anime roleplay game.

Character:
- Name: {char['name']}
- Description: {char['description']}
- Tags: {char['tags']}
- Category: {char['category']}

Generate realistic and sexy physical stats for this anime character.

Output strict JSON (no extra keys):
{{
  "height": "cm (e.g. 162cm)",
  "weight": "kg (e.g. 48kg)",
  "bust": "cm",
  "waist": "cm",
  "hip": "cm",
  "cup_size": "e.g. E cup",
  "blood_type": "A/B/O/AB",
  "birthday": "Month Day (e.g. March 15)",
  "hobby": "Short hobby description in Chinese",
  "secret": "A hidden desire or secret NSFW fact about this character, in Chinese, 1 sentence"
}}
"""
    raw = call_qwen(prompt)
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data
    except json.JSONDecodeError:
        print(f"  [PARSE ERROR] {raw[:60]}...")
        return None

def format_stats_block(stats):
    return f"""

---
【角色档案】
身高：{stats.get('height', '?')} | 体重：{stats.get('weight', '?')}
三围：B{stats.get('bust', '?')} / W{stats.get('waist', '?')} / H{stats.get('hip', '?')} ({stats.get('cup_size', '?')})
血型：{stats.get('blood_type', '?')} | 生日：{stats.get('birthday', '?')}
爱好：{stats.get('hobby', '?')}
秘密：{stats.get('secret', '?')}
---"""

def main():
    # Get all characters
    r = requests.get(f"{API_URL}/")
    all_chars = r.json()
    targets = [c for c in all_chars if c['id'] in TARGET_IDS]
    
    print(f"Adding body stats to {len(targets)} characters...\n")

    for char in targets:
        print(f"Processing {char['name']} (ID {char['id']})...")
        
        stats = generate_body_stats(char)
        if not stats:
            print(f"  [SKIP] Failed to generate stats.")
            continue
        
        stats_block = format_stats_block(stats)
        
        # Append stats to system_prompt (avoid duplicating if already has 角色档案)
        current_sp = char.get('system_prompt', '')
        if '【角色档案】' in current_sp:
            # Remove existing block and replace
            idx = current_sp.find('\n---\n【角色档案】')
            if idx != -1:
                current_sp = current_sp[:idx]
        
        new_sp = current_sp + stats_block
        
        update_r = requests.put(f"{API_URL}/{char['id']}", json={"system_prompt": new_sp})
        if update_r.status_code == 200:
            print(f"  [OK] {char['name']}: {stats.get('height')} {stats.get('bust')}/{stats.get('waist')}/{stats.get('hip')} {stats.get('cup_size')}")
        else:
            print(f"  [FAIL] {update_r.status_code}: {update_r.text[:80]}")

if __name__ == "__main__":
    main()
