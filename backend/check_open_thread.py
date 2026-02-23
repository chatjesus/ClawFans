import sys, os, json, time
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from models.database import SessionLocal, Character

LOG_PATH = "debug-90e70b.log"

db = SessionLocal()
chars = db.query(Character).all()

infected = []
for c in chars:
    g = c.greeting or ""
    if "OPEN THREAD" in g or "open thread" in g.lower():
        infected.append({
            "id": c.id,
            "name": c.name,
            "greeting_tail": g[-150:].replace('\n', ' ')
        })

print(f"Total chars with 'OPEN THREAD' in greeting: {len(infected)}")
for item in infected[:10]:
    print(f"\n  ID={item['id']} {item['name']}:")
    print(f"  ...{item['greeting_tail']}")

db.close()

with open(LOG_PATH, "a", encoding="utf-8") as f:
    f.write(json.dumps({
        "sessionId": "90e70b",
        "runId": "initial",
        "hypothesisId": "A-B",
        "location": "check_open_thread.py",
        "message": "open_thread_audit",
        "data": {"infected_count": len(infected), "sample": infected[:5]},
        "timestamp": int(time.time() * 1000),
    }) + "\n")
print(f"\nLogged.")
