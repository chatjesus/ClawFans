import sys, os, sqlite3
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from models.database import DATABASE_URL
print("DATABASE_URL:", DATABASE_URL)

backend_dir = os.path.join(os.path.dirname(__file__), "..", "backend")
for dbf in ["synclub.db", "clawfans.db"]:
    full_path = os.path.join(backend_dir, dbf)
    if os.path.exists(full_path):
        conn = sqlite3.connect(full_path)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(characters)")
        cols = [row[1] for row in cur.fetchall()]
        cur.execute("SELECT COUNT(*) FROM characters")
        cnt = cur.fetchone()[0]
        has_voice = "voice_id" in cols
        print(f"{dbf}: {cnt} characters, has voice_id={has_voice}, columns={cols[-5:]}")
        conn.close()
    else:
        print(f"{dbf}: NOT FOUND")
