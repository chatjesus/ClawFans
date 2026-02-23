"""Clean up orphaned user messages (no following assistant reply) in conv 14 and 15."""
import sys
sys.path.insert(0, "/opt/clawfans/backend")

# Use virtualenv
import subprocess, os

result = subprocess.run(
    ["python3", "-c", """
import sys
sys.path.insert(0, "/opt/clawfans/backend")
from models.database import SessionLocal, Message

db = SessionLocal()

for conv_id in [14, 15]:
    msgs = db.query(Message).filter(Message.conversation_id == conv_id).order_by(Message.created_at).all()
    to_delete = []
    for i, msg in enumerate(msgs):
        if msg.role == "user":
            has_reply = (i + 1 < len(msgs) and msgs[i+1].role == "assistant")
            if not has_reply:
                to_delete.append(msg.id)
    
    print(f"Conv {conv_id}: deleting {len(to_delete)} orphaned user messages: {to_delete}")
    for mid in to_delete:
        m = db.query(Message).filter(Message.id == mid).first()
        if m:
            db.delete(m)
    db.commit()

print("Done!")
db.close()
"""],
    capture_output=True, text=True,
    cwd="/opt/clawfans/backend",
    env={**os.environ, "PYTHONPATH": "/opt/clawfans/backend"}
)

# Try with venv
result2 = subprocess.run(
    ["/opt/clawfans/backend/venv/bin/python3", "-c", """
import sys
sys.path.insert(0, "/opt/clawfans/backend")
from models.database import SessionLocal, Message

db = SessionLocal()

for conv_id in [14, 15]:
    msgs = db.query(Message).filter(Message.conversation_id == conv_id).order_by(Message.created_at).all()
    to_delete = []
    for i, msg in enumerate(msgs):
        if msg.role == "user":
            has_reply = (i + 1 < len(msgs) and msgs[i+1].role == "assistant")
            if not has_reply:
                to_delete.append(msg.id)
    
    print(f"Conv {conv_id}: deleting {len(to_delete)} orphaned user messages: {to_delete}")
    for mid in to_delete:
        m = db.query(Message).filter(Message.id == mid).first()
        if m:
            db.delete(m)
    db.commit()

print("Done!")
db.close()
"""],
    capture_output=True, text=True,
    cwd="/opt/clawfans/backend"
)
print(result2.stdout)
if result2.stderr:
    print("STDERR:", result2.stderr[:500])
