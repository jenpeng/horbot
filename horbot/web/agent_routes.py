"""Agent management API routes."""

from __future__ import annotations

import inspect
import re
from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from horbot.config.normalizer import remove_agent_references, set_agent_team_memberships
from horbot.config.schema import Config
from horbot.utils.bootstrap import (
    normalize_bootstrap_file_content,
    reconcile_bootstrap_files,
    remove_setup_pending_marker,
    upsert_markdown_section,
)


class AgentBootstrapFileUpdateRequest(BaseModel):
    content: str = ""


class AgentBootstrapSummaryUpdateRequest(BaseModel):
    identity: list[str] = Field(default_factory=list)
    role_focus: list[str] = Field(default_factory=list)
    communication_style: list[str] = Field(default_factory=list)
    boundaries: list[str] = Field(default_factory=list)
    user_preferences: list[str] = Field(default_factory=list)


class CreateAgentRequest(BaseModel):
    id: str
    name: str
    description: str = ""
    profile: str = ""
    permission_profile: str = ""
    model: str = ""
    provider: str = "auto"
    system_prompt: str = ""
    capabilities: list[str] = []
    tools: list[str] = []
    skills: list[str] = []
    workspace: str = ""
    teams: list[str] = []
    personality: str = ""
    avatar: str = ""
    evolution_enabled: bool = True
    learning_enabled: bool = True
    memory_bank_profile: dict[str, Any] = Field(default_factory=dict)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _extract_soul_name_from_workspace(workspace_path) -> str | None:
    """Extract the AI name from SOUL.md file in the given workspace."""
    soul_path = workspace_path / "SOUL.md"
    if not soul_path.exists():
        return None

    try:
        content = soul_path.read_text(encoding="utf-8")

        name_match = re.search(r"我是([^，。\n]+)", content)
        if name_match:
            return name_match.group(1).strip()

        title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()
            if title not in ["灵魂", "Soul", "SOUL"]:
                return title
    except Exception:
        pass

    return None


def _normalize_string_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _normalize_agent_id(value: str) -> str:
    return value.strip().lower()


def _normalize_memory_bank_profile(payload: dict[str, Any] | None) -> dict[str, Any]:
    raw = payload or {}
    directives = raw.get("directives", [])
    if isinstance(directives, str):
        directives = directives.splitlines()
    normalized_directives = _normalize_string_list([
        str(value).strip()
        for value in directives
        if str(value).strip()
    ])
    reasoning_style = str(raw.get("reasoning_style") or raw.get("reasoningStyle") or "").strip()
    allowed_styles = {"balanced", "structured", "exploratory", "strict"}
    return {
        "mission": str(raw.get("mission") or "").strip(),
        "directives": normalized_directives,
        "reasoning_style": reasoning_style if reasoning_style in allowed_styles else "",
    }


def _validate_team_ids_exist(config: Config, team_ids: list[str]) -> list[str]:
    normalized = _normalize_string_list(team_ids)
    missing = [team_id for team_id in normalized if team_id not in config.teams.instances]
    if missing:
        raise HTTPException(status_code=400, detail=f"Unknown teams: {', '.join(missing)}")
    return normalized


def _cleanup_agent_storage(agent_id: str, workspace_override: str = "") -> None:
    from horbot.workspace.manager import get_workspace_manager

    workspace_manager = get_workspace_manager()
    if workspace_override.strip():
        workspace_manager.delete_agent_override_artifacts(workspace_override)
    workspace_manager.delete_agent_workspace(agent_id)


