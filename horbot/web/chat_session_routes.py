"""Chat session management API routes."""

from __future__ import annotations

import os
import uuid
from typing import Any, Awaitable, Callable, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    title: Optional[str] = None


async def create_new_session_payload(
    request: Optional[CreateSessionRequest],
    *,
    get_session_manager_fn: Callable[[], Any],
) -> dict[str, str]:
    """Create a new chat session."""
    manager = get_session_manager_fn()

    session_key = f"session_{uuid.uuid4().hex}"
    full_session_key = f"web:{session_key}"

    session = manager.get_or_create(full_session_key)
    title = ((request.title if request else None) or "").strip() or "新对话"
    session.title = title
    session.metadata["title"] = title
    session.metadata["created_at"] = session.created_at.isoformat()

    manager.save(session)

    return {"session_key": session_key, "title": title}


async def update_session_title_payload(
    session_key: str,
    title: str,
    *,
    resolve_chat_session_manager_fn: Callable[[str], Awaitable[tuple[Any, str]]],
) -> dict[str, str]:
    """Update session title."""
    manager, normalized_session_key = await resolve_chat_session_manager_fn(session_key)
    session = manager.get(normalized_session_key)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    resolved_title = title.strip() or "新对话"
    session.title = resolved_title
    session.metadata["title"] = resolved_title
    manager.save(session)

    return {"status": "success", "title": resolved_title}


async def delete_session_payload(
    session_key: str,
    *,
    resolve_chat_session_manager_fn: Callable[[str], Awaitable[tuple[Any, str]]],
) -> dict[str, str]:
    """Delete a session."""
    manager, normalized_session_key = await resolve_chat_session_manager_fn(session_key)
    session_path = manager._get_session_path(normalized_session_key)

    if session_path.exists():
        os.remove(session_path)
        manager.invalidate(normalized_session_key)
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Session not found")


async def list_chat_sessions_payload(
    *,
    get_session_manager_fn: Callable[[], Any],
) -> dict[str, list[dict[str, Any]]]:
    """List all chat sessions with metadata."""
    manager = get_session_manager_fn()
    session_infos = manager.list_sessions(key_prefix="web:")

    enriched_sessions = []
    for session_info in session_infos:
        session_key = session_info.get("key")
        if not session_key:
            continue

        title = session_info.get("title", "未命名对话")
        message_count = int(session_info.get("message_count", 0) or 0)
        created_at = session_info.get("created_at", "")

        if title == "未命名对话":
            session = manager.get(session_key)
            if session:
                title = session.metadata.get("title", "未命名对话")
                if title == "未命名对话" and session.messages:
                    for msg in session.messages:
                        if msg.get("role") == "user":
                            content = msg.get("content", "")
                            title = content[:50] + "..." if len(content) > 50 else content or "未命名对话"
                            break
                created_at = session.metadata.get("created_at", created_at)
                message_count = len(session.messages)

        enriched_sessions.append({
            "key": session_key,
            "title": title,
            "created_at": created_at,
            "message_count": message_count,
        })

    enriched_sessions.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return {"sessions": enriched_sessions}


def create_chat_session_router(
    *,
    get_session_manager_fn: Callable[[], Any],
    resolve_chat_session_manager_fn: Callable[[str], Awaitable[tuple[Any, str]]],
) -> APIRouter:
    """Create chat session routes."""

    router = APIRouter()

    @router.post("/chat/sessions")
    async def create_new_session(request: Optional[CreateSessionRequest] = None):
        return await create_new_session_payload(request, get_session_manager_fn=get_session_manager_fn)

    @router.put("/chat/sessions/{session_key}")
    async def update_session_title(session_key: str, title: str):
        return await update_session_title_payload(
            session_key,
            title,
            resolve_chat_session_manager_fn=resolve_chat_session_manager_fn,
        )

    @router.delete("/chat/sessions/{session_key}")
    async def delete_session(session_key: str):
        return await delete_session_payload(
            session_key,
            resolve_chat_session_manager_fn=resolve_chat_session_manager_fn,
        )

    @router.get("/chat/sessions")
    async def list_chat_sessions():
        return await list_chat_sessions_payload(get_session_manager_fn=get_session_manager_fn)

    return router
