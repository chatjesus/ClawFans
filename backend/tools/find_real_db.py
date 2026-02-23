import sqlite3, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

for dbname in ['clawfans.db', 'synclub.db']:
    path = os.path.abspath(dbname)
    if os.path.exists(path):
        conn = sqlite3.connect(path)
        tables = [t[0] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if 'characters' in tables:
            cnt = conn.execute("SELECT COUNT(*) FROM characters").fetchone()[0]
            print(f"{path} ({os.path.getsize(path)//1024}KB) → {cnt} characters")
        conn.close()
    else:
        print(f"{dbname}: NOT FOUND")

# Check which DB the SQLAlchemy engine connects to
from models.database import engine, SessionLocal, Character
from sqlalchemy import text
with engine.connect() as conn:
    cnt = conn.execute(text("SELECT COUNT(*) FROM characters")).fetchone()[0]
    print(f"\nSQLAlchemy engine ({engine.url}) → {cnt} characters")
    db = SessionLocal()
    sample = db.query(Character).order_by(Character.id.desc()).limit(3).all()
    print(f"Latest 3: {[(c.id, c.name) for c in sample]}")
    db.close()
