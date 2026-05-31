"""
Batch scene generation using Gemini 3.1 Flash Image.
Generates 5 scenes per character that's missing them.
"""
import os, sys, json, asyncio, time
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from pathlib import Path
from models.database import SessionLocal, Character

BACKEND_DIR = Path(__file__).parent.parent / "backend"
SCENES_DIR = BACKEND_DIR / "uploads" / "scenes"

GCP_CREDENTIALS = os.getenv(
    "GOOGLE_APPLICATION_CREDENTIALS",
    r"C:\Users\PRO\Desktop\CUDA\credentials\pdfconverter-415414-d9dbb1a4eec6.json",
)
GCP_PROJECT = os.getenv("GCP_PROJECT", "pdfconverter-415414")
GCP_LOCATION = os.getenv("GCP_LOCATION", "global")

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GCP_CREDENTIALS

_client = None
def get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION)
    return _client


async def plan_scenes(name: str, description: str, system_prompt: str) -> list[str]:
    """Use LLM to plan 5 scene descriptions for a character."""
    import httpx
    prompt = f"""你是一个视觉小说场景设计师。为以下角色设计5个场景描述（用英文），每个场景50-80词。

角色：{name}
描述：{(description or '')[:200]}
人设：{(system_prompt or '')[:300]}

场景要求：
- Scene 0: 角色自拍/肖像，在她的标志性场景中
- Scene 1: 角色展现情感的日常场景
- Scene 2: 暧昧/亲密场景（如靠近用户、眼神接触）
- Scene 3: 特殊场景（夜晚/雨天/节日等氛围场景）
- Scene 4: 性感/诱惑场景（暗示性的，不直接露骨）

输出格式（每行一个场景，纯英文，不要编号和标签）：
"""
    payload = {
        "model": "qwen2.5:14b",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.9, "num_predict": 600},
    }
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post("http://localhost:11434/api/chat", json=payload)
        r.raise_for_status()
        text = r.json()["message"]["content"].strip()

    lines = [l.strip() for l in text.split("\n") if l.strip() and not l.strip().startswith("#")]
    # Remove numbering
    cleaned = []
    for l in lines:
        for prefix in ["Scene 0:", "Scene 1:", "Scene 2:", "Scene 3:", "Scene 4:",
                        "0.", "1.", "2.", "3.", "4.", "0:", "1:", "2:", "3:", "4:",
                        "- ", "* "]:
            if l.startswith(prefix):
                l = l[len(prefix):].strip()
        if len(l) > 20:
            cleaned.append(l)
    return cleaned[:5]


MODELS = ["gemini-3.1-flash-image-preview", "gemini-3-pro-image-preview"]


async def generate_scene_image(prompt: str, ref_bytes: bytes = None, output_path: Path = None) -> bool:
    """Generate a scene image using Gemini, with retry and model fallback."""
    from google.genai import types

    for model in MODELS:
        for attempt in range(2):
            try:
                client = get_client()

                if ref_bytes:
                    contents = [
                        types.Part.from_bytes(data=ref_bytes, mime_type="image/png"),
                        types.Part.from_text(
                            text=f"Generate an illustration of this EXACT same character in: {prompt}. "
                            f"Style: detailed anime art, vibrant colors, professional quality. "
                            f"No text, no watermark. Keep character consistency."
                        ),
                    ]
                else:
                    contents = (
                        f"Generate a high-quality anime illustration: {prompt}. "
                        "Style: detailed anime art, vibrant colors, professional quality. "
                        "No text, no watermark."
                    )

                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE", "TEXT"],
                        temperature=1.0,
                    ),
                )

                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                        output_path.write_bytes(part.inline_data.data)
                        return True

            except Exception as e:
                err = str(e)
                if "disconnected" in err.lower() or "429" in err or "quota" in err.lower():
                    wait = 15 * (attempt + 1)
                    print(f"    !! Rate limited ({model}), waiting {wait}s...")
                    await asyncio.sleep(wait)
                    continue
                print(f"    !! Error ({model}): {err[:80]}")
                break

    return False


def load_ref(char_id: int, avatar_url: str) -> bytes:
    """Load character reference image."""
    refs_dir = BACKEND_DIR / "uploads" / "refs" / str(char_id)
    for candidate in ["char_0.png", "char_0.jpg"]:
        p = refs_dir / candidate
        if p.exists():
            return p.read_bytes()

    if avatar_url:
        if avatar_url.startswith("/avatars/"):
            p = BACKEND_DIR.parent / "frontend" / "public" / avatar_url.lstrip("/")
        elif avatar_url.startswith("/uploads/"):
            p = BACKEND_DIR / avatar_url.lstrip("/")
        else:
            return None
        if p.exists():
            return p.read_bytes()
    return None


async def process_character(char, db):
    """Generate all 5 scenes for one character."""
    scene_dir = SCENES_DIR / str(char.id)
    scene_dir.mkdir(parents=True, exist_ok=True)

    existing = len(list(scene_dir.glob("*.png")))
    if existing >= 5:
        print(f"  [{char.id}] {char.name}: skip (has {existing} scenes)")
        return

    print(f"\n  [{char.id}] {char.name}")

    # Plan scenes
    print(f"    Planning scenes...")
    scenes = await plan_scenes(char.name, char.description or "", char.system_prompt or "")
    if len(scenes) < 3:
        print(f"    !! Only got {len(scenes)} scene descriptions, need at least 3")
        # Pad with generic scenes
        while len(scenes) < 5:
            scenes.append(f"A beautiful anime character {char.name} in a scenic environment, detailed illustration")

    # Load reference
    ref_bytes = load_ref(char.id, char.avatar_url)
    ref_status = "with ref" if ref_bytes else "no ref"

    # Generate scenes
    for i, scene_desc in enumerate(scenes[:5]):
        out_path = scene_dir / f"scene_{i}.png"
        if out_path.exists():
            print(f"    scene_{i}: exists, skip")
            continue

        print(f"    scene_{i} ({ref_status}): {scene_desc[:60]}...")
        t0 = time.time()
        ok = await generate_scene_image(scene_desc, ref_bytes, out_path)
        t1 = time.time()

        if ok:
            size_kb = out_path.stat().st_size / 1024
            print(f"    scene_{i}: OK ({size_kb:.0f}KB, {t1-t0:.1f}s)")
        else:
            print(f"    scene_{i}: FAILED ({t1-t0:.1f}s)")

        await asyncio.sleep(10)  # Rate limit — Gemini image models need 10s+ between calls


async def main():
    db = SessionLocal()
    try:
        chars = (
            db.query(Character)
            .filter(Character.sort_weight >= 50)
            .order_by(Character.id)
            .all()
        )

        missing = []
        for c in chars:
            scene_dir = SCENES_DIR / str(c.id)
            count = len(list(scene_dir.glob("*.png"))) if scene_dir.exists() else 0
            if count < 5:
                missing.append(c)

        print(f"Generating scenes for {len(missing)} characters using Gemini 3.1 Flash Image...\n")

        for char in missing:
            try:
                await process_character(char, db)
            except Exception as e:
                print(f"  [{char.id}] {char.name}: ERROR - {e}")
                await asyncio.sleep(5)

        print("\n\nDone!")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
