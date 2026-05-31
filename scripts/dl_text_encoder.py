import requests, os

BASE = "D:/ComfyUI_Models/CatVTON/stable-diffusion-inpainting"
MIRROR = "https://hf-mirror.com"

attempts = [
    ("runwayml/stable-diffusion-inpainting", "text_encoder/model.fp16.safetensors"),
    ("runwayml/stable-diffusion-inpainting", "text_encoder/pytorch_model.bin"),
    ("runwayml/stable-diffusion-inpainting", "text_encoder/pytorch_model.fp16.bin"),
    ("stable-diffusion-v1-5/stable-diffusion-inpainting", "text_encoder/model.safetensors"),
    ("stable-diffusion-v1-5/stable-diffusion-inpainting", "text_encoder/model.fp16.safetensors"),
]

for repo, fpath in attempts:
    url = f"{MIRROR}/{repo}/resolve/main/{fpath}"
    print(f"Trying: {url}")
    try:
        r = requests.head(url, timeout=10, allow_redirects=True)
        cl = r.headers.get("Content-Length", "?")
        print(f"  Status: {r.status_code}, Size: {cl}")
        if r.status_code == 200:
            size = int(cl)
            local = os.path.join(BASE, "text_encoder", os.path.basename(fpath))
            print(f"  Downloading to {local} ({size/1024/1024:.1f} MB)...")
            r2 = requests.get(url, timeout=300, stream=True)
            downloaded = 0
            with open(local, "wb") as f:
                for chunk in r2.iter_content(65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if downloaded % (10*1024*1024) == 0:
                        print(f"  {downloaded/1024/1024:.0f} MB...")
            print(f"  Done: {downloaded/1024/1024:.1f} MB")
            break
    except Exception as e:
        print(f"  Error: {e}")
