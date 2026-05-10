"""Task workspace API routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query

from horbot.web.task_workspace_store import (
    TaskWorkspaceCreate,
    TaskWorkspaceStore,
    TaskWorkspaceUpdate,
    build_task_workspace_cwd,
    normalize_task_workspace_cwd,
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
            if request.cwd:
                transient_default_cwd = base_workspace
                request = request.model_copy(update={
                    "cwd": str(normalize_task_workspace_cwd(
                        request.cwd,
                        agent_workspace=base_workspace,
                        default_cwd=transient_default_cwd,
                        allow_external=True,
                    )),
                })
            store = get_store()
            task = store.create(
                request,
                default_cwd_factory=lambda task_id: build_task_workspace_cwd(
                    data_root=store.root,
                    agent_id=request.agent_id,
                    conversation_id=request.conversation_id,
                    session_key=request.session_key,
                    task_id=task_id,
                ),
            )
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
        store = get_store()
        existing = store.get(task_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Task workspace not found")
        try:
            _, base_workspace = resolve_agent_workspace_for_request(existing.agent_id)
            if request.cwd is not None:
                request = request.model_copy(update={
                    "cwd": str(normalize_task_workspace_cwd(
                        request.cwd,
                        agent_workspace=base_workspace,
                        default_cwd=Path(existing.cwd),
                        allow_external=True,
                    )),
                })
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        task = store.update(task_id, request)
        if task is None:
            raise HTTPException(status_code=404, detail="Task workspace not found")
        return task.model_dump()

    @router.delete("/task-workspaces/{task_id}")
    async def delete_task_workspace(task_id: str):
        deleted = get_store().delete(task_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Task workspace not found")
        return {"deleted": True, "task_id": task_id}

    @router.get("/task-workspaces/{task_id}/files")
    async def list_task_workspace_files(task_id: str, limit: int = Query(default=80, ge=1, le=300)):
        payload = get_store().list_files(task_id, limit=limit)
        if payload is None:
            raise HTTPException(status_code=404, detail="Task workspace not found")
        return payload

    @router.get("/task-workspaces/{task_id}/file")
    async def read_task_workspace_file(
        task_id: str,
        path: str = Query(..., min_length=1),
        max_bytes: int = Query(default=128_000, ge=1, le=512_000),
    ):
        try:
            payload = get_store().read_file(task_id, path, max_bytes=max_bytes)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except IsADirectoryError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if payload is None:
            raise HTTPException(status_code=404, detail="Task workspace not found")
        return payload

    @router.get("/task-workspaces/{task_id}/changes")
    async def list_task_workspace_changes(task_id: str, limit: int = Query(default=120, ge=1, le=300)):
        payload = get_store().list_changes(task_id, limit=limit)
        if payload is None:
            raise HTTPException(status_code=404, detail="Task workspace not found")
        return payload

    return router
