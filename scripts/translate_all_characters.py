"""
Batch translate all character content using local Qwen 2.5 14B.

Translates: description, greeting, system_prompt
Targets:    en, ja, ko, es, fr, pt, de  (zh is the source language)
Resume:     Already-translated entries are skipped automatically.

Usage:
  python -u scripts/translate_all_characters.py            # all locales
  python -u scripts/translate_all_characters.py --locale en ja   # specific
  python -u scripts/translate_all_characters.py --char-id 38     # one char
"""
import sys, argparse, json, time, requests
sys.stdout.reconfigure(encoding="utf-8")

API          = "http://localhost:8000/api/characters"
OLLAMA_URL   = "http://localhost:11434/api/generate"
MODEL        = "qwen2.5:14b"

# Priority order: English first (most impactful), then East Asian, then European
ALL_LOCALES = ["en", "ja", "ko", "es", "fr", "pt", "de"]

LOCALE_NAMES = {
    "en": "English", "ja": "Japanese", "ko": "Korean",
    "es": "Spanish", "fr": "French", "pt": "Portuguese", "de": "German",
}

# How much of system_prompt to translate (chars). Full prompts are very long.
# We translate the first ~600 chars (personality + scenario) and keep the rest.
SYSTEM_PROMPT_MAX = 600


# ── Ollama call ───────────────────────────────────────────────────────────────

def call_qwen(prompt: str, max_tokens: int = 1024) -> str | None:
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.3,   # low temp = faithful translation
            "num_predict": max_tokens,
            "num_ctx": 4096,
        },
    }
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=90)
        r.raise_for_status()
        return r.json().get("response", "")
    except Exception as e:
        print(f"    [OLLAMA ERROR] {e}")
        return None


def translate_fields(char: dict, locale: str) -> dict | None:
    """Ask Qwen to translate description, greeting, and system_prompt head."""
    lang = LOCALE_NAMES[locale]

    # Truncate system_prompt to keep it manageable
    sp_src = (char.get("system_prompt") or "")[:SYSTEM_PROMPT_MAX]

    prompt = f"""You are a professional translator for an adult AI character chat app.

Translate the following Chinese text into {lang}.
Keep the tone, style, and NSFW nuance exactly as in the original.
For system_prompt: keep the JSON-like field structure (Personality:, Appearance:, etc.) but translate the values.
Do NOT add explanations. Output ONLY valid JSON.

Input fields:
- description: {json.dumps(char.get('description', ''), ensure_ascii=False)}
- greeting: {json.dumps(char.get('greeting', ''), ensure_ascii=False)}
- system_prompt_head: {json.dumps(sp_src, ensure_ascii=False)}

Output format (strict JSON, no extra keys):
{{
  "description": "...",
  "greeting": "...",
  "system_prompt_head": "..."
}}"""

    raw = call_qwen(prompt)
    if not raw:
        return None

    try:
        data = json.loads(raw)
        return {
            "description":   data.get("description", ""),
            "greeting":      data.get("greeting", ""),
            "system_prompt": data.get("system_prompt_head", ""),
        }
    except json.JSONDecodeError:
        # Try to extract JSON substring
        import re
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
                return {
                    "description":   data.get("description", ""),
                    "greeting":      data.get("greeting", ""),
                    "system_prompt": data.get("system_prompt_head", ""),
                }
            except Exception:
                pass
        print(f"    [PARSE ERROR] {raw[:80]}...")
        return None


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--locale", nargs="+", default=ALL_LOCALES,
                        help="Locales to translate (default: all)")
    parser.add_argument("--char-id", type=int, default=None,
                        help="Translate a single character by ID")
    parser.add_argument("--force", action="store_true",
                        help="Re-translate even if already exists")
    args = parser.parse_args()

    locales = [l for l in args.locale if l in ALL_LOCALES]
    if not locales:
        print("No valid locales specified. Choose from:", ALL_LOCALES)
        return

    # Fetch all characters
    r = requests.get(f"{API}/")
    all_chars_cards = r.json()

    if args.char_id:
        all_chars_cards = [c for c in all_chars_cards if c["id"] == args.char_id]
        if not all_chars_cards:
            print(f"Character ID {args.char_id} not found.")
            return

    print(f"Characters to translate: {len(all_chars_cards)}")
    print(f"Target locales: {locales}")
    print(f"Total tasks: {len(all_chars_cards) * len(locales)}")
    print("=" * 60)

    done = 0
    skipped = 0
    failed = 0

    for card in all_chars_cards:
        cid = card["id"]
        # Fetch full character (includes system_prompt)
        full_r = requests.get(f"{API}/{cid}")
        char = full_r.json()

        # Fetch existing translations to know what's done
        tr_r = requests.get(f"{API}/{cid}/translations")
        existing = {t["locale"] for t in tr_r.json()} if tr_r.ok else set()

        print(f"\n[{cid}] {char['name']}")

        for locale in locales:
            if locale in existing and not args.force:
                print(f"  {locale}: [SKIP] already translated")
                skipped += 1
                continue

            print(f"  {locale} ({LOCALE_NAMES[locale]}): translating...", end="", flush=True)
            t_start = time.time()

            result = translate_fields(char, locale)

            if not result:
                print(f" FAILED")
                failed += 1
                continue

            elapsed = time.time() - t_start

            # Push to API
            payload = {
                "locale":        locale,
                "description":   result["description"],
                "greeting":      result["greeting"],
                "system_prompt": result["system_prompt"],
            }
            put_r = requests.put(f"{API}/{cid}/translations", json=payload)
            if put_r.ok:
                print(f" OK ({elapsed:.1f}s) — {result['description'][:40]}...")
                done += 1
            else:
                print(f" DB ERROR {put_r.status_code}")
                failed += 1

    print()
    print("=" * 60)
    print(f"Done: {done}  Skipped: {skipped}  Failed: {failed}")


if __name__ == "__main__":
    main()
