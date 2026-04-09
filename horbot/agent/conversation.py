"""
Agent 间对话上下文管理

提供 Agent 间对话的上下文构建和管理功能。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ConversationType(Enum):
    USER_TO_AGENT = "user_to_agent"
    AGENT_TO_AGENT = "agent_to_agent"


@dataclass
class ConversationContext:
    conversation_type: ConversationType
    source: str
    source_name: str
    target: str
    target_name: str
    trigger_message: Optional[str] = None
    
    def get_speaking_to(self) -> str:
        if self.conversation_type == ConversationType.USER_TO_AGENT:
            return "用户"
        else:
            return self.source_name
    
    def get_conversation_description(self) -> str:
        if self.conversation_type == ConversationType.USER_TO_AGENT:
            return f"用户正在和你（{self.target_name}）说话"
        else:
            return f"{self.source_name} 正在和你（{self.target_name}）对话"
    
    def to_dict(self) -> dict:
        return {
            "conversation_type": self.conversation_type.value,
            "source": self.source,
            "source_name": self.source_name,
            "target": self.target,
            "target_name": self.target_name,
            "trigger_message": self.trigger_message,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ConversationContext":
        return cls(
            conversation_type=ConversationType(data["conversation_type"]),
            source=data["source"],
            source_name=data["source_name"],
            target=data["target"],
            target_name=data["target_name"],
            trigger_message=data.get("trigger_message"),
        )


@dataclass
class ConversationChain:
    conversations: list[ConversationContext] = field(default_factory=list)
    
    def add_conversation(self, context: ConversationContext):
        self.conversations.append(context)
    
    def get_last_conversation(self) -> Optional[ConversationContext]:
        return self.conversations[-1] if self.conversations else None
    
    def get_conversations_for_agent(self, agent_id: str) -> list[ConversationContext]:
        result = []
        for conv in self.conversations:
            if conv.target == agent_id or conv.source == agent_id:
                result.append(conv)
        return result
    
    def to_dict(self) -> dict:
        return {
            "conversations": [c.to_dict() for c in self.conversations],
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ConversationChain":
        return cls(
            conversations=[ConversationContext.from_dict(c) for c in data.get("conversations", [])],
        )


def build_conversation_context(
    conversation_type: ConversationType,
    source_id: str,
    source_name: str,
    target_id: str,
    target_name: str,
    trigger_message: Optional[str] = None,
) -> ConversationContext:
    ctx = ConversationContext(
        conversation_type=conversation_type,
        source=source_id,
        source_name=source_name,
        target=target_id,
        target_name=target_name,
        trigger_message=trigger_message,
    )
    logger.info(f"[ConversationContext] Created: {ctx.get_conversation_description()}")
    return ctx


def filter_messages_for_agent(
    messages: list[dict],
    agent_id: str,
    agent_name: str,
    conversation_type: str | None = None,
) -> list[dict]:
    """Filter messages for a specific agent based on conversation context.
    
    Args:
        messages: List of messages to filter
        agent_id: The agent's ID
        agent_name: The agent's name
        conversation_type: Type of conversation (for context-aware filtering)
    
    Returns:
        Filtered list of messages relevant to this agent
    """
    filtered = []
    for msg in messages:
        role = msg.get("role", "")
        metadata = msg.get("metadata", {})
        source = metadata.get("source", "")
        target = metadata.get("target", "")
        msg_agent_id = metadata.get("agent_id", "")
        
        if role == "user":
            filtered.append(msg)
        elif role == "assistant":
            if msg_agent_id == agent_id:
                filtered.append(msg)
            elif source == agent_id:
                filtered.append(msg)
            elif target == agent_id:
                filtered.append(msg)
            elif not source and not target and not msg_agent_id:
                filtered.append(msg)
    
    return filtered


def format_history_for_agent(
    messages: list[dict],
    target_agent_id: str,
    target_agent_name: str,
    conversation_ctx: ConversationContext | None = None,
    is_group_chat: bool = False,
) -> list[dict]:
    """Format message history for a specific agent with proper context.
    
    This function:
    1. Filters messages to only include those relevant to the agent
    2. Formats messages with proper XML tags to show who said what
    3. Ensures tool_calls and tool messages are kept together
    
    Args:
        messages: List of messages from session history
        target_agent_id: The target agent's ID
        target_agent_name: The target agent's name
        conversation_ctx: Optional conversation context for agent-to-agent filtering
        is_group_chat: Whether this is a group chat environment
    
    Returns:
        Formatted list of messages for the agent
    """
    tool_call_ids_to_include = set()
    
    if conversation_ctx and conversation_ctx.conversation_type == ConversationType.AGENT_TO_AGENT:
        filtered = []
        for msg in messages:
            role = msg.get("role", "")
            metadata = msg.get("metadata", {})
            source = metadata.get("source", "")
            target = metadata.get("target", "")
            msg_agent_id = metadata.get("agent_id", "")
            
            if role == "user":
                # In agent-to-agent handoff, the latest trigger_message already carries
                # the task payload. Keeping all raw user turns here tends to leak old
                # mention syntax back into the reply and makes agents parrot handoff text.
                continue
            elif role == "assistant":
                if msg_agent_id == target_agent_id:
                    filtered.append(msg)
                    for tc in msg.get("tool_calls", []):
                        tool_call_ids_to_include.add(tc.get("id"))
                elif target == target_agent_id:
                    filtered.append(msg)
                elif source == conversation_ctx.source:
                    filtered.append(msg)
                    for tc in msg.get("tool_calls", []):
                        tool_call_ids_to_include.add(tc.get("id"))
            elif role == "tool":
                if msg.get("tool_call_id") in tool_call_ids_to_include:
                    filtered.append(msg)
    else:
        filtered = []
        for msg in messages:
            role = msg.get("role", "")
            metadata = msg.get("metadata", {})
            msg_agent_id = metadata.get("agent_id", "")
            
            if role == "user":
                filtered.append(msg)
            elif role == "assistant":
                if msg_agent_id == target_agent_id or not msg_agent_id:
                    filtered.append(msg)
                    for tc in msg.get("tool_calls", []):
                        tool_call_ids_to_include.add(tc.get("id"))
            elif role == "tool":
                if msg.get("tool_call_id") in tool_call_ids_to_include:
                    filtered.append(msg)
    
    tool_call_ids_in_filtered = set()
    for msg in filtered:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                tool_call_ids_in_filtered.add(tc.get("id"))
    
    tool_results_in_filtered = set()
    for msg in filtered:
        if msg.get("role") == "tool":
            tool_results_in_filtered.add(msg.get("tool_call_id"))
    
    tool_calls_without_results = tool_call_ids_in_filtered - tool_results_in_filtered
    if tool_calls_without_results:
        for msg in messages:
            if msg.get("role") == "tool" and msg.get("tool_call_id") in tool_calls_without_results:
                filtered.append(msg)
    
    out = []
    for m in filtered:
        entry: dict = {"role": m.get("role", ""), "content": m.get("content", "")}
        
        if m.get("role") == "assistant":
            metadata = m.get("metadata", {})
            msg_agent_id = metadata.get("agent_id", "")
            
            if is_group_chat:
                # In group chat, if the message is from the target agent itself, keep it plain.
                # If it's from other agents, wrap it in <message> tag.
                if msg_agent_id and msg_agent_id != target_agent_id and entry["content"]:
                    source_name = metadata.get("agent_name", metadata.get("source_name", "Assistant"))
                    target_name = metadata.get("target_name", "")
                    if target_name:
                        entry["content"] = f'<message from="{source_name}" to="{target_name}">\n{entry["content"]}\n</message>'
                    else:
                        entry["content"] = f'<message from="{source_name}">\n{entry["content"]}\n</message>'
            else:
                # In single chat, keep simple user/assistant roles.
                # Do nothing, just keep the content as is.
                pass
        
        for k in ("tool_calls", "tool_call_id", "name"):
            if k in m:
                entry[k] = m[k]
        out.append(entry)
    
    return out
