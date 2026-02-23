import sys, os, json, time
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

LOG_PATH = "debug-90e70b.log"

# Simulate what IMAGE_PROMPTS_GEN would produce for 苏雨柔 (NSFW=True)
# to check if the prompts are conservative or spicy

# Check what's in the create_50_chars.py IMAGE_PROMPTS_GEN
script_path = os.path.join(BACKEND_DIR, "..", "scripts", "create_50_chars.py")
with open(script_path, encoding='utf-8') as f:
    src = f.read()

# Extract IMAGE_PROMPTS_GEN section
import re
m = re.search(r'IMAGE_PROMPTS_GEN = """(.+?)"""', src, re.DOTALL)
img_prompt_template = m.group(1).strip() if m else "NOT FOUND"

# Check SCENE_PLANNER
m2 = re.search(r'SCENE_PLANNER = """(.+?)"""', src, re.DOTALL)
scene_planner = m2.group(1).strip() if m2 else "NOT FOUND"

# Check the nsfw=False flag on image prompt generation call
nsfw_flag_match = re.search(r'IMAGE_PROMPTS_GEN.+?nsfw=(\w+)', src, re.DOTALL)
nsfw_flag = nsfw_flag_match.group(1) if nsfw_flag_match else "not found"

print("=== IMAGE_PROMPTS_GEN NSFW instruction ===")
# Find the NSFW line in the template
for line in img_prompt_template.split('\n'):
    if 'NSFW' in line or 'nsfw' in line or 'suggestive' in line or 'alluring' in line:
        print(f"  >> {line}")

print(f"\n=== nsfw flag passed to chat_completion for image prompts ===")
print(f"  nsfw={nsfw_flag}  (True=abliterate model, False=safe model)")

print(f"\n=== SCENE_PLANNER NSFW instruction ===")
for line in scene_planner.split('\n'):
    if 'NSFW' in line or 'nsfw' in line or 'suggestive' in line or 'intimate' in line:
        print(f"  >> {line}")

# Also check existing ref image prompt files to see what Gemini received
from pathlib import Path
refs_dir = Path(BACKEND_DIR) / "uploads" / "refs"
sample_ids = [52, 53, 49, 50]
existing = {}
for cid in sample_ids:
    char_refs = refs_dir / str(cid)
    if char_refs.exists():
        files = list(char_refs.glob("*.png"))
        existing[cid] = [f.name for f in files]
        print(f"\n  Char {cid} refs: {[f.name for f in files]}")

# Log to debug file
with open(LOG_PATH, "a", encoding="utf-8") as f:
    f.write(json.dumps({
        "sessionId": "90e70b",
        "runId": "initial",
        "hypothesisId": "F-G-H",
        "location": "check_img_prompts.py",
        "message": "image_prompt_audit",
        "data": {
            "nsfw_model_flag": nsfw_flag,
            "img_prompt_nsfw_lines": [l for l in img_prompt_template.split('\n') if 'NSFW' in l or 'nsfw' in l],
            "scene_nsfw_lines": [l for l in scene_planner.split('\n') if 'NSFW' in l or 'nsfw' in l],
            "existing_ref_chars": list(existing.keys()),
        },
        "timestamp": int(time.time() * 1000),
    }) + "\n")
print(f"\nLog written.")
