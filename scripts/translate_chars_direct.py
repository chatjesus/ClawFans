"""
Batch translate character content directly via SQLite + Ollama.
No HTTP API calls - runs standalone from the backend folder.

Usage (run from project root):
  cd synclub-local\backend
  python -u ..\scripts\translate_chars_direct.py
  python -u ..\scripts\translate_chars_direct.py --locale ja ko
  python -u ..\scripts\translate_chars_direct.py --locale ja --char-id 38
"""
import sys, os, argparse, json, time, re, requests
sys.stdout.reconfigure(encoding="utf-8")

# Must run from backend folder for models to resolve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/../backend")
from models.database import SessionLocal, Character, CharacterTranslation
from sqlalchemy.exc import IntegrityError

OLLAMA_URL  = "http://localhost:11434/api/generate"
MODEL       = "qwen2.5:14b"
ALL_LOCALES = ["en", "ja", "ko", "es", "fr", "pt", "de"]
LOCALE_NAMES = {
    "en": "English", "ja": "Japanese", "ko": "Korean",
    "es": "Spanish", "fr": "French", "pt": "Portuguese", "de": "German",
}
SP_MAX = 500  # chars of system_prompt to translate


def call_qwen(prompt: str) -> str | None:
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.25, "num_predict": 900, "num_ctx": 3072},
    }
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=120)
        r.raise_for_status()
        return r.json().get("response", "")
    except Exception as e:
        print(f"[OLLAMA ERR] {e}")
        return None


def parse_json(raw: str) -> dict | None:
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return None


def translate_char(char: Character, locale: str) -> dict | None:
    lang = LOCALE_NAMES[locale]
    sp_src = (char.system_prompt or "")[:SP_MAX]

    prompt = (
        f'You are a professional translator for an adult AI character roleplay app.\n'
        f'Translate the following Chinese text into {lang}.\n'
        f'Keep the tone, personality, and adult/NSFW nuance exactly.\n'
        f'Translate field values but preserve any structural keywords like "Personality:", "Background:", etc.\n'
        f'Output ONLY valid JSON with exactly these three keys.\n\n'
        f'Input:\n'
        f'description: {json.dumps(char.description or "", ensure_ascii=False)}\n'
        f'greeting: {json.dumps(char.greeting or "", ensure_ascii=False)}\n'
        f'system_prompt_head: {json.dumps(sp_src, ensure_ascii=False)}\n\n'
        f'Output:\n'
        f'{{"description":"...","greeting":"...","system_prompt_head":"..."}}'
    )

    raw = call_qwen(prompt)
    if not raw:
        return None
    data = parse_json(raw)
    if not data:
        print(f"  [PARSE FAIL] {raw[:60]}")
        return None
    return {
        "description":   data.get("description", ""),
        "greeting":      data.get("greeting", ""),
        "system_prompt": data.get("system_prompt_head", ""),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--locale", nargs="+", default=ALL_LOCALES)
    parser.add_argument("--char-id", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    locales = [l for l in args.locale if l in ALL_LOCALES]
    if not locales:
        print("No valid locales."); return

    db = SessionLocal()
    try:
        q = db.query(Character).filter(Character.is_public == True)
        if args.char_id:
            q = q.filter(Character.id == args.char_id)
        chars = q.order_by(Character.id).all()

        print(f"Characters: {len(chars)}  Locales: {locales}")
        print(f"Total tasks: {len(chars) * len(locales)}")
        print("=" * 60)

        done = skipped = failed = 0

        for char in chars:
            # Preload existing translations for this char
            existing = {
                t.locale for t in
                db.query(CharacterTranslation).filter(
                    CharacterTranslation.character_id == char.id
                ).all()
            }

            print(f"\n[{char.id}] {char.name}")
            for locale in locales:
                if locale in existing and not args.force:
                    print(f"  {locale}: [SKIP]")
                    skipped += 1
                    continue

                print(f"  {locale} ({LOCALE_NAMES[locale]}): ...", end="", flush=True)
                t0 = time.time()

                result = translate_char(char, locale)
                if not result:
                    print(" FAILED")
                    failed += 1
                    continue

                elapsed = time.time() - t0

                # Upsert
                tr = db.query(CharacterTranslation).filter(
                    CharacterTranslation.character_id == char.id,
                    CharacterTranslation.locale == locale,
                ).first()

                if tr:
                    tr.description   = result["description"]
                    tr.greeting      = result["greeting"]
                    tr.system_prompt = result["system_prompt"]
                else:
                    tr = CharacterTranslation(
                        character_id=char.id,
                        locale=locale,
                        description=result["description"],
                        greeting=result["greeting"],
                        system_prompt=result["system_prompt"],
                    )
                    db.add(tr)

                db.commit()
                preview = result["description"][:45].replace("\n", " ")
                print(f" OK ({elapsed:.1f}s) — {preview}...")
                done += 1

        print("\n" + "=" * 60)
        print(f"Done: {done}  Skipped: {skipped}  Failed: {failed}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
