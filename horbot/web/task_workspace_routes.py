"""Task workspace API routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query

from horbot.web.task_workspace_store import (
    TaskWorkspaceCreate,
    TaskWorkspaceStore,
    TaskWorkspaceUpdate,
    build_conversation_task_cwd,
)


def create_task_workspace_router(
    resolve_agent_workspace_for_request: Callable[[str | None], tuple[Any | None, Path]],
    store_factory: Callable[[], TaskWorkspaceStore] | None = None,
) -> APIRouter:
    """Create routes for user-facing chat task workspaces."""

    router = APIRouter()

    def get_store() -> TaskWorkspaceStore:
        return store_factory() if store_factory else TaskWorkspaceStore()

    @router.get("/task-workspaces")
    async def list_task_workspaces(
        conversation_id: str | None = Query(default=None),
        agent_id: str | None = Query(default=None),
        session_key: str | None = Query(default=None),
    ):
        tasks = get_store().list(
            conversation_id=conversation_id,
            agent_id=agent_id,
            session_key=session_key,
        )
        return {"task_workspaces": [task.model_dump() for task in tasks]}

    @router.post("/task-workspaces")
    async def create_task_workspace(request: TaskWorkspaceCreate):
        try:
            _, base_workspace = resolve_agent_workspace_for_request(request.agent_id)
            default_cwd = build_conversation_task_cwd(
                base_workspace=base_workspace,
                conversation_id=request.conversation_id,
                session_key=request.session_key,
            )
            task = get_store().create(request, default_cwd=default_cwd)
            return task.model_dump()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/task-workspaces/{task_id}")
    async def get_task_workspace(task_id: str):
        task = get_store().get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task workspace not found")
        return task.model_dump()

    @router.patch("/task-workspaces/{task_id}")
    async def update_task_workspace(task_id: str, request: TaskWorkspaceUpdate):
        task = get_store().update(task_id, request)
        if task is None:
            raise HTTPException(status_code=404, detail="Task workspace not found")
        return task.model_dump()

    @router.get("/task-workspaces/{task_id}/files")
    async def list_task_workspace_files(task_id: str, limit: int = Query(default=80, ge=1, le=300)):
        payload = get_store().list_files(task_id, limit=limit)
        if payload is None:
            raise HTTPException(status_code=404, detail="Task workspace not found")
        return payload

    return router
