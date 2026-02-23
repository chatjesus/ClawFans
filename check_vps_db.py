import sys
sys.path.insert(0, "/opt/clawfans/backend")
from models.database import SessionLocal, Message, Conversation

db = SessionLocal()

for conv_id in [14, 15]:
    msgs = db.query(Message).filter(Message.conversation_id == conv_id).order_by(Message.created_at).all()
    print(f"\n=== Conv {conv_id}: {len(msgs)} messages ===")
    for m in msgs[-10:]:  # last 10
        print(f"  [{m.role}] id={m.id} created={m.created_at.strftime('%H:%M:%S')}: {m.content[:50]!r}")
    
    # Count orphaned user messages (user msg without following assistant)
    orphaned = 0
    for i, m in enumerate(msgs):
        if m.role == "user":
            has_response = (i + 1 < len(msgs) and msgs[i+1].role == "assistant")
            if not has_response:
                orphaned += 1
    print(f"  Orphaned user messages (no response): {orphaned}")

db.close()
