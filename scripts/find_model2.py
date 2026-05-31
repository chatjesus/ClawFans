import requests

MIRROR = "https://hf-mirror.com"

# Look for single-file checkpoint versions of realistic models
repos = [
    "SG161222/Realistic_Vision_V5.1_noVAE",
    "stablediffusionapi/realistic-vision-v51",
    "frankjoshua/realisticVisionV51_v51VAE",
    "Yntec/realistic-vision-v51",
]

for repo in repos:
    url = f"{MIRROR}/api/models/{repo}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            mid = data.get("id", "?")
            print(f"\nFound: {mid}")
            for s in data.get("siblings", []):
                fn = s.get("rfilename", "")
                if fn.endswith(".safetensors"):
                    print(f"  {fn}")
        else:
            print(f"\n{repo}: HTTP {r.status_code}")
    except Exception as e:
        print(f"\n{repo}: {e}")
