"""Tool registry for dynamic tool management with permission control."""

from dataclasses import dataclass, field
from typing import Any, Callable

from horbot.agent.tools.base import (
    Tool,
    ToolError,
    ValidationError,
    ExecutionError,
    PermissionError as ToolPermissionError,
    ToolMetadata,
    ToolCategory,
)
from horbot.agent.tools.permission import (
    PermissionManager,
    PermissionConfig,
    PermissionLevel,
    PermissionResult,
    is_sensitive_operation_with_params,
    is_protected_path,
    PROTECTED_PATHS,
)


@dataclass
class ExecutionResult:
    """Result of a tool execution."""
    success: bool
    output: str
    tool_name: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    recoverable: bool = True
    
    @classmethod
    def ok(cls, output: str, tool_name: str = "", params: dict[str, Any] | None = None) -> "ExecutionResult":
        return cls(success=True, output=output, tool_name=tool_name, params=params or {})
    
    @classmethod
    def fail(
        cls,
        error: str,
        tool_name: str = "",
        params: dict[str, Any] | None = None,
        recoverable: bool = True,
    ) -> "ExecutionResult":
        hint = "\n\n[Analyze the error above and try a different approach.]" if recoverable else ""
        return cls(
            success=False,
            output=f"Error: {error}{hint}",
            tool_name=tool_name,
            params=params or {},
            error=error,
            recoverable=recoverable,
        )


class PermissionDeniedError(Exception):
    """Raised when a tool execution is denied by permission policy."""
    pass


class ConfirmationRequiredError(Exception):
    """Raised when a tool execution requires user confirmation."""
    
    def __init__(self, tool_name: str, params: dict[str, Any], message: str = ""):
        self.tool_name = tool_name
        self.params = params
        self.message = message or f"Tool '{tool_name}' requires user confirmation"
        super().__init__(self.message)


