"""
Voice API — text-to-speech for character messages.
"""
import base64
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models.database import get_db, Character, Message
from services.voice_service import synthesize_speech, synthesize_speech_streaming

router = APIRouter(prefix="/api/voice", tags=["voice"])


class TTSRequest(BaseModel):
    text: str
    character_id: int


@router.post("/synthesize")
async def synthesize(req: TTSRequest, db: Session = Depends(get_db)):
    """Generate TTS audio for arbitrary text, return MP3 bytes directly."""
    import logging
    _log = logging.getLogger(__name__)
    _log.info(f"TTS request: text_len={len(req.text)} char_id={req.character_id}")

    char = db.query(Character).filter(Character.id == req.character_id).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    try:
        audio_bytes = await synthesize_speech_streaming(
            text=req.text,
            voice_id=char.voice_id or "",
            tags=char.tags or "",
            description=char.description or "",
        )
    except Exception as e:
        _log.error(f"TTS synthesis exception: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"TTS error: {e}")

    if not audio_bytes:
        raise HTTPException(status_code=500, detail="TTS synthesis returned empty")

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={"Content-Disposition": "inline; filename=tts.mp3"},
    )


@router.get("/message/{message_id}")
async def message_tts(message_id: int, db: Session = Depends(get_db)):
    """Generate TTS audio for an existing message, return MP3 directly."""
    msg = db.query(Message).filter(Message.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    from models.database import Conversation
    conv = db.query(Conversation).filter(Conversation.id == msg.conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    char = db.query(Character).filter(Character.id == conv.character_id).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    audio_bytes = await synthesize_speech_streaming(
        text=msg.content,
        voice_id=char.voice_id or "",
        tags=char.tags or "",
        description=char.description or "",
    )
    if not audio_bytes:
        raise HTTPException(status_code=500, detail="TTS synthesis failed")

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={"Content-Disposition": f"inline; filename=tts_{message_id}.mp3"},
    )


@router.get("/profiles")
async def list_profiles():
    """List available voice profiles for debugging/preview."""
    from services.voice_service import VOICE_PROFILES
    return {k: v["name"] for k, v in VOICE_PROFILES.items()}
