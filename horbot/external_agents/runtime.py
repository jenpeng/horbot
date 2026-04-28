"""Runtime dispatcher for external-agent adapters."""

from __future__ import annotations

from typing import Any, Optional

from horbot.external_agents.models import ExternalAgentInstance
from horbot.external_agents.registry import get_external_agent_adapter_registry


class ExternalAgentRuntime:
    """Dispatch external-agent calls to protocol/vendor adapters."""

    def _resolve_adapter_id(self, agent: ExternalAgentInstance) -> str:
        config = agent.config
        adapter_id = str(getattr(config, "adapter", "") or "").strip().lower()
        if adapter_id:
            return adapter_id
        return str(config.transport or "generic-agent-api").strip().lower()

    def _resolve_adapter(self, agent: ExternalAgentInstance):
        adapter_id = self._resolve_adapter_id(agent)
        registry = get_external_agent_adapter_registry()
        adapter = registry.get(adapter_id)
        if adapter is not None:
            return adapter_id, adapter
        return adapter_id, None

    async def complete(
        self,
        agent: ExternalAgentInstance,
        *,
        message: str,
        session_key: str,
        history: list[dict[str, Any]] | None = None,
        conversation: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, object]:
        adapter_id, adapter = self._resolve_adapter(agent)
        if adapter is None:
            return {
                "ok": False,
                "detail": f"Unsupported external agent adapter: {adapter_id}",
                "adapter": adapter_id,
                "endpoint": agent.config.endpoint,
                "mode": "adapter_dispatch",
                "content": "",
            }

        result = await adapter.complete(
            agent,
            message=message,
            session_key=session_key,
            history=history,
            conversation=conversation,
            metadata=metadata,
        )
        result.setdefault("adapter", adapter.adapter_id)
        return result

    async def probe(self, agent: ExternalAgentInstance) -> dict[str, object]:
        adapter_id, adapter = self._resolve_adapter(agent)
        if adapter is None:
            return {
                "ok": False,
                "detail": f"Unsupported external agent adapter: {adapter_id}",
                "adapter": adapter_id,
                "endpoint": agent.config.endpoint,
                "mode": "adapter_probe",
            }

        result = await adapter.probe(agent)
        result.setdefault("adapter", adapter.adapter_id)
        return result


_runtime: Optional[ExternalAgentRuntime] = None


def get_external_agent_runtime() -> ExternalAgentRuntime:
    """Get the shared external-agent runtime dispatcher."""

    global _runtime
    if _runtime is None:
        _runtime = ExternalAgentRuntime()
    return _runtime
