# -*- coding: utf-8 -*-
"""
Stage 4 — TTS narration audio generation for manga drama scenes.

Generates one narration file per scene using local GPT-SoVITS,
with character-matched voice selection.

Usage:
  python scripts/manga_tts_gen.py --char-id 53
  python scripts/manga_tts_gen.py --char-id 53 --episode 1
"""

import sys, os, asyncio, json, argparse
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.platform == "win32":
    import ctypes; ctypes.windll.kernel32.SetConsoleOutputCP(65001)

BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from pathlib import Path
from models.database import SessionLocal, Character
from services.tts_service import gptsovits_available, _pick_sovits_ref, _stream_sovits, _clean_for_tts

OUTPUT_BASE = Path("uploads/manga")


async def _synthesize_to_file(text: str, tags: str, output_path: str) -> str:
    """Synthesize text to audio file using local GPT-SoVITS only."""
    if not await gptsovits_available():
        raise RuntimeError("Local GPT-SoVITS is not running on http://127.0.0.1:9880")

    cleaned = _clean_for_tts(text)
    ref_audio = _pick_sovits_ref(tags)
    chunks = []
    async for chunk in _stream_sovits(cleaned, ref_audio):
        chunks.append(chunk)

    if not chunks:
        raise RuntimeError(f"No audio generated for: {text[:30]}...")

    audio_data = b"".join(chunks)
    with open(output_path, "wb") as f:
        f.write(audio_data)

    return output_path


async def generate_narrations(char_id: int, episode: int = 1) -> list[str]:
    """Generate narration audio for all scenes in an episode."""
    script_path = OUTPUT_BASE / str(char_id) / f"script_ep{episode}.json"
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")

    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    db = SessionLocal()
    try:
        char = db.query(Character).filter(Character.id == char_id).first()
        if not char:
            raise ValueError(f"Character {char_id} not found")

        char_tags = char.tags or ""
        print(f"[TTS] Character: {char.name}, Engine: local GPT-SoVITS")
    finally:
        db.close()

    scenes = script["scenes"]
    out_dir = OUTPUT_BASE / str(char_id)
    audio_paths = []

    for scene in scenes:
        sid = scene["id"]
        out_path = out_dir / f"narration_ep{episode}_s{sid}.wav"

        if out_path.exists():
            print(f"  Scene {sid}: audio exists, skipping")
            audio_paths.append(str(out_path))
            continue

        narration = scene.get("narration", "")
        dialogue = scene.get("dialogue", "")
        text = dialogue if dialogue else narration
        if not text:
            print(f"  Scene {sid}: no narration text, skipping")
            audio_paths.append("")
            continue

        print(f"  Scene {sid}: synthesizing '{text[:30]}...'")
        try:
            await _synthesize_to_file(text, char_tags, str(out_path))
            size = out_path.stat().st_size
            print(f"  Scene {sid}: saved → {out_path} ({size} bytes)")
            audio_paths.append(str(out_path))
        except Exception as e:
            print(f"  Scene {sid}: TTS FAILED — {e}")
            audio_paths.append("")

    return audio_paths


async def main():
    parser = argparse.ArgumentParser(description="Generate manga drama narration audio")
    parser.add_argument("--char-id", type=int, required=True)
    parser.add_argument("--episode", type=int, default=1)
    args = parser.parse_args()

    paths = await generate_narrations(args.char_id, args.episode)
    ok = sum(1 for p in paths if p)
    print(f"\n[TTS] Generated {ok} / {len(paths)} audio files")


if __name__ == "__main__":
    asyncio.run(main())
