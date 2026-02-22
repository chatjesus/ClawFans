"""
Session router: resolves (platform, platform_user_id, character_id) to a ChatSession.
Creates new sessions on demand (lazy).
"""
from datetime import datetime
from sqlalchemy.orm import Session as DBSession

from models.database import ChatSession, Character
from gateway.contracts import InboundEvent


DEFAULT_CHARACTER_ID = 1


def resolve_session(event: InboundEvent, db: DBSession) -> ChatSession:
    """Find or create a ChatSession for this inbound event."""
    character_id = event.character_id or DEFAULT_CHARACTER_ID

    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        raise ValueError(f"Character {character_id} not found")

    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.platform == event.platform.value,
            ChatSession.platform_user_id == event.platform_user_id,
            ChatSession.character_id == character_id,
            ChatSession.status == "active",
        )
        .first()
    )

    if not session:
        session = ChatSession(
            platform=event.platform.value,
            platform_user_id=event.platform_user_id,
            character_id=character_id,
            status="active",
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    session.last_active_at = datetime.utcnow()
    db.commit()

    return session
