"""
Memory retriever: fetches relevant user memories for prompt injection.
"""
from sqlalchemy.orm import Session as DBSession
from models.database import UserMemory


def retrieve_memories(
    db: DBSession,
    user_id: str,
    character_id: int,
    limit: int = 10,
) -> list[UserMemory]:
    """Retrieve the most relevant memories for a user+character pair."""
    return (
        db.query(UserMemory)
        .filter(
            UserMemory.user_id == user_id,
            UserMemory.character_id == character_id,
            UserMemory.confidence >= 0.3,
        )
        .order_by(UserMemory.confidence.desc(), UserMemory.updated_at.desc())
        .limit(limit)
        .all()
    )
