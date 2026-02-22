import requests, json
try:
    r = requests.get("http://localhost:8000/api/characters/38")
    data = r.json()
    print(json.dumps(data, indent=2, ensure_ascii=False))
except Exception as e:
    print(e)
