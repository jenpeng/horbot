"""Team management for multi-agent system."""

from pathlib import Path
from typing import Optional, Dict, Any, List

from loguru import logger

from horbot.config.schema import TeamConfig, TeamsConfig, Config
from horbot.config.loader import get_cached_config
from horbot.workspace.manager import get_workspace_manager
from horbot.team.shared_memory import SharedMemoryManager


class TeamInstance:
    """Represents a team instance."""
    
    def __init__(self, config: TeamConfig):
        self._config = config
        self._workspace_manager = get_workspace_manager()
        self._shared_memory: Optional[SharedMemoryManager] = None
    
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
    def members(self) -> List[str]:
        return self._config.members

    @property
    def member_profiles(self) -> Dict[str, Any]:
        return {
            agent_id: profile.model_dump(by_alias=True)
            for agent_id, profile in self._config.member_profiles.items()
        }

    def get_member_profile(self, agent_id: str) -> Dict[str, Any]:
        profile = self._config.member_profiles.get(agent_id)
        if profile is None:
            return {
                "role": "member",
                "responsibility": "",
                "priority": 100,
                "isLead": False,
            }
        return profile.model_dump(by_alias=True)

    def get_ordered_member_ids(self) -> List[str]:
        def sort_key(agent_id: str) -> tuple[int, int, int]:
            profile = self._config.member_profiles.get(agent_id)
            is_lead = 1 if profile and profile.is_lead else 0
            priority = profile.priority if profile else 100
            original_index = self._config.members.index(agent_id)
            return (-is_lead, priority, original_index)

        return sorted(self._config.members, key=sort_key)
    
    @property
    def config(self) -> TeamConfig:
        return self._config
    
    def get_workspace(self) -> Path:
        """Get the team's shared workspace directory."""
        ws = self._workspace_manager.get_team_workspace(self.id)
        return Path(ws.workspace_path)
    
    def get_shared_memory(self) -> SharedMemoryManager:
        """Get the team's shared memory manager."""
        if self._shared_memory is None:
            self._shared_memory = SharedMemoryManager(self.id)
        return self._shared_memory
    
    def has_member(self, agent_id: str) -> bool:
        """Check if an agent is a member of this team."""
        return agent_id in self._config.members
    
    def add_member(self, agent_id: str) -> None:
        """Add an agent to the team."""
        if agent_id not in self._config.members:
            self._config.members.append(agent_id)
    
    def remove_member(self, agent_id: str) -> bool:
        """Remove an agent from the team."""
        if agent_id in self._config.members:
            self._config.members.remove(agent_id)
            return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        workspace = self.get_workspace()
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "members": self.members,
            "member_profiles": self.member_profiles,
            "workspace": self._config.workspace,
            "effective_workspace": str(workspace),
        }


class TeamManager:
    """Manages all team instances.
    
    Responsibilities:
    - Load team configurations
    - Create and manage team instances
    - Manage team membership
    - Provide team lookup by ID or member
    """
    
    _instance: Optional["TeamManager"] = None
    
    def __new__(cls) -> "TeamManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._teams: Dict[str, TeamInstance] = {}
            cls._instance._initialized = False
        return cls._instance
    
    @classmethod
    def get_instance(cls) -> "TeamManager":
        return cls()
    
    def initialize(self, config: Optional[Config] = None) -> None:
        """Initialize the manager with configuration."""
        if self._initialized:
            return
        
        config = config or get_cached_config()
        self._load_teams(config.teams)
        self._initialized = True
    
    def reload(self, config: Optional[Config] = None) -> None:
        """Reload teams from configuration.
        
        This method clears existing teams and reloads from config.
        Used for hot-reload when configuration changes.
        """
        config = config or get_cached_config()
        self._teams.clear()
        self._load_teams(config.teams)
        self._initialized = True
        logger.info(f"TeamManager reloaded with {len(self._teams)} teams")
    
    def _load_teams(self, teams_config: TeamsConfig) -> None:
        """Load teams from configuration."""
        if teams_config.instances:
            for team_id, team_config in teams_config.instances.items():
                team_config.id = team_id
                self._create_team(team_config)
    
    def _create_team(self, config: TeamConfig) -> TeamInstance:
        """Create a team instance and its workspace."""
        instance = TeamInstance(config)
        self._teams[config.id] = instance
        
        self._ensure_workspace(config.id)
        
        return instance
    
    def _ensure_workspace(self, team_id: str) -> None:
        """Ensure the team's workspace exists."""
        get_workspace_manager().get_team_workspace(team_id)
    
    def get_team(self, team_id: str) -> Optional[TeamInstance]:
        """Get a team by ID."""
        if not self._initialized:
            self.initialize()
        return self._teams.get(team_id)
    
    def get_all_teams(self) -> List[TeamInstance]:
        """Get all team instances."""
        if not self._initialized:
            self.initialize()
        return list(self._teams.values())
    
    def get_teams_for_agent(self, agent_id: str) -> List[TeamInstance]:
        """Get all teams that an agent is a member of."""
        if not self._initialized:
            self.initialize()
        return [t for t in self._teams.values() if t.has_member(agent_id)]
    
    def get_team_ids_for_agent(self, agent_id: str) -> List[str]:
        """Get all team IDs that an agent is a member of."""
        return [t.id for t in self.get_teams_for_agent(agent_id)]
    
    def register_team(self, config: TeamConfig) -> TeamInstance:
        """Register a new team."""
        if config.id in self._teams:
            raise ValueError(f"Team {config.id} already exists")
        return self._create_team(config)
    
    def unregister_team(self, team_id: str) -> bool:
        """Unregister a team."""
        if team_id in self._teams:
            del self._teams[team_id]
            return True
        return False
    
    def add_agent_to_team(self, team_id: str, agent_id: str) -> bool:
        """Add an agent to a team."""
        team = self.get_team(team_id)
        if team:
            team.add_member(agent_id)
            return True
        return False
    
    def remove_agent_from_team(self, team_id: str, agent_id: str) -> bool:
        """Remove an agent from a team."""
        team = self.get_team(team_id)
        if team:
            return team.remove_member(agent_id)
        return False
    
    def list_team_ids(self) -> List[str]:
        """List all team IDs."""
        if not self._initialized:
            self.initialize()
        return list(self._teams.keys())


def get_team_manager() -> TeamManager:
    """Get the singleton TeamManager instance."""
    return TeamManager.get_instance()