def create_agent_router(
    *,
    build_agent_runtime_capabilities: Callable[[Any], dict[str, Any]],
    resolve_agent_workspace_for_request: Callable[[str | None], tuple[Any | None, Any]],
    agent_bootstrap_file_path: Callable[[str, str], tuple[Any, str]],
    read_bootstrap_file: Callable[[Any], dict[str, Any]],
    build_agent_bootstrap_payload: Callable[[Any], dict[str, Any]],
    ensure_agent_bootstrap_files: Callable[[Any], None],
    reset_agent_loop_fn: Callable[[], Any],
) -> APIRouter:
    """Create agent management routes."""

    router = APIRouter()

    @router.get("/agents")
    async def list_agents():
        """List all available agents."""
        from horbot.agent.manager import get_agent_manager

        agent_manager = get_agent_manager()
        agents = agent_manager.get_all_agents()

        agent_list = []
        for agent in agents:
            agent_dict = agent.to_dict()
            workspace = agent.get_workspace()
            soul_name = _extract_soul_name_from_workspace(workspace)
            if soul_name:
                agent_dict["name"] = soul_name
            agent_dict.update(build_agent_runtime_capabilities(agent))
            agent_list.append(agent_dict)

        return {
            "agents": agent_list,
            "count": len(agents),
        }

    @router.get("/agents/{agent_id}")
    async def get_agent(agent_id: str):
        """Get details of a specific agent."""
        from horbot.agent.manager import get_agent_manager

        agent_manager = get_agent_manager()
        agent = agent_manager.get_agent(agent_id)

        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

        agent_dict = agent.to_dict()
        agent_dict.update(build_agent_runtime_capabilities(agent))
        return agent_dict

    @router.get("/agents/{agent_id}/bootstrap-files")
    async def get_agent_bootstrap_files(agent_id: str):
        """Get editable bootstrap files for a specific agent."""
        agent, workspace_path = resolve_agent_workspace_for_request(agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

        payload = build_agent_bootstrap_payload(agent)
        payload["workspace_path"] = str(workspace_path)
        return payload

    @router.put("/agents/{agent_id}/bootstrap-files/{file_kind}")
    async def update_agent_bootstrap_file(
        agent_id: str,
        file_kind: str,
        request: AgentBootstrapFileUpdateRequest,
    ):
        """Create or update an agent bootstrap file."""
        agent, _ = resolve_agent_workspace_for_request(agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

        file_path, file_name = agent_bootstrap_file_path(agent_id, file_kind)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        normalized_kind = (file_kind or "").strip().lower()
        try:
            normalized_content = normalize_bootstrap_file_content(request.content or "", normalized_kind)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        file_path.write_text(normalized_content, encoding="utf-8")
        if normalized_kind in {"soul", "user"}:
            reconcile_bootstrap_files(
                file_path.parent,
                agent_name=agent.name,
                updated_file=file_name,
            )

        return {
            "status": "updated",
            "agent_id": agent.id,
            "agent_name": agent.name,
            "file": file_name,
            "path": str(file_path),
            "content": normalized_content,
        }

    @router.put("/agents/{agent_id}/bootstrap-summary")
    async def update_agent_bootstrap_summary(
        agent_id: str,
        request: AgentBootstrapSummaryUpdateRequest,
    ):
        """Update structured bootstrap summary and write back to markdown files."""
        agent, _ = resolve_agent_workspace_for_request(agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

        soul_path, _ = agent_bootstrap_file_path(agent_id, "soul")
        user_path, _ = agent_bootstrap_file_path(agent_id, "user")

        existing_soul = read_bootstrap_file(soul_path)["content"]
        existing_user = read_bootstrap_file(user_path)["content"]

        next_soul = remove_setup_pending_marker(existing_soul)
        next_user = remove_setup_pending_marker(existing_user)

        next_soul = upsert_markdown_section(next_soul, "身份定位", request.identity)
        next_soul = upsert_markdown_section(next_soul, "职责重点", request.role_focus)
        next_soul = upsert_markdown_section(next_soul, "沟通风格", request.communication_style)
        next_soul = upsert_markdown_section(next_soul, "边界约束", request.boundaries)
        next_user = upsert_markdown_section(next_user, "用户偏好", request.user_preferences)
        try:
            next_soul = normalize_bootstrap_file_content(next_soul, "soul")
            next_user = normalize_bootstrap_file_content(next_user, "user")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        soul_path.parent.mkdir(parents=True, exist_ok=True)
        user_path.parent.mkdir(parents=True, exist_ok=True)
        soul_path.write_text(next_soul, encoding="utf-8")
        user_path.write_text(next_user, encoding="utf-8")

        payload = build_agent_bootstrap_payload(agent)
        return {
            "status": "updated",
            **payload,
        }

    @router.get("/agents/{agent_id}/workspace")
    async def get_agent_workspace(agent_id: str):
        """Get workspace information for a specific agent."""
        from horbot.agent.manager import get_agent_manager
        from horbot.workspace.manager import AGENT_METADATA_DIRNAME

        agent_manager = get_agent_manager()
        agent = agent_manager.get_agent(agent_id)

        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

        workspace_path = agent.get_workspace()
        memory_path = agent.get_memory_dir()
        sessions_path = agent.get_sessions_dir()
        skills_path = agent.get_skills_dir()
        workspace_override = bool(getattr(agent.config, "workspace", "").strip())

        workspace_info = {
            "agent_id": agent_id,
            "workspace_path": str(workspace_path),
            "memory_path": str(memory_path),
            "sessions_path": str(sessions_path),
            "skills_path": str(skills_path),
            "workspace": {
                "path": str(workspace_path),
                "label": workspace_path.name or str(workspace_path),
                "role": "agent-workspace-override" if workspace_override else "agent-default-workspace",
                "metadata_dirname": AGENT_METADATA_DIRNAME,
                "note": "Agent runtime metadata is stored under this workspace in .horbot-agent/.",
            },
            "runtime_paths": {
                "memory": {
                    "path": str(memory_path),
                    "label": memory_path.name or str(memory_path),
                    "role": "agent-memory",
                },
                "sessions": {
                    "path": str(sessions_path),
                    "label": sessions_path.name or str(sessions_path),
                    "role": "agent-sessions",
                },
                "skills": {
                    "path": str(skills_path),
                    "label": skills_path.name or str(skills_path),
                    "role": "agent-skills",
                },
            },
            "exists": workspace_path.exists(),
        }

        if workspace_path.exists():
            try:
                workspace_info["files_count"] = sum(1 for _ in workspace_path.rglob("*") if _.is_file())
            except Exception:
                workspace_info["files_count"] = 0

        return workspace_info

    @router.post("/agents")
    async def create_agent(request: CreateAgentRequest):
        """Create a new agent."""
        from horbot.agent.manager import get_agent_manager
        from horbot.config.loader import load_config, save_config
        from horbot.config.schema import AgentConfig

        config = load_config()

        request_id = request.id.strip()
        request_name = request.name.strip()
        request_provider = request.provider.strip()
        request_model = request.model.strip()
        normalized_request_id = _normalize_agent_id(request_id)

        if not request_id:
            raise HTTPException(status_code=400, detail="Agent ID is required")

        if not request_name:
            raise HTTPException(status_code=400, detail="Agent name is required")

        if not request_provider or request_provider == "auto":
            raise HTTPException(status_code=400, detail="Agent provider is required")

        if not request_model:
            raise HTTPException(status_code=400, detail="Agent model is required")

        existing_agent_id = next(
            (
                existing_id
                for existing_id in config.agents.instances
                if _normalize_agent_id(existing_id) == normalized_request_id
            ),
            None,
        )
        if existing_agent_id is not None:
            raise HTTPException(status_code=400, detail=f"Agent ID '{request_id}' already exists")

        team_ids = _validate_team_ids_exist(config, request.teams)

        agent_config = AgentConfig(
            id=request_id,
            name=request_name,
            description=request.description,
            profile=request.profile.strip(),
            permission_profile=request.permission_profile.strip(),
            model=request_model,
            provider=request_provider,
            system_prompt=request.system_prompt,
            capabilities=_normalize_string_list(request.capabilities),
            tools=_normalize_string_list(request.tools),
            skills=_normalize_string_list(request.skills),
            workspace=request.workspace.strip(),
            teams=team_ids,
            personality=request.personality,
            avatar=request.avatar,
            evolution_enabled=request.evolution_enabled,
            learning_enabled=request.learning_enabled,
            memory_bank_profile=_normalize_memory_bank_profile(request.memory_bank_profile),
        )

        config.agents.instances[request_id] = agent_config
        set_agent_team_memberships(config, request_id, team_ids)

        try:
            save_config(config)

            agent_manager = get_agent_manager()
            agent_manager.reload()
            created_agent = agent_manager.get_agent(request_id)
            ensure_agent_bootstrap_files(created_agent)
            await _maybe_await(reset_agent_loop_fn())

            return {
                "status": "created",
                "agent_id": request_id,
                "message": f"Agent '{request_name}' created successfully",
            }
        except Exception as exc:
            logger.error("Failed to create agent: {}", exc)
            raise HTTPException(status_code=500, detail=f"Failed to create agent: {str(exc)}")

    @router.put("/agents/{agent_id}")
    async def update_agent(agent_id: str, request: CreateAgentRequest):
        """Update an existing agent."""
        from horbot.agent.manager import get_agent_manager
        from horbot.config.loader import load_config, save_config
        from horbot.config.schema import AgentConfig

        config = load_config()

        if agent_id not in config.agents.instances:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

        request_name = request.name.strip()
        if not request_name:
            raise HTTPException(status_code=400, detail="Agent name is required")

        team_ids = _validate_team_ids_exist(config, request.teams)

        agent_config = AgentConfig(
            id=agent_id,
            name=request_name,
            description=request.description,
            profile=request.profile.strip(),
            permission_profile=request.permission_profile.strip(),
            model=request.model,
            provider=request.provider,
            system_prompt=request.system_prompt,
            capabilities=_normalize_string_list(request.capabilities),
            tools=_normalize_string_list(request.tools),
            skills=_normalize_string_list(request.skills),
            workspace=request.workspace.strip(),
            teams=team_ids,
            personality=request.personality,
            avatar=request.avatar,
            evolution_enabled=request.evolution_enabled,
            learning_enabled=request.learning_enabled,
            memory_bank_profile=_normalize_memory_bank_profile(request.memory_bank_profile),
        )

        config.agents.instances[agent_id] = agent_config
        set_agent_team_memberships(config, agent_id, team_ids)

        try:
            save_config(config)

            agent_manager = get_agent_manager()
            agent_manager.reload()
            updated_agent = agent_manager.get_agent(agent_id)
            ensure_agent_bootstrap_files(updated_agent)
            await _maybe_await(reset_agent_loop_fn())

            return {
                "status": "updated",
                "agent_id": agent_id,
                "message": f"Agent '{request_name}' updated successfully",
            }
        except Exception as exc:
            logger.error("Failed to update agent: {}", exc)
            raise HTTPException(status_code=500, detail=f"Failed to update agent: {str(exc)}")

    @router.delete("/agents/{agent_id}")
    async def delete_agent(agent_id: str):
        """Delete an agent."""
        from horbot.agent.manager import get_agent_manager
        from horbot.config.loader import load_config, save_config

        config = load_config()

        if agent_id not in config.agents.instances:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

        agent_config = config.agents.instances[agent_id]

        try:
            _cleanup_agent_storage(agent_id, str(agent_config.workspace or ""))
            remove_agent_references(config, agent_id)
            del config.agents.instances[agent_id]
            save_config(config)

            agent_manager = get_agent_manager()
            agent_manager.reload()
            await _maybe_await(reset_agent_loop_fn())

            return {
                "status": "deleted",
                "agent_id": agent_id,
                "message": f"Agent '{agent_id}' deleted successfully",
            }
        except Exception as exc:
            logger.error("Failed to delete agent: {}", exc)
            raise HTTPException(status_code=500, detail=f"Failed to delete agent: {str(exc)}")

    return router
