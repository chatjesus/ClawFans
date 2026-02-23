import urllib.request
import json

# Test Ollama directly
url = "http://127.0.0.1:11434/api/chat"
payload = json.dumps({
    "model": "qwen2.5:7b",
    "messages": [{"role": "user", "content": "Say hello in 5 words."}],
    "stream": True,
    "options": {
        "temperature": 0.7,
        "num_predict": 100,
        "num_ctx": 8192
    }
}).encode()

req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
try:
    resp = urllib.request.urlopen(req, timeout=60)
    print("Ollama STATUS:", resp.status)
    total = ""
    for line in resp:
        line = line.decode().strip()
        if line:
            data = json.loads(line)
            if data.get("done"):
                print(f"\nDONE - prompt_eval_count: {data.get('prompt_eval_count', '?')}, eval_count: {data.get('eval_count', '?')}")
                break
            content = data.get("message", {}).get("content", "")
            total += content
            print(content, end="", flush=True)
    print(f"\nTotal chars: {len(total)}")
except Exception as e:
    print("ERROR:", type(e).__name__, str(e)[:300])
