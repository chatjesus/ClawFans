"""
Download NoobAI XL for ComfyUI — best uncensored NSFW anime image model.

Usage:
  python scripts/download_noobai.py                          # auto-download from HuggingFace
  python scripts/download_noobai.py --civitai YOUR_API_KEY  # download latest from CivitAI
"""
import os, sys, time, argparse
from pathlib import Path

CKPT_DIR = Path(r"C:\Users\PRO\Desktop\CUDA\ComfyUI\models\checkpoints")
CKPT_DIR.mkdir(parents=True, exist_ok=True)

# Available public sources (no auth required)
HF_SOURCES = [
    # Toc/toc public mirror of NoobAI XL v-pred v1.0
    ("Toc/toc", "models/NoobAI-XL-Vpred-v1.0.safetensors", "NoobAI-XL-Vpred-v1.0.safetensors"),
    # arcacolab public mirror
    ("arcacolab/models", "NoobAI-XL-Vpred-v1.0.safetensors", "NoobAI-XL-Vpred-v1.0.safetensors"),
]

# CivitAI model version ID for NoobAI XL v-pred latest
CIVITAI_VERSION_ID = "1190596"  # NoobAI-XL-Vpred bf16 6.62GB


def download_civitai(api_key: str) -> bool:
    """Download from CivitAI with API key (latest version)."""
    import requests
    dest = CKPT_DIR / "noobaiXL-vpred-latest.safetensors"
    if dest.exists() and dest.stat().st_size > 1e9:
        print(f"Already exists: {dest}")
        return True
    url = f"https://civitai.com/api/download/models/{CIVITAI_VERSION_ID}"
    headers = {"Authorization": f"Bearer {api_key}"}
    print(f"Downloading from CivitAI (model version {CIVITAI_VERSION_ID})...")
    r = requests.get(url, headers=headers, stream=True, timeout=60)
    if r.status_code != 200:
        print(f"CivitAI error: {r.status_code} {r.text[:200]}")
        return False
    total = int(r.headers.get("content-length", 0))
    downloaded = 0
    t0 = time.time()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024*1024):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded / total * 100
                speed = downloaded / (time.time() - t0 + 0.001) / 1e6
                print(f"  {pct:.1f}% — {downloaded//1e6:.0f}/{total//1e6:.0f} MB — {speed:.1f} MB/s", end="\r")
    print(f"\nDone! Saved to: {dest}")
    return True


def download_huggingface() -> bool:
    """Try public HuggingFace mirrors."""
    from huggingface_hub import hf_hub_download
    for repo, filename, dest_name in HF_SOURCES:
        dest = CKPT_DIR / dest_name
        if dest.exists() and dest.stat().st_size > 1e9:
            print(f"Already exists: {dest} ({dest.stat().st_size/1e9:.1f}GB)")
            return True
        print(f"Trying {repo}/{filename}...")
        try:
            t0 = time.time()
            path = hf_hub_download(
                repo_id=repo,
                filename=filename,
                local_dir=str(CKPT_DIR),
                local_dir_use_symlinks=False,
            )
            elapsed = time.time() - t0
            gb = Path(path).stat().st_size / 1e9
            print(f"Done! {gb:.1f}GB in {elapsed/60:.1f} min -> {path}")
            return True
        except Exception as e:
            print(f"  Failed: {e}")
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--civitai", metavar="API_KEY", help="CivitAI API key for download")
    args = parser.parse_args()

    # Check if already installed
    for f in CKPT_DIR.glob("*.safetensors"):
        if any(x in f.name.lower() for x in ["noob", "illustrious", "pony", "sdxl"]):
            print(f"SDXL model already installed: {f} ({f.stat().st_size/1e9:.1f}GB)")
            print("ComfyUI is ready to use!")
            return

    print("=" * 60)
    print("  NoobAI XL — NSFW Anime Image Model for ComfyUI")
    print("  ~6.5GB download, RTX 5090 ready")
    print("=" * 60)
    print()

    if args.civitai:
        success = download_civitai(args.civitai)
    else:
        print("Trying public HuggingFace mirrors (no auth needed)...")
        print("For latest version, use: --civitai YOUR_CIVITAI_API_KEY")
        print()
        success = download_huggingface()

    if success:
        print()
        print("Model downloaded! Next steps:")
        print("  1. Start ComfyUI: cd C:\\Users\\PRO\\Desktop\\CUDA && .\\start_comfyui.ps1")
        print("  2. Regenerate images: python scripts/regen_images.py --new --force-nsfw")
    else:
        print()
        print("Auto-download failed. Please download manually:")
        print()
        print("Option A — CivitAI (best, needs API key):")
        print("  1. Get API key from https://civitai.com/user/account")
        print("  2. Run: python scripts/download_noobai.py --civitai YOUR_KEY")
        print()
        print("Option B — Manual download:")
        print("  1. Visit https://civitai.com/models/833294")
        print("  2. Download 'NoobAI-XL-Vpred-1.0 bf16' (~6.5GB)")
        print(f"  3. Save to: {CKPT_DIR}")


if __name__ == "__main__":
    main()
