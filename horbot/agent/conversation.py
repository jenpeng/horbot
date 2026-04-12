"""
Agent 间对话上下文管理

提供 Agent 间对话的上下文构建和管理功能。
"""

from dataclasses import dataclass, field
from enum import Enum
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

_SUMMARY_TRIGGER_MARKER = "现在直接面向用户输出最终总结"
_GENERIC_MENTION_PATTERN = re.compile(r"@[\w\u4e00-\u9fff-]+")
_SUMMARY_HANDOFF_KEYWORDS = (
    "总结",
    "收尾",
    "汇总",
    "汇报",
    "给用户",
    "最终答复",
    "最终回复",
    "最终规划",
)
_RELAY_COORDINATION_KEYWORDS = (
    "接力",
    "接棒",
    "轮到",
    "交给",
    "继续补",
    "继续讨论",
    "继续拆",
    "继续推演",
    "你继续",
    "请你继续",
    "等你",
    "等 ",
    "回给",
    "收口",
)


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


def _normalize_agent_mention_token(text: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff-]+", "", (text or "")).lower()


def _build_agent_mention_regex(agent_name: str, agent_id: str) -> re.Pattern[str] | None:
    variants: set[str] = set()
    for value in (agent_name, agent_id):
        if value:
            variants.add(value.strip())

    if agent_name:
        first_token = re.split(r"\s+", agent_name.strip(), maxsplit=1)[0]
        if first_token:
            variants.add(first_token)
        normalized_name = _normalize_agent_mention_token(agent_name)
        if normalized_name:
            variants.add(normalized_name)

    variants = {item for item in variants if item}
    if not variants:
        return None

    escaped = "|".join(sorted((re.escape(item) for item in variants), key=len, reverse=True))
    return re.compile(rf"@(?:{escaped})(?=$|[\s,，。！？；;:：])")


def _is_user_summary_turn(conversation_ctx: ConversationContext | None) -> bool:
    if not conversation_ctx or conversation_ctx.conversation_type != ConversationType.USER_TO_AGENT:
        return False
    trigger_message = (conversation_ctx.trigger_message or "").strip()
    return _SUMMARY_TRIGGER_MARKER in trigger_message


def _sanitize_summary_turn_message(
    content: str,
    *,
    target_agent_id: str,
    target_agent_name: str,
    metadata: dict,
) -> str:
    text = (content or "").strip()
    if not text:
        return ""

    target_mention_regex = _build_agent_mention_regex(target_agent_name, target_agent_id)
    directed_to_target = metadata.get("target") == target_agent_id
    authored_by_target = metadata.get("agent_id") == target_agent_id
    segments = re.findall(r"[^。！？!?；;，,\n]+[。！？!?；;，,\n]*", text) or [text]
    sanitized_segments: list[str] = []

    for segment in segments:
        match = re.match(r"(?P<body>.*?)(?P<suffix>[。！？!?；;，,\n]*)$", segment, re.S)
        if not match:
            continue
        body = match.group("body").strip()
        suffix = match.group("suffix")
        if not body:
            continue

        normalized = re.sub(r"\s+", "", body)
        mentions_any_agent = bool(_GENERIC_MENTION_PATTERN.search(body))
        mentions_target_agent = bool(target_mention_regex.search(body)) if target_mention_regex else False
        has_summary_handoff = any(keyword in normalized for keyword in _SUMMARY_HANDOFF_KEYWORDS)
        has_relay_coordination = any(keyword in normalized for keyword in _RELAY_COORDINATION_KEYWORDS)

        if authored_by_target and mentions_any_agent:
            continue
        if has_summary_handoff and (directed_to_target or mentions_target_agent or mentions_any_agent):
            continue
        if has_relay_coordination and mentions_any_agent:
            continue

        body = re.sub(r"^(?:@\S+\s*)+", "", body).strip(" \t,，:：;-")
        body = re.sub(r"\s{2,}", " ", body).strip()
        if not body:
            continue

        sanitized_segments.append(f"{body}{suffix}")

    sanitized = "".join(sanitized_segments).strip()
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)
    return sanitized


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
    is_user_summary_turn = _is_user_summary_turn(conversation_ctx)
    
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
                if not is_user_summary_turn:
                    filtered.append(msg)
            elif role == "assistant":
                if is_group_chat:
                    filtered.append(msg)
                    for tc in msg.get("tool_calls", []):
                        tool_call_ids_to_include.add(tc.get("id"))
                elif msg_agent_id == target_agent_id or not msg_agent_id:
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
            if is_group_chat and is_user_summary_turn and entry["content"]:
                entry["content"] = _sanitize_summary_turn_message(
                    entry["content"],
                    target_agent_id=target_agent_id,
                    target_agent_name=target_agent_name,
                    metadata=metadata,
                )
                if not entry["content"] and not m.get("tool_calls"):
                    continue
            
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
