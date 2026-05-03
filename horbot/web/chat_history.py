"""Chat history normalization and paging helpers."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from loguru import logger

from horbot.session.manager import SessionManager
from horbot.web.message_content import clean_message_content
from horbot.web.upload_preview import _normalize_saved_assistant_content_and_files

def ensure_history_message_id(message: dict[str, Any]) -> str:
    """Return a stable message id for legacy history entries missing `id`.

    Older persisted assistant messages may not have message ids. The frontend
    reloads history multiple times, so random fallback ids cause duplicates to
    be appended and later grouped into one oversized bubble. Use a stable
    fingerprint instead.
    """
    existing_id = message.get("id")
    if isinstance(existing_id, str) and existing_id.strip():
        return existing_id

    metadata = message.get("metadata") or {}
    fingerprint_source = {
        "role": message.get("role") or "",
        "timestamp": message.get("timestamp") or "",
        "content": clean_message_content(str(message.get("content") or "")),
        "agent_id": metadata.get("agent_id") or "",
        "agent_name": metadata.get("agent_name") or "",
        "turn_id": metadata.get("turn_id") or "",
        "request_id": metadata.get("request_id") or "",
    }
    payload = json.dumps(fingerprint_source, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
    return f"legacy-{digest}"


def _history_message_fingerprint(message: dict[str, Any]) -> str:
    metadata = message.get("metadata") or {}
    fingerprint_source = {
        "role": message.get("role") or "",
        "timestamp": message.get("timestamp") or "",
        "content": clean_message_content(str(message.get("content") or "")),
        "agent_id": metadata.get("agent_id") or "",
        "agent_name": metadata.get("agent_name") or "",
        "turn_id": metadata.get("turn_id") or "",
        "request_id": metadata.get("request_id") or "",
    }
    payload = json.dumps(fingerprint_source, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _history_sort_key(message: dict[str, Any]) -> tuple[int, datetime]:
    timestamp = message.get("timestamp")
    if not isinstance(timestamp, str) or not timestamp.strip():
        return (1, datetime.min)
    try:
        return (0, datetime.fromisoformat(timestamp))
    except ValueError:
        return (1, datetime.min)


def _merge_history_messages(message_groups: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    index_by_id: dict[str, int] = {}
    index_by_fingerprint: dict[str, int] = {}

    for group in message_groups:
        for raw_message in group:
            message = dict(raw_message)
            message["id"] = ensure_history_message_id(message)
            fingerprint = _history_message_fingerprint(message)
            existing_index = index_by_id.get(message["id"])
            if existing_index is None:
                existing_index = index_by_fingerprint.get(fingerprint)

            if existing_index is None:
                next_index = len(merged)
                merged.append(message)
                index_by_id[message["id"]] = next_index
                index_by_fingerprint[fingerprint] = next_index
                continue

            existing_message = merged[existing_index]
            merged_message = {
                **existing_message,
                **message,
                "content": message.get("content") or existing_message.get("content") or "",
                "files": message.get("files") or existing_message.get("files"),
                "execution_steps": message.get("execution_steps") or existing_message.get("execution_steps"),
                "metadata": {
                    **(existing_message.get("metadata") or {}),
                    **(message.get("metadata") or {}),
                },
            }
            merged[existing_index] = merged_message
            index_by_id[merged_message["id"]] = existing_index
            index_by_fingerprint[fingerprint] = existing_index

    return [
        item["message"]
        for item in sorted(
            (
                {"message": message, "index": index}
                for index, message in enumerate(merged)
            ),
            key=lambda item: (_history_sort_key(item["message"]), item["index"]),
        )
    ]


def _unique_session_managers(managers: list[SessionManager]) -> list[SessionManager]:
    unique: list[SessionManager] = []
    seen_dirs: set[str] = set()
    for manager in managers:
        sessions_dir = str(Path(manager.sessions_dir).resolve())
        if sessions_dir in seen_dirs:
            continue
        seen_dirs.add(sessions_dir)
        unique.append(manager)
    return unique


def _legacy_agent_session_managers(agent) -> list[SessionManager]:
    candidates: list[SessionManager] = []
    try:
        primary_sessions_dir = Path(agent.get_sessions_dir()).resolve()
        workspace_sessions_dir = (Path(agent.get_workspace()) / "sessions").resolve()
        if workspace_sessions_dir != primary_sessions_dir and workspace_sessions_dir.exists():
            candidates.append(SessionManager(workspace=workspace_sessions_dir))
    except Exception as exc:
        logger.warning("Failed to resolve legacy session path for agent {}: {}", getattr(agent, "id", "unknown"), exc)
    return candidates


def _load_merged_session_messages(session_key: str, managers: list[SessionManager]) -> list[dict[str, Any]]:
    message_groups: list[list[dict[str, Any]]] = []
    for manager in _unique_session_managers(managers):
        # History endpoints must reflect the latest persisted conversation even
        # when another SessionManager instance saved the same session.
        manager.invalidate(session_key)
        session = manager.get(session_key)
        if session and session.messages:
            message_groups.append(list(session.messages))
    if not message_groups:
        return []
    return _merge_history_messages(message_groups)


DEFAULT_CONVERSATION_HISTORY_LIMIT = 80
MAX_CONVERSATION_HISTORY_LIMIT = 200
DEFAULT_CONVERSATION_AROUND_CONTEXT = 20
MAX_CONVERSATION_AROUND_CONTEXT = 100
DEFAULT_CONVERSATION_SEARCH_LIMIT = 20
MAX_CONVERSATION_SEARCH_LIMIT = 100


def _clamp_history_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_CONVERSATION_HISTORY_LIMIT
    return max(1, min(int(limit), MAX_CONVERSATION_HISTORY_LIMIT))


def _clamp_history_context(value: int | None) -> int:
    if value is None:
        return DEFAULT_CONVERSATION_AROUND_CONTEXT
    return max(0, min(int(value), MAX_CONVERSATION_AROUND_CONTEXT))


def _clamp_conversation_search_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_CONVERSATION_SEARCH_LIMIT
    return max(1, min(int(limit), MAX_CONVERSATION_SEARCH_LIMIT))


def _find_history_message_position(messages: list[dict[str, Any]], message_id: str | None) -> int | None:
    if not message_id:
        return None

    for index, message in enumerate(messages):
        resolved_message_id = message.get("id") or ensure_history_message_id(message)
        if resolved_message_id == message_id:
            return index
    return None


def _slice_history_window(
    messages: list[dict[str, Any]],
    *,
    limit: int,
    before_id: str | None = None,
    after_id: str | None = None,
    around_id: str | None = None,
    context_before: int | None = None,
    context_after: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    total_messages = len(messages)
    if total_messages == 0:
        return [], {
            "limit": limit,
            "returned_messages": 0,
            "total_messages": 0,
            "has_more_before": False,
            "has_more_after": False,
            "oldest_message_id": None,
            "newest_message_id": None,
        }

    start = 0
    end = total_messages
    anchor_index = None

    if around_id:
        anchor_index = _find_history_message_position(messages, around_id)
        if anchor_index is None:
            start = max(0, total_messages - limit)
            end = total_messages
        else:
            safe_before = _clamp_history_context(context_before)
            safe_after = _clamp_history_context(context_after)
            start = max(0, anchor_index - safe_before)
            end = min(total_messages, anchor_index + safe_after + 1)
    elif after_id:
        after_index = _find_history_message_position(messages, after_id)
        if after_index is None:
            start = total_messages
            end = total_messages
        else:
            start = min(total_messages, after_index + 1)
            end = min(total_messages, start + limit)
    elif before_id:
        before_index = _find_history_message_position(messages, before_id)
        end = before_index if before_index is not None else total_messages
        start = max(0, end - limit)
    else:
        end = total_messages
        start = max(0, end - limit)

    window = messages[start:end]
    oldest_message_id = ensure_history_message_id(window[0]) if window else None
    newest_message_id = ensure_history_message_id(window[-1]) if window else None

    return window, {
        "limit": limit,
        "returned_messages": len(window),
        "total_messages": total_messages,
        "has_more_before": start > 0,
        "has_more_after": end < total_messages,
        "oldest_message_id": oldest_message_id,
        "newest_message_id": newest_message_id,
        "anchor_message_id": around_id if anchor_index is not None else None,
    }


def _normalize_history_message_for_api(message: dict[str, Any]) -> dict[str, Any]:
    cleaned_msg = dict(message)
    cleaned_msg["id"] = ensure_history_message_id(cleaned_msg)
    if cleaned_msg.get("role") == "assistant":
        normalized_content, normalized_files = _normalize_saved_assistant_content_and_files(
            cleaned_msg.get("content"),
            cleaned_msg.get("files"),
        )
        cleaned_msg["content"] = normalized_content
        if normalized_files:
            cleaned_msg["files"] = normalized_files
        else:
            cleaned_msg.pop("files", None)
    elif "content" in cleaned_msg and isinstance(cleaned_msg["content"], str):
        cleaned_msg["content"] = clean_message_content(cleaned_msg["content"])
    return cleaned_msg


def _is_displayable_history_message(message: dict[str, Any]) -> bool:
    if message.get("_type") == "metadata":
        return False
    if message.get("role") == "tool":
        return False

    content = message.get("content")
    has_content = isinstance(content, str) and bool(content.strip())
    has_tool_calls = isinstance(message.get("tool_calls"), list) and bool(message.get("tool_calls"))
    has_files = isinstance(message.get("files"), list) and bool(message.get("files"))
    has_execution_steps = isinstance(message.get("execution_steps"), list) and bool(message.get("execution_steps"))

    if not has_content and not has_tool_calls and not has_files and not has_execution_steps:
        return False
    if has_content and isinstance(content, str) and content.startswith("Message sent to "):
        return False
    return True


def _prepare_conversation_history_messages(raw_messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared_messages: list[dict[str, Any]] = []
    for raw_message in raw_messages:
        normalized_message = _normalize_history_message_for_api(raw_message)
        if not _is_displayable_history_message(normalized_message):
            continue
        prepared_messages.append(normalized_message)
    return prepared_messages


def _build_history_search_preview(content: str, query: str, *, radius: int = 56) -> str:
    normalized_content = re.sub(r"\s+", " ", content or "").strip()
    normalized_query = re.sub(r"\s+", " ", query or "").strip()
    if not normalized_content:
        return ""
    if not normalized_query:
        return normalized_content[: radius * 2]

    content_folded = normalized_content.casefold()
    query_folded = normalized_query.casefold()
    match_index = content_folded.find(query_folded)
    if match_index < 0:
        return normalized_content[: radius * 2]

    start = max(0, match_index - radius)
    end = min(len(normalized_content), match_index + len(normalized_query) + radius)
    preview = normalized_content[start:end].strip()
    if start > 0:
        preview = f"...{preview}"
    if end < len(normalized_content):
        preview = f"{preview}..."
    return preview


def _parse_optional_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _find_session_message_index(
    session,
    *,
    message_id: str | None = None,
    turn_id: str | None = None,
    role: str | None = None,
) -> int:
    for idx in range(len(session.messages) - 1, -1, -1):
        msg = session.messages[idx]
        if role and msg.get("role") != role:
            continue
        if message_id and msg.get("id") == message_id:
            return idx
        metadata = msg.get("metadata", {})
        if turn_id and metadata.get("turn_id") == turn_id:
            return idx
    return -1
