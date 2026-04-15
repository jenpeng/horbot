"""Runtime models for external third-party agents."""

from __future__ import annotations

from typing import Any

from horbot.config.schema import ExternalAgentConfig


class ExternalAgentInstance:
    """Represents one configured external agent endpoint."""

    def __init__(self, config: ExternalAgentConfig):
        self._config = config

    @property
    def id(self) -> str:
        return self._config.id

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def config(self) -> ExternalAgentConfig:
        return self._config

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self._config.id,
            "name": self._config.name,
            "description": self._config.description,
            "avatar": self._config.avatar,
            "transport": self._config.transport,
            "endpoint": self._config.endpoint,
            "auth_type": self._config.auth_type,
            "auth_header": self._config.auth_header,
            "auth_secret_configured": bool(self._config.auth_secret),
            "capabilities": list(self._config.capabilities),
            "dm_enabled": self._config.dm_enabled,
            "team_enabled": self._config.team_enabled,
            "mention_required": self._config.mention_required,
            "timeout_s": self._config.timeout_s,
            "max_turn_chars": self._config.max_turn_chars,
            "context_scope": self._config.context_scope,
            "memory_access": self._config.memory_access,
            "file_access": self._config.file_access,
            "metadata": dict(self._config.metadata or {}),
        }
