"""Inbound bot endpoint adapter for vendor/local external agents."""

from __future__ import annotations

from typing import Any

from horbot.external_agents.adapters.base import ExternalAgentAdapter, ExternalAgentResult
from horbot.external_agents.models import ExternalAgentInstance


class InboundBotAdapter(ExternalAgentAdapter):
    """Expose a Horbot-issued bot endpoint for external platforms to push into."""

    adapter_id = "inbound-bot"

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
        inbound = agent.to_dict().get("inbound") or {}
        return {
            "ok": False,
            "detail": "Inbound Bot Endpoint waits for the external platform to push messages into Horbot; outbound task dispatch is not supported for this adapter.",
            "mode": "inbound_bot",
            "content": "",
            "inbound": inbound,
        }

    async def probe(self, agent: ExternalAgentInstance) -> ExternalAgentResult:
        inbound = agent.to_dict().get("inbound") or {}
        if not inbound:
            return {
                "ok": False,
                "detail": "Inbound bot credentials are missing. Save the external agent again to generate App ID and Token.",
                "mode": "inbound_bot_probe",
            }
        return {
            "ok": True,
            "detail": "Inbound Bot Endpoint is ready. Configure the App ID, Token, and Inbound URL in the external platform.",
            "mode": "inbound_bot_probe",
            "inbound": inbound,
        }
