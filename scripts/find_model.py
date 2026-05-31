import requests

MIRROR = "https://hf-mirror.com"

repos = [
    "SG161222/Realistic_Vision_V5.1_noVAE",
    "SG161222/Realistic_Vision_V5.1-inpainting",
]

for repo in repos:
    url = f"{MIRROR}/api/models/{repo}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            mid = data.get("id", "?")
            print(f"Found: {mid}")
            for s in data.get("siblings", []):
                fn = s.get("rfilename", "")
                if fn.endswith((".safetensors", ".ckpt", ".bin")) and "model" in fn.lower():
                    print(f"  {fn}")
        else:
            print(f"{repo}: HTTP {r.status_code}")
    except Exception as e:
        print(f"{repo}: {e}")
