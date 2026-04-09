"""Workspace management for multi-agent system."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import shutil

from horbot.config.schema import AgentWorkspaceConfig, TeamWorkspaceConfig
from horbot.utils.paths import get_horbot_root, get_workspace_dir

AGENT_METADATA_DIRNAME = ".horbot-agent"
TEAM_METADATA_DIRNAME = ".horbot-team"


@dataclass
class WorkspaceContext:
    """Current workspace context."""

    agent_id: Optional[str] = None
    team_id: Optional[str] = None
    workspace_root: Path = field(default_factory=get_horbot_root)


class WorkspaceManager:
    """Manages workspaces for agents and teams."""

    _instance: Optional["WorkspaceManager"] = None
    _context: WorkspaceContext = field(default_factory=WorkspaceContext)

    def __new__(cls) -> "WorkspaceManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._context = WorkspaceContext()
        return cls._instance

    @classmethod
    def get_instance(cls) -> "WorkspaceManager":
        return cls()

    def get_agents_root(self) -> Path:
        """Get the root directory for all agent workspaces."""
        path = get_horbot_root() / "agents"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_teams_root(self) -> Path:
        """Get the root directory for all team workspaces."""
        path = get_horbot_root() / "teams"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_shared_root(self) -> Path:
        """Get the global shared resources directory."""
        path = get_horbot_root() / "shared"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _resolve_override_path(self, raw_path: str) -> Path:
        path = Path(raw_path).expanduser()
        if path.is_absolute():
            return path.resolve()

        if path.parts and path.parts[0] == ".horbot":
            root = get_horbot_root()
            suffix = Path(*path.parts[1:]) if len(path.parts) > 1 else Path()
            return (root / suffix).resolve()

        try:
            from horbot.config.loader import get_cached_config

            config = get_cached_config()
            project_root = config._find_project_root()
            base_dir = project_root if project_root else get_horbot_root().parent
        except Exception:
            base_dir = get_horbot_root().parent

        return (base_dir / path).resolve()

    def _get_agent_config(self, agent_id: str):
        try:
            from horbot.config.loader import get_cached_config

            config = get_cached_config()
            agent = config.agents.instances.get(agent_id)
            if agent is not None:
                return agent
            if agent_id == "main":
                return next(iter(config.agents.instances.values()), None)
        except Exception:
            return None
        return None

    def _get_agent_workspace_override(self, agent_id: str) -> str:
        agent = self._get_agent_config(agent_id)
        if agent and agent.workspace:
            return agent.workspace
        return ""

    def _get_team_workspace_override(self, team_id: str) -> str:
        try:
            from horbot.config.loader import get_cached_config

            config = get_cached_config()
            team = config.teams.instances.get(team_id)
            if team and team.workspace:
                return team.workspace
        except Exception:
            return ""
        return ""

    def get_agent_workspace(self, agent_id: str, personality: str = "") -> AgentWorkspaceConfig:
        """Get workspace configuration for an agent."""
        workspace_override = self._get_agent_workspace_override(agent_id)
        if workspace_override:
            workspace_path = self._resolve_override_path(workspace_override)
            metadata_root = workspace_path / AGENT_METADATA_DIRNAME
            memory_path = metadata_root / "memory"
            sessions_path = metadata_root / "sessions"
            skills_path = metadata_root / "skills"
        else:
            agent_root = self.get_agents_root() / agent_id
            workspace_path = agent_root / "workspace"
            memory_path = agent_root / "memory"
            sessions_path = agent_root / "sessions"
            skills_path = agent_root / "skills"

        for path in [workspace_path, memory_path, sessions_path, skills_path]:
            path.mkdir(parents=True, exist_ok=True)

        self._ensure_agent_soul(workspace_path, agent_id, personality)

        return AgentWorkspaceConfig(
            workspace_path=str(workspace_path),
            memory_path=str(memory_path),
            sessions_path=str(sessions_path),
            skills_path=str(skills_path),
        )

    def _ensure_agent_soul(self, workspace_path: Path, agent_id: str, personality: str = "") -> None:
        """Ensure the agent has a SOUL.md file."""
        soul_path = workspace_path / "SOUL.md"
        if not soul_path.exists() and personality:
            soul_content = f"# 灵魂\n\n{personality}\n\n---\n\n*这是 {agent_id} Agent 的个性配置文件。*"
            soul_path.write_text(soul_content, encoding="utf-8")

    def get_shared_user_path(self) -> Path:
        """Get the path to the shared USER.md file."""
        try:
            from horbot.config.loader import get_cached_config

            workspace_path = get_cached_config().workspace_path
        except Exception:
            workspace_path = get_workspace_dir()
        workspace_path.mkdir(parents=True, exist_ok=True)
        return workspace_path / "USER.md"

    def get_team_workspace(self, team_id: str) -> TeamWorkspaceConfig:
        """Get workspace configuration for a team."""
        workspace_override = self._get_team_workspace_override(team_id)
        if workspace_override:
            workspace_path = self._resolve_override_path(workspace_override)
            metadata_root = workspace_path / TEAM_METADATA_DIRNAME
            shared_memory_path = metadata_root / "shared_memory"
            taskboard_path = metadata_root / "taskboard"
        else:
            team_root = self.get_teams_root() / team_id
            workspace_path = team_root / "workspace"
            shared_memory_path = team_root / "shared_memory"
            taskboard_path = team_root / "taskboard"

        for path in [workspace_path, shared_memory_path, taskboard_path]:
            path.mkdir(parents=True, exist_ok=True)

        return TeamWorkspaceConfig(
            workspace_path=str(workspace_path),
            shared_memory_path=str(shared_memory_path),
            taskboard_path=str(taskboard_path),
        )

    def agent_exists(self, agent_id: str) -> bool:
        """Check if an agent workspace exists."""
        return (self.get_agents_root() / agent_id).exists()

    def team_exists(self, team_id: str) -> bool:
        """Check if a team workspace exists."""
        return (self.get_teams_root() / team_id).exists()

    def delete_agent_workspace(self, agent_id: str) -> bool:
        """Delete an agent's workspace."""
        agent_root = self.get_agents_root() / agent_id
        if agent_root.exists():
            shutil.rmtree(agent_root)
            return True
        return False

    def delete_agent_override_artifacts(self, raw_workspace_path: str) -> bool:
        """Delete Horbot-managed files from a custom agent workspace.

        For custom workspaces we only remove agent-owned metadata and bootstrap
        files, so user-managed project files in the same directory remain intact.
        """
        workspace_path = self._resolve_override_path(raw_workspace_path)
        removed = False
        cleanup_targets = [
            workspace_path / AGENT_METADATA_DIRNAME,
            workspace_path / "SOUL.md",
            workspace_path / "USER.md",
        ]

        for target in cleanup_targets:
            if not target.exists():
                continue
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            removed = True

        return removed

    def delete_team_workspace(self, team_id: str) -> bool:
        """Delete a team's workspace."""
        team_root = self.get_teams_root() / team_id
        if team_root.exists():
            shutil.rmtree(team_root)
            return True
        return False

    def set_context(self, agent_id: Optional[str] = None, team_id: Optional[str] = None) -> None:
        """Set the current workspace context."""
        self._context.agent_id = agent_id
        self._context.team_id = team_id

    def get_context(self) -> WorkspaceContext:
        """Get the current workspace context."""
        return self._context

    def resolve_path(self, path: str, respect_context: bool = True) -> Path:
        """Resolve a path within the current workspace context."""
        if not respect_context or (self._context.agent_id is None and self._context.team_id is None):
            return Path(path).expanduser().resolve()

        if path.startswith("workspace://"):
            if self._context.agent_id:
                ws = self.get_agent_workspace(self._context.agent_id)
                return Path(ws.workspace_path) / path[12:]
            if self._context.team_id:
                ws = self.get_team_workspace(self._context.team_id)
                return Path(ws.workspace_path) / path[12:]

        if path.startswith("team://") and self._context.team_id:
            ws = self.get_team_workspace(self._context.team_id)
            return Path(ws.workspace_path) / path[7:]

        if not Path(path).is_absolute():
            if self._context.agent_id:
                ws = self.get_agent_workspace(self._context.agent_id)
                return Path(ws.workspace_path) / path
            if self._context.team_id:
                ws = self.get_team_workspace(self._context.team_id)
                return Path(ws.workspace_path) / path

        return Path(path).expanduser().resolve()

    def list_agents(self) -> list[str]:
        """List all agent IDs that have workspaces."""
        agents_root = self.get_agents_root()
        if not agents_root.exists():
            return []
        return [d.name for d in agents_root.iterdir() if d.is_dir()]

    def list_teams(self) -> list[str]:
        """List all team IDs that have workspaces."""
        teams_root = self.get_teams_root()
        if not teams_root.exists():
            return []
        return [d.name for d in teams_root.iterdir() if d.is_dir()]

    def is_path_in_workspace(self, path: Path, agent_id: Optional[str] = None, team_id: Optional[str] = None) -> bool:
        """Check if a path is within a specific workspace."""
        path = path.resolve()

        if agent_id:
            ws = self.get_agent_workspace(agent_id)
            workspace_root = Path(ws.workspace_path).resolve()
            if path.is_relative_to(workspace_root):
                return True

        if team_id:
            ws = self.get_team_workspace(team_id)
            workspace_root = Path(ws.workspace_path).resolve()
            if path.is_relative_to(workspace_root):
                return True

        return False


def get_workspace_manager() -> WorkspaceManager:
    """Get the singleton WorkspaceManager instance."""
    return WorkspaceManager.get_instance()
