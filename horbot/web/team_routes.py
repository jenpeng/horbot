"""Team management API routes."""

from __future__ import annotations

import inspect
from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from horbot.config.normalizer import remove_team_references, set_team_members
from horbot.config.schema import Config


class CreateTeamRequest(BaseModel):
    id: str
    name: str
    description: str = ""
    members: list[str] = []
    member_profiles: dict[str, Any] = {}
    workspace: str = ""


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


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


def _normalize_team_id(value: str) -> str:
    return value.strip().lower()


def _validate_team_member_ids_exist(config: Config, member_ids: list[str]) -> list[str]:
    normalized = _normalize_string_list(member_ids)
    unknown_ids: list[str] = []
    disabled_external_ids: list[str] = []

    for member_id in normalized:
        if member_id in config.agents.instances:
            continue
        external_agent = config.external_agents.instances.get(member_id)
        if external_agent is None:
            unknown_ids.append(member_id)
            continue
        if not bool(external_agent.team_enabled):
            disabled_external_ids.append(member_id)

    if unknown_ids:
        raise HTTPException(status_code=400, detail=f"Unknown team members: {', '.join(unknown_ids)}")
    if disabled_external_ids:
        raise HTTPException(
            status_code=400,
            detail=f"External agents are not team-enabled: {', '.join(disabled_external_ids)}",
        )
    return normalized


def _normalize_team_member_profiles(
    config: Config,
    member_ids: list[str],
    profiles: dict[str, Any] | None,
) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    raw_profiles = profiles or {}

    for agent_id in member_ids:
        profile_data = raw_profiles.get(agent_id) or {}
        normalized[agent_id] = {
            "role": str(profile_data.get("role") or "member").strip() or "member",
            "responsibility": str(profile_data.get("responsibility") or "").strip(),
            "priority": int(profile_data.get("priority", 100) or 100),
            "is_lead": bool(profile_data.get("isLead", profile_data.get("is_lead", False))),
        }

    for agent_id in raw_profiles:
        if agent_id not in config.agents.instances and agent_id not in config.external_agents.instances:
            raise HTTPException(status_code=400, detail=f"Unknown team member in member profiles: {agent_id}")
        if agent_id not in member_ids:
            raise HTTPException(status_code=400, detail=f"Member profile provided for non-member team member: {agent_id}")

    lead_ids = [agent_id for agent_id, profile in normalized.items() if profile["is_lead"]]
    if len(lead_ids) > 1:
        raise HTTPException(status_code=400, detail="A team can only have one lead agent")

    return normalized


