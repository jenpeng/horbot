"""Workspace access control for multi-agent system."""

from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from horbot.workspace.manager import WorkspaceManager, get_workspace_manager


@dataclass
class AccessCheckResult:
    """Result of an access check."""
    allowed: bool
    reason: str = ""
    resolved_path: Optional[Path] = None


class WorkspaceAccessControl:
    """Controls access to workspace resources.
    
    Enforces:
    - Agent can only access its own workspace
    - Agent can access team workspace if it's a member
    - No access to other agents' workspaces
    """
    
    def __init__(self, workspace_manager: Optional[WorkspaceManager] = None):
        self._manager = workspace_manager or get_workspace_manager()
    
    def check_read_access(
        self,
        path: Path,
        agent_id: Optional[str] = None,
        team_ids: Optional[list[str]] = None
    ) -> AccessCheckResult:
        """Check if an agent has read access to a path."""
        path = path.resolve()
        
        if agent_id:
            agent_ws = self._manager.get_agent_workspace(agent_id)
            agent_root = Path(agent_ws.workspace_path).resolve()
            if path.is_relative_to(agent_root):
                return AccessCheckResult(allowed=True, reason="Agent workspace", resolved_path=path)
        
        if team_ids:
            for team_id in team_ids:
                team_ws = self._manager.get_team_workspace(team_id)
                team_root = Path(team_ws.workspace_path).resolve()
                if path.is_relative_to(team_root):
                    return AccessCheckResult(allowed=True, reason=f"Team {team_id} workspace", resolved_path=path)
        
        shared_root = self._manager.get_shared_root().resolve()
        if path.is_relative_to(shared_root):
            return AccessCheckResult(allowed=True, reason="Shared resources", resolved_path=path)
        
        return AccessCheckResult(allowed=False, reason="Path outside accessible workspaces")
    
    def check_write_access(
        self,
        path: Path,
        agent_id: Optional[str] = None,
        team_ids: Optional[list[str]] = None
    ) -> AccessCheckResult:
        """Check if an agent has write access to a path."""
        path = path.resolve()
        
        if agent_id:
            agent_ws = self._manager.get_agent_workspace(agent_id)
            agent_root = Path(agent_ws.workspace_path).resolve()
            if path.is_relative_to(agent_root):
                return AccessCheckResult(allowed=True, reason="Agent workspace", resolved_path=path)
        
        if team_ids:
            for team_id in team_ids:
                team_ws = self._manager.get_team_workspace(team_id)
                team_root = Path(team_ws.workspace_path).resolve()
                if path.is_relative_to(team_root):
                    return AccessCheckResult(allowed=True, reason=f"Team {team_id} workspace", resolved_path=path)
        
        shared_root = self._manager.get_shared_root().resolve()
        if path.is_relative_to(shared_root):
            return AccessCheckResult(allowed=False, reason="Shared resources are read-only")
        
        return AccessCheckResult(allowed=False, reason="Path outside accessible workspaces")
    
    def resolve_path_in_context(
        self,
        path: str,
        agent_id: Optional[str] = None,
        team_ids: Optional[list[str]] = None
    ) -> Path:
        """Resolve a path within the agent's context.
        
        - Absolute paths are returned as-is
        - Relative paths are resolved within agent workspace (if set)
        - Supports workspace:// and team:// protocol prefixes
        """
        if path.startswith("workspace://"):
            if agent_id:
                ws = self._manager.get_agent_workspace(agent_id)
                return Path(ws.workspace_path) / path[12:]
            raise ValueError("No agent context for workspace:// path")
        
        if path.startswith("team://"):
            parts = path[7:].split("/", 1)
            if len(parts) == 2:
                team_id, rest = parts
                ws = self._manager.get_team_workspace(team_id)
                return Path(ws.workspace_path) / rest
            raise ValueError(f"Invalid team:// path format: {path}")
        
        p = Path(path).expanduser()
        if p.is_absolute():
            return p.resolve()
        
        if agent_id:
            ws = self._manager.get_agent_workspace(agent_id)
            return (Path(ws.workspace_path) / path).resolve()
        
        return p.resolve()


def get_access_control() -> WorkspaceAccessControl:
    """Get the singleton WorkspaceAccessControl instance."""
    return WorkspaceAccessControl()
