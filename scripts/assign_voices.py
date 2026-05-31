"""
Batch assign TTS voice_id to all characters based on their tags + description.
Run once after adding voice_id column, or re-run to update assignments.

Usage:
    python scripts/assign_voices.py [--dry-run] [--char-id N]
"""
import sys, os, argparse
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from models.database import SessionLocal, Character
from services.tts_service import pick_voice_for_character, VOICE_PROFILES

VOICE_DISPLAY = {vid: name for vid, (name, _, _) in VOICE_PROFILES.items()}


def assign_voice(char, dry_run=False):
    voice = pick_voice_for_character(
        tags=char.tags or "",
        description=char.description or "",
        name=char.name or "",
        voice_id="",  # force re-selection
    )
    display = VOICE_DISPLAY.get(voice, voice)
    print(f"  [{char.id:3d}] {char.name[:18]:18} → {display} ({voice})")
    if not dry_run:
        char.voice_id = voice
    return voice


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--char-id", type=int, default=0, help="Only update this character ID")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.char_id:
            chars = db.query(Character).filter(Character.id == args.char_id).all()
        else:
            chars = db.query(Character).order_by(Character.id).all()

        print(f"{'DRY RUN — ' if args.dry_run else ''}Assigning voices to {len(chars)} characters...\n")

        voice_counts: dict[str, int] = {}
        for char in chars:
            v = assign_voice(char, dry_run=args.dry_run)
            voice_counts[VOICE_DISPLAY.get(v, v)] = voice_counts.get(VOICE_DISPLAY.get(v, v), 0) + 1

        if not args.dry_run:
            db.commit()
            print(f"\n✓ Saved voice assignments for {len(chars)} characters")

        print("\nVoice distribution:")
        for voice, count in sorted(voice_counts.items(), key=lambda x: -x[1]):
            print(f"  {voice}: {count}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
