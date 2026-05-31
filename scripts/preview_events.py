import sys, os, json
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from models.database import SessionLocal, CharacterEvent, Character

db = SessionLocal()
events = (
    db.query(CharacterEvent)
    .join(Character, CharacterEvent.char_id == Character.id)
    .filter(CharacterEvent.char_id == 45)
    .order_by(CharacterEvent.sort_order)
    .all()
)
char = db.query(Character).filter(Character.id == 45).first()
print(f"\n角色: {char.name if char else '?'} — {len(events)} 个剧情事件\n")
for e in events:
    print("=" * 60)
    print(f"  标题: {e.title}")
    print(f"  类型: {e.event_type}  触发: {e.trigger_json}")
    print(f"  描述: {(e.description or '')[:100]}...")
    choices = json.loads(e.choices_json or "[]")
    for i, c in enumerate(choices):
        delta = c.get("intimacy_delta", 0)
        sign = "+" if delta >= 0 else ""
        print(f"  选{chr(65+i)}: {c.get('text','')}  ({sign}{delta})")
    print()
db.close()
