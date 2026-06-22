"""
Chat API – conversation management and streaming chat with AI characters.
"""
import asyncio
import json
import re
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional

from models.database import get_db, Character, CharacterTranslation, Conversation, Message
from models.schemas import (
    ConversationCreate, ConversationResponse, ConversationDetail,
    ChatMessageCreate, ChatMessageResponse,
)
from services.chat_service import generate_reply_stream, process_reply_images, StreamResult
from services.image_service import extract_image_tags, extract_scene_tags, get_pregenerated_scenes
from services.scene_service import ensure_scenes_background
from auth.clerk import get_current_user_id

# Keywords that indicate the user wants to see an image / selfie
IMAGE_INTENT_RE = re.compile(
    r"(自拍|selfie|照片|photo|图片|picture|看看你|身材|胸部|胸|脸部|脸|腿|腰|"
    r"正面照|侧面|背面|全身|半身|show me|send me|发(一张|张|个)|"
    r"拍(一张|张|个)|take a pic|give me a pic|let me see you|show yourself|"
    r"your pic|your photo|your selfie|your body|your figure|your face|your chest)",
    re.IGNORECASE,
)

LOCALE_LANGUAGE = {
    "en": "English",
    "zh": "Simplified Chinese", "zh-TW": "Traditional Chinese",
    "ja": "Japanese", "ko": "Korean",
    "es": "Spanish", "fr": "French", "pt": "Portuguese",
    "de": "German", "ru": "Russian", "it": "Italian",
    "th": "Thai", "vi": "Vietnamese", "id": "Indonesian", "ar": "Arabic",
}

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ── Conversation Management ──

