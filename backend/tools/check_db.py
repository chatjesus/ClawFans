import sqlite3, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

for dbname in ['synclub.db', 'clawfans.db']:
    conn = sqlite3.connect(dbname)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print(f"{dbname}: tables={[t[0] for t in tables]}")
    if any(t[0]=='characters' for t in tables):
        cnt = conn.execute("SELECT COUNT(*) FROM characters").fetchone()[0]
        print(f"  characters count: {cnt}")
    conn.close()
