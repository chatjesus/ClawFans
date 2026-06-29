"""
Live MiMo voice probe (NOT a test) — confirm the 4 zh-CN presets each
synthesize distinct audio on the user's Token Plan key.

Run:  backend\\venv\\Scripts\\python.exe scripts\\probe_mimo_voices.py
"""
import asyncio
import contextlib
import hashlib
import os
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
for line in open(ENV, encoding="utf-8"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()

from services.mimo_tts import synthesize_mimo

# 冰糖 already verified in a prior run; Token Plan rate-limits (429) back-to-back
# calls, so we space them out and probe the remaining three.
VOICES = ["茉莉", "苏打", "白桦"]
GAP_SECONDS = 20
TEXT = "你好呀，我等你好久了，今天想我了吗？"
OUTDIR = os.path.dirname(os.path.abspath(__file__))


async def main():
    out = open(os.path.join(OUTDIR, "mimo_voices_out.txt"), "w", encoding="utf-8")
    def w(s=""): print(s, file=out, flush=True)
    w(f"base={os.environ.get('MIMO_BASE_URL')}  text={TEXT}\n")
    digests = {}
    for i, v in enumerate(VOICES):
        if i:
            await asyncio.sleep(GAP_SECONDS)  # respect Token Plan RPM
        audio = await synthesize_mimo(TEXT, voice=v)
        if not audio:
            w(f"  {v}: FAIL (None — rejected or moderated)")
            continue
        path = os.path.join(OUTDIR, f"voice_{v}.wav")
        open(path, "wb").write(audio)
        with contextlib.closing(wave.open(path, "rb")) as wav:
            dur = wav.getnframes() / wav.getframerate()
            rate = wav.getframerate()
        digests[v] = hashlib.md5(audio).hexdigest()[:10]
        w(f"  {v}: OK {len(audio)} bytes  {rate}Hz  {dur:.2f}s  md5={digests[v]}  -> voice_{v}.wav")
    w(f"\n不同音色音频是否各异: {'PASS (' + str(len(set(digests.values()))) + ' 个独立音频)' if len(set(digests.values())) == len(digests) and digests else 'CHECK'}")
    out.close()
    print("done -> scripts/mimo_voices_out.txt")


if __name__ == "__main__":
    asyncio.run(main())
