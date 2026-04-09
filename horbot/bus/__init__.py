"""Message bus module for decoupled channel-agent communication."""

from horbot.bus.events import InboundMessage, OutboundMessage
from horbot.bus.queue import MessageBus

__all__ = ["MessageBus", "InboundMessage", "OutboundMessage"]
