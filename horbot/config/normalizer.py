"""Helpers to keep configuration relationships internally consistent."""

from __future__ import annotations

from typing import Iterable

from horbot.config.schema import Config

_CHANNEL_TYPES = {
    "whatsapp",
    "telegram",
    "discord",
    "feishu",
    "wecom",
    "mochat",
    "dingtalk",
    "email",
    "slack",
    "qq",
    "matrix",
    "sharecrm",
}


def _legacy_endpoint_id(channel_type: str) -> str:
    return f"legacy:{channel_type}"


def _unique_str_list(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def ensure_single_main_agent(config: Config, preferred_main_id: str | None = None) -> None:
    """Legacy no-op kept for backward compatibility."""
    del config, preferred_main_id


def set_agent_team_memberships(config: Config, agent_id: str, team_ids: Iterable[str]) -> list[str]:
    """Apply authoritative team memberships for one agent and sync both sides."""
    normalized_team_ids = _unique_str_list(team_ids)
    agent = config.agents.instances[agent_id]
    agent.teams = normalized_team_ids

    for team in config.teams.instances.values():
        team.members = [member_id for member_id in _unique_str_list(team.members) if member_id != agent_id]

    for team_id in normalized_team_ids:
        team = config.teams.instances[team_id]
        team.members = _unique_str_list([*team.members, agent_id])

    return normalized_team_ids


def set_team_members(config: Config, team_id: str, member_ids: Iterable[str]) -> list[str]:
    """Apply authoritative members for one team and sync both sides."""
    normalized_member_ids = _unique_str_list(member_ids)
    team = config.teams.instances[team_id]
    team.members = normalized_member_ids

    for agent in config.agents.instances.values():
        agent.teams = [existing_team_id for existing_team_id in _unique_str_list(agent.teams) if existing_team_id != team_id]

    for member_id in normalized_member_ids:
        agent = config.agents.instances[member_id]
        agent.teams = _unique_str_list([*agent.teams, team_id])

    return normalized_member_ids


def remove_agent_references(config: Config, agent_id: str) -> None:
    """Remove an agent from all team member lists."""
    for team in config.teams.instances.values():
        team.members = [member_id for member_id in _unique_str_list(team.members) if member_id != agent_id]
        if agent_id in team.member_profiles:
            del team.member_profiles[agent_id]


def remove_team_references(config: Config, team_id: str) -> None:
    """Remove a team from all agent team lists."""
    for agent in config.agents.instances.values():
        agent.teams = [existing_team_id for existing_team_id in _unique_str_list(agent.teams) if existing_team_id != team_id]


def normalize_config(config: Config) -> Config:
    """Normalize cross-references and duplicate list fields in-place."""
    for agent in config.agents.instances.values():
        agent.capabilities = _unique_str_list(agent.capabilities)
        agent.tools = _unique_str_list(agent.tools)
        agent.skills = _unique_str_list(agent.skills)
        agent.teams = _unique_str_list(agent.teams)
        agent.channel_bindings = _unique_str_list(getattr(agent, "channel_bindings", []))
        agent.workspace = agent.workspace.strip()
        agent.is_main = False

    for team in config.teams.instances.values():
        team.members = _unique_str_list(team.members)
        team.workspace = team.workspace.strip()

    normalized_endpoints = []
    seen_endpoint_ids: set[str] = set()
    for endpoint in config.channels.endpoints:
        endpoint.id = endpoint.id.strip()
        endpoint.type = endpoint.type.strip().lower()
        endpoint.name = endpoint.name.strip()
        endpoint.agent_id = endpoint.agent_id.strip()
        endpoint.allow_from = _unique_str_list(endpoint.allow_from)
        if not endpoint.id or endpoint.id in seen_endpoint_ids:
            continue
        if endpoint.type not in _CHANNEL_TYPES:
            continue
        seen_endpoint_ids.add(endpoint.id)
        normalized_endpoints.append(endpoint)
    config.channels.endpoints = normalized_endpoints

    valid_agent_ids = set(config.agents.instances.keys())
    valid_team_ids = set(config.teams.instances.keys())
    valid_endpoint_ids = {endpoint.id for endpoint in config.channels.endpoints}
    valid_endpoint_ids.update(_legacy_endpoint_id(channel_type) for channel_type in _CHANNEL_TYPES)

    for agent in config.agents.instances.values():
        agent.teams = [team_id for team_id in agent.teams if team_id in valid_team_ids]
        agent.channel_bindings = [
            endpoint_id
            for endpoint_id in agent.channel_bindings
            if endpoint_id in valid_endpoint_ids
        ]

    for team in config.teams.instances.values():
        team.members = [member_id for member_id in team.members if member_id in valid_agent_ids]
        team.member_profiles = {
            member_id: profile
            for member_id, profile in team.member_profiles.items()
            if member_id in valid_agent_ids
        }

    for team_id, team in config.teams.instances.items():
        for member_id in team.members:
            agent = config.agents.instances.get(member_id)
            if agent is None:
                continue
            agent.teams = _unique_str_list([*agent.teams, team_id])

    for agent_id, agent in config.agents.instances.items():
        for team_id in agent.teams:
            team = config.teams.instances.get(team_id)
            if team is None:
                continue
            team.members = _unique_str_list([*team.members, agent_id])

    for endpoint in config.channels.endpoints:
        if endpoint.agent_id and endpoint.agent_id not in valid_agent_ids:
            endpoint.agent_id = ""

    for endpoint in config.channels.endpoints:
        if endpoint.agent_id:
            for other_agent_id, agent in config.agents.instances.items():
                bindings = [binding for binding in agent.channel_bindings if binding != endpoint.id]
                if other_agent_id == endpoint.agent_id:
                    agent.channel_bindings = _unique_str_list([*bindings, endpoint.id])
                else:
                    agent.channel_bindings = bindings

    for agent_id, agent in config.agents.instances.items():
        for endpoint_id in list(agent.channel_bindings):
            if endpoint_id.startswith("legacy:"):
                continue
            endpoint = next((item for item in config.channels.endpoints if item.id == endpoint_id), None)
            if endpoint is None:
                continue
            endpoint.agent_id = agent_id

    return config
