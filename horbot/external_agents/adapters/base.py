"""Base helpers and contracts for external third-party agent adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from horbot.config.schema import ExternalAgentConfig
from horbot.external_agents.models import ExternalAgentInstance


ExternalAgentResult = dict[str, object]


def build_auth_headers(config: ExternalAgentConfig) -> dict[str, str]:
    """Build outbound auth headers for an external agent probe/call."""

    if config.auth_type == "none" or not config.auth_secret:
        return {}

    header_name = (config.auth_header or "Authorization").strip() or "Authorization"
    if config.auth_type == "bearer":
        return {header_name: f"Bearer {config.auth_secret}"}
    return {header_name: config.auth_secret}


def build_standard_request_payload(
    agent: ExternalAgentInstance,
    *,
    message: str,
    session_key: str,
    history: list[dict[str, Any]] | None = None,
    conversation: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build Horbot's canonical external-agent request envelope."""

    config = agent.config
    max_turn_chars = max(1000, int(config.max_turn_chars or 12000))
    trimmed_message = (message or "").strip()[:max_turn_chars]
    normalized_history: list[dict[str, Any]] = []
    for item in history or []:
        role = str(item.get("role") or "").strip() or "user"
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        normalized_history.append({
            "role": role,
            "content": content[:max_turn_chars],
            "agent_id": item.get("agent_id"),
            "agent_name": item.get("agent_name"),
        })

    return {
        "message": trimmed_message,
        "session_key": session_key,
        "agent": {
            "id": agent.id,
            "name": agent.name,
            "description": config.description,
            "capabilities": list(config.capabilities or []),
            "adapter": config.adapter,
            "transport": config.transport,
        },
        "history": normalized_history,
        "conversation": dict(conversation or {}),
        "metadata": dict(metadata or {}),
    }


def extract_content_from_payload(payload: Any) -> str:
    """Extract assistant text from common vendor/generic response shapes."""

    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, dict):
        for key in ("content", "message", "output", "reply", "text", "response"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        choices = payload.get("choices")
        if isinstance(choices, list):
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                message = choice.get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str) and content.strip():
                        return content.strip()
                content = choice.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
    return ""


class ExternalAgentAdapter(ABC):
    """Protocol adapter for a vendor/platform/local external agent."""

    adapter_id = "base"

    @abstractmethod
    async def complete(
        self,
        agent: ExternalAgentInstance,
        *,
        message: str,
        session_key: str,
        history: list[dict[str, Any]] | None = None,
        conversation: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExternalAgentResult:
        """Send one chat turn to an external agent."""

    @abstractmethod
    async def probe(self, agent: ExternalAgentInstance) -> ExternalAgentResult:
        """Probe an external agent endpoint without sending a user task."""
