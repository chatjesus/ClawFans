import urllib.request
import json

url = "http://127.0.0.1/api/characters/?category=Featured&limit=10"
req = urllib.request.Request(url)
resp = urllib.request.urlopen(req, timeout=10)
chars = json.loads(resp.read())
for c in chars[:8]:
    print(f"id={c['id']}: name={c['name']!r:15} avatar={c.get('avatar_url','')!r}")
