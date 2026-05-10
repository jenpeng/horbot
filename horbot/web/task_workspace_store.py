"""Persistent store for chat task workspaces."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Callable, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from horbot.utils.helpers import safe_filename
from horbot.utils.paths import get_active_data_root

TaskWorkspaceStatus = Literal["ready", "running", "blocked", "done", "failed"]
TaskWorkspaceMode = Literal["conversation", "current", "scratch", "worktree"]


class TaskWorkspace(BaseModel):
    """User-facing task workspace attached to a chat conversation."""

    id: str
    title: str
    agent_id: str | None = None
    conversation_id: str | None = None
    session_key: str | None = None
    status: TaskWorkspaceStatus = "ready"
    cwd: str
    workspace_mode: TaskWorkspaceMode = "conversation"
    created_at: str
    updated_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskWorkspaceCreate(BaseModel):
    title: str
    agent_id: str | None = None
    conversation_id: str | None = None
    session_key: str | None = None
    cwd: str | None = None
    workspace_mode: TaskWorkspaceMode = "conversation"
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskWorkspaceUpdate(BaseModel):
    title: str | None = None
    status: TaskWorkspaceStatus | None = None
    cwd: str | None = None
    workspace_mode: TaskWorkspaceMode | None = None
    metadata: dict[str, Any] | None = None


class TaskWorkspaceStore:
    """Small JSON-backed task workspace registry.

    This intentionally stores task context only. It does not start execution or
    allocate git worktrees yet, so existing chat execution behavior remains unchanged.
    """

    def __init__(self, root: Path | None = None):
        self.root = root or get_active_data_root()
        self.store_path = self.root / "data" / "task_workspaces" / "tasks.json"

    def list(
        self,
        *,
        conversation_id: str | None = None,
        agent_id: str | None = None,
        session_key: str | None = None,
    ) -> list[TaskWorkspace]:
        tasks = self._load()
        if conversation_id:
            tasks = [task for task in tasks if task.conversation_id == conversation_id]
        if agent_id:
            tasks = [task for task in tasks if task.agent_id == agent_id]
        if session_key:
            tasks = [task for task in tasks if task.session_key == session_key]
        return sorted(tasks, key=lambda task: task.updated_at, reverse=True)

    def get(self, task_id: str) -> TaskWorkspace | None:
        return next((task for task in self._load() if task.id == task_id), None)

    def create(
        self,
        request: TaskWorkspaceCreate,
        *,
        default_cwd: Path | None = None,
        default_cwd_factory: Callable[[str], Path] | None = None,
    ) -> TaskWorkspace:
        now = _utc_now()
        title = _normalize_title(request.title)
        task_id = f"tw_{uuid4().hex[:12]}"
        cwd = self._resolve_create_cwd(
            request.cwd,
            default_cwd=default_cwd,
            default_cwd_factory=default_cwd_factory,
            task_id=task_id,
        )
        task = TaskWorkspace(
            id=task_id,
            title=title,
            agent_id=request.agent_id,
            conversation_id=request.conversation_id,
            session_key=request.session_key,
            status="ready",
            cwd=str(cwd),
            workspace_mode=request.workspace_mode,
            created_at=now,
            updated_at=now,
            metadata=dict(request.metadata or {}),
        )
        tasks = self._load()
        tasks.append(task)
        self._save(tasks)
        return task

    def update(self, task_id: str, request: TaskWorkspaceUpdate) -> TaskWorkspace | None:
        tasks = self._load()
        updated: TaskWorkspace | None = None
        next_tasks: list[TaskWorkspace] = []
        for task in tasks:
            if task.id != task_id:
                next_tasks.append(task)
                continue
            data = task.model_dump()
            if request.title is not None:
                data["title"] = _normalize_title(request.title)
            if request.status is not None:
                data["status"] = request.status
            if request.cwd is not None:
                data["cwd"] = str(self._resolve_cwd(request.cwd, default_cwd=Path(task.cwd)))
            if request.workspace_mode is not None:
                data["workspace_mode"] = request.workspace_mode
            if request.metadata is not None:
                data["metadata"] = dict(request.metadata)
            data["updated_at"] = _utc_now()
            updated = TaskWorkspace.model_validate(data)
            next_tasks.append(updated)
        if updated is not None:
            self._save(next_tasks)
        return updated

    def delete(self, task_id: str) -> bool:
        tasks = self._load()
        next_tasks = [task for task in tasks if task.id != task_id]
        if len(next_tasks) == len(tasks):
            return False
        self._save(next_tasks)
        return True

    def list_files(self, task_id: str, *, limit: int = 80) -> dict[str, Any] | None:
        task = self.get(task_id)
        if task is None:
            return None

        cwd = Path(task.cwd).expanduser()
        files: list[dict[str, Any]] = []
        if cwd.exists() and cwd.is_dir():
            for path in _iter_workspace_files(cwd, limit=limit):
                try:
                    stat = path.stat()
                except OSError:
                    continue
                files.append({
                    "path": str(path.relative_to(cwd)),
                    "name": path.name,
                    "kind": "directory" if path.is_dir() else "file",
                    "size": stat.st_size if path.is_file() else None,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                })

        return {
            "task_id": task.id,
            "cwd": task.cwd,
            "exists": cwd.exists(),
            "files": files,
            "truncated": len(files) >= limit,
        }

    def read_file(self, task_id: str, relative_path: str, *, max_bytes: int = 128_000) -> dict[str, Any] | None:
        task = self.get(task_id)
        if task is None:
            return None

        cwd = Path(task.cwd).expanduser().resolve()
        requested = (relative_path or "").strip()
        if not requested:
            raise ValueError("File path is required")
        target = (cwd / requested).resolve()
        try:
            target.relative_to(cwd)
        except ValueError as exc:
            raise ValueError("File path is outside the task workspace") from exc
        if not target.exists():
            raise FileNotFoundError("File not found")
        if not target.is_file():
            raise IsADirectoryError("Path is not a file")

        stat = target.stat()
        with target.open("rb") as handle:
            raw = handle.read(max_bytes)
        truncated = stat.st_size > max_bytes
        try:
            content = raw.decode("utf-8")
            encoding = "utf-8"
            binary = False
        except UnicodeDecodeError:
            content = raw.decode("utf-8", errors="replace")
            encoding = "utf-8-replacement"
            binary = True

        return {
            "task_id": task.id,
            "cwd": task.cwd,
            "path": str(target.relative_to(cwd)),
            "name": target.name,
            "size": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            "content": content,
            "encoding": encoding,
            "binary": binary,
            "truncated": truncated,
        }

    def list_changes(self, task_id: str, *, limit: int = 120) -> dict[str, Any] | None:
        task = self.get(task_id)
        if task is None:
            return None

        cwd = Path(task.cwd).expanduser()
        if not cwd.exists() or not cwd.is_dir():
            return {
                "task_id": task.id,
                "cwd": task.cwd,
                "available": False,
                "reason": "cwd_not_found",
                "changes": [],
                "truncated": False,
            }

        git_root = _find_git_root(cwd)
        if git_root is None:
            return {
                "task_id": task.id,
                "cwd": task.cwd,
                "available": False,
                "reason": "not_git_repo",
                "changes": [],
                "truncated": False,
            }

        try:
            result = subprocess.run(
                ["git", "-C", str(git_root), "status", "--short", "--", str(cwd)],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {
                "task_id": task.id,
                "cwd": task.cwd,
                "available": False,
                "reason": str(exc),
                "changes": [],
                "truncated": False,
            }

        if result.returncode != 0:
            return {
                "task_id": task.id,
                "cwd": task.cwd,
                "available": False,
                "reason": (result.stderr or "git_status_failed").strip(),
                "changes": [],
                "truncated": False,
            }

        lines = [line for line in result.stdout.splitlines() if line.strip()]
        changes = [_parse_git_status_line(line) for line in lines[:limit]]
        return {
            "task_id": task.id,
            "cwd": task.cwd,
            "available": True,
            "reason": None,
            "changes": changes,
            "truncated": len(lines) > limit,
        }

    def _load(self) -> list[TaskWorkspace]:
        if not self.store_path.exists():
            return []
        try:
            payload = json.loads(self.store_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        items = payload.get("tasks", []) if isinstance(payload, dict) else []
        tasks: list[TaskWorkspace] = []
        for item in items:
            try:
                tasks.append(TaskWorkspace.model_validate(item))
            except Exception:
                continue
        return tasks

    def _save(self, tasks: list[TaskWorkspace]) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.store_path.with_suffix(".json.tmp")
        payload = {
            "version": 1,
            "tasks": [task.model_dump() for task in sorted(tasks, key=lambda item: item.updated_at, reverse=True)],
        }
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp_path, self.store_path)

    def _resolve_cwd(self, cwd: str | None, *, default_cwd: Path) -> Path:
        raw = (cwd or "").strip()
        if raw:
            path = Path(raw).expanduser()
            if not path.is_absolute():
                path = default_cwd / path
            return path.resolve()
        return default_cwd.expanduser().resolve()

    def _resolve_create_cwd(
        self,
        cwd: str | None,
        *,
        default_cwd: Path | None,
        default_cwd_factory: Callable[[str], Path] | None,
        task_id: str,
    ) -> Path:
        raw = (cwd or "").strip()
        if raw:
            path = Path(raw).expanduser()
            if path.is_absolute():
                return path.resolve()

        resolved_default_cwd = default_cwd_factory(task_id) if default_cwd_factory else default_cwd
        if resolved_default_cwd is None:
            raise ValueError("A default task workspace cwd is required")
        return self._resolve_cwd(cwd, default_cwd=resolved_default_cwd)


def normalize_task_workspace_cwd(
    raw_cwd: str,
    *,
    agent_workspace: Path,
    default_cwd: Path,
    allow_external: bool = False,
) -> Path:
    """Resolve a task cwd and optionally ensure it stays inside the agent workspace."""

    raw = (raw_cwd or "").strip()
    if not raw:
        return default_cwd.expanduser().resolve()

    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = default_cwd / path
    resolved = path.resolve()
    if allow_external:
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    workspace_root = agent_workspace.expanduser().resolve()
    try:
        resolved.relative_to(workspace_root)
    except ValueError as exc:
        raise ValueError("Task workspace cwd is outside the target agent workspace") from exc
    return resolved


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_title(title: str) -> str:
    normalized = " ".join((title or "").strip().split())
    return normalized[:120] or "Untitled task"


def _iter_workspace_files(cwd: Path, *, limit: int):
    ignored_names = {".git", "__pycache__", "node_modules", ".venv", "dist", "build"}
    yielded = 0
    for path in cwd.rglob("*"):
        if yielded >= limit:
            break
        relative_parts = path.relative_to(cwd).parts
        if any(part in ignored_names for part in relative_parts):
            continue
        if any(part.startswith(".") and part not in {".horbot-agent"} for part in relative_parts):
            continue
        yielded += 1
        yield path


def _find_git_root(path: Path) -> Path | None:
    for candidate in [path, *path.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def _parse_git_status_line(line: str) -> dict[str, str]:
    status = line[:2].strip() or "changed"
    path = line[3:].strip() if len(line) > 3 else line.strip()
    return {
        "status": status,
        "path": path,
        "summary": line.strip(),
    }


def build_task_workspace_cwd(
    *,
    data_root: Path,
    agent_id: str | None,
    conversation_id: str | None,
    session_key: str | None,
    task_id: str,
) -> Path:
    """Build an isolated default cwd for a single chat task workspace."""

    agent_name = safe_filename(agent_id or "default") or "default"
    conversation_name = safe_filename(conversation_id or session_key or "default") or "default"
    task_name = safe_filename(task_id) or task_id
    path = data_root / "task-workspaces" / agent_name / conversation_name / task_name
    path.mkdir(parents=True, exist_ok=True)
    return path
