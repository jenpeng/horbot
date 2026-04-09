"""MCP client: connects to MCP servers and wraps their tools as native horbot tools."""

import asyncio
from contextlib import AsyncExitStack
import os
import shutil
import sys
from typing import Any
import re

import httpx
from loguru import logger

from horbot.agent.tools.base import Tool, ToolCategory
from horbot.agent.tools.registry import ToolRegistry


MCP_SERVER_CATEGORIES: dict[str, ToolCategory] = {
    "browser": ToolCategory.WEB,
    "excel": ToolCategory.FILESYSTEM,
    "office-powerpoint": ToolCategory.FILESYSTEM,
    "office-word": ToolCategory.FILESYSTEM,
    "puppeteer": ToolCategory.WEB,
    "chrome-devtools": ToolCategory.WEB,
}


def resolve_stdio_command(command: str) -> str:
    """Resolve Python-like MCP commands to a usable interpreter in the current environment."""
    normalized = (command or "").strip()
    if not normalized:
        return normalized

    command_name = os.path.basename(normalized)
    if command_name.startswith("python"):
        resolved = shutil.which(normalized)
        if resolved:
            return resolved
        return sys.executable

    return normalized


class MCPToolWrapper(Tool):
    """Wraps a single MCP server tool as a native horbot tool."""

    def __init__(self, session, server_name: str, tool_def, tool_timeout: int = 30, category: ToolCategory = ToolCategory.MCP):
        self._session = session
        self._original_name = tool_def.name
        self._name = f"mcp_{server_name}_{tool_def.name}"
        self._description = tool_def.description or tool_def.name
        self._parameters = tool_def.inputSchema or {"type": "object", "properties": {}}
        self._tool_timeout = tool_timeout
        self._category = category

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._parameters
    
    @property
    def category(self) -> ToolCategory:
        return self._category

    async def execute(self, **kwargs: Any) -> str:
        from mcp import types
        try:
            result = await asyncio.wait_for(
                self._session.call_tool(self._original_name, arguments=kwargs),
                timeout=self._tool_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("MCP tool '{}' timed out after {}s", self._name, self._tool_timeout)
            return f"(MCP tool call timed out after {self._tool_timeout}s)"
        parts = []
        for block in result.content:
            if isinstance(block, types.TextContent):
                parts.append(block.text)
            else:
                parts.append(str(block))
        return "\n".join(parts) or "(no output)"


class BrowserToolWrapper(Tool):
    """High-level browser tool backed by browser MCP actions."""

    _ACTION_TO_TOOL = {
        "navigate": "browser_navigate",
        "click": "browser_click",
        "type": "browser_type",
        "scroll": "browser_scroll",
        "screenshot": "browser_screenshot",
        "get_text": "browser_get_text",
        "get_html": "browser_get_html",
        "wait_for": "browser_wait_for",
        "evaluate": "browser_evaluate",
        "get_url": "browser_get_url",
        "get_title": "browser_get_title",
        "close": "browser_close",
        "new_tab": "browser_new_tab",
        "press_key": "browser_press_key",
        "find_elements": "browser_find_elements",
        "hover": "browser_hover",
        "back": "browser_goto_back",
        "forward": "browser_goto_forward",
        "reload": "browser_reload",
    }

    def __init__(self, session, tool_timeout: int = 30):
        self._session = session
        self._tool_timeout = tool_timeout

    @property
    def name(self) -> str:
        return "browser"

    @property
    def description(self) -> str:
        return (
            "Browser automation tool. Use this to open webpages, click elements, type text, "
            "wait for selectors, capture screenshots, read page text/HTML, and get the current "
            "page title or URL. Prefer this tool whenever the user asks to open, browse, click, "
            "search within, or inspect a webpage."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": list(self._ACTION_TO_TOOL.keys()),
                    "description": "Browser action to perform.",
                },
                "url": {"type": "string", "description": "Target URL for navigate/new_tab."},
                "selector": {"type": "string", "description": "CSS/text selector for click/type/wait/find/hover/get_text/get_html."},
                "text": {"type": "string", "description": "Text to type into an input element."},
                "timeout": {"type": "integer", "description": "Timeout in milliseconds for click/wait actions."},
                "delay": {"type": "integer", "description": "Typing delay in milliseconds for type action."},
                "direction": {"type": "string", "enum": ["up", "down"], "description": "Scroll direction."},
                "distance": {"type": "integer", "description": "Scroll distance in pixels."},
                "path": {"type": "string", "description": "Output path for screenshot action."},
                "script": {"type": "string", "description": "JavaScript code for evaluate action."},
                "key": {"type": "string", "description": "Keyboard key for press_key action."},
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs: Any) -> str:
        from mcp import types

        action = str(kwargs.get("action", "")).strip()
        target_tool = self._ACTION_TO_TOOL.get(action)
        if not target_tool:
            return f"Error: Unknown browser action '{action}'."

        arguments: dict[str, Any] = {}
        if action in {"navigate", "new_tab"} and kwargs.get("url"):
            arguments["url"] = kwargs["url"]
        if action in {"click", "wait_for"}:
            if kwargs.get("selector"):
                arguments["selector"] = kwargs["selector"]
            if kwargs.get("timeout") is not None:
                arguments["timeout"] = kwargs["timeout"]
        elif action in {"type"}:
            if kwargs.get("selector"):
                arguments["selector"] = kwargs["selector"]
            if kwargs.get("text") is not None:
                arguments["text"] = kwargs["text"]
            if kwargs.get("delay") is not None:
                arguments["delay"] = kwargs["delay"]
        elif action in {"scroll"}:
            if kwargs.get("direction"):
                arguments["direction"] = kwargs["direction"]
            if kwargs.get("distance") is not None:
                arguments["distance"] = kwargs["distance"]
        elif action in {"screenshot"} and kwargs.get("path"):
            arguments["path"] = kwargs["path"]
        elif action in {"get_text", "get_html", "find_elements", "hover"} and kwargs.get("selector"):
            arguments["selector"] = kwargs["selector"]
        elif action == "evaluate" and kwargs.get("script") is not None:
            arguments["script"] = kwargs["script"]
        elif action == "press_key" and kwargs.get("key") is not None:
            arguments["key"] = kwargs["key"]

        try:
            result = await asyncio.wait_for(
                self._session.call_tool(target_tool, arguments=arguments),
                timeout=self._tool_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("Browser tool action '{}' timed out after {}s", action, self._tool_timeout)
            return f"(browser action '{action}' timed out after {self._tool_timeout}s)"

        parts = []
        for block in result.content:
            if isinstance(block, types.TextContent):
                parts.append(block.text)
            else:
                parts.append(str(block))
        return "\n".join(parts) or "(no output)"


async def connect_mcp_servers(
    mcp_servers: dict, registry: ToolRegistry, stack: AsyncExitStack
) -> None:
    """Connect to configured MCP servers and register their tools."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    for name, cfg in mcp_servers.items():
        try:
            if cfg.command:
                command = resolve_stdio_command(cfg.command)
                params = StdioServerParameters(
                    command=command, args=cfg.args, env=cfg.env or None
                )
                read, write = await stack.enter_async_context(stdio_client(params))
            elif cfg.url:
                from mcp.client.streamable_http import streamable_http_client
                # Always provide an explicit httpx client so MCP HTTP transport does not
                # inherit httpx's default 5s timeout and preempt the higher-level tool timeout.
                http_client = await stack.enter_async_context(
                    httpx.AsyncClient(
                        headers=cfg.headers or None,
                        follow_redirects=True,
                        timeout=None,
                    )
                )
                read, write, _ = await stack.enter_async_context(
                    streamable_http_client(cfg.url, http_client=http_client)
                )
            else:
                logger.warning("MCP server '{}': no command or url configured, skipping", name)
                continue

            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            tools = await session.list_tools()
            category = MCP_SERVER_CATEGORIES.get(name, ToolCategory.MCP)
            for tool_def in tools.tools:
                wrapper = MCPToolWrapper(session, name, tool_def, tool_timeout=cfg.tool_timeout, category=category)
                registry.register(wrapper)
                logger.debug("MCP: registered tool '{}' from server '{}'", wrapper.name, name)

            if name == "browser":
                browser_wrapper = BrowserToolWrapper(session, tool_timeout=cfg.tool_timeout)
                registry.register(browser_wrapper)
                logger.debug("MCP: registered high-level tool '{}' from server '{}'", browser_wrapper.name, name)

            logger.info("MCP server '{}': connected, {} tools registered", name, len(tools.tools))
        except Exception as e:
            logger.error("MCP server '{}': failed to connect: {}", name, e)
