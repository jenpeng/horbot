"""Session management for conversation history."""

import json
import uuid
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import aiofiles
from loguru import logger

from horbot.utils.helpers import ensure_dir, safe_filename


def generate_session_id() -> str:
    """Generate a unique session ID."""
    return str(uuid.uuid4())[:8]


def extract_title_from_messages(messages: list[dict]) -> str:
    """Extract a title from the first user message."""
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            # Take first 50 chars as title, remove newlines
            title = content.replace("\n", " ")[:50]
            if len(content) > 50:
                title += "..."
            return title or "新对话"
    return "新对话"


@dataclass
class Session:
    """
    A conversation session.

    Stores messages in JSONL format for easy reading and persistence.

    Important: Messages are append-only for LLM cache efficiency.
    The consolidation process writes summaries to MEMORY.md/HISTORY.md
    but does NOT modify the messages list or get_history() output.
    """

    key: str  # channel:chat_id or session_id
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    last_consolidated: int = 0  # Number of messages already consolidated to files
    title: str = "新对话"  # Session title for display
    _pending_confirmations: dict[str, Any] = field(default_factory=dict)
    
    def add_message(
        self,
        role: str,
        content: str,
        dedup: bool = False,
        message_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        conversation_id: Optional[str] = None,
        conversation_type: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Add a message to the session.
        
        Args:
            role: Message role (user, assistant, system, tool)
            content: Message content
            dedup: If True, skip if last message has same role and content
            agent_id: ID of the agent (for assistant messages)
            agent_name: Name of the agent (for assistant messages)
            conversation_id: ID of the conversation
            conversation_type: Type of conversation (dm/team)
            **kwargs: Additional message fields (e.g., execution_steps, tool_calls, etc.)
            
        Returns:
            The message ID of the added message (or existing message if deduplicated)
        """
        message_id = message_id or str(uuid.uuid4())[:8]
        
        if dedup and self.messages:
            last_msg = self.messages[-1]
            if "execution_steps" in kwargs:
                pass
            elif "execution_steps" in last_msg:
                pass
            elif any(k in last_msg for k in ["tool_calls", "tool_call_id", "name"]):
                pass
            elif any(k in kwargs for k in ["files", "file_ids"]):
                pass
            elif (last_msg.get("role") == role and 
                  last_msg.get("content") == content):
                existing_id = last_msg.get("id", message_id)
                if agent_id and role == "assistant":
                    metadata = last_msg.setdefault("metadata", {})
                    metadata["agent_id"] = agent_id
                    if agent_name:
                        metadata["agent_name"] = agent_name
                return existing_id
        
        msg = {
            "id": message_id,
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        
        if "execution_steps" in kwargs:
            msg["execution_steps"] = kwargs.pop("execution_steps")
        
        msg.update(kwargs)
        
        if role == "assistant" and agent_id:
            metadata = msg.setdefault("metadata", {})
            metadata["agent_id"] = agent_id
            if agent_name:
                metadata["agent_name"] = agent_name
        
        if conversation_id:
            metadata = msg.setdefault("metadata", {})
            metadata["conversation_id"] = conversation_id
            if conversation_type:
                metadata["conversation_type"] = conversation_type
        
        self.messages.append(msg)
        self.updated_at = datetime.now()
        if self.title == "新对话" and role == "user":
            self.title = extract_title_from_messages(self.messages)
        
        return message_id
    
    def get_history(self, max_messages: int = 500) -> list[dict[str, Any]]:
        """Return unconsolidated messages for LLM input, aligned to a user turn."""
        unconsolidated = self.messages[self.last_consolidated:]
        sliced = unconsolidated[-max_messages:]

        # Drop leading non-user messages to avoid orphaned tool_result blocks
        for i, m in enumerate(sliced):
            if m.get("role") == "user":
                sliced = sliced[i:]
                break

        out: list[dict[str, Any]] = []
        for m in sliced:
            entry: dict[str, Any] = {"role": m["role"], "content": m.get("content", "")}
            
            if m.get("role") == "assistant":
                metadata = m.get("metadata", {})
                agent_name = metadata.get("agent_name")
                if agent_name and entry["content"]:
                    entry["content"] = f'<message from="{agent_name}">\n{entry["content"]}\n</message>'
            
            for k in ("tool_calls", "tool_call_id", "name"):
                if k in m:
                    entry[k] = m[k]
            out.append(entry)
        return out
    
    def clear(self) -> None:
        """Clear all messages and reset session to initial state."""
        self.messages = []
        self.last_consolidated = 0
        self.updated_at = datetime.now()


class SessionManager:
    """
    Manages conversation sessions.

    Sessions are stored as JSONL files in the sessions/active directory.
    Uses the unified paths module for directory locations.
    """

    def __init__(self, workspace: Path | None = None):
        if workspace is None:
            from horbot.utils.paths import get_sessions_active_dir
            self.sessions_dir = get_sessions_active_dir()
        else:
            workspace = Path(workspace) if not isinstance(workspace, Path) else workspace
            if workspace.name == "sessions":
                self.sessions_dir = ensure_dir(workspace)
            else:
                self.sessions_dir = ensure_dir(workspace / "sessions")
        self._cache: dict[str, Session] = {}
    
    def _get_session_path(self, key: str) -> Path:
        """Get the file path for a session."""
        safe_key = safe_filename(key.replace(":", "_"))
        return self.sessions_dir / f"{safe_key}.jsonl"
    
    def get(self, key: str) -> Session | None:
        """
        Get an existing session.
        
        Args:
            key: Session key.
        
        Returns:
            The session or None if not found.
        """
        if key in self._cache:
            return self._cache[key]
        
        session = self._load(key)
        if session:
            self._cache[key] = session
        return session
    
    def get_or_create(self, key: str) -> Session:
        """
        Get an existing session or create a new one.
        
        Args:
            key: Session key (usually channel:chat_id).
        
        Returns:
            The session.
        """
        session = self.get(key)
        if session is None:
            session = Session(key=key)
            self._cache[key] = session
        return session
    
    def _load(self, key: str) -> Session | None:
        """Load a session from disk."""
        path = self._get_session_path(key)
        if not path.exists():
            return None

        try:
            messages = []
            metadata = {}
            created_at = None
            last_consolidated = 0

            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    data = json.loads(line)

                    if data.get("_type") == "metadata":
                        metadata = data.get("metadata", {})
                        created_at = datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
                        last_consolidated = data.get("last_consolidated", 0)
                    else:
                        messages.append(data)

            return Session(
                key=key,
                messages=messages,
                created_at=created_at or datetime.now(),
                metadata=metadata,
                last_consolidated=last_consolidated,
                title=metadata.get("title", "新对话"),
            )
        except Exception as e:
            logger.warning("Failed to load session {}: {}", key, e)
            return None
    
    def save(self, session: Session) -> None:
        """Save a session to disk (synchronous version for compatibility)."""
        path = self._get_session_path(session.key)
        resolved_title = (session.title or session.metadata.get("title") or "新对话").strip() or "新对话"
        session.title = resolved_title
        session.metadata["title"] = resolved_title
        message_count = len(session.messages)

        with open(path, "w", encoding="utf-8") as f:
            metadata_line = {
                "_type": "metadata",
                "key": session.key,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "metadata": session.metadata,
                "last_consolidated": session.last_consolidated,
                "message_count": message_count,
            }
            f.write(json.dumps(metadata_line, ensure_ascii=False) + "\n")
            for msg in session.messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

        self._cache[session.key] = session
    
    async def async_save(self, session: Session) -> None:
        """Save a session to disk asynchronously."""
        path = self._get_session_path(session.key)
        resolved_title = (session.title or session.metadata.get("title") or "新对话").strip() or "新对话"
        session.title = resolved_title
        session.metadata["title"] = resolved_title
        message_count = len(session.messages)

        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            metadata_line = {
                "_type": "metadata",
                "key": session.key,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "metadata": session.metadata,
                "last_consolidated": session.last_consolidated,
                "message_count": message_count,
            }
            await f.write(json.dumps(metadata_line, ensure_ascii=False) + "\n")
            for msg in session.messages:
                await f.write(json.dumps(msg, ensure_ascii=False) + "\n")

        self._cache[session.key] = session
    
    def invalidate(self, key: str) -> None:
        """Remove a session from the in-memory cache."""
        self._cache.pop(key, None)
    
    def list_sessions(self) -> list[dict[str, Any]]:
        """
        List all sessions.
        
        Returns:
            List of session info dicts.
        """
        sessions = []
        
        for path in self.sessions_dir.glob("*.jsonl"):
            try:
                with open(path, encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    if first_line:
                        data = json.loads(first_line)
                        if data.get("_type") == "metadata":
                            metadata = data.get("metadata", {}) or {}
                            key = data.get("key") or path.stem.replace("_", ":", 1)
                            message_count = data.get("message_count")
                            if message_count is None:
                                message_count = 0
                                for line in f:
                                    if line.strip():
                                        message_count += 1
                            sessions.append({
                                "key": key,
                                "created_at": data.get("created_at"),
                                "updated_at": data.get("updated_at"),
                                "title": metadata.get("title", "未命名对话"),
                                "message_count": int(message_count),
                                "path": str(path)
                            })
            except Exception:
                continue
        
        return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)
