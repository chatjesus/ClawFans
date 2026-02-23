"""
fix_open_thread.py — 从数据库 greeting 中清除 OPEN THREAD 标签
策略：
  - "OPEN THREAD：xxx"  → "xxx"  (保留实际问题)
  - "**OPEN THREAD** ——xxx" → "xxx" (保留实际内容)
  - "——OPEN THREAD" / "*OPEN THREAD*" / "OPEN THREAD" → 删除
"""
import sys, os, re, json, time
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from models.database import SessionLocal, Character

LOG_PATH = "debug-90e70b.log"

OPEN_THREAD_RE = re.compile(
    r'[\*\-—\s]*'           # optional leading *, -, —, whitespace
    r'OPEN\s+THREAD'        # the label itself
    r'[\*]*'                # optional trailing *
    r'(?:[：:]\s*)?'         # optional colon
    r'(?:——\s*)?'           # optional em-dash separator
    r'(?P<content>.*)',     # optional actual content after the label
    re.IGNORECASE | re.DOTALL,
)

def strip_open_thread(text: str) -> str:
    if not text:
        return text
    # Find the OPEN THREAD marker (always appears near the end)
    m = OPEN_THREAD_RE.search(text)
    if not m:
        return text

    before = text[:m.start()].rstrip()
    content = (m.group('content') or '').strip()

    # If there's meaningful content after the label, keep it
    if content and len(content) > 3:
        return before + '  ' + content if before else content
    else:
        return before


db = SessionLocal()
chars = db.query(Character).all()

fixed = []
for c in chars:
    g = c.greeting or ""
    if "OPEN THREAD" in g or "open thread" in g.lower():
        cleaned = strip_open_thread(g)
        print(f"\nID={c.id} {c.name}")
        print(f"  BEFORE tail: ...{g[-120:]!r}")
        print(f"  AFTER  tail: ...{cleaned[-120:]!r}")
        c.greeting = cleaned
        fixed.append({"id": c.id, "name": c.name})

db.commit()
db.close()

print(f"\nFixed {len(fixed)} greetings.")

with open(LOG_PATH, "a", encoding="utf-8") as f:
    f.write(json.dumps({
        "sessionId": "90e70b",
        "runId": "post-fix",
        "hypothesisId": "A-B",
        "location": "fix_open_thread.py",
        "message": "open_thread_cleaned",
        "data": {"fixed_count": len(fixed), "ids": [x["id"] for x in fixed]},
        "timestamp": int(time.time() * 1000),
    }) + "\n")
