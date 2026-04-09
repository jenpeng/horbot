"""Checkpoint management for execution recovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
import json
import threading
import uuid


@dataclass
class Checkpoint:
    """A snapshot of execution state at a point in time."""
    id: str
    execution_id: str
    step_id: str
    step_index: int
    timestamp: str
    step_result: str | None = None
    step_error: str | None = None
    rollback_data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "execution_id": self.execution_id,
            "step_id": self.step_id,
            "step_index": self.step_index,
            "timestamp": self.timestamp,
            "step_result": self.step_result,
            "step_error": self.step_error,
            "rollback_data": self.rollback_data,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Checkpoint":
        """Create from dictionary."""
        return cls(
            id=data.get("id", ""),
            execution_id=data.get("execution_id", ""),
            step_id=data.get("step_id", ""),
            step_index=data.get("step_index", 0),
            timestamp=data.get("timestamp", ""),
            step_result=data.get("step_result"),
            step_error=data.get("step_error"),
            rollback_data=data.get("rollback_data", {}),
            metadata=data.get("metadata", {}),
        )


class CheckpointManager:
    """
    Manages checkpoints for execution recovery.
    
    Features:
    - Create checkpoints before each step
    - Support rollback to previous checkpoint
    - Automatic cleanup of old checkpoints
    """
    
    def __init__(
        self,
        checkpoint_dir: Path | str | None = None,
        workspace: Path | str | None = None,
    ):
        if checkpoint_dir:
            self._checkpoint_dir = Path(checkpoint_dir)
        elif workspace:
            self._checkpoint_dir = Path(workspace) / ".checkpoints"
        else:
            from horbot.utils.paths import get_workspace_dir

            self._checkpoint_dir = get_workspace_dir() / ".checkpoints"
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._checkpoints: dict[str, list[Checkpoint]] = {}
        self._rollback_handlers: dict[str, Callable[[dict], Any]] = {}
    
    def _get_checkpoint_file(self, execution_id: str) -> Path:
        """Get checkpoint file for an execution."""
        return self._checkpoint_dir / f"{execution_id}.jsonl"
    
    def register_rollback_handler(
        self,
        tool_name: str,
        handler: Callable[[dict], Any],
    ) -> None:
        """Register a rollback handler for a tool."""
        self._rollback_handlers[tool_name] = handler
    
    def create_checkpoint(
        self,
        execution_id: str,
        step_id: str,
        step_index: int,
        step_result: str | None = None,
        step_error: str | None = None,
        rollback_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Checkpoint:
        """Create a new checkpoint."""
        checkpoint = Checkpoint(
            id=str(uuid.uuid4())[:8],
            execution_id=execution_id,
            step_id=step_id,
            step_index=step_index,
            timestamp=datetime.now().isoformat(),
            step_result=step_result,
            step_error=step_error,
            rollback_data=rollback_data or {},
            metadata=metadata or {},
        )
        
        with self._lock:
            if execution_id not in self._checkpoints:
                self._checkpoints[execution_id] = []
            self._checkpoints[execution_id].append(checkpoint)
            self._persist_checkpoint(checkpoint)
        
        return checkpoint
    
    def _persist_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Persist checkpoint to file."""
        checkpoint_file = self._get_checkpoint_file(checkpoint.execution_id)
        
        with open(checkpoint_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(checkpoint.to_dict(), ensure_ascii=False) + "\n")
    
    def load_checkpoints(self, execution_id: str) -> list[Checkpoint]:
        """Load all checkpoints for an execution."""
        checkpoint_file = self._get_checkpoint_file(execution_id)
        
        if not checkpoint_file.exists():
            return []
        
        checkpoints = []
        try:
            with open(checkpoint_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            checkpoints.append(Checkpoint.from_dict(data))
                        except json.JSONDecodeError:
                            continue
        except Exception:
            pass
        
        with self._lock:
            self._checkpoints[execution_id] = checkpoints
        
        return checkpoints
    
    def get_latest_checkpoint(self, execution_id: str) -> Checkpoint | None:
        """Get the most recent checkpoint for an execution."""
        checkpoints = self._checkpoints.get(execution_id) or self.load_checkpoints(execution_id)
        
        if not checkpoints:
            return None
        
        return checkpoints[-1]
    
    def get_checkpoint_at_step(self, execution_id: str, step_index: int) -> Checkpoint | None:
        """Get checkpoint at a specific step index."""
        checkpoints = self._checkpoints.get(execution_id) or self.load_checkpoints(execution_id)
        
        for checkpoint in reversed(checkpoints):
            if checkpoint.step_index <= step_index:
                return checkpoint
        
        return None
    
    async def rollback_to_checkpoint(
        self,
        checkpoint: Checkpoint,
    ) -> tuple[bool, str]:
        """
        Rollback to a checkpoint.
        
        Executes rollback handlers in reverse order from latest to target.
        
        Returns:
            Tuple of (success, message)
        """
        execution_id = checkpoint.execution_id
        checkpoints = self._checkpoints.get(execution_id) or self.load_checkpoints(execution_id)
        
        checkpoints_to_rollback = [
            cp for cp in reversed(checkpoints)
            if cp.step_index > checkpoint.step_index and cp.rollback_data
        ]
        
        errors = []
        
        for cp in checkpoints_to_rollback:
            tool_name = cp.metadata.get("tool_name")
            if tool_name and tool_name in self._rollback_handlers:
                try:
                    handler = self._rollback_handlers[tool_name]
                    result = handler(cp.rollback_data)
                    if hasattr(result, '__await__'):
                        await result
                except Exception as e:
                    errors.append(f"Rollback failed for step {cp.step_id}: {str(e)}")
        
        if errors:
            return False, "; ".join(errors)
        
        return True, f"Rolled back to step {checkpoint.step_index}"
    
    def clear_checkpoints(self, execution_id: str) -> None:
        """Clear all checkpoints for an execution."""
        checkpoint_file = self._get_checkpoint_file(execution_id)
        
        with self._lock:
            self._checkpoints.pop(execution_id, None)
            if checkpoint_file.exists():
                checkpoint_file.unlink()
    
    def get_recovery_point(self, execution_id: str) -> int:
        """
        Get the step index to resume from.
        
        Returns the step index after the last successful checkpoint.
        """
        checkpoints = self._checkpoints.get(execution_id) or self.load_checkpoints(execution_id)
        
        successful = [
            cp for cp in checkpoints
            if cp.step_error is None
        ]
        
        if not successful:
            return 0
        
        return successful[-1].step_index + 1


_default_rollback_handlers: dict[str, Callable] = {}


def register_default_rollback_handlers(manager: CheckpointManager) -> None:
    """Register default rollback handlers for common tools."""
    
    def file_write_rollback(data: dict) -> None:
        import os
        original_content = data.get("original_content")
        file_path = data.get("file_path")
        if file_path and original_content is not None:
            with open(file_path, "w") as f:
                f.write(original_content)
    
    def file_delete_rollback(data: dict) -> None:
        import shutil
        backup_path = data.get("backup_path")
        original_path = data.get("original_path")
        if backup_path and original_path:
            shutil.move(backup_path, original_path)
    
    manager.register_rollback_handler("write_file", file_write_rollback)
    manager.register_rollback_handler("edit_file", file_write_rollback)
    manager.register_rollback_handler("exec", lambda data: None)
