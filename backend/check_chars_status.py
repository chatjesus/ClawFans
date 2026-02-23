import sys, os
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from models.database import SessionLocal, Character
from pathlib import Path

db = SessionLocal()
chars = db.query(Character).order_by(Character.id).all()
print(f'Total characters: {len(chars)}')

avatar_dir = Path(__file__).parent.parent / 'frontend' / 'public' / 'avatars'
uploads_dir = Path(__file__).parent / 'uploads' / 'refs'

print('\n--- No avatar / broken avatar ---')
missing = []
for c in chars:
    if not c.avatar_url or c.avatar_url == '/avatars/default.png':
        missing.append(c)
        print(f'  ID={c.id:3d} {c.name:<20} avatar={c.avatar_url}')
    else:
        # check if file actually exists
        fn = c.avatar_url.lstrip('/')
        fpath = Path(__file__).parent.parent / 'frontend' / 'public' / fn
        if not fpath.exists():
            missing.append(c)
            print(f'  ID={c.id:3d} {c.name:<20} MISSING FILE: {fpath}')

print(f'\nTotal missing: {len(missing)}')

print('\n--- All characters (id, name, sort_weight, has_avatar) ---')
for c in chars:
    fn = (c.avatar_url or '').lstrip('/')
    fpath = Path(__file__).parent.parent / 'frontend' / 'public' / fn if fn else None
    has_file = fpath.exists() if fpath else False
    has_refs = (uploads_dir / str(c.id)).exists()
    print(f'  ID={c.id:3d} w={c.sort_weight:4d} {c.name:<22} avatar={str(c.avatar_url):<35} file={has_file} refs={has_refs}')

db.close()
