"""Conversation history API routes."""

from __future__ import annotations

import re
from typing import Any, Callable, Optional

from fastapi import APIRouter, HTTPException, Response

from horbot.web.chat_history import (
    DEFAULT_CONVERSATION_AROUND_CONTEXT,
    DEFAULT_CONVERSATION_HISTORY_LIMIT,
    DEFAULT_CONVERSATION_SEARCH_LIMIT,
    _build_history_search_preview,
    _clamp_conversation_search_limit,
    _clamp_history_limit,
    _normalize_history_message_for_api,
    _parse_optional_iso_datetime,
    _prepare_conversation_history_messages,
    _slice_history_window,
)


async def get_conversation_messages_payload(
    conv_id: str,
    *,
    resolve_conversation_for_history: Callable[[str], Any],
    load_conversation_raw_messages: Callable[[Any], list[dict[str, Any]]],
    limit: int = DEFAULT_CONVERSATION_HISTORY_LIMIT,
    before_id: Optional[str] = None,
    after_id: Optional[str] = None,
    around_id: Optional[str] = None,
    context_before: int = DEFAULT_CONVERSATION_AROUND_CONTEXT,
    context_after: int = DEFAULT_CONVERSATION_AROUND_CONTEXT,
) -> dict[str, Any]:
    """Get messages for a specific conversation."""
    conv = resolve_conversation_for_history(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail=f"Conversation '{conv_id}' not found")
    raw_messages = load_conversation_raw_messages(conv)
    prepared_messages = _prepare_conversation_history_messages(raw_messages)
    window_messages, page = _slice_history_window(
        prepared_messages,
        limit=_clamp_history_limit(limit),
        before_id=before_id,
        after_id=after_id,
        around_id=around_id,
        context_before=context_before,
        context_after=context_after,
    )

    return {
        "conversation_id": conv_id,
        "conversation": conv.to_dict(),
        "messages": window_messages,
        "page": page,
    }


async def search_conversation_messages_payload(
    conv_id: str,
    q: str,
    *,
    resolve_conversation_for_history: Callable[[str], Any],
    load_conversation_raw_messages: Callable[[Any], list[dict[str, Any]]],
    limit: int = DEFAULT_CONVERSATION_SEARCH_LIMIT,
    offset: int = 0,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> dict[str, Any]:
    """Search a specific conversation across the full persisted history."""
    conv = resolve_conversation_for_history(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail=f"Conversation '{conv_id}' not found")

    query = re.sub(r"\s+", " ", q or "").strip()
    if not query:
        return {
            "conversation_id": conv_id,
            "conversation": conv.to_dict(),
            "query": "",
            "matches": [],
            "total_matches": 0,
            "has_more": False,
            "limit": _clamp_conversation_search_limit(limit),
        }

    safe_limit = _clamp_conversation_search_limit(limit)
    safe_offset = max(0, int(offset))
    normalized_query = query.casefold()
    since_dt = _parse_optional_iso_datetime(since)
    until_dt = _parse_optional_iso_datetime(until)
    raw_messages = load_conversation_raw_messages(conv)

    all_matches: list[dict[str, Any]] = []
    for raw_message in reversed(raw_messages):
        normalized_message = _normalize_history_message_for_api(raw_message)
        role = normalized_message.get("role")
        if role not in {"user", "assistant"}:
            continue

        content = normalized_message.get("content")
        if not isinstance(content, str):
            continue

        searchable_content = re.sub(r"\s+", " ", content).strip()
        if not searchable_content or normalized_query not in searchable_content.casefold():
            continue

        message_timestamp = normalized_message.get("timestamp")
        message_datetime = _parse_optional_iso_datetime(str(message_timestamp)) if message_timestamp else None
        if since_dt is not None and (message_datetime is None or message_datetime < since_dt):
            continue
        if until_dt is not None and (message_datetime is None or message_datetime > until_dt):
            continue

        metadata = normalized_message.get("metadata") or {}
        all_matches.append({
            "message_id": normalized_message["id"],
            "turn_id": metadata.get("turn_id"),
            "request_id": metadata.get("request_id"),
            "role": role,
            "preview": _build_history_search_preview(searchable_content, query),
            "timestamp": normalized_message.get("timestamp"),
            "agent_id": metadata.get("agent_id"),
            "agent_name": metadata.get("agent_name"),
        })

    return {
        "conversation_id": conv_id,
        "conversation": conv.to_dict(),
        "query": query,
        "matches": all_matches[safe_offset:safe_offset + safe_limit],
        "total_matches": len(all_matches),
        "has_more": safe_offset + safe_limit < len(all_matches),
        "limit": safe_limit,
        "offset": safe_offset,
        "next_offset": safe_offset + safe_limit if safe_offset + safe_limit < len(all_matches) else None,
        "since": since_dt.isoformat() if since_dt else None,
        "until": until_dt.isoformat() if until_dt else None,
    }


def create_conversation_router(
    *,
    resolve_conversation_for_history: Callable[[str], Any],
    load_conversation_raw_messages: Callable[[Any], list[dict[str, Any]]],
) -> APIRouter:
    """Create conversation routes."""

    router = APIRouter()

    @router.get("/conversations")
    async def list_conversations():
        """List all conversations."""
        from horbot.conversation import get_conversation_manager

        conv_manager = get_conversation_manager()

        dm_convs = conv_manager.get_dm_list()
        team_convs = conv_manager.get_team_list()

        return {
            "conversations": [c.to_dict() for c in conv_manager.get_all()],
            "dm": [c.to_dict() for c in dm_convs],
            "team": [c.to_dict() for c in team_convs],
        }

    @router.get("/conversations/{conv_id}")
    async def get_conversation(conv_id: str):
        """Get details of a specific conversation."""
        from horbot.conversation import get_conversation_manager

        conv_manager = get_conversation_manager()
        conv = conv_manager.get(conv_id)

        if not conv:
            raise HTTPException(status_code=404, detail=f"Conversation '{conv_id}' not found")

        return conv.to_dict()

    @router.get("/conversations/{conv_id}/messages")
    async def get_conversation_messages(
        response: Response,
        conv_id: str,
        limit: int = DEFAULT_CONVERSATION_HISTORY_LIMIT,
        before_id: Optional[str] = None,
        after_id: Optional[str] = None,
        around_id: Optional[str] = None,
        context_before: int = DEFAULT_CONVERSATION_AROUND_CONTEXT,
        context_after: int = DEFAULT_CONVERSATION_AROUND_CONTEXT,
    ):
        response.headers["Cache-Control"] = "no-store"
        return await get_conversation_messages_payload(
            conv_id,
            resolve_conversation_for_history=resolve_conversation_for_history,
            load_conversation_raw_messages=load_conversation_raw_messages,
            limit=limit,
            before_id=before_id,
            after_id=after_id,
            around_id=around_id,
            context_before=context_before,
            context_after=context_after,
        )

    @router.get("/conversations/{conv_id}/search")
    async def search_conversation_messages(
        response: Response,
        conv_id: str,
        q: str,
        limit: int = DEFAULT_CONVERSATION_SEARCH_LIMIT,
        offset: int = 0,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ):
        response.headers["Cache-Control"] = "no-store"
        return await search_conversation_messages_payload(
            conv_id,
            q,
            resolve_conversation_for_history=resolve_conversation_for_history,
            load_conversation_raw_messages=load_conversation_raw_messages,
            limit=limit,
            offset=offset,
            since=since,
            until=until,
        )

    return router
