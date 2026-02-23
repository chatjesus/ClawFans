import sys, os
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from models.database import SessionLocal, Character

db = SessionLocal()
old_chars = db.query(Character).filter(Character.id <= 48).all()
print(f"Old chars (id<=48): {len(old_chars)}")
for c in old_chars:
    old_w = c.sort_weight
    c.sort_weight = 50  # appear between new(100) and nothing
    print(f"  ID={c.id:3d} {c.name:<22} {old_w} -> 50")
db.commit()
db.close()
print("Done. Old chars now have sort_weight=50.")
