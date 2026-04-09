"""Execution state management with persistence and recovery."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any
import threading
import uuid


@dataclass
class ExecutionState:
    """Persistent state of a plan execution."""
    id: str
    plan_id: str
    plan_data: dict[str, Any]
    status: str
    current_step_index: int
    completed_steps: int
    failed_steps: int
    started_at: str | None = None
    paused_at: str | None = None
    completed_at: str | None = None
    last_checkpoint_at: str | None = None
    step_results: dict[str, str] = field(default_factory=dict)
    step_errors: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionState":
        """Create from dictionary."""
        return cls(
            id=data.get("id", ""),
            plan_id=data.get("plan_id", ""),
            plan_data=data.get("plan_data", {}),
            status=data.get("status", "pending"),
            current_step_index=data.get("current_step_index", 0),
            completed_steps=data.get("completed_steps", 0),
            failed_steps=data.get("failed_steps", 0),
            started_at=data.get("started_at"),
            paused_at=data.get("paused_at"),
            completed_at=data.get("completed_at"),
            last_checkpoint_at=data.get("last_checkpoint_at"),
            step_results=data.get("step_results", {}),
            step_errors=data.get("step_errors", {}),
            metadata=data.get("metadata", {}),
        )


class StateManager:
    """
    Manages execution state with persistence.
    
    Features:
    - Save/load state to JSON files
    - Checkpoint management
    - Recovery from failures
    - Thread-safe operations
    """
    
    def __init__(
        self,
        state_dir: Path | str | None = None,
        workspace: Path | str | None = None,
    ):
        if state_dir:
            self._state_dir = Path(state_dir)
        elif workspace:
            self._state_dir = Path(workspace) / ".state"
        else:
            from horbot.utils.paths import get_workspace_dir

            self._state_dir = get_workspace_dir() / ".state"
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._active_states: dict[str, ExecutionState] = {}
    
    def _get_state_file(self, state_id: str) -> Path:
        """Get the file path for a state."""
        return self._state_dir / f"{state_id}.json"
    
    def create_state(
        self,
        plan_data: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionState:
        """Create a new execution state."""
        state_id = str(uuid.uuid4())[:8]
        plan_id = plan_data.get("id", "unknown")
        
        state = ExecutionState(
            id=state_id,
            plan_id=plan_id,
            plan_data=plan_data,
            status="pending",
            current_step_index=0,
            completed_steps=0,
            failed_steps=0,
            metadata=metadata or {},
        )
        
        with self._lock:
            self._active_states[state_id] = state
            self._save_state(state)
        
        return state
    
    def _save_state(self, state: ExecutionState) -> None:
        """Save state to file."""
        state_file = self._get_state_file(state.id)
        state.last_checkpoint_at = datetime.now().isoformat()
        
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
    
    def load_state(self, state_id: str) -> ExecutionState | None:
        """Load state from file."""
        state_file = self._get_state_file(state_id)
        
        if not state_file.exists():
            return None
        
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ExecutionState.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None
    
    def update_state(
        self,
        state_id: str,
        status: str | None = None,
        current_step_index: int | None = None,
        completed_steps: int | None = None,
        failed_steps: int | None = None,
        step_result: tuple[str, str] | None = None,
        step_error: tuple[str, str] | None = None,
    ) -> ExecutionState | None:
        """Update state and persist."""
        with self._lock:
            state = self._active_states.get(state_id) or self.load_state(state_id)
            if not state:
                return None
            
            if status is not None:
                state.status = status
            if current_step_index is not None:
                state.current_step_index = current_step_index
            if completed_steps is not None:
                state.completed_steps = completed_steps
            if failed_steps is not None:
                state.failed_steps = failed_steps
            if step_result:
                state.step_results[step_result[0]] = step_result[1]
            if step_error:
                state.step_errors[step_error[0]] = step_error[1]
            
            self._save_state(state)
            self._active_states[state_id] = state
            
            return state
    
    def mark_started(self, state_id: str) -> None:
        """Mark execution as started."""
        self.update_state(
            state_id,
            status="running",
        )
        with self._lock:
            if state_id in self._active_states:
                self._active_states[state_id].started_at = datetime.now().isoformat()
    
    def mark_paused(self, state_id: str) -> None:
        """Mark execution as paused."""
        self.update_state(state_id, status="paused")
        with self._lock:
            if state_id in self._active_states:
                self._active_states[state_id].paused_at = datetime.now().isoformat()
    
    def mark_completed(self, state_id: str, success: bool = True) -> None:
        """Mark execution as completed."""
        status = "completed" if success else "failed"
        self.update_state(state_id, status=status)
        with self._lock:
            if state_id in self._active_states:
                self._active_states[state_id].completed_at = datetime.now().isoformat()
    
    def get_active_states(self) -> list[ExecutionState]:
        """Get all active (non-completed) states."""
        states = []
        for state_file in self._state_dir.glob("*.json"):
            try:
                state = self.load_state(state_file.stem)
                if state and state.status not in ("completed", "failed", "cancelled"):
                    states.append(state)
            except Exception:
                continue
        return states
    
    def get_recovery_state(self, plan_id: str) -> ExecutionState | None:
        """Find a recoverable state for a plan."""
        for state in self.get_active_states():
            if state.plan_id == plan_id and state.status == "paused":
                return state
        return None
    
    def cleanup_completed(self, max_age_hours: int = 24) -> int:
        """Remove old completed states. Returns count removed."""
        from datetime import timedelta
        
        removed = 0
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        for state_file in self._state_dir.glob("*.json"):
            try:
                state = self.load_state(state_file.stem)
                if state and state.status in ("completed", "failed", "cancelled"):
                    if state.completed_at:
                        completed = datetime.fromisoformat(state.completed_at)
                        if completed < cutoff:
                            state_file.unlink()
                            removed += 1
            except Exception:
                continue
        
        return removed
    
    def delete_state(self, state_id: str) -> bool:
        """Delete a state file."""
        state_file = self._get_state_file(state_id)
        
        with self._lock:
            self._active_states.pop(state_id, None)
        
        if state_file.exists():
            state_file.unlink()
            return True
        return False