@router.post("/conversations", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    data: ConversationCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Start a new conversation with a character."""
    char = db.query(Character).filter(Character.id == data.character_id).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    user_id = await get_current_user_id(request)
    conv = Conversation(
        character_id=data.character_id,
        title=f"Chat with {char.name}",
        clerk_user_id=None if user_id == "anonymous" else user_id,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    # Trigger scene pre-generation in background (non-blocking)
    import asyncio
    asyncio.create_task(ensure_scenes_background(
        char.id, char.name, char.description or "",
        char.system_prompt or "", char.avatar_url,
    ))

    return conv


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    request: Request,
    character_id: int = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List conversations with character info, optionally filtered by character."""
    from sqlalchemy.orm import joinedload

    user_id = await get_current_user_id(request)
    query = db.query(Conversation).options(joinedload(Conversation.character))
    if user_id != "anonymous":
        query = query.filter(
            (Conversation.clerk_user_id == user_id) |
            (Conversation.clerk_user_id == None)  # noqa: E711
        )
    if character_id:
        query = query.filter(Conversation.character_id == character_id)
    convs = query.order_by(Conversation.updated_at.desc()).offset(skip).limit(limit).all()

    result = []
    for conv in convs:
        char = conv.character
        result.append(ConversationResponse(
            id=conv.id,
            character_id=conv.character_id,
            title=conv.title,
            character_name=char.name if char else "",
            character_avatar=char.avatar_url if char else "",
            intimacy_level=conv.intimacy_level or 0,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
        ))
    return result


def _ensure_conv_visible(conv: Conversation, user_id: str) -> None:
    """A conversation is visible to its owner; anonymous-owned conversations
    are visible to anyone (no identity to verify against). Cross-user reads
    raise 403."""
    owner = conv.clerk_user_id
    if owner and owner != user_id:
        raise HTTPException(status_code=403, detail="Not your conversation")


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Get a conversation with all its messages."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    user_id = await get_current_user_id(request)
    _ensure_conv_visible(conv, user_id)

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
        intimacy_level=conv.intimacy_level or 0,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Delete a conversation and all its messages."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    user_id = await get_current_user_id(request)
    _ensure_conv_visible(conv, user_id)
    db.query(Message).filter(Message.conversation_id == conversation_id).delete()
    db.delete(conv)
    db.commit()


# ── Chat / Streaming ──

@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: int,
    data: ChatMessageCreate,
    request: Request,
    locale: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Send a message in a conversation and stream the AI response back.
    Uses Server-Sent Events (SSE) for real-time streaming.
    Accepts ?locale= to inject language directive into the system prompt.
    """
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    user_id = await get_current_user_id(request)
    _ensure_conv_visible(conv, user_id)

    char = db.query(Character).filter(Character.id == conv.character_id).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    # Build a request-scoped, localized prompt as a LOCAL string. We never
    # mutate `char.system_prompt` itself — doing so used to risk leaking
    # locale overlays back into the characters table on commit.
    localized_prompt: str | None = None
    if locale and locale not in ("zh", "zh-CN"):
        tr = db.query(CharacterTranslation).filter(
            CharacterTranslation.character_id == char.id,
            CharacterTranslation.locale == locale,
        ).first()
        if not tr and locale != "en":
            # Fallback to English
            tr = db.query(CharacterTranslation).filter(
                CharacterTranslation.character_id == char.id,
                CharacterTranslation.locale == "en",
            ).first()
        if tr and tr.system_prompt:
            localized_prompt = tr.system_prompt

    # Inject language directive so the model replies in user's language
    if locale and locale in LOCALE_LANGUAGE:
        base = localized_prompt if localized_prompt is not None else char.system_prompt
        lang = LOCALE_LANGUAGE[locale]
        directive = f"\n\n[IMPORTANT: Always reply in {lang}. Never switch languages.]"
        localized_prompt = base + directive

    async def event_stream():
        try:
            result = StreamResult()
            gen = generate_reply_stream(
                char, conv, data.content, db,
                user_id=user_id, result_holder=result,
                client_hour=data.client_hour,
                system_prompt_override=localized_prompt,
            )
            # Use a queue so keepalive timeouts never cancel the generator task
            _DONE = object()
            chunk_queue: asyncio.Queue = asyncio.Queue()

            async def _drain():
                try:
                    async for chunk in gen:
                        await chunk_queue.put(chunk)
                except Exception as exc:
                    await chunk_queue.put(exc)
                finally:
                    await chunk_queue.put(_DONE)

            drain_task = asyncio.create_task(_drain())

            while True:
                try:
                    item = await asyncio.wait_for(chunk_queue.get(), timeout=10.0)
                    if item is _DONE:
                        break
                    if isinstance(item, Exception):
                        raise item
                    yield f"data: {json.dumps({'content': item})}\n\n"
                except asyncio.TimeoutError:
                    if drain_task.done():
                        break
                    yield ": keepalive\n\n"

            await drain_task  # propagate any exception from the generator

            has_img = result.full_reply and extract_image_tags(result.full_reply)
            has_scene = result.full_reply and extract_scene_tags(result.full_reply)
            user_wants_image = bool(IMAGE_INTENT_RE.search(data.content))
            intimacy_level = conv.intimacy_level or 0

            # Auto-inject: user asked for image but LLM didn't produce any tag
            if user_wants_image and not (has_img or has_scene):
                scenes = get_pregenerated_scenes(char.id)
                if scenes:
                    # Rotate scenes based on message count to avoid showing same image twice
                    msg_count = db.query(Message).filter(
                        Message.conversation_id == conv.id
                    ).count()
                    # Avoid repeating the scene that was last shown (stored in last 3 msgs)
                    recent_content = " ".join(
                        m.content for m in db.query(Message)
                        .filter(Message.conversation_id == conv.id, Message.role == "assistant")
                        .order_by(Message.created_at.desc())
                        .limit(3)
                        .all()
                    )
                    used_indices = {i for i in scenes if f"scene_{i}" in recent_content}
                    available = {i: u for i, u in scenes.items() if i not in used_indices}
                    if not available:
                        available = scenes
                    idx = min(available.keys())
                    url = available[idx]
                    alt = f"{char.name}"
                    last_msg = (
                        db.query(Message)
                        .filter(Message.conversation_id == conv.id, Message.role == "assistant")
                        .order_by(Message.created_at.desc())
                        .first()
                    )
                    if last_msg:
                        last_msg.content = last_msg.content.rstrip() + f"\n\n![{alt}]({url})"
                        db.commit()
                    yield f"data: {json.dumps({'image': {'url': url, 'alt': alt}})}\n\n"

            elif has_img or has_scene:
                if has_img:
                    yield f"data: {json.dumps({'generating_image': True})}\n\n"

                instant, generated = await process_reply_images(
                    result.full_reply, conv.id, char.id, char.avatar_url, db,
                    intimacy_level=intimacy_level,
                )
                for img in instant:
                    yield f"data: {json.dumps({'image': img})}\n\n"
                for img in generated:
                    yield f"data: {json.dumps({'image': img})}\n\n"

            # ── Tool Call Execution ──────────────────────────────────────────
            if result.tool_call:
                tool_name = result.tool_call.get("tool", "")
                tool_args = result.tool_call.get("args", {})

                # Notify frontend: tool is executing
                yield f"data: {json.dumps({'tool_executing': {'name': tool_name, 'args': tool_args}})}\n\n"

                try:
                    from actions.registry import get_tool_registry
                    registry = get_tool_registry()
                    tool_result = await registry.execute(tool_name, tool_args)

                    # Notify frontend: tool result received
                    yield f"data: {json.dumps({'tool_result': {'name': tool_name, 'success': tool_result.success, 'output': tool_result.output or tool_result.error or ''}})}\n\n"

                    if tool_result.success:
                        # Second LLM pass: incorporate tool result into character response
                        from services.llm_service import chat_completion
                        from services.chat_service import build_messages
                        followup_context = build_messages(char, conv, db, user_id=user_id)
                        # Append the tool result as context for the follow-up
                        followup_context.append({
                            "role": "assistant",
                            "content": result.full_reply or "好的，我来帮你查一下。"
                        })
                        followup_context.append({
                            "role": "system",
                            "content": (
                                f"工具「{tool_name}」执行完成，返回结果：\n{tool_result.output}\n\n"
                                f"现在以{char.name}的身份，用自然的口吻把这个结果告诉用户。"
                                f"保持角色人设，不要照抄原文，要像真人一样转述。"
                                f"如果结果包含链接，可以直接引用。"
                            ),
                        })
                        followup_text = await chat_completion(followup_context, max_tokens=400)
                        if followup_text:
                            # Save follow-up to DB (append to last assistant message)
                            from models.database import Message as DBMessage
                            last_msg = (
                                db.query(DBMessage)
                                .filter(DBMessage.conversation_id == conv.id, DBMessage.role == "assistant")
                                .order_by(DBMessage.created_at.desc())
                                .first()
                            )
                            if last_msg:
                                last_msg.content = (last_msg.content or "") + "\n\n" + followup_text
                                db.commit()
                            yield f"data: {json.dumps({'tool_followup': followup_text})}\n\n"

                except Exception as te:
                    yield f"data: {json.dumps({'tool_result': {'name': tool_name, 'success': False, 'output': str(te)}})}\n\n"

            # Send intimacy update event
            if result.intimacy_update:
                yield f"data: {json.dumps({'intimacy': result.intimacy_update})}\n\n"

            # Send streak update event (only on new-day milestones)
            if result.streak_update and result.streak_update.get("is_new_day"):
                su = result.streak_update
                milestone = su.get("milestone") or {}
                yield f"data: {json.dumps({'streak': {'streak_days': su['streak_days'], 'broken': su.get('broken', False), 'milestone_toast': milestone.get('toast'), 'intimacy_bonus': milestone.get('intimacy_bonus', 0)}})}\n\n"

            # ── Story Event Trigger Check ────────────────────────────────────
            try:
                from services.event_service import check_events
                event_data = check_events(conv, char, db)
                if event_data:
                    yield f"data: {json.dumps({'story_event': event_data})}\n\n"
            except Exception as ev_err:
                import logging
                logging.getLogger(__name__).warning(f"Event check error: {ev_err}")

            # ── TTS Voice Generation (non-blocking) ──────────────────────────
            try:
                from services.voice_service import synthesize_speech
                display_text = result.full_reply or ""
                if display_text.strip():
                    audio_url = await synthesize_speech(
                        text=display_text,
                        voice_id=char.voice_id or "",
                        tags=char.tags or "",
                        description=char.description or "",
                    )
                    if audio_url:
                        yield f"data: {json.dumps({'voice': {'url': audio_url}})}\n\n"
            except Exception as tts_err:
                import logging
                logging.getLogger(__name__).warning(f"TTS error: {tts_err}")

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
async def get_messages(
    conversation_id: int,
    request: Request,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Get messages for a conversation."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    user_id = await get_current_user_id(request)
    _ensure_conv_visible(conv, user_id)

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return messages


@router.post("/conversations/{conversation_id}/checkin")
async def checkin(
    conversation_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Called when the user opens a chat. If they've been away long enough,
    the character proactively reaches out ('missed you'); the greeting is
    persisted as an assistant message and returned. Otherwise {greeting: null}.
    """
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    user_id = await get_current_user_id(request)
    _ensure_conv_visible(conv, user_id)

    char = db.query(Character).filter(Character.id == conv.character_id).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    # Daily check-in reward (reciprocity/habit loop): showing up deepens the bond.
    from datetime import date
    from services.checkin import grant_daily_checkin
    checkin_reward = grant_daily_checkin(conv, db, date.today().isoformat())

    from services.proactive_greeting import generate_return_greeting
    greeting = await generate_return_greeting(char, conv, db)

    resp = {
        "greeting": None,
        "checkin_reward": checkin_reward,
        "intimacy_level": conv.intimacy_level or 0,
    }
    if greeting:
        msg = Message(conversation_id=conv.id, role="assistant", content=greeting)
        db.add(msg)
        db.commit()
        db.refresh(msg)
        resp["greeting"] = greeting
        resp["message_id"] = msg.id
    return resp

