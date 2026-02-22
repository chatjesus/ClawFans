"""
Base channel adapter: abstract interface all platform adapters must implement.
"""
from abc import ABC, abstractmethod
from gateway.contracts import InboundEvent, AgentReply


class ChannelAdapter(ABC):
    """Abstract base for all channel adapters (Telegram, Discord, etc.)."""

    @abstractmethod
    async def send_reply(self, reply: AgentReply, platform_user_id: str) -> bool:
        """Send a reply back to the platform user. Returns True on success."""
        ...

    @abstractmethod
    async def send_typing(self, platform_user_id: str) -> None:
        """Send a typing indicator."""
        ...

    @abstractmethod
    def parse_inbound(self, raw_payload: dict) -> InboundEvent:
        """Convert a platform-specific payload into a normalized InboundEvent."""
        ...
