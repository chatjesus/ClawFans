import requests, random

API = "http://localhost:8000/api/characters"
chars = requests.get(API + "/", timeout=10).json()
for c in chars:
    if c["id"] > 8:
        mc = random.randint(50, 500)
        sc = random.randint(5, 80)
        cid = c["id"]
        r = requests.put(f"{API}/{cid}", json={"message_count": mc, "star_count": sc}, timeout=5)
        print(f"  {cid:>3d} | {c['name']:<15s} | msgs={mc}, stars={sc} | {r.status_code}")
print("Done")
