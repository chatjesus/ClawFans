"""
Memory store: CRUD operations for user memories.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session as DBSession
from models.database import UserMemory


def upsert_memory(
    db: DBSession,
    user_id: str,
    character_id: int,
    key: str,
    value: str,
    confidence: float = 0.7,
) -> UserMemory:
    """Create or update a memory entry."""
    existing = (
        db.query(UserMemory)
        .filter(
            UserMemory.user_id == user_id,
            UserMemory.character_id == character_id,
            UserMemory.key == key,
        )
        .first()
    )

    if existing:
        existing.value = value
        existing.confidence = confidence
        existing.updated_at = datetime.utcnow()
        db.commit()
        return existing

    mem = UserMemory(
        user_id=user_id,
        character_id=character_id,
        key=key,
        value=value,
        confidence=confidence,
    )
    db.add(mem)
    db.commit()
    db.refresh(mem)
    return mem


def delete_memory(db: DBSession, memory_id: int) -> bool:
    mem = db.query(UserMemory).filter(UserMemory.id == memory_id).first()
    if mem:
        db.delete(mem)
        db.commit()
        return True
    return False


def get_all_memories(
    db: DBSession,
    user_id: str,
    character_id: Optional[int] = None,
) -> list[UserMemory]:
    q = db.query(UserMemory).filter(UserMemory.user_id == user_id)
    if character_id:
        q = q.filter(UserMemory.character_id == character_id)
    return q.order_by(UserMemory.updated_at.desc()).all()
