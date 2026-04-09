"""Event types for the message bus."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class InboundMessage:
    """Message received from a chat channel."""
    
    channel: str  # telegram, discord, slack, whatsapp
    sender_id: str  # User identifier
    chat_id: str  # Chat/channel identifier
    content: str  # Message text
    channel_instance_id: str | None = None  # Endpoint instance identifier
    target_agent_id: str | None = None  # Bound target agent
    timestamp: datetime = field(default_factory=datetime.now)
    media: list[str] = field(default_factory=list)  # Media URLs
    metadata: dict[str, Any] = field(default_factory=dict)  # Channel-specific data
    session_key_override: str | None = None  # Optional override for thread-scoped sessions
    
    @property
    def session_key(self) -> str:
        """Unique key for session identification."""
        routing_key = self.channel_instance_id or self.channel
        return self.session_key_override or f"{routing_key}:{self.chat_id}"


@dataclass
class OutboundMessage:
    """Message to send to a chat channel."""
    
    channel: str
    chat_id: str
    content: str
    channel_instance_id: str | None = None
    target_agent_id: str | None = None
    reply_to: str | None = None
    media: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.channel_instance_id is None:
            self.channel_instance_id = (
                self.metadata.get("channel_instance_id")
                or self.metadata.get("_channel_instance_id")
            )
        if self.target_agent_id is None:
            self.target_agent_id = (
                self.metadata.get("target_agent_id")
                or self.metadata.get("_target_agent_id")
            )

