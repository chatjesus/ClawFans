import urllib.request
import json

url = "http://127.0.0.1:8000/api/chat/conversations/14/messages"
payload = json.dumps({"content": "hi"}).encode()
headers = {"Content-Type": "application/json"}

req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
try:
    resp = urllib.request.urlopen(req, timeout=60)
    print("STATUS:", resp.status)
    for line in resp:
        line = line.decode().strip()
        if line:
            print(line[:200])
            break
except Exception as e:
    print("ERROR:", e)
