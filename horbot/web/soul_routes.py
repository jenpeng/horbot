"""SOUL persona API routes."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import APIRouter


def create_soul_router(resolve_agent_workspace_for_request: Callable[[Optional[str]], tuple[Any | None, Path]]) -> APIRouter:
    """Create routes for reading the active agent persona."""

    router = APIRouter()

    @router.get("/soul")
    async def get_soul(agent_id: Optional[str] = None):
        """Get SOUL.md content for persona display."""
        agent, workspace_path = resolve_agent_workspace_for_request(agent_id)
        resolved_agent_id = agent.id if agent is not None else (agent_id or "main")
        soul_path = workspace_path / "SOUL.md"

        if not soul_path.exists():
            return {"name": "horbot", "content": "", "agent_id": resolved_agent_id}

        try:
            content = soul_path.read_text(encoding="utf-8")
            name_match = re.search(r"^# (.+)$", content, re.MULTILINE)
            name = name_match.group(1) if name_match else "horbot"

            name_match2 = re.search(r"我是([^，。\n]+)", content)
            if name_match2:
                name = name_match2.group(1).strip()

            return {"name": name, "content": content, "agent_id": resolved_agent_id}
        except Exception as exc:
            return {"name": "horbot", "content": "", "error": str(exc), "agent_id": resolved_agent_id}

    return router
