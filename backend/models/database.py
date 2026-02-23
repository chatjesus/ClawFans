"""
SQLite database models for ClawFans.
Tables: users, characters, conversations, messages, character_translations
"""
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime,
    ForeignKey, Boolean, Float, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = "sqlite:///./synclub.db"

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
    # Rich lore / background story (shown on profile, injected into context)
    backstory = Column(Text, default="")
    # JSON array of reference image paths for visual consistency
    # e.g. ["/uploads/refs/5/char_0.png", "/uploads/refs/5/char_1.png", ...]
    ref_images = Column(Text, default="")
    # Manual sort boost: higher = appears earlier in lists (default 0, new chars get 100)
    sort_weight = Column(Integer, default=0)
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
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String(20), default="active")
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


def get_db():
    """Dependency to get DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)

