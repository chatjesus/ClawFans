import urllib.request
import json

url = "http://127.0.0.1:8000/api/chat/conversations/14/messages"
payload = json.dumps({"content": "hello"}).encode()
headers = {"Content-Type": "application/json"}

req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
try:
    resp = urllib.request.urlopen(req, timeout=120)
    print("STATUS:", resp.status)
    for line in resp:
        line = line.decode().strip()
        if line:
            print("LINE:", repr(line[:300]))
except Exception as e:
    print("ERROR:", type(e).__name__, str(e)[:200])
