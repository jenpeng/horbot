"""MCP server and web-search provider API routes."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


GetConfigFn = Callable[[], Any]
SaveConfigFn = Callable[[Any], Any]
ResetAgentLoopFn = Callable[[], Awaitable[Any]]
SanitizeMcpServerFn = Callable[[str, Any], dict[str, Any]]


class MCPServerCreateRequest(BaseModel):
    name: str
    command: str = ""
    args: list[str] = []
    env: dict[str, str] = {}
    url: str = ""
    tool_timeout: int = 30
    headers: dict[str, str] = {}


def create_mcp_router(
    get_config: GetConfigFn,
    save_config_fn: SaveConfigFn,
    reset_agent_loop_fn: ResetAgentLoopFn,
    sanitize_mcp_server_fn: SanitizeMcpServerFn,
) -> APIRouter:
    """Create routes for MCP server settings and web-search provider catalog."""

    router = APIRouter()

    @router.get("/mcp-servers")
    async def get_mcp_servers():
        """Get MCP servers configuration."""
        config = get_config()
        servers = []
        if config.tools and config.tools.mcp_servers:
            for name, cfg in config.tools.mcp_servers.items():
                servers.append(sanitize_mcp_server_fn(name, cfg))
        return {"servers": servers}

    @router.get("/web-search-providers")
    async def get_web_search_providers():
        """Get supported web search providers."""
        return {
            "providers": [
                {"id": "duckduckgo", "name": "DuckDuckGo", "description": "免费搜索，无需 API key", "requires_api_key": False},
                {
                    "id": "brave",
                    "name": "Brave Search",
                    "description": "Brave 搜索 API，需要 API key",
                    "requires_api_key": True,
                    "api_key_url": "https://brave.com/search/api/",
                },
                {
                    "id": "tavily",
                    "name": "Tavily",
                    "description": "AI 优化的搜索 API，可通过 Tavily 开关显式启用或关闭",
                    "requires_api_key": True,
                    "api_key_url": "https://tavily.com/",
                    "enabled_config_key": "tavilyEnabled",
                },
                {
                    "id": "langsearch",
                    "name": "LangSearch",
                    "description": "免费 Web Search API，可通过 LangSearch 开关显式启用或关闭",
                    "requires_api_key": True,
                    "api_key_url": "https://langsearch.com/",
                    "enabled_config_key": "langsearchEnabled",
                },
            ]
        }

    @router.post("/mcp-servers")
    async def add_mcp_server(request: MCPServerCreateRequest):
        """Add a new MCP server."""
        try:
            from horbot.config.schema import MCPServerConfig, ToolsConfig

            config = get_config()
            if not config.tools:
                config.tools = ToolsConfig()
            if not config.tools.mcp_servers:
                config.tools.mcp_servers = {}
            if request.name in config.tools.mcp_servers:
                raise HTTPException(status_code=400, detail=f"MCP server '{request.name}' already exists")

            server_config = MCPServerConfig(
                command=request.command,
                args=request.args,
                env=request.env,
                url=request.url,
                tool_timeout=request.tool_timeout,
                headers=request.headers,
            )
            config.tools.mcp_servers[request.name] = server_config
            saved_path = save_config_fn(config)
            await reset_agent_loop_fn()
            return {
                "status": "success",
                "message": f"MCP server '{request.name}' added successfully",
                "path": str(saved_path),
                "server": sanitize_mcp_server_fn(request.name, server_config),
            }
        except HTTPException:
            raise
        except PermissionError as exc:
            raise HTTPException(status_code=500, detail=f"Permission denied: {str(exc)}. The application may be running in a sandbox environment.")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(exc)}")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to add MCP server: {str(exc)}")

    @router.put("/mcp-servers/{name}")
    async def update_mcp_server(name: str, request: dict[str, Any]):
        """Update an existing MCP server."""
        try:
            from horbot.config.schema import MCPServerConfig

            config = get_config()
            if not config.tools or not config.tools.mcp_servers or name not in config.tools.mcp_servers:
                raise HTTPException(status_code=404, detail=f"MCP server '{name}' not found")

            existing = config.tools.mcp_servers[name]
            incoming_env = request.get("env", existing.env)
            if isinstance(incoming_env, dict):
                incoming_env = {
                    key: (existing.env or {}).get(key, value) if value == "********" else value
                    for key, value in incoming_env.items()
                }
            incoming_headers = request.get("headers", existing.headers)
            if isinstance(incoming_headers, dict):
                incoming_headers = {
                    key: (existing.headers or {}).get(key, value) if value == "********" else value
                    for key, value in incoming_headers.items()
                }

            server_config = MCPServerConfig(
                command=request.get("command", existing.command),
                args=request.get("args", existing.args),
                env=incoming_env,
                url=request.get("url", existing.url),
                tool_timeout=request.get("tool_timeout", existing.tool_timeout),
                headers=incoming_headers,
            )
            config.tools.mcp_servers[name] = server_config
            saved_path = save_config_fn(config)
            await reset_agent_loop_fn()
            return {
                "status": "success",
                "message": f"MCP server '{name}' updated successfully",
                "path": str(saved_path),
                "server": sanitize_mcp_server_fn(name, server_config),
            }
        except HTTPException:
            raise
        except PermissionError as exc:
            raise HTTPException(status_code=500, detail=f"Permission denied: {str(exc)}. The application may be running in a sandbox environment.")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(exc)}")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to update MCP server: {str(exc)}")

    @router.delete("/mcp-servers/{name}")
    async def delete_mcp_server(name: str):
        """Delete an MCP server."""
        try:
            config = get_config()
            if not config.tools or not config.tools.mcp_servers:
                raise HTTPException(status_code=404, detail=f"MCP server '{name}' not found")
            if name not in config.tools.mcp_servers:
                raise HTTPException(status_code=404, detail=f"MCP server '{name}' not found")

            del config.tools.mcp_servers[name]
            saved_path = save_config_fn(config)
            await reset_agent_loop_fn()
            return {"status": "success", "message": f"MCP server '{name}' deleted successfully", "path": str(saved_path)}
        except HTTPException:
            raise
        except PermissionError as exc:
            raise HTTPException(status_code=500, detail=f"Permission denied: {str(exc)}. The application may be running in a sandbox environment.")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(exc)}")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to delete MCP server: {str(exc)}")

    return router
