# Backend Tools / Maintenance Scripts

These scripts are development and maintenance utilities — **not part of the application**.
They are safe to run locally for debugging or one-time data fixes.

| Script | Purpose |
|--------|---------|
| `check_db.py` | Inspect database tables and row counts |
| `find_real_db.py` | Locate the active SQLite database file |
| `check_chars_status.py` | Show character creation / image status |
| `check_img_prompts.py` | Review AI image generation prompts |
| `check_open_thread.py` | Inspect open conversation threads |
| `fix_open_thread.py` | Fix stuck/open conversation threads |
| `fix_old_char_weights.py` | Backfill sort_weight for legacy characters |
| `dedup_chars.py` | Remove duplicate character entries |

## Usage

All scripts must be run from the `backend/` directory:

```bash
cd backend
python tools/check_db.py
```
