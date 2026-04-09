"""Tool permission system for security control."""

from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Literal


class PermissionLevel(Enum):
    """Permission levels for tool access."""
    ALLOW = "allow"
    DENY = "deny"
    CONFIRM = "confirm"


@dataclass
class ToolGroup:
    """Definition of a tool group."""
    name: str
    tools: list[str]
    description: str = ""


@dataclass
class PermissionResult:
    """Result of a permission check."""
    level: PermissionLevel
    reason: str = ""
    tool_name: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_allowed(self) -> bool:
        return self.level == PermissionLevel.ALLOW
    
    @property
    def is_denied(self) -> bool:
        return self.level == PermissionLevel.DENY
    
    @property
    def needs_confirmation(self) -> bool:
        return self.level == PermissionLevel.CONFIRM
    
    def to_error_message(self) -> str | None:
        if self.is_denied:
            return f"Tool '{self.tool_name}' is not allowed: {self.reason}"
        if self.needs_confirmation:
            return f"Tool '{self.tool_name}' requires confirmation: {self.reason}"
        return None


TOOL_GROUPS: dict[str, ToolGroup] = {
    "fs": ToolGroup(
        name="fs",
        tools=["read_file", "write_file", "edit_file", "list_dir"],
        description="File system tools for reading, writing, and listing files"
    ),
    "web": ToolGroup(
        name="web",
        tools=["web_search", "web_fetch", "browser"],
        description="Web tools for searching and fetching web content"
    ),
    "runtime": ToolGroup(
        name="runtime",
        tools=["exec"],
        description="Runtime tools for executing shell commands"
    ),
    "automation": ToolGroup(
        name="automation",
        tools=["spawn", "cron", "task"],
        description="Automation tools for background tasks and scheduling"
    ),
    "messaging": ToolGroup(
        name="messaging",
        tools=["message"],
        description="Messaging tools for sending messages to users"
    ),
    "mcp": ToolGroup(
        name="mcp",
        tools=[],
        description="MCP (Model Context Protocol) tools - dynamically loaded"
    ),
}

PROFILES: dict[str, dict[str, list[str]]] = {
    "minimal": {
        "allow": [],
        "deny": ["group:runtime", "group:automation"],
    },
    "balanced": {
        "allow": ["group:fs", "group:web"],
        "deny": ["group:automation"],
        "confirm": ["group:runtime"],
    },
    "coding": {
        "allow": ["group:fs", "group:web", "group:runtime"],
        "deny": ["group:automation"],
    },
    "full": {
        "allow": ["group:fs", "group:web", "group:runtime", "group:automation", "group:messaging"],
        "deny": [],
    },
    "readonly": {
        "allow": ["read_file", "list_dir", "group:web"],
        "deny": ["write_file", "edit_file", "group:runtime", "group:automation"],
    },
}


@dataclass
class PermissionConfig:
    """Configuration for tool permissions."""
    profile: str = "balanced"
    allow: list[str] = field(default_factory=list)
    deny: list[str] = field(default_factory=list)
    confirm: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.profile and self.profile in PROFILES:
            profile = PROFILES[self.profile]
            if not self.allow and not self.deny and not self.confirm:
                self.allow = list(profile.get("allow", []))
                self.deny = list(profile.get("deny", []))
                self.confirm = list(profile.get("confirm", []))
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "allow": self.allow,
            "deny": self.deny,
            "confirm": self.confirm,
        }


