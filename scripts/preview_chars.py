import requests, sys
sys.stdout.reconfigure(encoding='utf-8')

ids_to_check = [38, 39, 41, 42, 43, 44]

for cid in ids_to_check:
    r = requests.get(f"http://localhost:8000/api/characters/{cid}")
    c = r.json()
    print(f"\n{'='*60}")
    print(f"ID {c['id']} | {c['name']} ({c['tags']})")
    print(f"简介: {c['description']}")
    # Find the body stats block
    sp = c.get('system_prompt', '')
    idx = sp.find('【角色档案】')
    if idx != -1:
        print(sp[idx-3:idx+300])
    else:
        print("[No body stats yet]")
