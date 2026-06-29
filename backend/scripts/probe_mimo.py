"""
MiMo TTS diagnostic matrix (NOT a test) — localizes a 401.

Reads MIMO_API_KEY from backend/.env and probes:
  1. GET  /v1/models      with api-key            -> is the KEY valid at all?
  2. POST /v1/chat (TTS)  with api-key            -> the documented call
  3. POST /v1/chat (TTS)  with Authorization Bearer -> alt auth scheme
On success, decodes + writes the wav. ASCII-only output (GBK terminal safe).

Run:  backend\\venv\\Scripts\\python.exe scripts\\probe_mimo.py
"""
import asyncio
import base64
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ENV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
for line in open(ENV, encoding="utf-8"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()   # override, don't setdefault

import httpx

KEY = os.environ.get("MIMO_API_KEY", "")
BASE = os.environ.get("MIMO_BASE_URL", "https://api.xiaomimimo.com").rstrip("/")
MODEL = os.environ.get("MIMO_TTS_MODEL", "mimo-v2.5-tts")
VOICE = os.environ.get("MIMO_VOICE", "mimo_default")
TEXT = "ni hao, deng ni hao jiu le."  # ascii text avoids any encoding doubt

TTS_BODY = {
    "model": MODEL,
    "messages": [{"role": "assistant", "content": TEXT}],
    "audio": {"format": "wav", "voice": VOICE},
}


def show(tag, resp):
    print(f"[{tag}] HTTP {resp.status_code}  ct={resp.headers.get('content-type','')[:40]}")
    body = resp.text
    print(f"       {body[:300].strip()}")
    return resp


async def main():
    print(f"key  : {KEY[:6]}...{KEY[-4:]}  len={len(KEY)}  hasWhitespace={any(c.isspace() for c in KEY)}")
    print(f"base : {BASE}   model/voice: {MODEL}/{VOICE}\n")
    if not KEY:
        print("NO KEY"); return

    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as c:
        # 1. key liveness
        try:
            show("models  api-key   ", await c.get(f"{BASE}/v1/models", headers={"api-key": KEY}))
        except Exception as e:
            print(f"[models] ERR {type(e).__name__}: {e}")

        # 2. documented TTS call
        r = None
        try:
            r = show("tts     api-key   ", await c.post(
                f"{BASE}/v1/chat/completions",
                headers={"api-key": KEY, "Content-Type": "application/json"}, json=TTS_BODY))
        except Exception as e:
            print(f"[tts api-key] ERR {type(e).__name__}: {e}")

        # 3. Bearer fallback
        try:
            show("tts     Bearer    ", await c.post(
                f"{BASE}/v1/chat/completions",
                headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}, json=TTS_BODY))
        except Exception as e:
            print(f"[tts bearer] ERR {type(e).__name__}: {e}")

    # decode audio if the documented call worked
    if r is not None and r.status_code == 200 and "json" in r.headers.get("content-type", ""):
        b64 = (r.json().get("choices", [{}])[0].get("message", {}).get("audio", {}).get("data"))
        if b64:
            raw = base64.b64decode(b64)
            out = os.path.join(os.path.dirname(__file__), "mimo_probe.wav")
            open(out, "wb").write(raw)
            print(f"\nOK decoded {len(raw)} bytes header={raw[:4]!r} -> {out}")
        else:
            print("\nWARN 200 but no audio.data (moderated or shape differs)")


if __name__ == "__main__":
    asyncio.run(main())
