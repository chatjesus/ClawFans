"""
Core message contracts for the gateway system.
All channel adapters produce InboundEvent and consume AgentReply.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Platform(str, Enum):
    WEB = "web"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    WHATSAPP = "whatsapp"


class MediaType(str, Enum):
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    FILE = "file"


class MediaAttachment(BaseModel):
    type: MediaType
    url: str
    mime_type: Optional[str] = None
    file_name: Optional[str] = None


class InboundEvent(BaseModel):
    """Normalized message coming from any channel adapter."""
    platform: Platform
    platform_user_id: str
    character_id: Optional[int] = None
    text: Optional[str] = None
    media: list[MediaAttachment] = Field(default_factory=list)
    command: Optional[str] = None
    command_args: Optional[str] = None
    raw_payload: Optional[dict] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ToolCallRequest(BaseModel):
    """A tool invocation requested by the agent."""
    tool_name: str
    arguments: dict = Field(default_factory=dict)


class ToolCallResult(BaseModel):
    """Result from executing a tool."""
    tool_name: str
    success: bool
    output: str = ""
    media: list[MediaAttachment] = Field(default_factory=list)
    error: Optional[str] = None


class AgentReply(BaseModel):
    """Normalized response to send back to any channel."""
    text: str = ""
    media: list[MediaAttachment] = Field(default_factory=list)
    tool_calls_used: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    session_id: Optional[int] = None
    character_id: Optional[int] = None
