"""External third-party agent management."""

from horbot.external_agents.manager import ExternalAgentManager, get_external_agent_manager
from horbot.external_agents.runtime import ExternalAgentRuntime, get_external_agent_runtime

__all__ = [
    "ExternalAgentManager",
    "ExternalAgentRuntime",
    "get_external_agent_manager",
    "get_external_agent_runtime",
]
