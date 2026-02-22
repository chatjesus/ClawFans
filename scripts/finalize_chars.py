"""Update avatar URLs and random stats for new characters (IDs 9-30)."""
import requests, random

API = "http://localhost:8000/api/characters"

avatar_map = {
    9: "yuki", 10: "ethan", 11: "lina", 12: "zero", 13: "sakura_mg",
    14: "raven", 15: "thorne", 16: "iris", 17: "xiaofan", 18: "mia_transfer",
    19: "detective_li", 20: "echo", 21: "time_k", 22: "nuannuan", 23: "kai",
    24: "npc_xiaomei", 25: "gl1tch", 26: "jiangci", 27: "susu", 28: "room404",
    29: "momo", 30: "pixel",
}

for db_id, file_id in avatar_map.items():
    mc = random.randint(80, 500)
    sc = random.randint(10, 80)
    r = requests.put(
        f"{API}/{db_id}",
        json={"avatar_url": f"/avatars/{file_id}.png", "message_count": mc, "star_count": sc},
        timeout=5,
    )
    print(f"  {db_id:>3d} | /avatars/{file_id}.png | msgs={mc} stars={sc} | {r.status_code}")

print("Done!")
