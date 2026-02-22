import requests
chars = requests.get("http://localhost:8000/api/characters/", timeout=10).json()
print(f"Total: {len(chars)} characters\n")
for c in chars:
    print(f"  {c['id']:>3d} | {c['name']:<20s} | {c['category']:<12s} | msgs={c['message_count']}, stars={c['star_count']}")
