import httpx, time

t0 = time.time()
r = httpx.post(
    "http://localhost:8000/api/voice/synthesize",
    json={"text": "你好呀，今天天气真好，想不想一起出去走走？", "character_id": 45},
    timeout=20,
)
t1 = time.time()
print(f"Status: {r.status_code}")
print(f"Time: {t1-t0:.1f}s")
print(f"Size: {len(r.content)} bytes")
print(f"Content-Type: {r.headers.get('content-type')}")

if r.status_code == 200:
    with open("test_api_tts.mp3", "wb") as f:
        f.write(r.content)
    print("Saved to test_api_tts.mp3")
else:
    print(f"Error: {r.text[:200]}")
