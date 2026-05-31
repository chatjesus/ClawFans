import sqlite3, sys, os
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "..", "backend", "synclub.db"))
cur = conn.cursor()

cur.execute("PRAGMA table_info(characters)")
cols = [row[1] for row in cur.fetchall()]
print("Existing columns:", cols)

if "voice_id" not in cols:
    cur.execute("ALTER TABLE characters ADD COLUMN voice_id VARCHAR(100) DEFAULT ''")
    print("Added: voice_id")
else:
    print("voice_id already exists")

conn.commit()
conn.close()
print("Migration complete")
