"""Download Realistic Vision V5.1 FP16 Inpainting model for ComfyUI."""
import requests, os

MIRROR = "https://hf-mirror.com"
REPO = "SG161222/Realistic_Vision_V5.1_noVAE"
FNAME = "Realistic_Vision_V5.1_fp16-no-ema-inpainting.safetensors"
DEST = r"D:\ComfyUI_Models\checkpoints"

os.makedirs(DEST, exist_ok=True)
local = os.path.join(DEST, FNAME)

if os.path.exists(local):
    sz = os.path.getsize(local)
    print(f"Already exists: {local} ({sz/1024/1024:.1f} MB)")
    exit(0)

url = f"{MIRROR}/{REPO}/resolve/main/{FNAME}"
print(f"Downloading: {url}")
print(f"To: {local}")

r = requests.head(url, timeout=10, allow_redirects=True)
total = int(r.headers.get("Content-Length", 0))
print(f"Size: {total/1024/1024:.1f} MB")

r = requests.get(url, timeout=600, stream=True)
r.raise_for_status()
downloaded = 0
with open(local + ".tmp", "wb") as f:
    for chunk in r.iter_content(65536):
        f.write(chunk)
        downloaded += len(chunk)
        pct = downloaded / total * 100 if total else 0
        if downloaded % (50 * 1024 * 1024) < 65536:
            print(f"  {downloaded/1024/1024:.0f} / {total/1024/1024:.0f} MB ({pct:.0f}%)")

os.rename(local + ".tmp", local)
print(f"Done: {os.path.getsize(local)/1024/1024:.1f} MB")