class ToolRegistry:
    """
    Registry for agent tools with permission control.
    
    Features:
    - Dynamic tool registration and unregistration
    - Permission-based access control
    - Audit logging support
    - Unified error handling
    - Tool metadata management
    - Runtime tool availability control (e.g., web_search)
    
    Usage:
        registry = ToolRegistry()
        registry.register(my_tool)
        result = await registry.execute("read_file", {"path": "/tmp/test.txt"})
    """
    
    WEB_TOOLS = {"web_search", "web_fetch"}
    
    def __init__(self, permission_manager: PermissionManager | None = None):
        self._tools: dict[str, Tool] = {}
        self._permission_manager = permission_manager or PermissionManager()
        self._audit_callback: Callable[[str, dict[str, Any], str | None, str | None], None] | None = None
        self._pre_execute_hook: Callable[[str, dict[str, Any]], bool] | None = None
        self._post_execute_hook: Callable[[str, dict[str, Any], str], None] | None = None
        self._web_search_enabled: bool = False
    
    def set_permission_manager(self, pm: PermissionManager) -> None:
        """Set the permission manager."""
        self._permission_manager = pm
    
    def set_audit_callback(
        self,
        callback: Callable[[str, dict[str, Any], str | None, str | None], None] | None,
    ) -> None:
        """Set callback for audit logging. Signature: (tool_name, params, result, error)"""
        self._audit_callback = callback
    
    def set_pre_execute_hook(
        self,
        hook: Callable[[str, dict[str, Any]], bool] | None,
    ) -> None:
        """Set hook to be called before tool execution. Return False to cancel."""
        self._pre_execute_hook = hook
    
    def set_post_execute_hook(
        self,
        hook: Callable[[str, dict[str, Any], str], None] | None,
    ) -> None:
        """Set hook to be called after successful tool execution."""
        self._post_execute_hook = hook
    
    def set_web_search_enabled(self, enabled: bool) -> None:
        """Enable or disable web search tools at runtime."""
        self._web_search_enabled = enabled
    
    def is_web_search_enabled(self) -> bool:
        """Check if web search tools are enabled."""
        return self._web_search_enabled
    
    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
    
    def unregister(self, name: str) -> bool:
        """Unregister a tool by name. Returns True if tool was registered."""
        if name in self._tools:
            del self._tools[name]
            return True
        return False
    
    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def has(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools
    
    def get_metadata(self, name: str) -> ToolMetadata | None:
        """Get metadata for a tool."""
        tool = self._tools.get(name)
        return tool.metadata if tool else None
    
    def get_all_metadata(self) -> dict[str, ToolMetadata]:
        """Get metadata for all registered tools."""
        return {name: tool.metadata for name, tool in self._tools.items()}
    
    def get_definitions(self) -> list[dict[str, Any]]:
        """Get all tool definitions in OpenAI format (only allowed tools)."""
        allowed_tools = self._permission_manager.get_allowed_tools(self.tool_names)
        return [self._tools[name].to_schema() for name in allowed_tools if name in self._tools]

    @staticmethod
    def _normalize_user_message_for_matching(user_message: Any) -> str:
        """Flatten multimodal user content into plain text for keyword matching."""
        if user_message is None:
            return ""
        if isinstance(user_message, str):
            return user_message
        if isinstance(user_message, list):
            text_parts: list[str] = []
            for item in user_message:
                if isinstance(item, str):
                    text_parts.append(item)
                    continue
                if isinstance(item, dict):
                    if item.get("type") == "text" and isinstance(item.get("text"), str):
                        text_parts.append(item["text"])
                        continue
                    if isinstance(item.get("content"), str):
                        text_parts.append(item["content"])
            return "\n".join(part for part in text_parts if part).strip()
        return str(user_message)
    
    def get_definitions_smart(self, user_message: Any = None, max_tools: int = 50, include_web_search: bool = False) -> list[dict[str, Any]]:
        """
        Get tool definitions with smart filtering based on user message.
        
        This reduces the number of tools sent to LLM, improving response time.
        Priority:
        1. Core tools (always included): read_file, write_file, exec, cron, etc.
        2. Relevant tools based on keywords in user message
        3. Remaining tools up to max_tools
        
        Args:
            user_message: User message to analyze for keyword matching
            max_tools: Maximum number of tools to return
            include_web_search: When True, web_search tool is always available
        """
        from horbot.agent.tools.base import ToolCategory
        from loguru import logger
        
        WEB_TOOLS = {"web_search", "web_fetch"}
        
        allowed_tools = self._permission_manager.get_allowed_tools(self.tool_names)
        available = [name for name in allowed_tools if name in self._tools]
        
        if not include_web_search:
            available = [name for name in available if name not in WEB_TOOLS]
        
        total_tools = len(available)
        
        CORE_TOOLS = {
            "read_file", "write_file", "edit_file", "list_dir",
            "cron", "task", "message", "spawn",
        }
        
        if include_web_search:
            CORE_TOOLS.update(WEB_TOOLS)
        
        KEYWORD_TOOL_MAP = {
            "ppt": {"mcp_office-powerpoint"},
            "powerpoint": {"mcp_office-powerpoint"},
            "演示": {"mcp_office-powerpoint"},
            "幻灯片": {"mcp_office-powerpoint"},
            "word": {"mcp_office-word"},
            "文档": {"mcp_office-word", "write_file", "read_file"},
            "excel": {"mcp_excel"},
            "表格": {"mcp_excel"},
            "spreadsheet": {"mcp_excel"},
            "browser": {"browser", "browser_", "mcp_browser"},
            "浏览器": {"browser", "browser_", "mcp_browser"},
            "打开": {"browser", "browser_", "mcp_browser", "web_fetch"},
            "访问": {"browser", "browser_", "mcp_browser", "web_fetch"},
            "页面": {"browser", "browser_", "mcp_browser", "web_fetch"},
            "页面标题": {"browser", "browser_", "mcp_browser"},
            "标题": {"browser", "browser_", "mcp_browser"},
            "网页": {"browser", "browser_", "mcp_browser", "web_fetch", "web_search"},
            "website": {"browser", "browser_", "mcp_browser", "web_fetch"},
            "url": {"browser", "browser_", "mcp_browser", "web_fetch"},
            "http://": {"browser", "browser_", "mcp_browser", "web_fetch"},
            "https://": {"browser", "browser_", "mcp_browser", "web_fetch"},
            "screenshot": {"browser", "browser_", "mcp_browser"},
            "截图": {"browser", "browser_", "mcp_browser"},
            "click": {"browser", "browser_", "mcp_browser"},
            "点击": {"browser", "browser_", "mcp_browser"},
            "提醒": {"cron"},
            "提醒我": {"task", "cron"},
            "定时": {"cron"},
            "定时任务": {"cron"},
            "任务": {"task", "cron"},
            "待办": {"cron"},
            "待办事项": {"task", "cron"},
            "reminder": {"cron"},
            "schedule": {"cron"},
            "task": {"task", "cron"},
            "tasks": {"task", "cron"},
            "todo": {"cron"},
            "喝水": {"cron"},
            "分钟后": {"task", "cron"},
            "小时后": {"task", "cron"},
            "明天": {"task", "cron"},
            "后天": {"task", "cron"},
            "calendar": {"task", "cron"},
            "执行命令": {"exec"},
            "运行": {"exec"},
            "run command": {"exec"},
            "execute": {"exec"},
            "shell": {"exec"},
            "终端": {"exec"},
        }
        
        selected = set()
        
        for tool in available:
            if tool in CORE_TOOLS:
                selected.add(tool)
        
        normalized_user_message = self._normalize_user_message_for_matching(user_message)

        keyword_matched = False
        if normalized_user_message:
            msg_lower = normalized_user_message.lower()
            for keyword, tool_prefixes in KEYWORD_TOOL_MAP.items():
                if keyword in msg_lower:
                    keyword_matched = True
                    for prefix in tool_prefixes:
                        for tool in available:
                            if tool.startswith(prefix) or tool == prefix:
                                selected.add(tool)
        
        if not keyword_matched:
            for tool in available:
                if len(selected) >= max_tools:
                    break
                selected.add(tool)
        
        if not include_web_search:
            selected = selected - WEB_TOOLS
        
        result = [self._tools[name].to_schema() for name in selected if name in self._tools]
        logger.debug(
            "Smart tool selection: {}/{} tools selected for message: {}",
            len(result),
            total_tools,
            normalized_user_message[:50] if normalized_user_message else "N/A",
        )
        return result
    
    def get_all_definitions(self) -> list[dict[str, Any]]:
        """Get all tool definitions regardless of permissions (for admin purposes)."""
        return [tool.to_schema() for tool in self._tools.values()]
    
    def check_permission(self, name: str) -> PermissionLevel:
        """Check permission level for a tool."""
        return self._permission_manager.check_permission(name)
    
    def check_permission_detailed(
        self,
        name: str,
        params: dict[str, Any] | None = None,
    ) -> PermissionResult:
        """Check permission with detailed result."""
        return self._permission_manager.check_permission_detailed(name, params)
    
    def requires_confirmation(self, name: str, params: dict[str, Any] | None = None) -> bool:
        """Check if tool requires user confirmation."""
        if name == "exec" and params:
            from horbot.agent.tools.permission import is_sensitive_operation
            return is_sensitive_operation(name, params)
        return self._permission_manager.check_permission(name) == PermissionLevel.CONFIRM
    
    def check_path_permission(self, path: str, protected_paths: list[str] | None = None) -> bool:
        """Check if path access is allowed. Returns False if path is protected."""
        return not is_protected_path(path, protected_paths)
    
    async def execute(self, name: str, params: dict[str, Any]) -> str:
        """
        Execute a tool by name with given parameters.
        
        This method handles:
        - Tool existence check
        - Permission validation
        - Parameter validation
        - Error handling
        - Audit logging
        
        Args:
            name: Tool name to execute
            params: Parameters to pass to the tool
        
        Returns:
            Tool execution result as string
        """
        result = await self._execute_internal(name, params, check_permission=True)
        return result.output
    
    async def execute_with_result(self, name: str, params: dict[str, Any]) -> ExecutionResult:
        """
        Execute a tool and return detailed result.
        
        Args:
            name: Tool name to execute
            params: Parameters to pass to the tool
        
        Returns:
            ExecutionResult with success status, output, and error details
        """
        return await self._execute_internal(name, params, check_permission=True)
    
    async def execute_confirmed(self, name: str, params: dict[str, Any]) -> str:
        """
        Execute a tool that has already been confirmed by the user.
        
        This method bypasses the permission check since confirmation was already obtained.
        """
        result = await self._execute_internal(name, params, check_permission=False, skip_guard=False)
        return result.output
    
    async def execute_with_confirmation(
        self,
        name: str,
        params: dict[str, Any],
        confirm_callback: Callable[[str, dict[str, Any]], bool] | None = None,
    ) -> str:
        """
        Execute a tool with confirmation support.
        
        If the tool requires confirmation, confirm_callback will be called.
        Signature: confirm_callback(tool_name, params) -> bool
        """
        permission = self._permission_manager.check_permission_detailed(name, params)
        
        if permission.needs_confirmation:
            if confirm_callback:
                confirmed = await confirm_callback(name, params) if callable(confirm_callback) else False
                if not confirmed:
                    error_msg = f"Tool '{name}' execution was not confirmed by user."
                    self._log_audit(name, params, None, error_msg)
                    return ExecutionResult.fail(error_msg, name, params).output
            else:
                raise ConfirmationRequiredError(name, params)
        
        result = await self._execute_internal(name, params, check_permission=False)
        return result.output
    
    async def _execute_internal(
        self,
        name: str,
        params: dict[str, Any],
        check_permission: bool = True,
        skip_guard: bool = False,
    ) -> ExecutionResult:
        """Internal execution logic with unified error handling."""
        
        tool = self._tools.get(name)
        if not tool:
            error_msg = f"Tool '{name}' not found. Available: {', '.join(self.tool_names)}"
            self._log_audit(name, params, None, error_msg)
            return ExecutionResult.fail(error_msg, name, params, recoverable=False)
        
        if name in self.WEB_TOOLS and not self._web_search_enabled:
            error_msg = f"Web search is not enabled. Please enable '联网搜索' to use {name} tool."
            self._log_audit(name, params, None, error_msg)
            return ExecutionResult.fail(error_msg, name, params, recoverable=False)
        
        if check_permission:
            permission = self._permission_manager.check_permission_detailed(name, params)
            
            if permission.is_denied:
                error_msg = permission.to_error_message() or f"Tool '{name}' is not allowed"
                self._log_audit(name, params, None, error_msg)
                return ExecutionResult.fail(error_msg, name, params, recoverable=False)
            
            if permission.needs_confirmation:
                error_msg = permission.to_error_message() or f"Tool '{name}' requires confirmation"
                self._log_audit(name, params, None, error_msg)
                return ExecutionResult.fail(error_msg, name, params, recoverable=True)
        
        path_param = params.get("path", "")
        if path_param and not self.check_path_permission(path_param):
            error_msg = f"Access to path '{path_param}' is protected."
            self._log_audit(name, params, None, error_msg)
            return ExecutionResult.fail(error_msg, name, params, recoverable=False)
        
        if self._pre_execute_hook:
            try:
                if not self._pre_execute_hook(name, params):
                    error_msg = f"Tool '{name}' execution was cancelled by pre-execute hook."
                    self._log_audit(name, params, None, error_msg)
                    return ExecutionResult.fail(error_msg, name, params, recoverable=True)
            except Exception as e:
                error_msg = f"Pre-execute hook error: {str(e)}"
                self._log_audit(name, params, None, error_msg)
                return ExecutionResult.fail(error_msg, name, params, recoverable=True)
        
        try:
            errors = tool.validate_params(params)
            if errors:
                error_msg = f"Invalid parameters: {'; '.join(errors)}"
                self._log_audit(name, params, None, error_msg)
                return ExecutionResult.fail(error_msg, name, params, recoverable=True)
            
            execute_params = params
            if skip_guard and name == "exec":
                execute_params = {**params, "skip_guard": True}
            
            result = await tool.execute(**execute_params)
            
            if isinstance(result, str) and result.startswith("Error"):
                self._log_audit(name, params, result, None)
                return ExecutionResult.fail(result[6:].strip(), name, params)
            
            self._log_audit(name, params, result, None)
            
            if self._post_execute_hook:
                try:
                    self._post_execute_hook(name, params, result)
                except Exception:
                    pass
            
            return ExecutionResult.ok(result, name, params)
            
        except ToolError as e:
            error_msg = e.to_result()
            self._log_audit(name, params, None, error_msg)
            return ExecutionResult.fail(str(e), name, params, e.recoverable)
        except Exception as e:
            error_msg = f"Unexpected error executing {name}: {str(e)}"
            self._log_audit(name, params, None, error_msg)
            return ExecutionResult.fail(error_msg, name, params, recoverable=True)
    
    def _log_audit(
        self,
        tool_name: str,
        params: dict[str, Any],
        result: str | None,
        error: str | None,
    ) -> None:
        """Log tool execution for audit purposes."""
        if self._audit_callback:
            try:
                self._audit_callback(tool_name, params, result, error)
            except Exception:
                pass
    
    @property
    def tool_names(self) -> list[str]:
        """Get list of registered tool names."""
        return list(self._tools.keys())
    
    @property
    def allowed_tool_names(self) -> list[str]:
        """Get list of allowed tool names."""
        return self._permission_manager.get_allowed_tools(self.tool_names)
    
    def get_tools_by_category(self, category: ToolCategory) -> list[Tool]:
        """Get all tools in a specific category."""
        return [
            tool for tool in self._tools.values()
            if tool.metadata.category == category
        ]
    
    def get_tools_by_tag(self, tag: str) -> list[Tool]:
        """Get all tools with a specific tag."""
        return [
            tool for tool in self._tools.values()
            if tag in tool.metadata.tags
        ]
    
    def get_dangerous_tools(self) -> list[Tool]:
        """Get all tools marked as dangerous."""
        return [
            tool for tool in self._tools.values()
            if tool.metadata.dangerous
        ]
    
    def __len__(self) -> int:
        return len(self._tools)
    
    def __contains__(self, name: str) -> bool:
        return name in self._tools
    
    def __iter__(self):
        return iter(self._tools.items())
    
    def __repr__(self) -> str:
        return f"<ToolRegistry: {len(self._tools)} tools>"


class ConfigureMCPTool(Tool):
    """Tool to manage MCP server configurations."""

    @property
    def name(self) -> str:
        return "configure_mcp"

    @property
    def description(self) -> str:
        return """Manage MCP (Model Context Protocol) server configurations.

Operations:
- list: List all configured MCP servers
- add: Add a new MCP server configuration
- remove: Remove an MCP server configuration

For 'add' operation, provide server details (name is required).
For stdio servers, provide 'command' and optionally 'args' and 'env'.
For HTTP servers, provide 'url' and optionally 'headers'.
"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "add", "remove"],
                    "description": "The action to perform: list, add, or remove"
                },
                "name": {
                    "type": "string",
                    "description": "Server name (required for add and remove operations)"
                },
                "command": {
                    "type": "string",
                    "description": "Command to run for stdio MCP server (e.g., 'npx', 'uvx')"
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Command arguments for stdio MCP server"
                },
                "env": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "Environment variables for stdio MCP server"
                },
                "url": {
                    "type": "string",
                    "description": "URL for HTTP MCP server (streamable HTTP endpoint)"
                },
                "tool_timeout": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 300,
                    "description": "Timeout in seconds for tool calls (default: 30)"
                },
                "headers": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "Custom HTTP headers for HTTP MCP server"
                }
            },
            "required": ["action"]
        }

    async def execute(self, **kwargs: Any) -> str:
        from horbot.config.loader import load_config, save_config, invalidate_config_cache
        from horbot.config.schema import MCPServerConfig

        action = kwargs.get("action")

        if action == "list":
            return self._list_servers()
        elif action == "add":
            return self._add_server(kwargs)
        elif action == "remove":
            return self._remove_server(kwargs)
        else:
            return f"Error: Unknown action '{action}'. Valid actions are: list, add, remove"

    def _list_servers(self) -> str:
        from horbot.config.loader import load_config

        config = load_config()
        servers = config.tools.mcp_servers

        if not servers:
            return "No MCP servers configured."

        lines = ["Configured MCP servers:"]
        for name, cfg in servers.items():
            if cfg.command:
                cmd_str = f"{cfg.command} {' '.join(cfg.args)}" if cfg.args else cfg.command
                lines.append(f"  - {name} (stdio): {cmd_str}")
            elif cfg.url:
                lines.append(f"  - {name} (http): {cfg.url}")
            else:
                lines.append(f"  - {name}: (no command or url)")

            if cfg.env:
                lines.append(f"    env: {list(cfg.env.keys())}")
            if cfg.headers:
                lines.append(f"    headers: {list(cfg.headers.keys())}")
            if cfg.tool_timeout != 30:
                lines.append(f"    timeout: {cfg.tool_timeout}s")

        return "\n".join(lines)

    def _add_server(self, params: dict[str, Any]) -> str:
        from horbot.config.loader import load_config, save_config, invalidate_config_cache
        from horbot.config.schema import MCPServerConfig

        name = params.get("name")
        if not name:
            return "Error: 'name' is required for add operation"

        if not isinstance(name, str) or not name.strip():
            return "Error: 'name' must be a non-empty string"

        name = name.strip()

        command = params.get("command", "")
        url = params.get("url", "")

        if not command and not url:
            return "Error: Either 'command' (for stdio) or 'url' (for HTTP) must be provided"

        config = load_config()

        if name in config.tools.mcp_servers:
            return f"Error: MCP server '{name}' already exists. Remove it first or use a different name."

        server_config = MCPServerConfig(
            command=command or "",
            args=params.get("args", []),
            env=params.get("env", {}),
            url=url or "",
            headers=params.get("headers", {}),
            tool_timeout=params.get("tool_timeout", 30),
        )

        config.tools.mcp_servers[name] = server_config

        try:
            save_config(config)
            invalidate_config_cache()
        except PermissionError as e:
            return f"Error: Failed to save configuration: {e}"
        except Exception as e:
            return f"Error: Failed to save configuration: {str(e)}"

        server_type = "stdio" if command else "http"
        endpoint = f"{command} {' '.join(params.get('args', []))}".strip() if command else url
        return f"Successfully added MCP server '{name}' ({server_type}): {endpoint}\n\nNote: Restart the agent to connect to the new MCP server."

    def _remove_server(self, params: dict[str, Any]) -> str:
        from horbot.config.loader import load_config, save_config, invalidate_config_cache

        name = params.get("name")
        if not name:
            return "Error: 'name' is required for remove operation"

        if not isinstance(name, str) or not name.strip():
            return "Error: 'name' must be a non-empty string"

        name = name.strip()

        config = load_config()

        if name not in config.tools.mcp_servers:
            available = list(config.tools.mcp_servers.keys())
            if available:
                return f"Error: MCP server '{name}' not found. Available servers: {', '.join(available)}"
            else:
                return f"Error: MCP server '{name}' not found. No servers are currently configured."

        del config.tools.mcp_servers[name]

        try:
            save_config(config)
            invalidate_config_cache()
        except PermissionError as e:
            return f"Error: Failed to save configuration: {e}"
        except Exception as e:
            return f"Error: Failed to save configuration: {str(e)}"

        return f"Successfully removed MCP server '{name}'.\n\nNote: Restart the agent to fully disconnect from the removed MCP server."
