import requests, random

API = "http://localhost:8000/api/characters"

# Delete duplicates (IDs 31+)
for cid in range(31, 53):
    r = requests.delete(f"{API}/{cid}", timeout=5)
    print(f"  DELETE {cid} -> {r.status_code}")

# Update stats for new characters (IDs 9-30)
for cid in range(9, 31):
    mc = random.randint(50, 500)
    sc = random.randint(5, 80)
    r = requests.put(f"{API}/{cid}", json={"message_count": mc, "star_count": sc}, timeout=5)
    print(f"  UPDATE {cid} msgs={mc} stars={sc} -> {r.status_code}")

print("\nDone. Verifying...")
chars = requests.get(API + "/", params={"limit": 100}, timeout=10).json()
print(f"Total characters: {len(chars)}")
