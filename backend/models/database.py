"""
SQLite database models for ClawFans.
Tables: users, characters, conversations, messages, character_translations
"""
import os
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime,
    ForeignKey, Boolean, Float, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# Allow overriding via environment variable for different environments.
# Default: clawfans.db in the backend directory (matches README / compose).
def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///./clawfans.db")


DATABASE_URL = get_database_url()

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 10},
)

# Enable WAL mode: allows concurrent reads and writes, fixes SQLite lock contention
# during long-lived SSE streaming sessions
with engine.connect() as _conn:
    _conn.execute(__import__("sqlalchemy").text("PRAGMA journal_mode=WAL"))
    _conn.execute(__import__("sqlalchemy").text("PRAGMA busy_timeout=8000"))

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    avatar_url = Column(String(500), default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    characters = relationship("Character", back_populates="creator")
    conversations = relationship("Conversation", back_populates="user")
    favorites = relationship("Favorite", back_populates="user")


class Character(Base):
    __tablename__ = "characters"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, default="")
    system_prompt = Column(Text, nullable=False)
    greeting = Column(Text, default="Hello! How can I help you today?")
    avatar_url = Column(String(500), default="")
    tags = Column(String(500), default="")  # comma-separated tags
    category = Column(String(50), default="Featured")
    is_public = Column(Boolean, default=True)
    message_count = Column(Integer, default=0)
    star_count = Column(Integer, default=0)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # Clerk user identity (string); used when the creator authed via Clerk
    # rather than the legacy integer-FK users table.
    clerk_creator_id = Column(String(200), nullable=True, index=True)
    # Rich lore / background story (shown on profile, injected into context)
    backstory = Column(Text, default="")
    # JSON array of reference image paths for visual consistency
    # e.g. ["/uploads/refs/5/char_0.png", "/uploads/refs/5/char_1.png", ...]
    ref_images = Column(Text, default="")
    # Manual sort boost: higher = appears earlier in lists (default 0, new chars get 100)
    sort_weight = Column(Integer, default=0)
    # TTS voice ID (edge-tts voice name). Empty = auto-select from tags+description.
    voice_id = Column(String(100), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = relationship("User", back_populates="characters")
    conversations = relationship("Conversation", back_populates="character")
    favorites = relationship("Favorite", back_populates="character")
    translations = relationship("CharacterTranslation", back_populates="character",
                                cascade="all, delete-orphan")


class CharacterTranslation(Base):
    """Stores translated content for a character in a specific locale."""
    __tablename__ = "character_translations"
    __table_args__ = (UniqueConstraint("character_id", "locale", name="uq_char_locale"),)

    id = Column(Integer, primary_key=True, index=True)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False, index=True)
    locale = Column(String(10), nullable=False, index=True)   # e.g. "en", "ja", "ko"
    description = Column(Text, default="")
    greeting = Column(Text, default="")
    system_prompt = Column(Text, nullable=True)               # None = use original
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    character = relationship("Character", back_populates="translations")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # Clerk user identity (string) — separate from legacy integer user_id
    clerk_user_id = Column(String(200), nullable=True, index=True)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    title = Column(String(200), default="New Chat")
    # Intimacy level (0-100): controls how revealing character's photos can be
    intimacy_level = Column(Integer, default=0)
    # Streak tracking: consecutive days with at least one message
    streak_days = Column(Integer, default=0)
    last_chat_date = Column(String(10), nullable=True)   # ISO date "2026-02-22"
    last_checkin_date = Column(String(10), nullable=True)  # daily check-in reward marker
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="conversations")
    character = relationship("Character", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="favorites")
    character = relationship("Character", back_populates="favorites")


# ── Gateway / Multi-Channel Models ──────────────────────────────────────────

class ChatSession(Base):
    """Cross-platform session: one per (user, character, platform)."""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(30), nullable=False, index=True)
    platform_user_id = Column(String(200), nullable=False, index=True)
    # For Telegram: the chat_id used to send proactive messages (same as platform_user_id for DMs)
    telegram_chat_id = Column(String(200), nullable=True)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String(20), default="active")
    # Proactive message tracking: last time we sent one (to avoid spam)
    last_proactive_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active_at = Column(DateTime, default=datetime.utcnow)

    character = relationship("Character")
    messages = relationship("GatewayMessage", back_populates="session", order_by="GatewayMessage.created_at")


class GatewayMessage(Base):
    """Messages routed through the gateway (all platforms)."""
    __tablename__ = "gateway_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    tool_calls_json = Column(Text, nullable=True)
    tool_results_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")


