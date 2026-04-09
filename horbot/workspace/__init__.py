"""Workspace management for multi-agent system."""

from .manager import WorkspaceManager, WorkspaceContext, get_workspace_manager
from .access_control import WorkspaceAccessControl, AccessCheckResult, get_access_control

__all__ = [
    "WorkspaceManager",
    "WorkspaceContext",
    "get_workspace_manager",
    "WorkspaceAccessControl",
    "AccessCheckResult",
    "get_access_control",
]
