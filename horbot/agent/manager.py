"""Agent management for multi-agent system."""

from pathlib import Path
from typing import Optional, Dict, Any

from loguru import logger

from horbot.config.schema import AgentConfig, AgentsConfig, Config
from horbot.config.loader import get_cached_config
from horbot.utils.paths import get_agent_memory_dir
from horbot.workspace.manager import get_workspace_manager


class AgentInstance:
    """Represents a running agent instance."""
    
    def __init__(self, config: AgentConfig):
        self._config = config
        self._workspace_manager = get_workspace_manager()
    
    @property
    def id(self) -> str:
        return self._config.id
    
    @property
    def name(self) -> str:
        return self._config.name
    
    @property
    def description(self) -> str:
        return self._config.description
    
    @property
    def model(self) -> str:
        return self._config.model.strip()

    @property
    def provider(self) -> str:
        if self._config.provider and self._config.provider != "auto":
            return self._config.provider
        if not self.model:
            return ""
        config = get_cached_config()
        return config.get_provider_name(self.model) or ""

    @property
    def setup_required(self) -> bool:
        return not bool(self.model and self.provider)
    
    @property
    def capabilities(self) -> list[str]:
        return self._config.capabilities
    
    @property
    def teams(self) -> list[str]:
        return self._config.teams
    
    @property
    def is_main(self) -> bool:
        return self._config.is_main
    
    @property
    def personality(self) -> str:
        return self._config.personality

    @property
    def config(self) -> AgentConfig:
        return self._config
    
    def get_workspace(self) -> Path:
        """Get the agent's workspace directory."""
        personality = self._config.personality if self._config else ""
        ws = self._workspace_manager.get_agent_workspace(self.id, personality)
        return Path(ws.workspace_path)
    
    def get_memory_dir(self) -> Path:
        """Get the agent's memory directory."""
        return get_agent_memory_dir(self.id)
    
    def get_sessions_dir(self) -> Path:
        """Get the agent's sessions directory."""
        personality = self._config.personality if self._config else ""
        ws = self._workspace_manager.get_agent_workspace(self.id, personality)
        return Path(ws.sessions_path)
    
    def get_skills_dir(self) -> Path:
        """Get the agent's skills directory."""
        personality = self._config.personality if self._config else ""
        ws = self._workspace_manager.get_agent_workspace(self.id, personality)
        return Path(ws.skills_path)
    
    def has_capability(self, capability: str) -> bool:
        """Check if the agent has a specific capability."""
        return capability in self._config.capabilities
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        workspace = self.get_workspace()
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "profile": self._config.profile,
            "permission_profile": self._config.permission_profile,
            "model": self.model,
            "provider": self.provider,
            "model_override": self._config.model,
            "provider_override": self._config.provider,
            "capabilities": self.capabilities,
            "tools": self._config.tools,
            "skills": self._config.skills,
            "teams": self.teams,
            "is_main": self.is_main,
            "system_prompt": self._config.system_prompt,
            "personality": self._config.personality,
            "avatar": self._config.avatar,
            "workspace": self._config.workspace,
            "effective_workspace": str(workspace),
            "evolution_enabled": self._config.evolution_enabled,
            "learning_enabled": self._config.learning_enabled,
            "memory_bank_profile": self._config.memory_bank_profile.model_dump(),
            "setup_required": self.setup_required,
        }