class PermissionManager:
    """
    Manages tool permissions with allow/deny/confirm levels.
    
    Priority: deny > confirm > allow
    
    Features:
    - Group-based permission management
    - Path-based access control
    - Sensitive operation detection
    - Permission caching for performance
    
    Usage:
        pm = PermissionManager(config)
        result = pm.check_permission("exec")
        if result.is_denied:
            return result.to_error_message()
    """
    
    def __init__(
        self,
        config: PermissionConfig | None = None,
        *,
        profile: str = "balanced",
        allow: list[str] | None = None,
        deny: list[str] | None = None,
        confirm: list[str] | None = None,
        confirm_sensitive: bool = True,
    ):
        if config:
            self._config = config
        else:
            self._config = PermissionConfig(
                profile=profile,
                allow=allow or [],
                deny=deny or [],
                confirm=confirm or [],
            )
        
        self._confirm_sensitive = confirm_sensitive
        self._expanded_allow = self._expand_groups(self._config.allow)
        self._expanded_deny = self._expand_groups(self._config.deny)
        self._expanded_confirm = self._expand_groups(self._config.confirm)
        self._on_permission_change: Callable[[str, PermissionLevel], None] | None = None
    
    def _expand_groups(self, items: list[str]) -> set[str]:
        """Expand group references (e.g., 'group:fs') to actual tool names."""
        expanded: set[str] = set()
        for item in items:
            if item.startswith("group:"):
                group_name = item[6:]
                if group_name in TOOL_GROUPS:
                    expanded.update(TOOL_GROUPS[group_name].tools)
            else:
                expanded.add(item)
        return expanded
    
    def check_permission(self, tool_name: str) -> PermissionLevel:
        """
        Check the permission level for a tool.
        
        Priority: deny > confirm > allow
        
        Returns:
            PermissionLevel indicating the access level
        """
        if tool_name in self._expanded_deny:
            return PermissionLevel.DENY
        if tool_name in self._expanded_confirm:
            return PermissionLevel.CONFIRM
        if tool_name in self._expanded_allow:
            return PermissionLevel.ALLOW
        
        if self._config.profile == "full":
            return PermissionLevel.ALLOW
        
        return PermissionLevel.DENY
    
    def check_permission_detailed(
        self,
        tool_name: str,
        params: dict[str, Any] | None = None,
    ) -> PermissionResult:
        """
        Check permission with detailed result including reason.
        
        Args:
            tool_name: Name of the tool to check
            params: Optional parameters for context-aware checks
        
        Returns:
            PermissionResult with level, reason, and context
        """
        level = self.check_permission(tool_name)
        reason = self._get_reason(tool_name, level)
        
        result = PermissionResult(
            level=level,
            reason=reason,
            tool_name=tool_name,
            params=params or {},
        )
        
        if params and level != PermissionLevel.DENY:
            path_result = self._check_path_permission(params)
            if path_result:
                return path_result
            
            sensitive_result = self._check_sensitive_operation(tool_name, params)
            if sensitive_result:
                return sensitive_result
        
        return result
    
    def _get_reason(self, tool_name: str, level: PermissionLevel) -> str:
        """Get the reason for a permission level."""
        if level == PermissionLevel.DENY:
            if tool_name in self._expanded_deny:
                return "Tool is in deny list"
            return "Tool not in allow list"
        if level == PermissionLevel.CONFIRM:
            return "Tool requires user confirmation"
        return "Tool is allowed"
    
    def _check_path_permission(self, params: dict[str, Any]) -> PermissionResult | None:
        """Check if path access is allowed."""
        path = params.get("path", "")
        if path and is_protected_path(path):
            return PermissionResult(
                level=PermissionLevel.DENY,
                reason=f"Path '{path}' is protected",
                params=params,
            )
        return None
    
    def _check_sensitive_operation(
        self,
        tool_name: str,
        params: dict[str, Any],
    ) -> PermissionResult | None:
        """Check if operation is sensitive and needs confirmation."""
        if not self._confirm_sensitive:
            return None
        
        if is_sensitive_operation(tool_name, params):
            return PermissionResult(
                level=PermissionLevel.CONFIRM,
                reason="Sensitive operation requires confirmation",
                tool_name=tool_name,
                params=params,
            )
        return None
    
    def is_allowed(self, tool_name: str) -> bool:
        """Check if a tool is allowed (not denied)."""
        return self.check_permission(tool_name) != PermissionLevel.DENY
    
    def needs_confirmation(self, tool_name: str) -> bool:
        """Check if a tool requires user confirmation."""
        return self.check_permission(tool_name) == PermissionLevel.CONFIRM
    
    def get_allowed_tools(self, all_tools: list[str]) -> list[str]:
        """Get list of tools that are allowed (including those needing confirmation)."""
        return [t for t in all_tools if self.is_allowed(t)]
    
    def get_denied_tools(self, all_tools: list[str]) -> list[str]:
        """Get list of tools that are denied."""
        return [t for t in all_tools if not self.is_allowed(t)]
    
    def get_tools_needing_confirmation(self, all_tools: list[str]) -> list[str]:
        """Get list of tools that require confirmation."""
        return [t for t in all_tools if self.needs_confirmation(t)]
    
    def update_config(self, config: PermissionConfig) -> None:
        """Update permission configuration."""
        self._config = config
        self._expanded_allow = self._expand_groups(self._config.allow)
        self._expanded_deny = self._expand_groups(self._config.deny)
        self._expanded_confirm = self._expand_groups(self._config.confirm)
    
    def set_on_permission_change(
        self,
        callback: Callable[[str, PermissionLevel], None] | None,
    ) -> None:
        """Set callback for permission changes."""
        self._on_permission_change = callback
    
    def to_dict(self) -> dict[str, Any]:
        """Export configuration as dictionary."""
        return {
            **self._config.to_dict(),
            "expanded_allow": list(self._expanded_allow),
            "expanded_deny": list(self._expanded_deny),
            "expanded_confirm": list(self._expanded_confirm),
        }


