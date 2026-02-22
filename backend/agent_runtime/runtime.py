"""
Agent runtime: processes inbound events, manages the tool-call loop,
persists messages, and returns AgentReply.
"""
import re
import json
import logging
from datetime import datetime
from typing import AsyncGenerator, Optional

from sqlalchemy.orm import Session as DBSession

from models.database import Character, ChatSession, GatewayMessage
from gateway.contracts import InboundEvent, AgentReply, ToolCallRequest, ToolCallResult
from agent_runtime.context import build_context
from actions.registry import get_tool_registry
from memory.extractor import extract_memories
from services.llm_service import chat_completion_stream, chat_completion

logger = logging.getLogger(__name__)

TOOL_CALL_PATTERN = re.compile(r"```tool\s*\n?({.*?})\s*\n?```", re.DOTALL)


class AgentRuntime:
    def __init__(self, db: DBSession, session: ChatSession, character: Character):
        self.db = db
        self.session = session
        self.character = character
        self.registry = get_tool_registry()

    async def process(self, event: InboundEvent) -> AgentReply:
        """Full processing pipeline for one inbound event."""
        if event.text:
            self._save_message("user", event.text)

        tool_schemas_text = self.registry.get_schemas_text()
        context = build_context(
            self.character, self.session, self.db,
            tool_schemas_text=tool_schemas_text,
        )

        reply_text = await chat_completion(context)

        tool_calls_used = []
        tool_call_match = TOOL_CALL_PATTERN.search(reply_text)
        if tool_call_match:
            try:
                tool_data = json.loads(tool_call_match.group(1))
                tool_name = tool_data.get("tool", "")
                tool_args = tool_data.get("args", {})

                result = await self.registry.execute(tool_name, tool_args)
                tool_calls_used.append(tool_name)

                clean_text = TOOL_CALL_PATTERN.sub("", reply_text).strip()

                followup_context = context + [
                    {"role": "assistant", "content": clean_text},
                    {"role": "system", "content": (
                        f"Tool '{tool_name}' returned:\n{result.output}\n\n"
                        f"Now write {self.character.name}'s response incorporating this result. "
                        f"Stay in character."
                    )},
                ]
                reply_text = await chat_completion(followup_context)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Tool call failed: {e}")
                reply_text = TOOL_CALL_PATTERN.sub("", reply_text).strip()

        if reply_text.strip():
            self._save_message("assistant", reply_text)

        # Background memory extraction (non-blocking)
        if event.text:
            try:
                await extract_memories(self.db, self.session, event.text, reply_text)
            except Exception as e:
                logger.warning(f"Memory extraction failed: {e}")

        self.character.message_count = (self.character.message_count or 0) + 2
        self.db.commit()

        media = []
        for result in [r for r in [tool_call_match] if r]:
            pass

        return AgentReply(
            text=reply_text,
            tool_calls_used=tool_calls_used,
            session_id=self.session.id,
            character_id=self.character.id,
        )

    async def process_stream(self, event: InboundEvent) -> AsyncGenerator[str, None]:
        """Streaming variant for web frontend compatibility."""
        if event.text:
            self._save_message("user", event.text)

        tool_schemas_text = self.registry.get_schemas_text()
        context = build_context(
            self.character, self.session, self.db,
            tool_schemas_text=tool_schemas_text,
        )

        full_reply = ""
        async for chunk in chat_completion_stream(context):
            full_reply += chunk
            yield chunk

        if full_reply.strip():
            self._save_message("assistant", full_reply)
            self.character.message_count = (self.character.message_count or 0) + 2
            self.db.commit()

        if event.text:
            try:
                await extract_memories(self.db, self.session, event.text, full_reply)
            except Exception:
                pass

    def _save_message(self, role: str, content: str):
        msg = GatewayMessage(
            session_id=self.session.id,
            role=role,
            content=content,
        )
        self.db.add(msg)
        self.db.commit()