class AgentManager:
    """Manages all agent instances.
    
    Responsibilities:
    - Load agent configurations
    - Create and manage agent instances
    - Provide agent lookup by ID or capability
    - Manage agent workspaces
    """
    
    _instance: Optional["AgentManager"] = None
    
    def __new__(cls) -> "AgentManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents: Dict[str, AgentInstance] = {}
            cls._instance._main_agent_id: Optional[str] = None
            cls._instance._initialized = False
        return cls._instance
    
    @classmethod
    def get_instance(cls) -> "AgentManager":
        return cls()
    
    def initialize(self, config: Optional[Config] = None) -> None:
        """Initialize the manager with configuration."""
        if self._initialized:
            return
        
        config = config or get_cached_config()
        self._load_agents(config.agents)
        self._initialized = True
    
    def reload(self, config: Optional[Config] = None) -> None:
        """Reload agents from configuration.
        
        This method clears existing agents and reloads from config.
        Used for hot-reload when configuration changes.
        """
        config = config or get_cached_config()
        self._agents.clear()
        self._main_agent_id = None
        self._load_agents(config.agents)
        self._initialized = True
        logger.info(f"AgentManager reloaded with {len(self._agents)} agents")
    
    def _load_agents(self, agents_config: AgentsConfig) -> None:
        """Load agents from configuration."""
        if agents_config.instances:
            for agent_id, agent_config in agents_config.instances.items():
                agent_config.id = agent_id
                self._create_agent(agent_config)
        if self._agents:
            if "main" in self._agents:
                self._main_agent_id = "main"
            elif not self._main_agent_id:
                self._main_agent_id = next(iter(self._agents.keys()))
        self._sync_default_agent_marker()
    
    def _create_agent(self, config: AgentConfig) -> AgentInstance:
        """Create an agent instance and its workspace."""
        instance = AgentInstance(config)
        self._agents[config.id] = instance
        
        if self._main_agent_id is None:
            self._main_agent_id = config.id
        config.is_main = config.id == self._main_agent_id
        
        self._ensure_workspace(config.id, config.personality)
        
        return instance

    def _sync_default_agent_marker(self) -> None:
        """Keep the legacy is_main marker aligned with the current default agent."""
        for agent_id, agent in self._agents.items():
            agent.config.is_main = agent_id == self._main_agent_id
    
    def _ensure_workspace(self, agent_id: str, personality: str = "") -> None:
        """Ensure the agent's workspace exists."""
        get_workspace_manager().get_agent_workspace(agent_id, personality)
    
    def get_agent(self, agent_id: str) -> Optional[AgentInstance]:
        """Get an agent by ID."""
        if not self._initialized:
            self.initialize()
        agent = self._agents.get(agent_id)
        if agent is not None:
            return agent
        if agent_id == "main":
            return self.get_default_agent()
        return None

    def get_default_agent(self) -> Optional[AgentInstance]:
        """Get the default agent for generic fallbacks."""
        if not self._initialized:
            self.initialize()
        if self._main_agent_id:
            return self._agents.get(self._main_agent_id)
        return next(iter(self._agents.values()), None)

    def get_main_agent(self) -> Optional[AgentInstance]:
        """Backward-compatible alias for the default agent."""
        return self.get_default_agent()
    
    def get_all_agents(self) -> list[AgentInstance]:
        """Get all agent instances."""
        if not self._initialized:
            self.initialize()
        return list(self._agents.values())
    
    def get_agents_by_capability(self, capability: str) -> list[AgentInstance]:
        """Get agents that have a specific capability."""
        if not self._initialized:
            self.initialize()
        return [a for a in self._agents.values() if a.has_capability(capability)]
    
    def get_agents_in_team(self, team_id: str) -> list[AgentInstance]:
        """Get agents that are members of a specific team."""
        if not self._initialized:
            self.initialize()
        return [a for a in self._agents.values() if team_id in a.teams]
    
    def register_agent(self, config: AgentConfig) -> AgentInstance:
        """Register a new agent."""
        if config.id in self._agents:
            raise ValueError(f"Agent {config.id} already exists")
        instance = self._create_agent(config)
        self._sync_default_agent_marker()
        return instance
    
    def unregister_agent(self, agent_id: str) -> bool:
        """Unregister an agent."""
        if agent_id in self._agents:
            del self._agents[agent_id]
            if self._main_agent_id == agent_id:
                self._main_agent_id = next(iter(self._agents.keys()), None)
            self._sync_default_agent_marker()
            return True
        return False
    
    def list_agent_ids(self) -> list[str]:
        """List all agent IDs."""
        if not self._initialized:
            self.initialize()
        return list(self._agents.keys())


def get_agent_manager() -> AgentManager:
    """Get the singleton AgentManager instance."""
    return AgentManager.get_instance()
