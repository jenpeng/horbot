"""Adapter registry for external agents."""

from __future__ import annotations

from horbot.external_agents.adapters.base import ExternalAgentAdapter
from horbot.external_agents.adapters.generic_agent_api import GenericAgentApiAdapter
from horbot.external_agents.adapters.inbound_bot import InboundBotAdapter
from horbot.external_agents.adapters.openai_compatible import OpenAICompatibleAdapter


class ExternalAgentAdapterRegistry:
    """Resolve adapter IDs and legacy transport aliases to adapter instances."""

    def __init__(self) -> None:
        generic = GenericAgentApiAdapter()
        inbound_bot = InboundBotAdapter()
        openai = OpenAICompatibleAdapter()
        self._adapters: dict[str, ExternalAgentAdapter] = {
            generic.adapter_id: generic,
            "generic": generic,
            "http": generic,
            "http_sse": generic,
            "sse-chat": generic,
            "websocket": generic,
            "websocket-chat": generic,
            inbound_bot.adapter_id: inbound_bot,
            "channel-backed-agent": inbound_bot,
            "web-ui-bridge": inbound_bot,
            openai.adapter_id: openai,
            "openai": openai,
            "openai-chat-completions": openai,
        }

    def get(self, adapter_id: str) -> ExternalAgentAdapter | None:
        return self._adapters.get(adapter_id.strip().lower())

    def register(self, adapter_id: str, adapter: ExternalAgentAdapter, *aliases: str) -> None:
        """Register a first-party or plugin-provided adapter."""

        self._adapters[adapter_id.strip().lower()] = adapter
        for alias in aliases:
            self._adapters[alias.strip().lower()] = adapter

    def list_adapter_ids(self) -> list[str]:
        return sorted(self._adapters.keys())


_registry: ExternalAgentAdapterRegistry | None = None


def get_external_agent_adapter_registry() -> ExternalAgentAdapterRegistry:
    global _registry
    if _registry is None:
        _registry = ExternalAgentAdapterRegistry()
    return _registry
