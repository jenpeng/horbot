"""Subagent management API routes."""

from __future__ import annotations

import inspect
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException


def create_subagent_router(get_agent_loop: Callable[..., Any]) -> APIRouter:
    """Create routes for subagent management."""

    router = APIRouter()

    async def resolve_agent_loop():
        result = get_agent_loop()
        if inspect.isawaitable(result):
            return await result
        return result

    @router.get("/subagents")
    async def list_subagents(session_key: str | None = None, agent_loop=Depends(resolve_agent_loop)):
        """List all running subagents."""
        subagents = agent_loop.subagents.list_subagents(session_key=session_key)
        return {
            "subagents": [info.to_dict() for info in subagents],
            "count": len(subagents),
        }

    @router.post("/subagents/{task_id}/cancel")
    async def cancel_subagent(task_id: str, agent_loop=Depends(resolve_agent_loop)):
        """Cancel a specific subagent by task_id."""
        info = agent_loop.subagents.get_subagent_info(task_id)
        if not info:
            raise HTTPException(status_code=404, detail=f"Subagent '{task_id}' not found")

        cancelled = await agent_loop.subagents.cancel(task_id)
        if cancelled:
            return {
                "status": "cancelled",
                "task_id": task_id,
                "message": f"Subagent [{info.label}] cancelled successfully",
            }
        return {
            "status": "already_completed",
            "task_id": task_id,
            "message": f"Subagent [{info.label}] was already completed",
        }

    @router.post("/subagents/cancel-all")
    async def cancel_all_subagents(session_key: str | None = None, agent_loop=Depends(resolve_agent_loop)):
        """Cancel all running subagents, optionally filtered by session."""
        if session_key:
            cancelled = await agent_loop.subagents.cancel_by_session(session_key)
        else:
            cancelled = await agent_loop.subagents.cancel_all()

        return {
            "status": "success",
            "cancelled_count": cancelled,
            "message": f"Cancelled {cancelled} subagent(s)",
        }

    @router.get("/subagents/{task_id}")
    async def get_subagent_info(task_id: str, agent_loop=Depends(resolve_agent_loop)):
        """Get information about a specific subagent."""
        info = agent_loop.subagents.get_subagent_info(task_id)
        if not info:
            raise HTTPException(status_code=404, detail=f"Subagent '{task_id}' not found")
        return info.to_dict()

    return router
