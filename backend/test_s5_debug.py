"""Debug scene 5: isolate whether RAI block comes from IMAGE or PROMPT."""
import asyncio, os, sys, json, time
sys.path.insert(0, r"C:\Users\PRO\Desktop\CUDA\synclub-local\scripts")
from manga_video_gen import generate_video_veo

LOG = "debug-90e70b.log"

def log(hyp, msg, data):
    entry = {"sessionId":"90e70b","hypothesisId":hyp,"location":"test_s5_debug.py","message":msg,"data":data,"timestamp":int(time.time()*1000)}
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

# The original problematic prompt
PROMPT_ORIGINAL = (
    "anime style, 2D cel animation, illustrated. "
    "A woman in her early thirties, Su Yurou, standing near the door. "
    "A man stands across from her, his gaze steady. "
    "Camera motion: She looks at him with a mixture of curiosity and intrigue."
)

# Safe neutral prompt — no mention of two people
PROMPT_SAFE = (
    "anime style, 2D cel animation, illustrated. "
    "A beautiful woman with shoulder-length black hair, alone in a warmly lit room, "
    "looking thoughtfully into the distance. Gentle breeze, soft lighting. "
    "Camera motion: slow zoom in."
)

S5_FRAME   = r"uploads\manga\53\frame_ep1_s5.png"   # s5 key frame (suspected)
S0_FRAME   = r"uploads\manga\53\frame_ep1_s0.png"   # s0 key frame (known working)

async def main():
    # Verify fix: test new s5 frame with auto-retry desaturate logic
    out = r"uploads\manga\53\clip_ep1_s5.mp4"
    if os.path.exists(out):
        os.remove(out)

    log("B-FIX", "post-fix test start", {"frame": S5_FRAME, "prompt": PROMPT_SAFE[:80]})
    print(f"\n=== Post-fix verification: new s5 frame + auto-retry logic ===")
    try:
        await generate_video_veo(S5_FRAME, PROMPT_SAFE, out)
        log("B-FIX", "post-fix PASS", {"result":"PASS"})
        print(f"  → PASS - s5 generated successfully with I2V or desaturate fallback!")
    except Exception as e:
        log("B-FIX", "post-fix FAIL", {"result":"FAIL","error":str(e)[:200]})
        print(f"  → FAIL: {str(e)[:200]}")

asyncio.run(main())
