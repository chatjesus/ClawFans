"""
Update database URLs after migrating images to Cloudflare R2.

Changes made:
  1. ref_images JSON paths: /uploads/refs/... → R2 public URL
  2. avatar_url: characters whose avatar file is missing use their first
     char_0.png ref image as the avatar instead.

Usage:
  python scripts/update_db_urls.py --dry-run   # preview only
  python scripts/update_db_urls.py             # apply changes
"""
import sys, os, argparse, json, re
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

DB_PATH    = Path(__file__).parent.parent / "backend" / "clawfans.db"
PUBLIC_URL = "https://assets.tinyclaw.dev"


def to_r2(path: str) -> str:
    """Convert a local /uploads/... path to a full R2 URL."""
    if not path:
        return path
    if path.startswith(PUBLIC_URL):
        return path          # already R2
    if path.startswith("/uploads/"):
        return f"{PUBLIC_URL}{path}"
    if path.startswith("uploads/"):
        return f"{PUBLIC_URL}/{path}"
    return path


def avatar_is_missing(avatar_url: str) -> bool:
    """Return True for dynamic /avatars/char_XX_... URLs (files that no longer exist)."""
    if not avatar_url:
        return True
    return bool(re.match(r"^/avatars/char_\d+", avatar_url))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    cur.execute("SELECT id, avatar_url, ref_images FROM characters")
    rows = cur.fetchall()

    changed_avatar = 0
    changed_refs   = 0

    for row_id, avatar_url, ref_images_raw in rows:
        new_avatar = avatar_url
        new_refs   = ref_images_raw

        # ── Update ref_images (JSON array of paths) ───────────────────────
        if ref_images_raw:
            try:
                refs = json.loads(ref_images_raw)
                if isinstance(refs, list):
                    updated = [to_r2(p) for p in refs]
                    if updated != refs:
                        new_refs = json.dumps(updated, ensure_ascii=False)
                        changed_refs += 1
            except (json.JSONDecodeError, TypeError):
                pass   # not valid JSON, leave unchanged

        # ── Fix avatar_url for characters whose avatar file is missing ────
        if avatar_is_missing(avatar_url):
            # Try to use char_0.png from their ref images
            try:
                refs = json.loads(ref_images_raw) if ref_images_raw else []
                char_img = next((p for p in refs if "char_0" in p), None)
                if char_img:
                    new_avatar = to_r2(char_img)
                    changed_avatar += 1
            except Exception:
                pass

        if new_avatar != avatar_url or new_refs != ref_images_raw:
            if args.dry_run:
                if new_avatar != avatar_url:
                    print(f"  ID={row_id} avatar: {avatar_url!r} → {new_avatar!r}")
                if new_refs != ref_images_raw:
                    print(f"  ID={row_id} refs updated (first: {json.loads(new_refs)[0] if new_refs else '?'}...)")
            else:
                cur.execute(
                    "UPDATE characters SET avatar_url=?, ref_images=? WHERE id=?",
                    (new_avatar, new_refs, row_id),
                )

    if not args.dry_run:
        conn.commit()
        print(f"Updated {changed_avatar} avatar URLs and {changed_refs} ref_images rows.")
    else:
        print(f"\n[DRY RUN] Would update {changed_avatar} avatar URLs, {changed_refs} ref_images rows.")

    conn.close()


if __name__ == "__main__":
    main()
