"""Conversation management for internal chat sessions."""

from .manager import (
    ConversationType,
    Conversation,
    ConversationManager,
    get_conversation_manager,
)

__all__ = [
    "ConversationType",
    "Conversation",
    "ConversationManager",
    "get_conversation_manager",
]