def create_team_router(reset_agent_loop_fn: Callable[[], Any]) -> APIRouter:
    """Create team management routes."""

    router = APIRouter()

    @router.get("/teams")
    async def list_teams():
        """List all available teams."""
        from horbot.team.manager import get_team_manager

        team_manager = get_team_manager()
        teams = team_manager.get_all_teams()

        return {
            "teams": [team.to_dict() for team in teams],
            "count": len(teams),
        }

    @router.get("/teams/{team_id}")
    async def get_team(team_id: str):
        """Get details of a specific team."""
        from horbot.team.manager import get_team_manager

        team_manager = get_team_manager()
        team = team_manager.get_team(team_id)

        if not team:
            raise HTTPException(status_code=404, detail=f"Team '{team_id}' not found")

        return team.to_dict()

    @router.get("/teams/{team_id}/members")
    async def get_team_members(team_id: str):
        """Get members of a specific team."""
        from horbot.agent.manager import get_agent_manager
        from horbot.external_agents.manager import get_external_agent_manager
        from horbot.team.manager import get_team_manager

        team_manager = get_team_manager()
        agent_manager = get_agent_manager()
        external_agent_manager = get_external_agent_manager()

        team = team_manager.get_team(team_id)
        if not team:
            raise HTTPException(status_code=404, detail=f"Team '{team_id}' not found")

        def _member_profile(member_id: str) -> dict[str, Any]:
            return dict(team.member_profiles.get(member_id, {}) or {})

        members: list[dict[str, Any]] = []
        internal_members: list[dict[str, Any]] = []
        external_members: list[dict[str, Any]] = []
        member_order: list[dict[str, str]] = []
        for agent_id in team.members:
            agent = agent_manager.get_agent(agent_id)
            if agent:
                payload = {
                    "id": agent_id,
                    "kind": "internal",
                    "profile": _member_profile(agent_id),
                    "agent": agent.to_dict(),
                }
                members.append(payload)
                internal_members.append(payload)
                member_order.append({"id": agent_id, "kind": "internal"})
                continue
            external_agent = external_agent_manager.get_external_agent(agent_id)
            if external_agent:
                payload = {
                    "id": agent_id,
                    "kind": "external",
                    "profile": _member_profile(agent_id),
                    "external_agent": external_agent.to_dict(),
                }
                members.append(payload)
                external_members.append(payload)
                member_order.append({"id": agent_id, "kind": "external"})

        return {
            "team_id": team_id,
            "members": members,
            "internal_members": internal_members,
            "external_members": external_members,
            "member_order": member_order,
            "count": len(members),
            "counts": {
                "total": len(members),
                "internal": len(internal_members),
                "external": len(external_members),
            },
        }

    @router.get("/teams/{team_id}/workspace")
    async def get_team_workspace(team_id: str):
        """Get workspace information for a specific team."""
        from horbot.team.manager import get_team_manager
        from horbot.workspace.manager import TEAM_METADATA_DIRNAME

        team_manager = get_team_manager()
        team = team_manager.get_team(team_id)

        if not team:
            raise HTTPException(status_code=404, detail=f"Team '{team_id}' not found")

        workspace_path = team.get_workspace()
        workspace_override = bool(getattr(team.config, "workspace", "").strip())

        workspace_info = {
            "team_id": team_id,
            "workspace_path": str(workspace_path),
            "workspace": {
                "path": str(workspace_path),
                "label": workspace_path.name or str(workspace_path),
                "role": "team-workspace-override" if workspace_override else "team-default-workspace",
                "metadata_dirname": TEAM_METADATA_DIRNAME,
                "note": "Team collaboration metadata is stored under this workspace in .horbot-team/.",
            },
            "exists": workspace_path.exists(),
        }

        if workspace_path.exists():
            try:
                workspace_info["files_count"] = sum(1 for _ in workspace_path.rglob("*") if _.is_file())
            except Exception:
                workspace_info["files_count"] = 0

        return workspace_info

    @router.get("/teams/{team_id}/shared-memory")
    async def get_team_shared_memory(team_id: str):
        """Get shared memory for a specific team."""
        from horbot.team.manager import get_team_manager

        team_manager = get_team_manager()
        team = team_manager.get_team(team_id)

        if not team:
            raise HTTPException(status_code=404, detail=f"Team '{team_id}' not found")

        shared_memory = team.get_shared_memory()
        context = shared_memory.get_all_context()

        return {
            "team_id": team_id,
            "context": context,
        }

    @router.post("/teams")
    async def create_team(request: CreateTeamRequest):
        """Create a new team."""
        from horbot.config.loader import load_config, save_config
        from horbot.config.schema import TeamConfig
        from horbot.team.manager import get_team_manager

        config = load_config()

        request_id = request.id.strip()
        request_name = request.name.strip()
        normalized_request_id = _normalize_team_id(request_id)

        if not request_id:
            raise HTTPException(status_code=400, detail="Team ID is required")

        if not request_name:
            raise HTTPException(status_code=400, detail="Team name is required")

        existing_team_id = next(
            (
                existing_id
                for existing_id in config.teams.instances
                if _normalize_team_id(existing_id) == normalized_request_id
            ),
            None,
        )
        if existing_team_id is not None:
            raise HTTPException(status_code=400, detail=f"Team ID '{request_id}' already exists")

        member_ids = _validate_team_member_ids_exist(config, request.members)
        member_profiles = _normalize_team_member_profiles(config, member_ids, request.member_profiles)

        team_config = TeamConfig(
            id=request_id,
            name=request_name,
            description=request.description,
            members=member_ids,
            member_profiles=member_profiles,
            workspace=request.workspace.strip(),
        )

        config.teams.instances[request_id] = team_config
        set_team_members(config, request_id, member_ids)

        try:
            save_config(config)

            team_manager = get_team_manager()
            team_manager.reload()
            await _maybe_await(reset_agent_loop_fn())

            return {
                "status": "created",
                "team_id": request_id,
                "message": f"Team '{request_name}' created successfully",
            }
        except Exception as exc:
            logger.error("Failed to create team: {}", exc)
            raise HTTPException(status_code=500, detail=f"Failed to create team: {str(exc)}")

    @router.put("/teams/{team_id}")
    async def update_team(team_id: str, request: CreateTeamRequest):
        """Update an existing team."""
        from horbot.config.loader import load_config, save_config
        from horbot.config.schema import TeamConfig
        from horbot.team.manager import get_team_manager

        config = load_config()

        if team_id not in config.teams.instances:
            raise HTTPException(status_code=404, detail=f"Team '{team_id}' not found")

        request_name = request.name.strip()
        if not request_name:
            raise HTTPException(status_code=400, detail="Team name is required")

        member_ids = _validate_team_member_ids_exist(config, request.members)
        member_profiles = _normalize_team_member_profiles(config, member_ids, request.member_profiles)

        team_config = TeamConfig(
            id=team_id,
            name=request_name,
            description=request.description,
            members=member_ids,
            member_profiles=member_profiles,
            workspace=request.workspace.strip(),
        )

        config.teams.instances[team_id] = team_config
        set_team_members(config, team_id, member_ids)

        try:
            save_config(config)

            team_manager = get_team_manager()
            team_manager.reload()
            await _maybe_await(reset_agent_loop_fn())

            return {
                "status": "updated",
                "team_id": team_id,
                "message": f"Team '{request_name}' updated successfully",
            }
        except Exception as exc:
            logger.error("Failed to update team: {}", exc)
            raise HTTPException(status_code=500, detail=f"Failed to update team: {str(exc)}")

    @router.delete("/teams/{team_id}")
    async def delete_team(team_id: str):
        """Delete a team."""
        from horbot.config.loader import load_config, save_config
        from horbot.team.manager import get_team_manager

        config = load_config()

        if team_id not in config.teams.instances:
            raise HTTPException(status_code=404, detail=f"Team '{team_id}' not found")

        remove_team_references(config, team_id)
        del config.teams.instances[team_id]

        try:
            save_config(config)

            team_manager = get_team_manager()
            team_manager.reload()
            await _maybe_await(reset_agent_loop_fn())

            return {
                "status": "deleted",
                "team_id": team_id,
                "message": f"Team '{team_id}' deleted successfully",
            }
        except Exception as exc:
            logger.error("Failed to delete team: {}", exc)
            raise HTTPException(status_code=500, detail=f"Failed to delete team: {str(exc)}")

    return router
