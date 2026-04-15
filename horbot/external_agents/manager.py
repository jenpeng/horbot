"""Manager for external third-party agents."""

from __future__ import annotations

from typing import Optional

from loguru import logger

from horbot.config.loader import get_cached_config
from horbot.config.schema import Config, ExternalAgentsConfig
from horbot.external_agents.models import ExternalAgentInstance


class ExternalAgentManager:
    """Loads and serves configured external agents."""

    _instance: Optional["ExternalAgentManager"] = None

    def __new__(cls) -> "ExternalAgentManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents = {}
            cls._instance._initialized = False
        return cls._instance

    @classmethod
    def get_instance(cls) -> "ExternalAgentManager":
        return cls()

    def initialize(self, config: Optional[Config] = None) -> None:
        if self._initialized:
            return
        config = config or get_cached_config()
        self._load(config.external_agents)
        self._initialized = True

    def reload(self, config: Optional[Config] = None) -> None:
        config = config or get_cached_config()
        self._agents.clear()
        self._load(config.external_agents)
        self._initialized = True
        logger.info("ExternalAgentManager reloaded with {} external agents", len(self._agents))

    def _load(self, external_agents_config: ExternalAgentsConfig) -> None:
        for agent_id, agent_config in external_agents_config.instances.items():
            agent_config.id = agent_id
            self._agents[agent_id] = ExternalAgentInstance(agent_config)

    def get_external_agent(self, agent_id: str) -> Optional[ExternalAgentInstance]:
        if not self._initialized:
            self.initialize()
        return self._agents.get(agent_id)

    def get_all_external_agents(self) -> list[ExternalAgentInstance]:
        if not self._initialized:
            self.initialize()
        return list(self._agents.values())


def get_external_agent_manager() -> ExternalAgentManager:
    """Get the shared external agent manager."""

    return ExternalAgentManager.get_instance()
