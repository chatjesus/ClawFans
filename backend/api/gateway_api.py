"""
Gateway API endpoint: unified inbound handler for all platforms.
Also provides session/memory inspection endpoints for admin/debug.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DBSession

from models.database import get_db, ChatSession, GatewayMessage, UserMemory
from gateway.contracts import InboundEvent, AgentReply, Platform
from gateway.handler import handle_inbound
from gateway.router import resolve_session
from agent_runtime.runtime import AgentRuntime
from models.database import Character

router = APIRouter(prefix="/api/gateway", tags=["gateway"])


@router.post("/inbound", response_model=AgentReply)
async def gateway_inbound(event: InboundEvent, db: DBSession = Depends(get_db)):
    """Process an inbound event through the full gateway pipeline."""
    reply = await handle_inbound(event, db)
    return reply


@router.post("/inbound/stream")
async def gateway_inbound_stream(event: InboundEvent, db: DBSession = Depends(get_db)):
    """Streaming variant: returns SSE chunks for real-time UIs."""
    if event.command:
        reply = await handle_inbound(event, db)
        async def single():
            yield f"data: {reply.text}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(single(), media_type="text/event-stream")

    session = resolve_session(event, db)
    character = db.query(Character).filter(Character.id == session.character_id).first()
    if not character:
        raise HTTPException(404, "Character not found")

    runtime = AgentRuntime(db=db, session=session, character=character)

    async def stream():
        async for chunk in runtime.process_stream(event):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/sessions")
def list_sessions(
    platform: str = None,
    platform_user_id: str = None,
    limit: int = 50,
    db: DBSession = Depends(get_db),
):
    """List gateway sessions with optional filters."""
    q = db.query(ChatSession)
    if platform:
        q = q.filter(ChatSession.platform == platform)
    if platform_user_id:
        q = q.filter(ChatSession.platform_user_id == platform_user_id)
    sessions = q.order_by(ChatSession.last_active_at.desc()).limit(limit).all()
    return [
        {
            "id": s.id,
            "platform": s.platform,
            "platform_user_id": s.platform_user_id,
            "character_id": s.character_id,
            "character_name": s.character.name if s.character else None,
            "status": s.status,
            "last_active_at": s.last_active_at.isoformat() if s.last_active_at else None,
        }
        for s in sessions
    ]


@router.get("/sessions/{session_id}/messages")
def get_session_messages(session_id: int, limit: int = 50, db: DBSession = Depends(get_db)):
    """Get messages for a gateway session."""
    messages = (
        db.query(GatewayMessage)
        .filter(GatewayMessage.session_id == session_id)
        .order_by(GatewayMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content[:200],
            "created_at": m.created_at.isoformat(),
        }
        for m in reversed(messages)
    ]


@router.get("/memories/{platform_user_id}")
def get_user_memories(
    platform_user_id: str,
    character_id: int = None,
    db: DBSession = Depends(get_db),
):
    """Get stored memories for a user."""
    q = db.query(UserMemory).filter(UserMemory.user_id == platform_user_id)
    if character_id:
        q = q.filter(UserMemory.character_id == character_id)
    memories = q.order_by(UserMemory.updated_at.desc()).all()
    return [
        {
            "id": m.id,
            "character_id": m.character_id,
            "key": m.key,
            "value": m.value,
            "confidence": m.confidence,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
        }
        for m in memories
    ]
