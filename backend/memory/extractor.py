"""
Memory extractor: analyzes conversation turns to extract durable facts.
Uses the local Qwen model to identify user preferences, profile data, etc.
"""
import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session as DBSession
from models.database import ChatSession, UserMemory
from services.llm_service import chat_completion

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """\
Analyze the following conversation exchange and extract any important facts about the user \
that should be remembered for future conversations.

User said: {user_text}
Character replied: {assistant_text}

Extract facts as a JSON array. Each fact should have "key" and "value".
Keys should be categories like: user.name, user.city, user.job, user.hobby, \
user.relationship_status, user.preference, user.emotional_state, user.recent_event, etc.

If there are no meaningful facts to extract, return an empty array: []

Return ONLY valid JSON array, no other text.
"""


async def extract_memories_for_user(
    db: DBSession,
    user_id: str,
    character_id: int,
    user_text: str,
    assistant_text: str,
) -> list[dict]:
    """Extract memories using user_id and character_id directly (no ChatSession needed)."""
    return await _run_extraction(db, user_id, character_id, user_text, assistant_text)


async def extract_memories(
    db: DBSession,
    session: ChatSession,
    user_text: str,
    assistant_text: str,
) -> list[dict]:
    """Extract and persist memory facts from a conversation turn (gateway path)."""
    return await _run_extraction(
        db, session.platform_user_id, session.character_id, user_text, assistant_text
    )


async def _run_extraction(
    db: DBSession,
    user_id: str,
    character_id: int,
    user_text: str,
    assistant_text: str,
) -> list[dict]:
    """Core extraction logic shared by all paths."""
    prompt = EXTRACTION_PROMPT.format(
        user_text=user_text[:500],
        assistant_text=assistant_text[:500],
    )

    try:
        raw = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=512,
        )

        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]

        facts = json.loads(raw)
        if not isinstance(facts, list):
            return []

        saved = []
        for fact in facts:
            key = fact.get("key", "").strip()
            value = fact.get("value", "").strip()
            if not key or not value:
                continue

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
                existing.confidence = min(existing.confidence + 0.1, 1.0)
                existing.updated_at = datetime.utcnow()
            else:
                mem = UserMemory(
                    user_id=user_id,
                    character_id=character_id,
                    key=key,
                    value=value,
                    confidence=0.7,
                )
                db.add(mem)

            saved.append({"key": key, "value": value})

        db.commit()
        if saved:
            logger.info(f"Extracted {len(saved)} memories for user {user_id}")
        return saved

    except (json.JSONDecodeError, Exception) as e:
        logger.debug(f"Memory extraction skipped: {e}")
        return []
