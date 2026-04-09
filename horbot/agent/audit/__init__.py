"""Audit logging system for tool execution tracking."""

import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any, Literal
import threading
import hashlib


@dataclass
class AuditEntry:
    """Single audit log entry."""
    timestamp: str
    tool_name: str
    params: dict[str, Any]
    result: str | None = None
    error: str | None = None
    session_id: str | None = None
    channel: str | None = None
    user_id: str | None = None
    duration_ms: int | None = None
    permission_level: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class AuditLogger:
    """
    Audit logger for tracking tool executions.
    
    Features:
    - JSON Lines format for easy parsing
    - Thread-safe writes
    - Automatic log rotation
    - Query support for filtering
    """
    
    def __init__(
        self,
        log_dir: Path | str | None = None,
        workspace: Path | str | None = None,
        max_file_size_mb: int = 10,
        max_files: int = 10,
        sensitive_keys: set[str] | None = None,
    ):
        if log_dir:
            self._log_dir = Path(log_dir)
        elif workspace:
            self._log_dir = Path(workspace) / ".audit"
        else:
            from horbot.utils.paths import get_workspace_dir

            self._log_dir = get_workspace_dir() / ".audit"
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._max_file_size = max_file_size_mb * 1024 * 1024
        self._max_files = max_files
        self._lock = threading.Lock()
        self._current_file: Path | None = None
        self._current_size: int = 0
        
        self._sensitive_keys = sensitive_keys or {
            "password", "token", "api_key", "secret", "credential",
            "private_key", "access_token", "refresh_token",
        }
    
    def _sanitize_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Sanitize sensitive parameters."""
        sanitized = {}
        for key, value in params.items():
            if key.lower() in self._sensitive_keys:
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, str) and len(value) > 500:
                sanitized[key] = value[:500] + "...[truncated]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_params(value)
            else:
                sanitized[key] = value
        return sanitized
    
    def _get_log_file(self) -> Path:
        """Get current log file path."""
        today = datetime.now().strftime("%Y-%m-%d")
        return self._log_dir / f"audit-{today}.jsonl"
    
    def _rotate_if_needed(self, file_path: Path) -> None:
        """Rotate log file if it exceeds max size."""
        if not file_path.exists():
            return
        
        if file_path.stat().st_size >= self._max_file_size:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            rotated = file_path.with_suffix(f".{timestamp}.jsonl")
            file_path.rename(rotated)
            
            self._cleanup_old_files()
    
    def _cleanup_old_files(self) -> None:
        """Remove old log files beyond max_files limit."""
        log_files = sorted(
            self._log_dir.glob("audit-*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        
        for old_file in log_files[self._max_files:]:
            try:
                old_file.unlink()
            except Exception:
                pass
    
    def log(
        self,
        tool_name: str,
        params: dict[str, Any],
        result: str | None = None,
        error: str | None = None,
        session_id: str | None = None,
        channel: str | None = None,
        user_id: str | None = None,
        duration_ms: int | None = None,
        permission_level: str | None = None,
    ) -> None:
        """Log a tool execution event."""
        entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            tool_name=tool_name,
            params=self._sanitize_params(params),
            result=result[:1000] if result and len(result) > 1000 else result,
            error=error[:1000] if error and len(error) > 1000 else error,
            session_id=session_id,
            channel=channel,
            user_id=user_id,
            duration_ms=duration_ms,
            permission_level=permission_level,
        )
        
        with self._lock:
            log_file = self._get_log_file()
            self._rotate_if_needed(log_file)
            
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(entry.to_json() + "\n")
    
    def query(
        self,
        tool_name: str | None = None,
        session_id: str | None = None,
        channel: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        has_error: bool | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Query audit logs with filters."""
        results: list[AuditEntry] = []
        
        log_files = sorted(
            self._log_dir.glob("audit-*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        
        for log_file in log_files:
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            data = json.loads(line)
                            entry = AuditEntry(**data)
                        except (json.JSONDecodeError, TypeError):
                            continue
                        
                        if tool_name and entry.tool_name != tool_name:
                            continue
                        if session_id and entry.session_id != session_id:
                            continue
                        if channel and entry.channel != channel:
                            continue
                        if start_time:
                            entry_time = datetime.fromisoformat(entry.timestamp)
                            if entry_time < start_time:
                                continue
                        if end_time:
                            entry_time = datetime.fromisoformat(entry.timestamp)
                            if entry_time > end_time:
                                continue
                        if has_error is not None:
                            if has_error and not entry.error:
                                continue
                            if not has_error and entry.error:
                                continue
                        
                        results.append(entry)
                        if len(results) >= limit:
                            return results
            except Exception:
                continue
        
        return results
    
    def get_stats(self, hours: int = 24) -> dict[str, Any]:
        """Get statistics for the last N hours."""
        from datetime import timedelta
        
        start_time = datetime.now() - timedelta(hours=hours)
        entries = self.query(start_time=start_time, limit=10000)
        
        tool_counts: dict[str, int] = {}
        error_counts: dict[str, int] = {}
        total_duration = 0
        duration_count = 0
        
        for entry in entries:
            tool_counts[entry.tool_name] = tool_counts.get(entry.tool_name, 0) + 1
            if entry.error:
                error_counts[entry.tool_name] = error_counts.get(entry.tool_name, 0) + 1
            if entry.duration_ms:
                total_duration += entry.duration_ms
                duration_count += 1
        
        return {
            "period_hours": hours,
            "total_calls": len(entries),
            "unique_tools": len(tool_counts),
            "tool_counts": tool_counts,
            "error_counts": error_counts,
            "avg_duration_ms": total_duration / duration_count if duration_count > 0 else 0,
        }


_global_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance."""
    global _global_logger
    if _global_logger is None:
        _global_logger = AuditLogger()
    return _global_logger


def set_audit_logger(logger: AuditLogger) -> None:
    """Set the global audit logger instance."""
    global _global_logger
    _global_logger = logger
