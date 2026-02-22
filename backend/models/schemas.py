"""
Pydantic schemas for request/response validation.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── Character Schemas ──

class CharacterCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    system_prompt: str = Field(..., min_length=1)
    greeting: str = "Hello! How can I help you today?"
    avatar_url: str = ""
    tags: str = ""          # comma-separated, e.g. "Romance,Fantasy"
    category: str = "Featured"
    is_public: bool = True


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    greeting: Optional[str] = None
    avatar_url: Optional[str] = None
    tags: Optional[str] = None
    category: Optional[str] = None
    is_public: Optional[bool] = None
    message_count: Optional[int] = None
    star_count: Optional[int] = None


class CharacterResponse(BaseModel):
    id: int
    name: str
    description: str
    system_prompt: str
    greeting: str
    avatar_url: str
    tags: str
    category: str
    is_public: bool
    message_count: int
    star_count: int
    creator_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CharacterCard(BaseModel):
    """Lighter response for gallery cards."""
    id: int
    name: str
    description: str
    avatar_url: str
    tags: str
    category: str
    message_count: int
    star_count: int

    model_config = {"from_attributes": True}


# ── Chat Schemas ──

class ChatMessageCreate(BaseModel):
    content: str = Field(..., min_length=1)


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationCreate(BaseModel):
    character_id: int


class ConversationResponse(BaseModel):
    id: int
    character_id: int
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetail(BaseModel):
    id: int
    character_id: int
    character_name: str = ""
    character_avatar: str = ""
    title: str
    messages: list[ChatMessageResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Auth Schemas ──

class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    email: str
    password: str = Field(..., min_length=6)


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    avatar_url: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

