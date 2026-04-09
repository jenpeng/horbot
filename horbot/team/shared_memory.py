"""Team shared memory management."""

from pathlib import Path
from typing import Optional
from datetime import datetime
import json
from dataclasses import dataclass, field, asdict
import shutil
import re

from horbot.utils.paths import get_team_shared_memory_dir, get_agent_memory_dir


@dataclass
class SharedMemoryEntry:
    """A shared memory entry."""
    id: str
    content: str
    author_agent_id: str
    created_at: str
    updated_at: str
    tags: list[str] = field(default_factory=list)
    category: str = "general"


@dataclass
class MemoryVersion:
    """A version record for memory files."""
    version_id: str
    timestamp: str
    file_type: str
    agent_id: str
    description: str


class SharedMemoryManager:
    """Manages shared memory for a team.
    
    File structure:
    teams/{team_id}/shared_memory/
    ├── insights.md       # Team insights and learnings
    ├── decisions.md      # Important decisions
    ├── context.md        # Shared context
    ├── entries.json      # Structured entries index
    └── versions/         # Version history
        ├── insights/
        ├── decisions/
        └── context/
    """
    
    VERSION_DIR = "versions"
    SCOPES = {
        "team_decisions": ("team_decisions.md", "Team Decisions"),
        "shared_constraints": ("shared_constraints.md", "Shared Constraints"),
        "active_handoff": ("active_handoff.md", "Active Handoff"),
        "unresolved_blockers": ("unresolved_blockers.md", "Unresolved Blockers"),
    }
    SCOPE_FALLBACKS = {
        "team_decisions": ("team_decisions.md", "decisions.md"),
        "shared_constraints": ("shared_constraints.md", "insights.md"),
        "active_handoff": ("active_handoff.md", "context.md"),
        "unresolved_blockers": ("unresolved_blockers.md",),
    }
    
    def __init__(self, team_id: str):
        self._team_id = team_id
        self._memory_dir = get_team_shared_memory_dir(team_id)
        self._entries_file = self._memory_dir / "entries.json"
        self._versions_dir = self._memory_dir / self.VERSION_DIR
        self._versions_index = self._versions_dir / "versions_index.json"
        self._ensure_files()
    
    def _ensure_files(self) -> None:
        """Ensure all memory files exist."""
        for filename in ["insights.md", "decisions.md", "context.md"]:
            path = self._memory_dir / filename
            if not path.exists():
                path.write_text(f"# {filename.replace('.md', '').title()}\n\n", encoding="utf-8")
        for filename, title in self.SCOPES.values():
            path = self._memory_dir / filename
            if not path.exists():
                path.write_text(f"# {title}\n\n", encoding="utf-8")
        
        if not self._entries_file.exists():
            self._entries_file.write_text("[]", encoding="utf-8")
        
        for subdir in ["insights", "decisions", "context", *self.SCOPES.keys()]:
            version_subdir = self._versions_dir / subdir
            version_subdir.mkdir(parents=True, exist_ok=True)
        
        if not self._versions_index.exists():
            self._versions_index.write_text("[]", encoding="utf-8")
    
    def get_insights_path(self) -> Path:
        return self._memory_dir / "insights.md"
    
    def get_decisions_path(self) -> Path:
        return self._memory_dir / "decisions.md"
    
    def get_context_path(self) -> Path:
        return self._memory_dir / "context.md"

    def get_scope_path(self, scope: str) -> Path:
        filename, _title = self.SCOPES[scope]
        return self._memory_dir / filename
    
    def read_insights(self) -> str:
        return self.get_insights_path().read_text(encoding="utf-8")
    
    def read_decisions(self) -> str:
        return self.get_decisions_path().read_text(encoding="utf-8")
    
    def read_context(self) -> str:
        return self.get_context_path().read_text(encoding="utf-8")

    def read_scope(self, scope: str) -> str:
        fallback_names = self.SCOPE_FALLBACKS.get(scope, ())
        for filename in fallback_names:
            path = self._memory_dir / filename
            if path.exists():
                content = path.read_text(encoding="utf-8")
                body = re.sub(r"^#.*$", "", content, count=1, flags=re.MULTILINE).strip()
                if body:
                    return content
        return ""

    def _append_markdown_entry(self, path: Path, file_type: str, content: str, agent_id: str) -> None:
        self._create_version(file_type, agent_id, f"Before appending new {file_type}")
        timestamp = datetime.now().isoformat()
        entry = f"\n## [{timestamp}] by {agent_id}\n{content}\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
    
    def append_insight(self, content: str, agent_id: str) -> None:
        """Append an insight to the shared insights file."""
        self._append_markdown_entry(self.get_insights_path(), "insights", content, agent_id)

    def append_decision(self, content: str, agent_id: str) -> None:
        """Append a decision to the shared decisions file."""
        self._append_markdown_entry(self.get_decisions_path(), "decisions", content, agent_id)
        self.append_scope_entry("team_decisions", content, agent_id)

    def update_context(self, content: str, agent_id: str = "system") -> None:
        """Update the shared context file."""
        self._create_version("context", agent_id, "Before context update")
        path = self.get_context_path()
        path.write_text(content, encoding="utf-8")
        self.write_scope("active_handoff", content, agent_id)

    def write_scope(self, scope: str, content: str, agent_id: str = "system") -> None:
        path = self.get_scope_path(scope)
        self._create_version(scope, agent_id, f"Before updating {scope}")
        path.write_text(content, encoding="utf-8")

    def append_scope_entry(self, scope: str, content: str, agent_id: str) -> None:
        self._append_markdown_entry(self.get_scope_path(scope), scope, content, agent_id)
    
    def add_entry(self, entry: SharedMemoryEntry) -> None:
        """Add a structured entry to the index."""
        entries = self.list_entries()
        entries.append(asdict(entry))
        self._entries_file.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    
    def list_entries(self) -> list[dict]:
        """List all structured entries."""
        if not self._entries_file.exists():
            return []
        return json.loads(self._entries_file.read_text(encoding="utf-8"))
    
    def search_entries(self, query: str) -> list[dict]:
        """Search entries by content or tags."""
        entries = self.list_entries()
        query_lower = query.lower()
        return [
            e for e in entries
            if query_lower in e.get("content", "").lower()
            or query_lower in " ".join(e.get("tags", [])).lower()
        ]
    
    def sync_to_agent(self, agent_id: str) -> dict[str, str]:
        """Sync shared memory to an agent's memory directory.
        
        Returns a dict with the synced content types and their paths.
        """
        agent_memory_dir = get_agent_memory_dir(agent_id)
        synced = {}
        
        team_memory_link = agent_memory_dir / f"team_{self._team_id}"
        team_memory_link.mkdir(parents=True, exist_ok=True)
        
        for file_type, filename in [
            ("insights", "insights.md"),
            ("decisions", "decisions.md"),
            ("context", "context.md"),
            ("entries", "entries.json"),
        ]:
            src = self._memory_dir / filename
            dst = team_memory_link / filename
            if src.exists():
                shutil.copy2(src, dst)
                synced[file_type] = str(dst)
        
        return synced
    
    def merge_from_agent(self, agent_id: str, content: str, content_type: str = "insight") -> None:
        """Merge an agent's contribution into shared memory.
        
        Args:
            agent_id: The agent contributing the content
            content: The content to merge
            content_type: Type of content ('insight', 'decision', 'context')
        """
        if content_type == "insight":
            self.append_insight(content, agent_id)
        elif content_type == "decision":
            self.append_decision(content, agent_id)
        elif content_type == "context":
            current = self.read_context()
            timestamp = datetime.now().isoformat()
            updated = f"{current}\n\n## Update from {agent_id} [{timestamp}]\n{content}\n"
            self.update_context(updated, agent_id)
        else:
            entry = SharedMemoryEntry(
                id=f"merge_{datetime.now().strftime('%Y%m%d%H%M%S')}_{agent_id}",
                content=content,
                author_agent_id=agent_id,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                category=content_type,
            )
            self.add_entry(entry)

    @staticmethod
    def _truncate_markdown(content: str, max_chars: int) -> str:
        compact_lines = [line.strip() for line in content.splitlines() if line.strip()]
        if not compact_lines:
            return ""
        output: list[str] = []
        used = 0
        for line in compact_lines:
            addition = len(line) if not output else len(line) + 1
            if used + addition <= max_chars:
                output.append(line)
                used += addition
                continue
            if max_chars - used > 12:
                output.append(line[: max(8, max_chars - used - 3)].rstrip() + "...")
            break
        return "\n".join(output)

    def _infer_scopes_from_query(self, query: str | None) -> list[str]:
        if not query:
            return ["active_handoff", "unresolved_blockers"]
        normalized = query.lower()
        scopes: list[str] = []
        if any(token in normalized for token in ("决策", "方案", "decision", "plan", "design")):
            scopes.append("team_decisions")
        if any(token in normalized for token in ("约束", "边界", "限制", "规则", "constraint", "permission")):
            scopes.append("shared_constraints")
        if any(token in normalized for token in ("交接", "接力", "handoff", "relay", "下一棒")):
            scopes.append("active_handoff")
        if any(token in normalized for token in ("阻塞", "问题", "失败", "风险", "blocker", "issue", "error")):
            scopes.append("unresolved_blockers")
        return scopes or list(self.SCOPES.keys())

    def get_scoped_context(
        self,
        scopes: list[str] | None = None,
        query: str | None = None,
        *,
        max_chars_per_scope: int = 320,
    ) -> str:
        selected_scopes = scopes or self._infer_scopes_from_query(query)
        parts: list[str] = []
        for scope in selected_scopes:
            if scope not in self.SCOPES:
                continue
            content = self.read_scope(scope)
            if not content.strip():
                continue
            title = self.SCOPES[scope][1]
            parts.append(f"## {title}\n{self._truncate_markdown(content, max_chars_per_scope)}")
        return "\n\n".join(parts).strip()
    
    def _create_version(self, file_type: str, agent_id: str, description: str) -> None:
        """Create a version backup of a memory file."""
        source_map = {
            "insights": self.get_insights_path(),
            "decisions": self.get_decisions_path(),
            "context": self.get_context_path(),
            **{scope: self.get_scope_path(scope) for scope in self.SCOPES},
        }
        
        source_path = source_map.get(file_type)
        if not source_path or not source_path.exists():
            return
        
        timestamp = datetime.now()
        version_id = timestamp.strftime("%Y%m%d_%H%M%S")
        version_filename = f"{version_id}.md"
        
        version_dir = self._versions_dir / file_type
        version_path = version_dir / version_filename
        
        shutil.copy2(source_path, version_path)
        
        version_record = MemoryVersion(
            version_id=version_id,
            timestamp=timestamp.isoformat(),
            file_type=file_type,
            agent_id=agent_id,
            description=description,
        )
        
        versions = self._load_versions_index()
        versions.append(asdict(version_record))
        self._save_versions_index(versions)
    
    def _load_versions_index(self) -> list[dict]:
        """Load the versions index."""
        if not self._versions_index.exists():
            return []
        return json.loads(self._versions_index.read_text(encoding="utf-8"))
    
    def _save_versions_index(self, versions: list[dict]) -> None:
        """Save the versions index."""
        self._versions_index.write_text(
            json.dumps(versions, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    
    def get_version(self, timestamp: str) -> Optional[dict]:
        """Get a specific version of memory files.
        
        Args:
            timestamp: ISO format timestamp or version_id (YYYYMMDD_HHMMSS)
        
        Returns:
            Dict with version info and content, or None if not found.
        """
        versions = self._load_versions_index()
        
        matching_version = None
        for v in versions:
            if timestamp in v["version_id"] or timestamp in v["timestamp"]:
                matching_version = v
                break
        
        if not matching_version:
            return None
        
        file_type = matching_version["file_type"]
        version_id = matching_version["version_id"]
        version_path = self._versions_dir / file_type / f"{version_id}.md"
        
        if not version_path.exists():
            return None
        
        return {
            "version_info": matching_version,
            "content": version_path.read_text(encoding="utf-8"),
            "path": str(version_path),
        }
    
    def list_versions(self, file_type: Optional[str] = None) -> list[dict]:
        """List all versions, optionally filtered by file type.
        
        Args:
            file_type: Optional filter ('insights', 'decisions', 'context')
        
        Returns:
            List of version records, newest first.
        """
        versions = self._load_versions_index()
        
        if file_type:
            versions = [v for v in versions if v["file_type"] == file_type]
        
        versions.sort(key=lambda x: x["timestamp"], reverse=True)
        return versions
    
    def restore_version(self, version_id: str, agent_id: str = "system") -> bool:
        """Restore a specific version as the current version.
        
        Args:
            version_id: The version ID to restore
            agent_id: The agent performing the restoration
        
        Returns:
            True if successful, False otherwise.
        """
        version_data = self.get_version(version_id)
        if not version_data:
            return False
        
        version_info = version_data["version_info"]
        file_type = version_info["file_type"]
        content = version_data["content"]
        
        self._create_version(file_type, agent_id, f"Before restoring version {version_id}")
        
        source_map = {
            "insights": self.get_insights_path(),
            "decisions": self.get_decisions_path(),
            "context": self.get_context_path(),
            **{scope: self.get_scope_path(scope) for scope in self.SCOPES},
        }
        
        target_path = source_map.get(file_type)
        if target_path:
            target_path.write_text(content, encoding="utf-8")
            return True
        
        return False
    
    def get_all_content(self) -> dict[str, str]:
        """Get all shared memory content.
        
        Returns:
            Dict with insights, decisions, and context content.
        """
        return {
            "insights": self.read_insights(),
            "decisions": self.read_decisions(),
            "context": self.read_context(),
            **{scope: self.read_scope(scope) for scope in self.SCOPES},
        }

    def get_all_context(self) -> str:
        """Compatibility wrapper returning scoped team memory context."""
        return self.get_scoped_context(scopes=list(self.SCOPES.keys()))
    
    def get_summary(self) -> dict:
        """Get a summary of the shared memory state."""
        entries = self.list_entries()
        versions = self.list_versions()
        
        return {
            "team_id": self._team_id,
            "entries_count": len(entries),
            "versions_count": len(versions),
            "categories": list(set(e.get("category", "general") for e in entries)),
            "last_updated": max(
                (e.get("updated_at", "") for e in entries),
                default=None
            ),
        }


def get_shared_memory_manager(team_id: str) -> SharedMemoryManager:
    """Get a SharedMemoryManager for a team."""
    return SharedMemoryManager(team_id)
