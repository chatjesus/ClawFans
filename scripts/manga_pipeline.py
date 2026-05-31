# -*- coding: utf-8 -*-
"""
Manga Drama Pipeline — End-to-end orchestrator.

Runs all 5 stages sequentially for a given character:
  1. Script generation (LLM)
  2. Key frame generation (ComfyUI)
  3. Video clip generation (Wan 2.1 I2V local)
  4. Narration audio (local GPT-SoVITS)
  5. Assembly (ffmpeg)

Usage:
  python scripts/manga_pipeline.py --char-id 53
  python scripts/manga_pipeline.py --char-id 53 --episode 2
  python scripts/manga_pipeline.py --batch 53,55,61,64,109
"""

import sys, os, asyncio, json, argparse, time
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.platform == "win32":
    import ctypes; ctypes.windll.kernel32.SetConsoleOutputCP(65001)

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(SCRIPT_DIR, "..", "backend")
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from manga_script_gen import generate_script
from manga_frame_gen import generate_frames
from manga_video_gen import generate_clips
from manga_tts_gen import generate_narrations
from manga_assemble import assemble_episode


# ── Default characters for first batch (from plan) ──────────────────────────
DEFAULT_CHARS = [
    53,   # 苏雨柔 — 御姐职场
    54,   # 沈知意 — 冷艳律师
    56,   # 乔夏   — 反差萌博主
    57,   # 余灯   — 内向图书馆员
    210,  # 安律师 — 职场严肃/下班反差
]

# Some databases use shifted IDs for the same characters.
# If a planned ID doesn't exist, we automatically try a known alias.
CHAR_ID_ALIASES = {
    54: 55,
    56: 61,
    57: 64,
}


def _resolve_char_id(char_id: int) -> int:
    """Resolve planned character ID to an existing DB ID (with alias fallback)."""
    from models.database import SessionLocal, Character
    db = SessionLocal()
    try:
        if db.query(Character).filter(Character.id == char_id).first():
            return char_id
        alias = CHAR_ID_ALIASES.get(char_id)
        if alias and db.query(Character).filter(Character.id == alias).first():
            print(f"[Batch] Character ID {char_id} not found, using alias {alias}")
            return alias
        return char_id
    finally:
        db.close()


async def run_pipeline(char_id: int, episode: int = 1, engine: str = "wan",
                       skip_video: bool = False, frame_provider: str = "comfyui") -> str:
    """Run the full manga drama pipeline for one character + episode."""
    total_start = time.time()

    resolved_id = _resolve_char_id(char_id)

    print(f"\n{'='*60}")
    print(f" MANGA PIPELINE: Character {char_id}, Episode {episode}")
    if resolved_id != char_id:
        print(f" Resolved ID: {resolved_id}")
    print(f" Engine: {engine}")
    print(f"{'='*60}\n")

    # Stage 1: Script
    print("[1/5] Generating script...")
    t0 = time.time()
    script = await generate_script(resolved_id, episode)
    n_scenes = len(script.get("scenes", []))
    print(f"  → {n_scenes} scenes in {time.time()-t0:.1f}s\n")

    # Stage 2: Key Frames
    print("[2/5] Generating key frames...")
    t0 = time.time()
    frames = await generate_frames(resolved_id, episode, provider=frame_provider)
    ok_frames = sum(1 for f in frames if f)
    print(f"  → {ok_frames}/{len(frames)} frames in {time.time()-t0:.1f}s\n")

    # Stage 3: Video Clips
    if not skip_video:
        print(f"[3/5] Generating video clips ({engine})...")
        t0 = time.time()
        clips = await generate_clips(resolved_id, episode, engine)
        ok_clips = sum(1 for c in clips if c)
        print(f"  → {ok_clips}/{len(clips)} clips in {time.time()-t0:.1f}s\n")
    else:
        print("[3/5] Skipping video generation (--skip-video)\n")

    # Stage 4: TTS Narration
    print("[4/5] Generating narration audio...")
    t0 = time.time()
    audios = await generate_narrations(resolved_id, episode)
    ok_audio = sum(1 for a in audios if a)
    print(f"  → {ok_audio}/{len(audios)} audio files in {time.time()-t0:.1f}s\n")

    # Stage 5: Assembly
    if not skip_video:
        print("[5/5] Assembling final episode...")
        t0 = time.time()
        output = assemble_episode(resolved_id, episode)
        print(f"  → {output} in {time.time()-t0:.1f}s\n")
    else:
        output = "(skipped — no video clips)"
        print("[5/5] Skipping assembly (no video clips)\n")

    total = time.time() - total_start
    print(f"{'='*60}")
    print(f" DONE: {output}")
    print(f" Total time: {total:.1f}s ({total/60:.1f} min)")
    print(f"{'='*60}\n")

    return output


async def main():

    parser = argparse.ArgumentParser(description="Manga Drama Pipeline")
    parser.add_argument("--char-id", type=int, help="Single character ID")
    parser.add_argument("--episode", type=int, default=1)
    parser.add_argument("--engine", choices=["wan"], default="wan")
    parser.add_argument("--batch", type=str, help="Comma-separated character IDs")
    parser.add_argument("--frame-provider", choices=["comfyui"], default="comfyui")
    parser.add_argument("--skip-video", action="store_true",
                        help="Skip video gen (test script+frames+tts only)")
    args = parser.parse_args()

    if args.batch:
        char_ids = [int(x.strip()) for x in args.batch.split(",")]
    elif args.char_id:
        char_ids = [args.char_id]
    else:
        char_ids = DEFAULT_CHARS

    results = {}
    for cid in char_ids:
        try:
            output = await run_pipeline(
                cid,
                args.episode,
                args.engine,
                args.skip_video,
                frame_provider=args.frame_provider,
            )
            results[cid] = output
        except Exception as e:
            print(f"\n[ERROR] Character {cid} failed: {e}\n")
            results[cid] = f"FAILED: {e}"

    print("\n" + "="*60)
    print(" BATCH RESULTS")
    print("="*60)
    for cid, result in results.items():
        status = "OK" if "FAILED" not in str(result) else "FAIL"
        print(f"  [{status}] Character {cid}: {result}")


if __name__ == "__main__":
    asyncio.run(main())
