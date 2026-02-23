import urllib.request
import json

url = "http://127.0.0.1:8000/api/chat/conversations/14/messages"
payload = json.dumps({"content": "你好"}).encode()
headers = {"Content-Type": "application/json"}

req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
try:
    resp = urllib.request.urlopen(req, timeout=120)
    print("STATUS:", resp.status)
    chunks = 0
    text_chunks = 0
    for line in resp:
        line = line.decode().strip()
        if not line:
            continue
        chunks += 1
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                if "content" in data:
                    text_chunks += 1
                    if text_chunks == 1:
                        print("FIRST CONTENT CHUNK:", data["content"][:50])
                if data.get("done"):
                    print(f"DONE! Total chunks: {chunks}, text chunks: {text_chunks}")
                    break
                if "error" in data:
                    print("ERROR:", data["error"])
                    break
            except:
                pass
        if chunks > 200:
            print(f"Got {chunks} chunks so far (still streaming...)")
            break
except Exception as e:
    print("ERROR:", e)
