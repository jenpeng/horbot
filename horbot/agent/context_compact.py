"""Context compression module - 3-layer strategy with topic segmentation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from loguru import logger


@dataclass
class TopicSegment:
    """A segment of conversation focused on a single topic."""
    
    topic: str
    start_idx: int
    end_idx: int
    messages: list[dict] = field(default_factory=list)
    summary: str = ""
    
    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "start_idx": self.start_idx,
            "end_idx": self.end_idx,
            "message_count": len(self.messages),
            "summary": self.summary,
        }


@dataclass
class CompressionResult:
    """Result of context compression."""
    
    messages: list[dict]
    original_tokens: int
    compressed_tokens: int
    reduction_percent: float
    was_compressed: bool
    topics: list[TopicSegment] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "original_tokens": self.original_tokens,
            "compressed_tokens": self.compressed_tokens,
            "reduction_percent": round(self.reduction_percent, 1),
            "was_compressed": self.was_compressed,
            "topics": [t.to_dict() for t in self.topics],
        }


TOPIC_KEYWORDS = {
    "code": ["代码", "函数", "类", "方法", "变量", "bug", "修复", "实现", "code", "function", "class", "method", "variable", "fix", "implement"],
    "project": ["项目", "工程", "horbot", "project", "repo", "repository", "仓库"],
    "file": ["文件", "目录", "路径", "file", "directory", "path", "folder"],
    "config": ["配置", "设置", "参数", "config", "setting", "parameter", "option"],
    "test": ["测试", "test", "testing", "unittest", "pytest"],
    "api": ["api", "接口", "endpoint", "请求", "response", "request"],
    "database": ["数据库", "database", "sql", "表", "table", "query"],
    "ui": ["界面", "前端", "页面", "ui", "frontend", "page", "component"],
    "deploy": ["部署", "发布", "deploy", "release", "docker", "k8s"],
    "doc": ["文档", "说明", "doc", "documentation", "readme"],
    "git": ["git", "commit", "branch", "merge", "pull", "push", "分支"],
    "chat": ["聊天", "对话", "chat", "conversation", "消息", "message"],
    "other": [],
}

TOPIC_INDICATORS = [
    r"^(让我|帮我|请|can you|please|help me|i want|i need)",
    r"^(现在|接下来|then|next|now)",
    r"^(另外|还有|also|another|besides)",
    r"^(换个话题|新话题|new topic|by the way)",
    r"^(回到|继续|back to|continue)",
]


def extract_topic_from_message(message: dict) -> str:
    """Extract the main topic from a single message.
    
    Returns a topic label based on keywords found in the message.
    """
    content = message.get("content", "")
    
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    tool_name = block.get("name", "")
                    text_parts.append(f"tool:{tool_name}")
        content = " ".join(text_parts)
    
    if not isinstance(content, str):
        return "other"
    
    content_lower = content.lower()
    
    scores = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        if topic == "other":
            continue
        score = sum(1 for kw in keywords if kw in content_lower)
        if score > 0:
            scores[topic] = score
    
    if scores:
        return max(scores, key=scores.get)
    
    return "other"


def calculate_topic_similarity(topic1: str, topic2: str) -> float:
    """Calculate similarity between two topics."""
    if topic1 == topic2:
        return 1.0
    
    related_topics = {
        ("code", "project"): 0.6,
        ("code", "test"): 0.7,
        ("code", "file"): 0.5,
        ("project", "config"): 0.5,
        ("api", "database"): 0.5,
        ("ui", "code"): 0.4,
        ("git", "project"): 0.6,
        ("doc", "project"): 0.5,
    }
    
    key = tuple(sorted([topic1, topic2]))
    return related_topics.get(key, 0.0)


def detect_topic_change(
    messages: list[dict],
    min_segment_size: int = 3,
    similarity_threshold: float = 0.4,
) -> list[TopicSegment]:
    """Detect topic segments in a conversation.
    
    Analyzes messages to identify topic boundaries and groups
    related messages into segments.
    
    Args:
        messages: List of message dicts
        min_segment_size: Minimum messages per segment
        similarity_threshold: Threshold for considering topics similar
        
    Returns:
        List of TopicSegment objects
    """
    if not messages:
        return []
    
    non_system = [m for m in messages if m.get("role") != "system"]
    if not non_system:
        return []
    
    topics_per_message = []
    for msg in non_system:
        topic = extract_topic_from_message(msg)
        topics_per_message.append(topic)
    
    segments = []
    current_segment_start = 0
    current_topic = topics_per_message[0] if topics_per_message else "other"
    
    for i, topic in enumerate(topics_per_message):
        similarity = calculate_topic_similarity(current_topic, topic)
        
        is_explicit_switch = False
        content = non_system[i].get("content", "")
        if isinstance(content, str):
            for pattern in TOPIC_INDICATORS:
                if re.search(pattern, content, re.IGNORECASE):
                    is_explicit_switch = True
                    break
        
        if similarity < similarity_threshold or is_explicit_switch:
            if i - current_segment_start >= min_segment_size:
                segment_messages = non_system[current_segment_start:i]
                segments.append(TopicSegment(
                    topic=current_topic,
                    start_idx=current_segment_start,
                    end_idx=i - 1,
                    messages=segment_messages,
                ))
                current_segment_start = i
                current_topic = topic
            else:
                current_topic = topic
    
    if current_segment_start < len(non_system):
        segment_messages = non_system[current_segment_start:]
        segments.append(TopicSegment(
            topic=current_topic,
            start_idx=current_segment_start,
            end_idx=len(non_system) - 1,
            messages=segment_messages,
        ))
    
    return segments


def compress_segment_to_summary(segment: TopicSegment) -> str:
    """Compress a topic segment to a concise summary.
    
    Creates a topic-specific summary that preserves context
    without mixing with other topics.
    """
    messages = segment.messages
    topic = segment.topic
    
    user_queries = []
    assistant_actions = []
    tools_used = []
    key_decisions = []
    
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        
        if role == "user":
            if isinstance(content, str):
                query = content.strip()[:150]
                if query:
                    user_queries.append(query)
        elif role == "assistant":
            if isinstance(content, str):
                if any(word in content.lower() for word in ["完成", "成功", "done", "success", "fixed", "修复"]):
                    key_decisions.append(content[:100])
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tools_used.append(block.get("name", "unknown"))
    
    summary_parts = [f"[Topic: {topic.upper()}]"]
    
    if user_queries:
        unique_queries = list(dict.fromkeys(user_queries))[-3:]
        summary_parts.append(f"用户请求: {'; '.join(unique_queries)}")
    
    if tools_used:
        unique_tools = list(dict.fromkeys(tools_used))[-5:]
        summary_parts.append(f"使用工具: {', '.join(unique_tools)}")
    
    if key_decisions:
        summary_parts.append(f"关键结果: {key_decisions[-1]}")
    
    segment.summary = " | ".join(summary_parts)
    return segment.summary


def estimate_tokens(messages: list[dict]) -> int:
    """Estimate token count for messages.
    
    Uses a simple heuristic: ~4 characters per token for most text.
    This is a rough estimate but sufficient for triggering compression.
    """
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += len(content) // 4
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        total += len(block.get("text", "")) // 4
                    elif block.get("type") == "tool_result":
                        total += len(str(block.get("content", ""))) // 4
                    elif block.get("type") == "tool_use":
                        total += len(str(block.get("input", {}))) // 4
        total += 10
    return total


def extract_tool_info(messages: list[dict]) -> list[dict]:
    """Extract tool call information from messages for summary."""
    tool_calls = []
    for msg in messages:
        content = msg.get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "tool_use":
                        tool_calls.append({
                            "name": block.get("name", "unknown"),
                            "input": str(block.get("input", {}))[:100]
                        })
    return tool_calls


def compress_tool_results(content: list[dict]) -> list[dict]:
    """Compress tool results to summaries."""
    compressed = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_result":
            result_content = block.get("content", "")
            if isinstance(result_content, str) and len(result_content) > 2000:
                compressed.append({
                    "type": "tool_result",
                    "tool_use_id": block.get("tool_use_id", ""),
                    "content": f"[Compressed result: {len(result_content)} chars] {result_content[:500]}..."
                })
            else:
                compressed.append(block)
        else:
            compressed.append(block)
    return compressed


def compress_to_summary(messages: list[dict]) -> str:
    """Compress a list of messages to a summary (legacy function)."""
    topics = set()
    tools_used = []
    user_queries = []
    
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        
        if role == "user":
            if isinstance(content, str) and len(content) < 200:
                user_queries.append(content[:100])
        elif role == "assistant":
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tools_used.append(block.get("name", "unknown"))
        
        if isinstance(content, str):
            words = content.lower().split()
            for word in words[:20]:
                if len(word) > 5:
                    topics.add(word)
    
    summary_parts = []
    
    if user_queries:
        summary_parts.append(f"User queries: {'; '.join(user_queries[-5:])}")
    
    if tools_used:
        unique_tools = list(dict.fromkeys(tools_used))
        summary_parts.append(f"Tools used: {', '.join(unique_tools[:10])}")
    
    if topics:
        summary_parts.append(f"Key topics: {', '.join(list(topics)[:10])}")
    
    if summary_parts:
        return " | ".join(summary_parts)
    return "Previous conversation context"


def segmented_compact_context(
    messages: list[dict],
    max_tokens: int = 100000,
    preserve_recent: int = 10,
    compress_tool_results_flag: bool = True,
    return_details: bool = False,
) -> list[dict] | CompressionResult:
    """Apply topic-aware segmented context compression.
    
    This improved compression strategy:
    1. Detects topic segments in the conversation
    2. Compresses each segment independently
    3. Preserves topic boundaries in the summary
    4. Keeps recent context intact
    
    Args:
        messages: List of message dicts
        max_tokens: Token threshold to trigger compression
        preserve_recent: Number of recent messages to preserve
        compress_tool_results_flag: Whether to compress long tool results
        return_details: If True, return CompressionResult with details
        
    Returns:
        Compressed message list, or CompressionResult if return_details=True
    """
    current_tokens = estimate_tokens(messages)
    
    if current_tokens <= max_tokens:
        logger.debug(f"Context under threshold: {current_tokens} <= {max_tokens}")
        if return_details:
            return CompressionResult(
                messages=messages,
                original_tokens=current_tokens,
                compressed_tokens=current_tokens,
                reduction_percent=0.0,
                was_compressed=False,
            )
        return messages
    
    logger.info(f"Segmented context compression triggered: {current_tokens} > {max_tokens}")
    
    result = []
    
    system_messages = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]
    
    result.extend(system_messages)
    
    if len(non_system) <= preserve_recent:
        result.extend(non_system)
        if return_details:
            return CompressionResult(
                messages=result,
                original_tokens=current_tokens,
                compressed_tokens=current_tokens,
                reduction_percent=0.0,
                was_compressed=False,
            )
        return result
    
    middle_messages = non_system[:-preserve_recent]
    recent_messages = non_system[-preserve_recent:]
    
    segments = detect_topic_change(middle_messages)
    
    if len(segments) <= 1:
        summary = compress_to_summary(middle_messages)
        result.append({
            "role": "user",
            "content": f"[Previous conversation summary]\n{summary}"
        })
    else:
        segment_summaries = []
        for i, segment in enumerate(segments):
            summary = compress_segment_to_summary(segment)
            segment_summaries.append(f"\n{summary}")
        
        combined_summary = "\n".join([
            "[Previous conversation - Topic Segments]",
            "=" * 40,
            *segment_summaries,
        ])
        
        result.append({
            "role": "user",
            "content": combined_summary
        })
    
    if compress_tool_results_flag:
        for msg in recent_messages:
            content = msg.get("content")
            if isinstance(content, list):
                msg["content"] = compress_tool_results(content)
    
    result.extend(recent_messages)
    
    new_tokens = estimate_tokens(result)
    reduction = (1 - new_tokens / current_tokens) * 100
    logger.info(f"Context compressed: {current_tokens} -> {new_tokens} tokens ({reduction:.1f}% reduction, {len(segments)} topics)")
    
    if return_details:
        return CompressionResult(
            messages=result,
            original_tokens=current_tokens,
            compressed_tokens=new_tokens,
            reduction_percent=reduction,
            was_compressed=True,
            topics=segments,
        )
    
    return result


def compact_context(
    messages: list[dict],
    max_tokens: int = 100000,
    preserve_recent: int = 10,
    compress_tool_results_flag: bool = True,
    return_details: bool = False,
    use_segmentation: bool = True,
) -> list[dict] | CompressionResult:
    """Apply context compression with optional topic segmentation.
    
    Layer 1 (Preserve): System messages + recent N messages
    Layer 2 (Compress): Middle conversation compressed to topic-aware summary
    Layer 3 (Discard): Redundant information removed
    
    Args:
        messages: List of message dicts
        max_tokens: Token threshold to trigger compression
        preserve_recent: Number of recent messages to preserve
        compress_tool_results_flag: Whether to compress long tool results
        return_details: If True, return CompressionResult with details
        use_segmentation: If True, use topic-aware segmentation (default)
        
    Returns:
        Compressed message list, or CompressionResult if return_details=True
    """
    if use_segmentation:
        return segmented_compact_context(
            messages=messages,
            max_tokens=max_tokens,
            preserve_recent=preserve_recent,
            compress_tool_results_flag=compress_tool_results_flag,
            return_details=return_details,
        )
    
    current_tokens = estimate_tokens(messages)
    
    if current_tokens <= max_tokens:
        logger.debug(f"Context under threshold: {current_tokens} <= {max_tokens}")
        if return_details:
            return CompressionResult(
                messages=messages,
                original_tokens=current_tokens,
                compressed_tokens=current_tokens,
                reduction_percent=0.0,
                was_compressed=False,
            )
        return messages
    
    logger.info(f"Context compression triggered: {current_tokens} > {max_tokens}")
    
    result = []
    
    system_messages = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]
    
    result.extend(system_messages)
    
    if len(non_system) <= preserve_recent:
        result.extend(non_system)
        if return_details:
            return CompressionResult(
                messages=result,
                original_tokens=current_tokens,
                compressed_tokens=current_tokens,
                reduction_percent=0.0,
                was_compressed=False,
            )
        return result
    
    middle_messages = non_system[:-preserve_recent]
    recent_messages = non_system[-preserve_recent:]
    
    summary = compress_to_summary(middle_messages)
    
    tool_info = extract_tool_info(middle_messages)
    if tool_info:
        summary += f"\n\nTool calls in previous context:\n"
        for tc in tool_info[-10:]:
            summary += f"- {tc['name']}: {tc['input']}\n"
    
    result.append({
        "role": "user",
        "content": f"[Previous conversation summary]\n{summary}"
    })
    
    if compress_tool_results_flag:
        for msg in recent_messages:
            content = msg.get("content")
            if isinstance(content, list):
                msg["content"] = compress_tool_results(content)
    
    result.extend(recent_messages)
    
    new_tokens = estimate_tokens(result)
    reduction = (1 - new_tokens / current_tokens) * 100
    logger.info(f"Context compressed: {current_tokens} -> {new_tokens} tokens ({reduction:.1f}% reduction)")
    
    if return_details:
        return CompressionResult(
            messages=result,
            original_tokens=current_tokens,
            compressed_tokens=new_tokens,
            reduction_percent=reduction,
            was_compressed=True,
        )
    
    return result
