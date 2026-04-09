"""Team management for multi-agent system."""

from .shared_memory import SharedMemoryManager, SharedMemoryEntry, get_shared_memory_manager
from .manager import TeamManager, TeamInstance, get_team_manager

__all__ = [
    "SharedMemoryManager",
    "SharedMemoryEntry",
    "get_shared_memory_manager",
    "TeamManager",
    "TeamInstance",
    "get_team_manager",
]
