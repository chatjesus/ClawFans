"""
dedup_chars.py — 去掉批量创建产生的重复角色
策略：同名角色保留「有真实头像文件」的那个（优先最高 ID），
      没有头像的保留最高 ID，其余全部删除。
"""
import sys, os, shutil
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path
from collections import defaultdict
from models.database import SessionLocal, Character

FRONTEND_PUB = Path(__file__).parent.parent / "frontend" / "public"
UPLOADS = Path(__file__).parent / "uploads"

db = SessionLocal()

# 只处理 sort_weight >= 100 的新角色
new_chars = db.query(Character).filter(Character.sort_weight >= 100).order_by(Character.id).all()
print(f"New chars (weight>=100): {len(new_chars)}")

# 按名字分组
by_name = defaultdict(list)
for c in new_chars:
    by_name[c.name].append(c)

keep_ids = set()
delete_ids = set()

for name, group in by_name.items():
    # 优先保留有真实头像文件的
    def has_real_avatar(c):
        if not c.avatar_url or c.avatar_url == "/avatars/default.png":
            return False
        fn = c.avatar_url.lstrip("/")
        return (FRONTEND_PUB / fn).exists()

    with_avatar = [c for c in group if has_real_avatar(c)]
    without_avatar = [c for c in group if not has_real_avatar(c)]

    if with_avatar:
        # Keep the highest-ID one with a real avatar
        keeper = max(with_avatar, key=lambda c: c.id)
    else:
        # All have default; keep the highest ID (latest, best prompts)
        keeper = max(group, key=lambda c: c.id)

    keep_ids.add(keeper.id)
    for c in group:
        if c.id != keeper.id:
            delete_ids.add(c.id)

print(f"\nKeeping {len(keep_ids)} new characters, deleting {len(delete_ids)} duplicates")

# Preview first
to_delete = db.query(Character).filter(Character.id.in_(delete_ids)).order_by(Character.id).all()
print(f"\nWill DELETE these {len(to_delete)} records:")
for c in to_delete[:20]:
    print(f"  ID={c.id:3d} {c.name:<22} avatar={c.avatar_url}")
if len(to_delete) > 20:
    print(f"  ... and {len(to_delete)-20} more")

print(f"\nWill KEEP:")
to_keep = db.query(Character).filter(Character.id.in_(keep_ids)).order_by(Character.id).all()
for c in to_keep:
    fn = (c.avatar_url or "").lstrip("/")
    has_file = (FRONTEND_PUB / fn).exists() if fn and fn != "avatars/default.png" else False
    print(f"  ID={c.id:3d} {c.name:<22} avatar_ok={has_file}")

ans = input("\nProceed with deletion? [y/N] ")
if ans.lower() != "y":
    print("Aborted.")
    db.close()
    sys.exit(0)

# Delete orphaned uploads/refs and uploads/scenes for deleted IDs
deleted_count = 0
for c in to_delete:
    # Clean up uploads
    for subdir in ["refs", "scenes"]:
        d = UPLOADS / subdir / str(c.id)
        if d.exists():
            shutil.rmtree(str(d))
    # Clean up avatar file if it's not shared
    if c.avatar_url and c.avatar_url != "/avatars/default.png":
        fn = c.avatar_url.lstrip("/")
        fpath = FRONTEND_PUB / fn
        if fpath.exists():
            fpath.unlink()
    db.delete(c)
    deleted_count += 1

db.commit()
print(f"\nDeleted {deleted_count} duplicate characters.")

# Show remaining new chars without avatar
remaining = db.query(Character).filter(Character.sort_weight >= 100).order_by(Character.id).all()
no_avatar = [c for c in remaining if not c.avatar_url or c.avatar_url == "/avatars/default.png"
             or not (FRONTEND_PUB / c.avatar_url.lstrip("/")).exists()]
print(f"\nRemaining new chars: {len(remaining)}")
print(f"Still missing avatars: {len(no_avatar)}")
for c in no_avatar:
    print(f"  ID={c.id:3d} {c.name}")

db.close()
print("\nDone. Run 'python scripts/regen_images.py --new' to generate missing avatars.")
