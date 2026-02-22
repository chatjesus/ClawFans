"""
Chat API – conversation management and streaming chat with AI characters.
"""
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from models.database import get_db, Character, Conversation, Message
from models.schemas import (
    ConversationCreate, ConversationResponse, ConversationDetail,
    ChatMessageCreate, ChatMessageResponse,
)
from services.chat_service import generate_reply_stream

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ── Conversation Management ──

@router.post("/conversations", response_model=ConversationResponse, status_code=201)
def create_conversation(data: ConversationCreate, db: Session = Depends(get_db)):
    """Start a new conversation with a character."""
    char = db.query(Character).filter(Character.id == data.character_id).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    conv = Conversation(
        character_id=data.character_id,
        title=f"Chat with {char.name}",
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


@router.get("/conversations", response_model=list[ConversationResponse])
def list_conversations(
    character_id: int = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List conversations, optionally filtered by character."""
    query = db.query(Conversation)
    if character_id:
        query = query.filter(Conversation.character_id == character_id)
    return query.order_by(Conversation.updated_at.desc()).offset(skip).limit(limit).all()


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """Get a conversation with all its messages."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    char = db.query(Character).filter(Character.id == conv.character_id).first()

    return ConversationDetail(
        id=conv.id,
        character_id=conv.character_id,
        character_name=char.name if char else "",
        character_avatar=char.avatar_url if char else "",
        title=conv.title,
        messages=[
            ChatMessageResponse(
                id=m.id, role=m.role, content=m.content, created_at=m.created_at
            )
            for m in conv.messages
        ],
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """Delete a conversation and all its messages."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.query(Message).filter(Message.conversation_id == conversation_id).delete()
    db.delete(conv)
    db.commit()


# ── Chat / Streaming ──

@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: int,
    data: ChatMessageCreate,
    db: Session = Depends(get_db),
):
    """
    Send a message in a conversation and stream the AI response back.
    Uses Server-Sent Events (SSE) for real-time streaming.
    """
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    char = db.query(Character).filter(Character.id == conv.character_id).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    async def event_stream():
        try:
            async for chunk in generate_reply_stream(char, conv, data.content, db):
                # SSE format
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations/{conversation_id}/messages", response_model=list[ChatMessageResponse])
def get_messages(
    conversation_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Get messages for a conversation."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return messages

