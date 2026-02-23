"""
One-time migration: add backstory and ref_images columns to characters table.
Safe to run multiple times (skips if column already exists).

Usage:
  cd synclub-local/backend
  python ../scripts/migrate_add_ref_images.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", "synclub.db")

MIGRATIONS = [
    ("backstory",   "ALTER TABLE characters ADD COLUMN backstory TEXT DEFAULT ''"),
    ("ref_images",  "ALTER TABLE characters ADD COLUMN ref_images TEXT DEFAULT ''"),
    ("sort_weight", "ALTER TABLE characters ADD COLUMN sort_weight INTEGER DEFAULT 0"),
]


def column_exists(conn: sqlite3.Connection, table: str, col: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == col for row in cur.fetchall())


def main():
    print(f"DB: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    for col, sql in MIGRATIONS:
        if column_exists(conn, "characters", col):
            print(f"  SKIP: column '{col}' already exists")
        else:
            conn.execute(sql)
            conn.commit()
            print(f"  OK:   added column '{col}'")
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    main()