SENSITIVE_OPERATIONS: set[str] = {
    "write_file",
    "edit_file",
    "exec",
    "spawn",
    "cron",
}

PROTECTED_PATHS: list[str] = [
    "~/.ssh",
    "~/.gnupg",
    "~/.env",
    "**/.env",
    "**/credentials.json",
    "**/.credentials",
    "/etc",
    "/usr",
    "/bin",
    "/sbin",
    "/root",
]

DANGEROUS_COMMANDS: set[str] = {
    "rm -rf",
    "rm -r",
    "rm -f",
    "sudo",
    "chmod",
    "chown",
    "mkfs",
    "dd",
    "> /dev/",
    "eval",
    "shutdown",
    "reboot",
    "init 0",
    "init 6",
}


@lru_cache(maxsize=256)
def _is_sensitive_operation_cached(tool_name: str) -> bool:
    """Cached check for sensitive operations by tool name only."""
    return tool_name in SENSITIVE_OPERATIONS


def is_sensitive_operation(tool_name: str, params: dict[str, Any] | None = None) -> bool:
    """
    Check if an operation is considered sensitive.
    
    Args:
        tool_name: Name of the tool
        params: Optional parameters for detailed check
    
    Returns:
        True if the operation is sensitive
    """
    if tool_name == "exec" and params:
        command = params.get("command", "")
        for dangerous in DANGEROUS_COMMANDS:
            if dangerous in command:
                return True
        return False
    
    if _is_sensitive_operation_cached(tool_name):
        if params is None:
            return True
        
        if tool_name in ("write_file", "edit_file"):
            path = params.get("path", "")
            if any(pattern in path.lower() for pattern in [".env", "config", "credential", "secret", "key"]):
                return True
    
    return False


def is_sensitive_operation_with_params(tool_name: str, params: dict[str, Any]) -> bool:
    """Check if an operation is sensitive with actual parameters."""
    return is_sensitive_operation(tool_name, params)


@lru_cache(maxsize=256)
def is_protected_path_cached(path: str) -> bool:
    """Cached version of path protection check."""
    return _check_protected_path(path)


def _check_protected_path(path: str) -> bool:
    """Internal function to check if a path is protected."""
    import fnmatch
    
    expanded_path = str(Path(path).expanduser().resolve())
    
    for pattern in PROTECTED_PATHS:
        expanded_pattern = str(Path(pattern).expanduser())
        if fnmatch.fnmatch(expanded_path, expanded_pattern):
            return True
        if fnmatch.fnmatch(expanded_path, expanded_pattern + "/*"):
            return True
        if expanded_path.startswith(expanded_pattern.rstrip("*")):
            return True
    
    return False


def is_protected_path(path: str, protected_paths: list[str] | None = None) -> bool:
    """Check if a path is protected."""
    if protected_paths is None:
        return is_protected_path_cached(path)
    
    import fnmatch
    
    expanded_path = str(Path(path).expanduser().resolve())
    
    for pattern in protected_paths:
        expanded_pattern = str(Path(pattern).expanduser())
        if fnmatch.fnmatch(expanded_path, expanded_pattern):
            return True
        if fnmatch.fnmatch(expanded_path, expanded_pattern + "/*"):
            return True
        if expanded_path.startswith(expanded_pattern.rstrip("*")):
            return True
    
    return False


def clear_permission_cache() -> None:
    """Clear all permission-related caches."""
    _is_sensitive_operation_cached.cache_clear()
    is_protected_path_cached.cache_clear()