class UserMemory(Base):
    """Durable per-user, per-character memory facts."""
    __tablename__ = "user_memories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(200), nullable=False, index=True)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False, index=True)
    key = Column(String(200), nullable=False)
    value = Column(Text, nullable=False)
    confidence = Column(Float, default=0.7)
    source_message_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ScheduledJob(Base):
    """Proactive message jobs and scheduled tasks."""
    __tablename__ = "scheduled_jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(200), nullable=False, index=True)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    platform = Column(String(30), nullable=False)
    run_at = Column(DateTime, nullable=False, index=True)
    job_type = Column(String(50), nullable=False)
    payload_json = Column(Text, nullable=True)
    status = Column(String(20), default="pending", index=True)
    attempts = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class IdentityLink(Base):
    """Links a user across platforms (web user_id <-> telegram user_id, etc.)."""
    __tablename__ = "identity_links"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    platform = Column(String(30), nullable=False)
    platform_user_id = Column(String(200), nullable=False)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Event / Story System ──────────────────────────────────────────────────────

class CharacterEvent(Base):
    """
    Story event template for a character.
    Triggered at certain intimacy milestones or special conditions.
    Each event has 3 choices that affect intimacy and may unlock content.
    """
    __tablename__ = "character_events"

    id = Column(Integer, primary_key=True, index=True)
    char_id = Column(Integer, ForeignKey("characters.id"), nullable=False, index=True)
    event_type = Column(String(30), default="milestone")  # milestone/daily/crisis/anniversary
    title = Column(String(200), nullable=False)           # "凌晨三点的消息"
    description = Column(Text, default="")               # Scene setup text shown to user
    trigger_json = Column(Text, default="{}")            # {"type":"intimacy_gte","value":20}
    choices_json = Column(Text, default="[]")            # [{text, intimacy_delta, unlock_hint}]
    outcome_prompt = Column(Text, default="")            # LLM prompt for character reaction
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    character = relationship("Character")
    instances = relationship("ConversationEvent", back_populates="event")


class ConversationEvent(Base):
    """Per-conversation event instance — tracks state for each user's relationship."""
    __tablename__ = "conversation_events"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    event_id = Column(Integer, ForeignKey("character_events.id"), nullable=False)
    status = Column(String(20), default="pending")       # pending/active/completed/skipped
    choice_index = Column(Integer, nullable=True)        # which option user selected (0/1/2)
    triggered_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    conversation = relationship("Conversation")
    event = relationship("CharacterEvent", back_populates="instances")


class OpsConfig(Base):
    """Operator-tunable settings (the configurable adult-operations layer).
    One row per key; value is JSON-encoded so ints/floats/bools round-trip.
    Read through services/ops_config.py (which merges with defaults)."""
    __tablename__ = "ops_config"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)  # JSON-encoded
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def get_db():
    """Dependency to get DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _add_column_sql(table_name: str, col) -> str:
    """Build an `ALTER TABLE … ADD COLUMN` statement for a single ORM column.
    Only emits a DEFAULT for simple scalar defaults (SQLite can't add a
    NOT NULL column without one, and callable defaults like utcnow can't be
    expressed in DDL — but those columns are old and never missing)."""
    col_type = col.type.compile(dialect=engine.dialect)
    sql = f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type}"
    default = col.default
    if default is not None and getattr(default, "is_scalar", False):
        val = default.arg
        if isinstance(val, bool):
            sql += f" DEFAULT {1 if val else 0}"
        elif isinstance(val, (int, float)):
            sql += f" DEFAULT {val}"
        elif isinstance(val, str):
            escaped = val.replace("'", "''")
            sql += f" DEFAULT '{escaped}'"
    return sql


def ensure_columns(bind=None) -> None:
    """Forward-migrate existing tables: add any model columns that are missing.

    create_all() only creates missing *tables*, never missing *columns*, so a
    database created before a model gained a column drifts and breaks on every
    query. This adds those columns in place (no data loss). Idempotent; a no-op
    on a fresh/current schema. There's no Alembic in this project, so this is
    the safety net when models evolve.
    """
    from sqlalchemy import inspect as sa_inspect, text
    bind = bind or engine
    insp = sa_inspect(bind)
    existing_tables = set(insp.get_table_names())
    with bind.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # create_all() will create it fresh, with all columns
            live_cols = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name not in live_cols:
                    conn.execute(text(_add_column_sql(table.name, col)))


def init_db():
    """Create all tables, then forward-migrate any drifted columns."""
    Base.metadata.create_all(bind=engine)
    ensure_columns(engine)

