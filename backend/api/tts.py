"""
TTS API endpoints.

GET /api/tts/synthesize?text=...&char_id=...  → streams MP3/WAV audio
GET /api/tts/engine                            → returns current engine info
"""

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse

from models.database import SessionLocal, Character
from services.tts_service import synthesize_stream, get_engine_info

router = APIRouter(prefix="/api/tts", tags=["tts"])


@router.get("/synthesize")
async def synthesize(
    text: str = Query(..., description="Text to synthesize (plain Chinese)"),
    char_id: int = Query(0, description="Character ID — used to pick matching voice"),
):
    """
    Stream TTS audio for the given text.
    Returns audio/mpeg stream (MP3 from edge-tts or WAV from GPT-SoVITS).
    """
    text = text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text must not be empty")
    if len(text) > 2000:
        raise HTTPException(status_code=400, detail="text too long (max 2000 chars)")

    tags, category, description, name, voice_id = "", "", "", "", ""
    if char_id:
        db = SessionLocal()
        try:
            char = db.query(Character).filter(Character.id == char_id).first()
            if char:
                tags = char.tags or ""
                category = char.category or ""
                description = char.description or ""
                name = char.name or ""
                voice_id = getattr(char, "voice_id", "") or ""
        finally:
            db.close()

    async def _generator():
        try:
            chunk_count = 0
            async for chunk in synthesize_stream(
                text,
                tags=tags,
                category=category,
                description=description,
                name=name,
                voice_id=voice_id,
            ):
                chunk_count += 1
                yield chunk
            if chunk_count == 0:
                print(f"[TTS WARN] Zero chunks for char_id={char_id} name={name!r}")
        except Exception as e:
            print(f"[TTS ERROR] synthesis failed for {name!r}: {e}")

    return StreamingResponse(
        _generator(),
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/engine")
async def engine_status():
    """Return which TTS engine is currently active and available voices."""
    return await get_engine_info()
