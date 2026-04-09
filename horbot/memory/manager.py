"""Unified memory management for multi-agent system."""

from pathlib import Path
from typing import Optional
from datetime import datetime
import json
from dataclasses import dataclass

from horbot.utils.paths import (
    get_agent_memory_dir,
    get_team_shared_memory_dir,
    get_memory_dir
)
from horbot.team.shared_memory import SharedMemoryManager


@dataclass
class MemoryContext:
    """Context for memory operations."""
    agent_id: Optional[str] = None
    team_ids: list[str] = None
    
    def __post_init__(self):
        if self.team_ids is None:
            self.team_ids = []


class UnifiedMemoryManager:
    """Unified memory manager for agent and team memories.
    
    Provides a unified interface for:
    - Agent private memory (isolated)
    - Team shared memory (collaborative)
    - Global memory (common knowledge)
    """
    
    _instance: Optional["UnifiedMemoryManager"] = None
    
    def __new__(cls) -> "UnifiedMemoryManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._context = MemoryContext()
        return cls._instance
    
    @classmethod
    def get_instance(cls) -> "UnifiedMemoryManager":
        return cls()
    
    def set_context(self, agent_id: Optional[str] = None, team_ids: Optional[list[str]] = None) -> None:
        """Set the current memory context."""
        self._context.agent_id = agent_id
        self._context.team_ids = team_ids or []
    
    def get_context(self) -> MemoryContext:
        return self._context
    
    def get_agent_memory_path(self, filename: str = "MEMORY.md") -> Optional[Path]:
        """Get path to agent's memory file."""
        if not self._context.agent_id:
            return None
        return get_agent_memory_dir(self._context.agent_id) / filename
    
    def read_agent_memory(self) -> str:
        """Read agent's private memory."""
        path = self.get_agent_memory_path("MEMORY.md")
        if path and path.exists():
            return path.read_text(encoding="utf-8")
        return ""
    
    def write_agent_memory(self, content: str) -> None:
        """Write to agent's private memory."""
        path = self.get_agent_memory_path("MEMORY.md")
        if path:
            path.write_text(content, encoding="utf-8")
    
    def append_agent_memory(self, content: str) -> None:
        """Append to agent's private memory."""
        path = self.get_agent_memory_path("MEMORY.md")
        if path:
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"\n{content}")
    
    def get_agent_history_path(self) -> Optional[Path]:
        """Get path to agent's history file."""
        return self.get_agent_memory_path("HISTORY.md")
    
    def append_to_history(self, entry: str) -> None:
        """Append an entry to agent's history."""
        path = self.get_agent_history_path()
        if path:
            timestamp = datetime.now().isoformat()
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"\n## [{timestamp}]\n{entry}\n")
    
    def get_team_memory_manager(self, team_id: str) -> SharedMemoryManager:
        """Get shared memory manager for a team."""
        return SharedMemoryManager(team_id)
    
    def read_team_insights(self, team_id: str) -> str:
        """Read team's shared insights."""
        return self.get_team_memory_manager(team_id).read_insights()
    
    def read_team_decisions(self, team_id: str) -> str:
        """Read team's shared decisions."""
        return self.get_team_memory_manager(team_id).read_decisions()
    
    def read_team_context(self, team_id: str) -> str:
        """Read team's shared context."""
        return self.get_team_memory_manager(team_id).read_context()
    
    def append_team_insight(self, team_id: str, content: str) -> None:
        """Append an insight to team's shared memory."""
        if not self._context.agent_id:
            raise ValueError("No agent context set")
        self.get_team_memory_manager(team_id).append_insight(content, self._context.agent_id)
    
    def append_team_decision(self, team_id: str, content: str) -> None:
        """Append a decision to team's shared memory."""
        if not self._context.agent_id:
            raise ValueError("No agent context set")
        self.get_team_memory_manager(team_id).append_decision(content, self._context.agent_id)
    
    def get_all_context(self) -> str:
        """Get all relevant memory context for current agent.
        
        Combines:
        - Agent private memory
        - All team shared memories
        - Global memory
        """
        parts = []
        
        agent_memory = self.read_agent_memory()
        if agent_memory:
            parts.append(f"# Agent Memory\n\n{agent_memory}")
        
        for team_id in self._context.team_ids:
            team_context = self.read_team_context(team_id)
            if team_context:
                parts.append(f"# Team {team_id} Context\n\n{team_context}")
        
        return "\n\n---\n\n".join(parts)
    
    def search_memories(self, query: str) -> list[dict]:
        """Search across all accessible memories."""
        results = []
        
        agent_memory = self.read_agent_memory()
        if query.lower() in agent_memory.lower():
            results.append({
                "source": "agent",
                "agent_id": self._context.agent_id,
                "match": "MEMORY.md"
            })
        
        for team_id in self._context.team_ids:
            entries = self.get_team_memory_manager(team_id).search_entries(query)
            for entry in entries:
                results.append({
                    "source": "team",
                    "team_id": team_id,
                    "entry": entry
                })
        
        return results
    
    def cleanup_old_history(self, max_entries: int = 1000) -> None:
        """Clean up old history entries."""
        path = self.get_agent_history_path()
        if not path or not path.exists():
            return
        
        lines = path.read_text(encoding="utf-8").split("\n")
        if len(lines) > max_entries:
            kept_lines = lines[-max_entries:]
            path.write_text("\n".join(kept_lines), encoding="utf-8")
    
    def archive_memory(self, archive_name: str) -> None:
        """Archive current memory state."""
        if not self._context.agent_id:
            return
        
        archive_dir = get_agent_memory_dir(self._context.agent_id) / "archives"
        archive_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_path = archive_dir / f"{archive_name}_{timestamp}.json"
        
        archive_data = {
            "agent_id": self._context.agent_id,
            "timestamp": datetime.now().isoformat(),
            "memory": self.read_agent_memory(),
        }
        
        archive_path.write_text(json.dumps(archive_data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_memory_manager() -> UnifiedMemoryManager:
    """Get the singleton UnifiedMemoryManager instance."""
    return UnifiedMemoryManager.get_instance()
