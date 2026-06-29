"""
MiMo Token Plan (tp- key) region prober — finds the right regional base URL.

tp- keys require a region-specific Token Plan host, NOT api.xiaomimimo.com.
Tries CN / SGP / AMS, prints status, decodes wav on the one that works.

Run:  backend\\venv\\Scripts\\python.exe scripts\\probe_mimo_tp.py
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
        os.environ[k.strip()] = v.strip()

import httpx

KEY = os.environ["MIMO_API_KEY"]
MODEL = os.environ.get("MIMO_TTS_MODEL", "mimo-v2.5-tts")
VOICE = os.environ.get("MIMO_VOICE", "mimo_default")
TEXT = "ni hao ya, wo deng ni hao jiu le."

# hosts WITHOUT /v1 — our adapter appends /v1/chat/completions
HOSTS = {
    "CN ": "https://token-plan-cn.xiaomimimo.com",
    "SGP": "https://token-plan-sgp.xiaomimimo.com",
    "AMS": "https://token-plan-ams.xiaomimimo.com",
}
BODY = {"model": MODEL, "messages": [{"role": "assistant", "content": TEXT}],
        "audio": {"format": "wav", "voice": VOICE}}


async def main():
    print(f"key {KEY[:6]}...{KEY[-4:]}  model {MODEL}  voice {VOICE}\n")
    winner = None
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as c:
        for tag, host in HOSTS.items():
            url = f"{host}/v1/chat/completions"
            try:
                r = await c.post(url, headers={"api-key": KEY, "Content-Type": "application/json"}, json=BODY)
            except Exception as e:
                print(f"[{tag}] {host:45} ERR {type(e).__name__}: {str(e)[:80]}")
                continue
            note = r.text[:120].replace("\n", " ")
            print(f"[{tag}] {host:45} HTTP {r.status_code}  {note}")
            if r.status_code == 200 and winner is None:
                winner = (host, r)

    if winner:
        host, r = winner
        print(f"\n>>> WORKING REGION: {host}")
        try:
            b64 = r.json()["choices"][0]["message"]["audio"]["data"]
            raw = base64.b64decode(b64)
            out = os.path.join(os.path.dirname(__file__), "mimo_probe.wav")
            open(out, "wb").write(raw)
            print(f">>> decoded {len(raw)} bytes header={raw[:4]!r} -> {out}")
        except Exception as e:
            print(f">>> 200 but could not decode audio: {e}\n    body: {r.text[:300]}")
        print(f"\nSET IN .env:  MIMO_BASE_URL={host}")
    else:
        print("\nNo region returned 200. See statuses above (401=key invalid for that region/plan).")


if __name__ == "__main__":
    asyncio.run(main())
