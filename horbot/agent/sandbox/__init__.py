"""Security sandbox for safe tool execution."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
import fnmatch
import os

from horbot.agent.tools.permission import (
    PROTECTED_PATHS,
    DANGEROUS_COMMANDS,
    is_protected_path,
    is_sensitive_operation,
)


@dataclass
class SandboxConfig:
    """Configuration for the security sandbox."""
    allowed_dirs: list[str] = field(default_factory=list)
    protected_paths: list[str] = field(default_factory=lambda: PROTECTED_PATHS)
    dangerous_commands: set[str] = field(default_factory=lambda: DANGEROUS_COMMANDS)
    max_file_size_mb: int = 100
    allow_symlinks: bool = False
    allow_absolute_paths: bool = True
    restrict_to_workspace: bool = False


class PathGuard:
    """
    Guards file system access to prevent unauthorized path operations.
    
    Features:
    - Workspace restriction
    - Protected path blocking
    - Symlink attack prevention
    - Path traversal prevention
    """
    
    def __init__(
        self,
        workspace: Path | None = None,
        config: SandboxConfig | None = None,
    ):
        self._workspace = workspace.resolve() if workspace else None
        self._config = config or SandboxConfig()
        
        if self._config.restrict_to_workspace and self._workspace:
            self._config.allowed_dirs = [str(self._workspace)]
    
    def _resolve_path(self, path: str) -> Path:
        """Resolve a path, handling relative paths and symlinks."""
        p = Path(path).expanduser()
        
        if not p.is_absolute() and self._workspace:
            p = self._workspace / p
        
        try:
            resolved = p.resolve()
        except Exception:
            resolved = p
        
        if not self._config.allow_symlinks:
            if resolved.is_symlink():
                raise PermissionError(f"Symlink access is not allowed: {path}")
        
        return resolved
    
    def _is_in_allowed_dir(self, path: Path) -> bool:
        """Check if path is within allowed directories."""
        if not self._config.allowed_dirs:
            return True
        
        for allowed in self._config.allowed_dirs:
            allowed_path = Path(allowed).expanduser().resolve()
            try:
                path.relative_to(allowed_path)
                return True
            except ValueError:
                continue
        
        return False
    
    def _is_protected(self, path: Path) -> bool:
        """Check if path is protected."""
        path_str = str(path)
        
        for pattern in self._config.protected_paths:
            expanded_pattern = str(Path(pattern).expanduser())
            
            if fnmatch.fnmatch(path_str, expanded_pattern):
                return True
            if fnmatch.fnmatch(path_str, expanded_pattern + "/*"):
                return True
            if path_str.startswith(expanded_pattern.rstrip("*")):
                return True
        
        return False
    
    def check_read_access(self, path: str) -> tuple[bool, str]:
        """
        Check if read access is allowed for the given path.
        
        Returns:
            Tuple of (is_allowed, error_message)
        """
        try:
            resolved = self._resolve_path(path)
        except PermissionError as e:
            return False, str(e)
        
        if self._is_protected(resolved):
            return False, f"Path is protected: {path}"
        
        if self._config.restrict_to_workspace and not self._is_in_allowed_dir(resolved):
            return False, f"Path is outside allowed directories: {path}"
        
        return True, ""
    
    def check_write_access(self, path: str) -> tuple[bool, str]:
        """
        Check if write access is allowed for the given path.
        
        Returns:
            Tuple of (is_allowed, error_message)
        """
        try:
            resolved = self._resolve_path(path)
        except PermissionError as e:
            return False, str(e)
        
        if self._is_protected(resolved):
            return False, f"Path is protected: {path}"
        
        if self._config.restrict_to_workspace and not self._is_in_allowed_dir(resolved):
            return False, f"Path is outside allowed directories: {path}"
        
        return True, ""
    
    def check_delete_access(self, path: str) -> tuple[bool, str]:
        """
        Check if delete access is allowed for the given path.
        
        Returns:
            Tuple of (is_allowed, error_message)
        """
        try:
            resolved = self._resolve_path(path)
        except PermissionError as e:
            return False, str(e)
        
        if self._is_protected(resolved):
            return False, f"Path is protected: {path}"
        
        if self._config.restrict_to_workspace and not self._is_in_allowed_dir(resolved):
            return False, f"Path is outside allowed directories: {path}"
        
        if self._workspace and resolved == self._workspace:
            return False, "Cannot delete workspace root directory"
        
        return True, ""
    
    def validate_path(self, path: str, operation: str = "read") -> Path:
        """
        Validate and resolve a path for the given operation.
        
        Args:
            path: The path to validate
            operation: One of "read", "write", "delete"
        
        Returns:
            Resolved Path object
        
        Raises:
            PermissionError: If access is denied
        """
        if operation == "read":
            allowed, error = self.check_read_access(path)
        elif operation == "write":
            allowed, error = self.check_write_access(path)
        elif operation == "delete":
            allowed, error = self.check_delete_access(path)
        else:
            raise ValueError(f"Unknown operation: {operation}")
        
        if not allowed:
            raise PermissionError(error)
        
        return self._resolve_path(path)


class CommandFilter:
    """
    Filters shell commands to prevent dangerous operations.
    """
    
    def __init__(
        self,
        dangerous_commands: set[str] | None = None,
        allowed_commands: set[str] | None = None,
    ):
        self._dangerous = dangerous_commands or DANGEROUS_COMMANDS
        self._allowed = allowed_commands
    
    def check_command(self, command: str) -> tuple[bool, str, str]:
        """
        Check if a command is safe to execute.
        
        Returns:
            Tuple of (is_safe, risk_level, reason)
            risk_level: "safe", "warning", "dangerous"
        """
        command_lower = command.lower()
        
        for dangerous in self._dangerous:
            if dangerous.lower() in command_lower:
                return False, "dangerous", f"Command contains dangerous pattern: {dangerous}"
        
        if self._allowed:
            base_cmd = command.split()[0] if command.split() else ""
            if base_cmd not in self._allowed:
                return False, "warning", f"Command '{base_cmd}' is not in allowed list"
        
        if any(pattern in command_lower for pattern in ["rm ", "del ", "format ", "mkfs"]):
            return True, "warning", "Command may delete files - use with caution"
        
        return True, "safe", ""
    
    def sanitize_command(self, command: str) -> str:
        """Remove potentially dangerous parts from command."""
        sanitized = command
        
        dangerous_patterns = [
            ("rm -rf /", "rm -rf ./"),
            ("> /dev/", "> /dev/null"),
            ("sudo ", ""),
        ]
        
        for dangerous, safe in dangerous_patterns:
            sanitized = sanitized.replace(dangerous, safe)
        
        return sanitized


class ConfirmationManager:
    """
    Manages confirmation requests for sensitive operations.
    """
    
    def __init__(self):
        self._pending_confirmations: dict[str, dict[str, Any]] = {}
        self._confirmation_timeout_seconds: int = 300
    
    def create_confirmation_request(
        self,
        tool_name: str,
        params: dict[str, Any],
        reason: str,
    ) -> str:
        """Create a confirmation request and return its ID."""
        import uuid
        import time
        
        confirmation_id = str(uuid.uuid4())[:8]
        
        self._pending_confirmations[confirmation_id] = {
            "tool_name": tool_name,
            "params": params,
            "reason": reason,
            "created_at": time.time(),
            "status": "pending",
        }
        
        return confirmation_id
    
    def get_confirmation_request(self, confirmation_id: str) -> dict[str, Any] | None:
        """Get a confirmation request by ID."""
        return self._pending_confirmations.get(confirmation_id)
    
    def confirm(self, confirmation_id: str, approved: bool = True) -> bool:
        """Confirm or reject a pending request."""
        request = self._pending_confirmations.get(confirmation_id)
        if not request:
            return False
        
        request["status"] = "approved" if approved else "rejected"
        return True
    
    def is_expired(self, confirmation_id: str) -> bool:
        """Check if a confirmation request has expired."""
        import time
        
        request = self._pending_confirmations.get(confirmation_id)
        if not request:
            return True
        
        elapsed = time.time() - request["created_at"]
        return elapsed > self._confirmation_timeout_seconds
    
    def cleanup_expired(self) -> int:
        """Remove expired confirmation requests. Returns count removed."""
        import time
        
        current_time = time.time()
        expired_ids = [
            cid for cid, req in self._pending_confirmations.items()
            if current_time - req["created_at"] > self._confirmation_timeout_seconds
        ]
        
        for cid in expired_ids:
            del self._pending_confirmations[cid]
        
        return len(expired_ids)
    
    def format_confirmation_message(self, confirmation_id: str) -> str:
        """Format a confirmation request as a user-friendly message."""
        request = self._pending_confirmations.get(confirmation_id)
        if not request:
            return f"Confirmation request {confirmation_id} not found"
        
        tool_name = request["tool_name"]
        params = request["params"]
        reason = request["reason"]
        
        msg_parts = [
            f"⚠️ **Confirmation Required** (ID: {confirmation_id})",
            f"",
            f"**Tool**: {tool_name}",
            f"**Reason**: {reason}",
            f"",
            f"**Parameters**:",
        ]
        
        for key, value in params.items():
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            msg_parts.append(f"  - {key}: {value}")
        
        msg_parts.extend([
            f"",
            f"Reply with `confirm {confirmation_id}` to approve",
            f"or `reject {confirmation_id}` to deny.",
        ])
        
        return "\n".join(msg_parts)
