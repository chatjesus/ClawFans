import requests
import json
import re

API_URL = "http://localhost:8000/api/characters"
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:14b"

def get_ollama_response(prompt):
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",  # Force JSON output
        "options": {
            "temperature": 0.8,
            "num_ctx": 4096
        }
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        response.raise_for_status()
        return response.json().get("response", "")
    except Exception as e:
        print(f"Error calling Ollama: {e}")
        return None

def enrich_character(char):
    print(f"Enriching {char['name']} (ID: {char['id']})...")
    
    # Prompt for NSFW/Adult content
    prompt = f"""
    You are an expert creative writer for an adult roleplay chat application.
    
    Character: {char['name']}
    Current Description: {char['description']}
    Tags: {char['tags']}
    
    Task: 
    Rewrite the character's "description" and "system_prompt" to be more detailed, immersive, and explicitly suggestive/NSFW (尺度大).
    
    Requirements:
    1. "description": A short, alluring hook (Chinese). 1-2 sentences. 
       - Example: "The strict teacher who secretly wants to be dominated..."
    2. "system_prompt": A detailed instruction set for the AI (English/Chinese mix ok).
       - Define personality: {char['tags']}
       - Define kinks/fetishes implied by tags.
       - Define scenario: Where are they? What is the user doing?
       - The character should be willing to engage in adult/NSFW content.
    
    Output JSON format:
    {{
        "description": "...",
        "system_prompt": "..."
    }}
    """
    
    response_text = get_ollama_response(prompt)
    if not response_text:
        return

    try:
        data = json.loads(response_text)
        if "description" in data and "system_prompt" in data:
            # Update DB
            update_payload = {
                "description": data["description"],
                "system_prompt": data["system_prompt"]
            }
            # Handle trailing slash in API_URL if needed
            url = f"{API_URL}/{char['id']}"
            r = requests.put(url, json=update_payload)
            if r.status_code == 200:
                print(f"  [SUCCESS] Updated {char['name']}")
            else:
                print(f"  [FAIL] API Error {r.status_code}: {r.text}")
        else:
            print(f"  [FAIL] JSON missing keys: {data.keys()}")
    except json.JSONDecodeError:
        print(f"  [FAIL] Invalid JSON from Ollama: {response_text[:50]}...")
    except Exception as e:
        print(f"  [FAIL] Error: {e}")

def main():
    # 1. Get all characters
    try:
        r = requests.get(f"{API_URL}/")
        chars = r.json()
    except Exception as e:
        print(f"Error fetching characters: {e}")
        return

    # 2. Filter target characters
    # Target new batch (>=38) and Romance/Roleplay categories
    targets = []
    for c in chars:
        # Explicitly target the new "Sexy" batch
        if c['id'] >= 38:
            targets.append(c)
            continue
            
        # Also target existing Romance/Roleplay if they seem relevant
        # Exclude "Wellness", "Horror", "Game" for now to keep it focused
        if c['category'] in ['Romance', 'Roleplay', 'Anime', 'Maid', 'School']:
            targets.append(c)

    print(f"Found {len(targets)} characters to enrich (NSFW focus).")
    
    # Process them
    for char in targets:
        enrich_character(char)

if __name__ == "__main__":
    main()
