"""Agent loop: the core processing engine."""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from contextlib import AsyncExitStack
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from loguru import logger

from horbot.agent.errors import AgentException
from horbot.agent.skill_evolution import SkillEvolutionEngine
from horbot.agent.tool_executor import ToolExecutor
from horbot.agent.message_processor import MessageProcessor
from horbot.agent.context import ContextBuilder
from horbot.agent.context_compact import compact_context, estimate_tokens, CompressionResult
from horbot.agent.memory import MemoryStore
from horbot.agent.subagent import SubagentManager
from horbot.agent.tools.cron import CronTool, TaskToolWrapper
from horbot.agent.tools.filesystem import ListDirTool, ReadFileTool
from horbot.agent.tools.safe_editor import SafeWriteFileTool, SafeEditFileTool
from horbot.agent.tools.message import MessageTool
from horbot.agent.tools.registry import ToolRegistry, ConfirmationRequiredError, ConfigureMCPTool
from horbot.agent.tools.permission import PermissionLevel
from horbot.agent.tools.shell import ExecTool
from horbot.agent.tools.spawn import SpawnTool
from horbot.agent.tools.web import WebFetchTool, WebSearchTool
from horbot.agent.tools.token_usage import TokenUsageTool
from horbot.agent.planner import TaskAnalyzer, PlanGenerator, PlanValidator
from horbot.agent.planner.models import Plan, PlanStatus
from horbot.agent.executor import PlanExecutor
from horbot.agent.token_tracker import get_token_tracker
from horbot.bus.events import InboundMessage, OutboundMessage
from horbot.bus.queue import MessageBus
from horbot.providers.base import LLMProvider
from horbot.session.manager import Session, SessionManager
from horbot.utils.helpers import parse_session_key_with_known_routes

if TYPE_CHECKING:
    from horbot.config.schema import ChannelsConfig, ExecToolConfig
    from horbot.cron.service import CronService


class AgentLoop:
    """
    The agent loop is the core processing engine.

    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """

    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = 40,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        memory_window: int = 100,
        brave_api_key: str | None = None,
        exec_config: ExecToolConfig | None = None,
        cron_service: CronService | None = None,
        restrict_to_workspace: bool = False,
        session_manager: SessionManager | None = None,
        mcp_servers: dict | None = None,
        channels_config: ChannelsConfig | None = None,
        use_hierarchical_context: bool = True,
        enable_hot_reload: bool = True,
        system_prompt: str | None = None,
        personality: str | None = None,
        agent_id: str | None = None,
        agent_name: str | None = None,
        team_ids: list[str] | None = None,
    ):
        from horbot.config.schema import ExecToolConfig
        from horbot.config.loader import get_cached_config, on_config_change
        self.bus = bus
        self.channels_config = channels_config
        self.provider = provider
        self.workspace = workspace
        self._model = model
        self._agent_id = agent_id
        self._agent_name = agent_name
        self._team_ids = team_ids or []
        self._max_iterations = max_iterations
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._memory_window = memory_window
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace
        self.use_hierarchical_context = use_hierarchical_context
        self.enable_hot_reload = enable_hot_reload
        self._system_prompt = system_prompt
        self._personality = personality

        self.context = ContextBuilder(
            workspace,
            use_hierarchical=use_hierarchical_context,
            agent_name=agent_name,
            agent_id=agent_id,
            team_ids=self._team_ids,
        )
        self.sessions = session_manager or SessionManager(workspace)
        self.tools = ToolRegistry()
        self._tool_executor = ToolExecutor(self.tools, self.context)
        self._message_processor = MessageProcessor(self)
        self._get_config = get_cached_config
        
        logger.info(f"AgentLoop initialized with workspace: {workspace}")
        soul_path = workspace / "SOUL.md" if isinstance(workspace, Path) else Path(workspace) / "SOUL.md"
        logger.info(f"SOUL.md path: {soul_path}, exists: {soul_path.exists()}")
        
        self._init_permission_manager()
        
        self._init_subagents(provider, workspace, bus, brave_api_key, restrict_to_workspace)
        self._init_runtime_state(mcp_servers)
        self._register_default_tools()
        
        if self.enable_hot_reload:
            self._register_config_callback()

    @property
    def model(self) -> str:
        return self._model or self.provider.get_default_model()

    @property
    def max_iterations(self) -> int:
        config = self._get_config()
        return config.agents.defaults.max_tool_iterations if config else self._max_iterations

    @property
    def temperature(self) -> float:
        config = self._get_config()
        return config.agents.defaults.temperature if config else self._temperature

    @property
    def max_tokens(self) -> int:
        config = self._get_config()
        return config.agents.defaults.max_tokens if config else self._max_tokens

    @property
    def memory_window(self) -> int:
        config = self._get_config()
        return config.agents.defaults.memory_window if config else self._memory_window

    def _memory_store(self) -> MemoryStore:
        return MemoryStore(
            self.workspace,
            agent_id=self._agent_id,
            team_ids=self._team_ids,
        )

    def _get_model_for_context(
        self,
        has_image: bool = False,
        has_audio: bool = False,
        has_video: bool = False,
        has_file: bool = False,
        is_planning: bool = False,
    ) -> str:
        """Get model name based on context.
        
        Args:
            has_image: Whether the request includes images
            has_audio: Whether the request includes audio
            has_video: Whether the request includes video
            has_file: Whether the request includes documents
            is_planning: Whether this is a planning request
            
        Returns:
            Model name to use
        """
        config = self._get_config()
        if config and hasattr(config, 'models'):
            model, provider = config.get_model_for_scenario(
                scenario="main",
                has_image=has_image,
                has_audio=has_audio,
                has_video=has_video,
                has_file=has_file,
                is_planning=is_planning,
            )
            return model
        return self.model

    def _init_permission_manager(self):
        """Initialize permission manager from config."""
        from horbot.agent.tools.permission import PermissionManager

        config = self._get_config()
        if config and hasattr(config, 'tools') and hasattr(config.tools, 'permission'):
            pm_config = self._resolve_permission_config(config)
            confirm_sensitive = True
            if hasattr(config, 'autonomous') and hasattr(config.autonomous, 'confirm_sensitive'):
                confirm_sensitive = config.autonomous.confirm_sensitive
            
            pm = PermissionManager(
                profile=pm_config.profile,
                allow=pm_config.allow,
                deny=pm_config.deny,
                confirm=pm_config.confirm,
                confirm_sensitive=confirm_sensitive,
            )
            self.tools.set_permission_manager(pm)
            logger.debug(f"Permission manager initialized with profile: {pm_config.profile}, confirm_sensitive: {confirm_sensitive}")

    def _resolve_permission_config(self, config):
        """Resolve effective permission config for the current agent."""
        pm_config = getattr(getattr(config, "tools", None), "permission", None)
        if pm_config is None:
            return None

        if not self._agent_id:
            return pm_config

        agent_config = getattr(getattr(config, "agents", None), "instances", {}).get(self._agent_id)
        agent_permission_profile = getattr(agent_config, "permission_profile", "") if agent_config else ""
        agent_permission_profile = str(agent_permission_profile or "").strip()
        if not agent_permission_profile:
            return pm_config

        return type(pm_config)(
            profile=agent_permission_profile,
            allow=[],
            deny=[],
            confirm=[],
        )

    def _get_web_search_config(self) -> dict:
        """Get web search configuration from config file."""
        config = self._get_config()
        if config and hasattr(config, 'tools') and hasattr(config.tools, 'web') and hasattr(config.tools.web, 'search'):
            search_config = config.tools.web.search
            return {
                "provider": getattr(search_config, 'provider', 'duckduckgo'),
                "apiKey": getattr(search_config, 'api_key', ''),
                "maxResults": getattr(search_config, 'max_results', 5),
            }
        return {"provider": "duckduckgo", "apiKey": "", "maxResults": 5}

    def _init_subagents(self, provider, workspace, bus, brave_api_key, restrict_to_workspace):
        """Initialize subagents manager."""
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            brave_api_key=brave_api_key,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
        )

    def _init_runtime_state(self, mcp_servers):
        """Initialize runtime state."""
        from horbot.agent.executor.checkpoint import CheckpointManager
        from horbot.agent.executor.state import StateManager
        from horbot.agent.audit import AuditLogger
        
        self._running = False
        self._mcp_servers = mcp_servers or {}
        self._mcp_stack: AsyncExitStack | None = None
        self._mcp_connected = False
        self._mcp_connecting = False
        self._consolidating: set[str] = set()
        self._consolidation_tasks: set[asyncio.Task] = set()
        self._consolidation_locks: dict[str, asyncio.Lock] = {}
        self._skill_review_tasks: set[asyncio.Task] = set()
        self._active_tasks: dict[str, list[asyncio.Task]] = {}
        self._processing_lock = asyncio.Lock()
        self._message_locks: dict[str, asyncio.Lock] = {}
        
        self._checkpoint_manager = CheckpointManager(workspace=self.workspace)
        self._state_manager = StateManager(workspace=self.workspace)
        self._audit_logger = AuditLogger(workspace=self.workspace)
        
        self._task_analyzer = TaskAnalyzer(
            complexity_threshold=0.35,
            min_steps_for_planning=2,
            provider=self.provider,
        )
        
        config = self._get_config()
        planning_model = None
        planning_provider = None
        
        if config and hasattr(config, 'agents') and hasattr(config.agents, 'defaults'):
            defaults = config.agents.defaults
            planning_model = defaults.planning_model
            planning_provider_name = getattr(defaults, 'planning_provider', None)
            
            if planning_model:
                logger.info("Planning model configured: {}", planning_model)
            
            if planning_provider_name:
                from horbot.providers.registry import create_provider
                from horbot.utils.paths import get_uploads_dir
                try:
                    provider_config = getattr(config.providers, planning_provider_name, None)
                    if provider_config:
                        upload_dir = str(get_uploads_dir())
                        planning_provider = create_provider(
                            provider_name=planning_provider_name,
                            api_key=provider_config.api_key,
                            api_base=provider_config.api_base,
                            extra_headers=provider_config.extra_headers,
                            default_model=planning_model,
                            upload_dir=upload_dir,
                        )
                        logger.info("Planning provider configured: {}", planning_provider_name)
                except Exception as e:
                    logger.warning("Failed to create planning provider '{}': {}. Using default provider.", 
                                  planning_provider_name, e)
        
        self._plan_generator = PlanGenerator(
            provider=self.provider,
            model=self.model,
            planning_model=planning_model,
            planning_provider=planning_provider,
        )
        self._plan_validator = PlanValidator(available_tools=self.tools.tool_names)
        self._plan_executor = PlanExecutor(tool_registry=self.tools, validator=self._plan_validator)
        self._active_plans: dict[str, Plan] = {}
        self._planning_enabled = True  # 默认启用规划功能

    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        allowed_dir = self.workspace if self.restrict_to_workspace else None
        for cls in (ReadFileTool, SafeWriteFileTool, SafeEditFileTool, ListDirTool):
            self.tools.register(cls(workspace=self.workspace, allowed_dir=allowed_dir))
        self.tools.register(ExecTool(
            working_dir=str(self.workspace),
            timeout=self.exec_config.timeout,
            restrict_to_workspace=self.restrict_to_workspace,
            path_append=self.exec_config.path_append,
        ))
        
        # Get web search config from config file
        web_search_config = self._get_web_search_config()
        self.tools.register(WebSearchTool(
            provider=web_search_config.get("provider", "duckduckgo"),
            api_key=web_search_config.get("apiKey", ""),
            max_results=web_search_config.get("maxResults", 5),
        ))
        self.tools.register(WebFetchTool())
        self.tools.register(MessageTool(send_callback=self.bus.publish_outbound))
        self.tools.register(SpawnTool(manager=self.subagents))
        self.tools.register(ConfigureMCPTool())
        self.tools.register(TokenUsageTool())
        if self.cron_service:
            cron_tool = CronTool(self.cron_service)
            self.tools.register(cron_tool)
            self.tools.register(TaskToolWrapper(cron_tool))
    
    def _register_config_callback(self) -> None:
        """Register callback for configuration hot-reload."""
        from horbot.config.loader import on_config_change
        on_config_change(self._on_config_update)
        logger.info("Registered config hot-reload callback")
    
    def _on_config_update(self, old_config, new_config) -> None:
        """Handle configuration update from hot-reload.
        
        Args:
            old_config: Previous configuration.
            new_config: New configuration.
        """
        logger.info("Configuration updated, applying changes...")
        
        try:
            if hasattr(new_config, 'agents') and hasattr(new_config.agents, 'defaults'):
                defaults = new_config.agents.defaults
                
                if hasattr(defaults, 'max_tool_iterations'):
                    self._max_iterations = defaults.max_tool_iterations
                    logger.info(f"Updated max_iterations to {self._max_iterations}")
                
                if hasattr(defaults, 'temperature'):
                    self._temperature = defaults.temperature
                    logger.info(f"Updated temperature to {self._temperature}")
                
                if hasattr(defaults, 'max_tokens'):
                    self._max_tokens = defaults.max_tokens
                    logger.info(f"Updated max_tokens to {self._max_tokens}")
                
                if hasattr(defaults, 'memory_window'):
                    self._memory_window = defaults.memory_window
                    logger.info(f"Updated memory_window to {self._memory_window}")
            
            if hasattr(new_config, 'tools'):
                if hasattr(new_config.tools, 'restrict_to_workspace'):
                    self.restrict_to_workspace = new_config.tools.restrict_to_workspace
                    logger.info(f"Updated restrict_to_workspace to {self.restrict_to_workspace}")
                
                if hasattr(new_config.tools, 'permission'):
                    self._update_permission_manager(new_config.tools.permission)
            
            if hasattr(new_config, 'tools') and hasattr(new_config.tools, 'mcp_servers'):
                if old_config and hasattr(old_config, 'tools') and hasattr(old_config.tools, 'mcp_servers'):
                    old_mcp = old_config.tools.mcp_servers
                    new_mcp = new_config.tools.mcp_servers
                    if old_mcp != new_mcp:
                        logger.info("MCP servers configuration changed, scheduling reload...")
                        asyncio.create_task(self.reload_mcp(new_mcp))
            
            self._update_provider_config(old_config, new_config)
            
            logger.info("Configuration hot-reload completed successfully")
            
        except Exception as e:
            logger.error(f"Error applying configuration update: {e}")
    
    def _update_permission_manager(self, permission_config) -> None:
        """Update permission manager with new configuration.
        
        Args:
            permission_config: New permission configuration.
        """
        from horbot.agent.tools.permission import PermissionManager

        try:
            config = self._get_config()
            confirm_sensitive = True
            if config and hasattr(config, 'autonomous') and hasattr(config.autonomous, 'confirm_sensitive'):
                confirm_sensitive = config.autonomous.confirm_sensitive

            effective_permission_config = self._resolve_permission_config(config) if config else permission_config
            if effective_permission_config is None:
                effective_permission_config = permission_config
            
            pm = PermissionManager(
                profile=effective_permission_config.profile,
                allow=effective_permission_config.allow,
                deny=effective_permission_config.deny,
                confirm=effective_permission_config.confirm,
                confirm_sensitive=confirm_sensitive,
            )
            self.tools.set_permission_manager(pm)
            logger.info(f"Updated permission manager with profile: {effective_permission_config.profile}, confirm_sensitive: {confirm_sensitive}")
        except Exception as e:
            logger.error(f"Failed to update permission manager: {e}")
    
    def _update_provider_config(self, old_config, new_config) -> None:
        """Update provider configuration when model/provider changes.
        
        Args:
            old_config: Previous configuration.
            new_config: New configuration.
        """
        if not hasattr(new_config, 'agents') or not hasattr(new_config.agents, 'defaults'):
            logger.debug("_update_provider_config: No agents.defaults in new_config")
            return
        
        if not hasattr(new_config, 'providers'):
            logger.debug("_update_provider_config: No providers in new_config")
            return
        
        defaults = new_config.agents.defaults
        providers = new_config.providers
        
        old_model = None
        old_provider_name = None
        new_model = None
        new_provider_name = None
        
        if old_config and hasattr(old_config, 'agents') and hasattr(old_config.agents, 'defaults'):
            old_defaults = old_config.agents.defaults
            if hasattr(old_defaults, 'models') and hasattr(old_defaults.models, 'main'):
                old_model = old_defaults.models.main.model
                old_provider_name = old_defaults.models.main.provider
        
        if hasattr(defaults, 'models') and hasattr(defaults.models, 'main'):
            new_model = defaults.models.main.model
            new_provider_name = defaults.models.main.provider
        
        logger.debug(f"_update_provider_config: old={old_provider_name}/{old_model}, new={new_provider_name}/{new_model}")
        
        if old_model != new_model or old_provider_name != new_provider_name:
            logger.info(f"Model/provider changed: {old_provider_name}/{old_model} -> {new_provider_name}/{new_model}")
            
            if new_provider_name and new_model:
                provider_config = getattr(providers, new_provider_name, None)
                if provider_config:
                    from horbot.providers.registry import create_provider
                    from horbot.utils.paths import get_uploads_dir
                    
                    try:
                        upload_dir = str(get_uploads_dir())
                        new_provider = create_provider(
                            provider_name=new_provider_name,
                            api_key=provider_config.api_key,
                            api_base=provider_config.api_base,
                            extra_headers=provider_config.extra_headers,
                            default_model=new_model,
                            upload_dir=upload_dir,
                        )
                        
                        self.provider = new_provider
                        self._model = new_model
                        logger.info(f"Provider updated successfully: {new_provider_name}/{new_model}")
                        
                        if hasattr(self, '_task_analyzer') and self._task_analyzer:
                            self._task_analyzer.provider = new_provider
                        
                        if hasattr(self, '_plan_generator') and self._plan_generator:
                            self._plan_generator.provider = new_provider
                            self._plan_generator.model = new_model
                        
                    except Exception as e:
                        logger.error(f"Failed to update provider: {e}")

    def _get_available_skills(self) -> list[str]:
        """Get list of available skill names."""
        if not hasattr(self.context, 'skills') or not self.context.skills:
            return []
        try:
            skills = self.context.skills.list_skills()
            return [s.get("name", "") for s in skills if s.get("available", True) and s.get("enabled", True)]
        except Exception as e:
            logger.warning(f"Failed to get available skills: {e}")
            return []

    def _get_available_mcp_tools(self) -> list[str]:
        """Get list of available MCP tool names."""
        mcp_tools = []
        if not self._mcp_servers:
            return mcp_tools
        try:
            for server_name in self._mcp_servers.keys():
                # MCP tools are named as: mcp_{server}_{tool}
                # We just return the server names as prefixes
                mcp_tools.append(f"mcp_{server_name}_*")
        except Exception as e:
            logger.warning(f"Failed to get available MCP tools: {e}")
        return mcp_tools

    def _is_new_task(self, content: str, session) -> bool:
        """Detect if user is starting a new task vs continuing a conversation.
        
        Returns True if this appears to be a new task that should clear previous context.
        """
        if not session.messages:
            return False
        
        content_lower = content.strip().lower()
        
        # Skip if it's a continuation response (short, conversational)
        if len(content) < 10:
            return False
        
        # Skip if it's a slash command
        if content_lower.startswith("/"):
            return False
        
        # Skip if it's a continuation phrase
        continuation_phrases = [
            "继续", "continue", "好的", "ok", "是的", "yes", "对", "right",
            "请继续", "please continue", "然后呢", "and then", "接下来",
            "修改", "修改一下", "改一下", "调整", "调整一下",
            "再", "再来", "还要", "还有",
        ]
        for phrase in continuation_phrases:
            if content_lower.startswith(phrase):
                return False
        
        # Detect new task indicators
        new_task_indicators = [
            "帮我", "请帮我", "帮我做", "帮我写", "帮我创建", "帮我实现",
            "创建一个", "写一个", "实现一个", "做一个", "开发一个",
            "分析", "分析一下", "检查", "检查一下", "测试", "测试一下",
            "帮我分析", "帮我检查", "帮我测试",
            "规划", "计划", "设计", "实现", "开发", "构建",
            "help me", "create", "build", "implement", "develop", "design",
            "analyze", "check", "test", "plan",
            "/plan", "新任务", "new task",
        ]
        
        for indicator in new_task_indicators:
            if content_lower.startswith(indicator):
                # Check if last message was a complete response (not asking for continuation)
                if session.messages:
                    last_msg = session.messages[-1] if session.messages else None
                    if last_msg and last_msg.get("role") == "assistant":
                        last_content = last_msg.get("content", "")
                        # If last message was a complete response (not asking a question)
                        if last_content and not last_content.strip().endswith("?"):
                            return True
        
        return False

    async def _connect_mcp(self) -> None:
        """Connect to configured MCP servers (one-time, lazy)."""
        if self._mcp_connected or self._mcp_connecting or not self._mcp_servers:
            return
        self._mcp_connecting = True
        from horbot.agent.tools.mcp import connect_mcp_servers
        try:
            self._mcp_stack = AsyncExitStack()
            await self._mcp_stack.__aenter__()
            await connect_mcp_servers(self._mcp_servers, self.tools, self._mcp_stack)
            self._mcp_connected = True
        except Exception as e:
            logger.error("Failed to connect MCP servers (will retry next message): {}", e)
            if self._mcp_stack:
                try:
                    await self._mcp_stack.aclose()
                except Exception:
                    pass
                self._mcp_stack = None
        finally:
            self._mcp_connecting = False

    def _set_tool_context(
        self,
        channel: str,
        chat_id: str,
        message_id: str | None = None,
        channel_instance_id: str | None = None,
        target_agent_id: str | None = None,
    ) -> None:
        """Update context for all tools that need routing info."""
        if message_tool := self.tools.get("message"):
            if isinstance(message_tool, MessageTool):
                message_tool.set_context(
                    channel,
                    chat_id,
                    message_id,
                    channel_instance_id=channel_instance_id,
                    target_agent_id=target_agent_id,
                )

        if spawn_tool := self.tools.get("spawn"):
            if isinstance(spawn_tool, SpawnTool):
                spawn_tool.set_context(channel, chat_id)

        if cron_tool := self.tools.get("cron"):
            if isinstance(cron_tool, CronTool):
                cron_tool.set_context(channel, chat_id)

        if task_tool := self.tools.get("task"):
            if isinstance(task_tool, TaskToolWrapper):
                task_tool.set_context(channel, chat_id)

    def _list_bound_channel_endpoints(self) -> list[dict[str, str]]:
        if not self._agent_id:
            return []
        try:
            from horbot.channels.endpoints import list_channel_endpoints

            config = self._get_config()
            endpoints = []
            for endpoint in list_channel_endpoints(config):
                if endpoint.agent_id != self._agent_id or not endpoint.enabled:
                    continue
                endpoints.append(
                    {
                        "id": endpoint.id,
                        "channel": endpoint.type,
                        "name": endpoint.name or endpoint.id,
                    }
                )
            return endpoints
        except Exception as exc:
            logger.debug("Failed to list bound channel endpoints: {}", exc)
            return []

    def _list_recent_external_targets(self, limit: int = 6) -> list[dict[str, str]]:
        endpoint_lookup = {item["id"]: item for item in self._list_bound_channel_endpoints()}
        results: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()

        try:
            for session_info in self.sessions.list_sessions():
                key = str(session_info.get("key") or "")
                if ":" not in key:
                    continue
                endpoint_id, chat_id = parse_session_key_with_known_routes(
                    key,
                    known_route_keys=endpoint_lookup.keys(),
                )
                if not chat_id or endpoint_id in {"web", "cli", "system"}:
                    continue
                if endpoint_lookup and endpoint_id not in endpoint_lookup:
                    continue
                unique_key = (endpoint_id, chat_id)
                if unique_key in seen:
                    continue
                seen.add(unique_key)
                endpoint_meta = endpoint_lookup.get(endpoint_id, {})
                results.append(
                    {
                        "endpoint_id": endpoint_id,
                        "channel": endpoint_meta.get("channel", endpoint_id),
                        "endpoint_name": endpoint_meta.get("name", endpoint_id),
                        "chat_id": chat_id,
                        "updated_at": str(session_info.get("updated_at") or ""),
                    }
                )
                if len(results) >= limit:
                    break
        except Exception as exc:
            logger.debug("Failed to list recent external targets: {}", exc)

        return results

    def _list_team_chat_targets(self) -> list[dict[str, str]]:
        if not self._team_ids:
            return []
        try:
            from horbot.agent.manager import get_agent_manager
            from horbot.team.manager import get_team_manager

            agent_manager = get_agent_manager()
            team_manager = get_team_manager()
            targets: list[dict[str, str]] = []
            for team_id in self._team_ids:
                team = team_manager.get_team(team_id)
                if not team:
                    continue
                members = []
                for member_id in team.get_ordered_member_ids():
                    member = agent_manager.get_agent(member_id)
                    member_name = getattr(member, "name", member_id)
                    members.append(f"{member_name}({member_id})")
                targets.append(
                    {
                        "team_id": team.id,
                        "team_name": team.name,
                        "chat_id": f"team_{team.id}",
                        "members": ", ".join(members),
                    }
                )
            return targets
        except Exception as exc:
            logger.debug("Failed to list team chat targets: {}", exc)
            return []

    def _build_bound_channel_runtime_hints(self, msg: InboundMessage) -> list[str]:
        if msg.channel != "web":
            return []

        bound_endpoints = self._list_bound_channel_endpoints()
        recent_targets = self._list_recent_external_targets()
        team_targets = self._list_team_chat_targets()
        if not bound_endpoints and not recent_targets and not team_targets:
            return []

        lines = [
            "[Bound Channel Routing]",
            "- When the user asks you to send a message or execute work in an external bound channel/group, use the `message` tool instead of replying as plain text.",
            "- To route through a specific bound account/endpoint, pass `channel_instance_id` to the `message` tool.",
            "- If the destination group is ambiguous, ask a short clarifying question before sending.",
        ]
        if bound_endpoints:
            lines.append("- Bound endpoints:")
            for endpoint in bound_endpoints:
                lines.append(
                    f"  - id={endpoint['id']} | channel={endpoint['channel']} | name={endpoint['name']}"
                )
        if recent_targets:
            lines.append("- Recent external chats known to this agent:")
            for target in recent_targets:
                lines.append(
                    "  - "
                    f"endpoint_id={target['endpoint_id']} | channel={target['channel']} | "
                    f"name={target['endpoint_name']} | chat_id={target['chat_id']}"
                )
        if team_targets:
            lines.append("- Team group chats available from web:")
            lines.append("  - To post into a team group, use `message` with channel=`web` and chat_id=`team_<team_id>`.")
            lines.append("  - To trigger teammates from that group, either include @mentions in the content or pass `mentioned_agents` and `trigger_group_chat=true`.")
            current_chat_id = str(getattr(msg, "chat_id", "") or "")
            if current_chat_id.startswith("team_"):
                lines.append("  - If you are already speaking inside the current web team chat, do not use `message` to post back into that same `team_<team_id>` just to hand off work.")
                lines.append("  - In that case, reply inline in the current conversation and include `@AgentName` so the existing group-chat relay can continue in the same turn.")
                lines.append("  - If the user expects multi-agent discussion, do not write a full final answer before teammates respond.")
                lines.append("  - Give only your own first-pass, explicitly hand off quickly, and let the visible relay continue round by round.")
                lines.append("  - If you mention a teammate, stop after the handoff request or your local partial view. Do not pre-write the teammate's future意见, merged summary, or final plan.")
                lines.append("  - Do not claim 'based on their feedback' or 'final summary' until that teammate has actually replied in history.")
            for target in team_targets:
                lines.append(
                    "  - "
                    f"team_id={target['team_id']} | team={target['team_name']} | "
                    f"chat_id={target['chat_id']} | members={target['members']}"
                )
        return ["\n".join(lines)]

    def _build_execution_source_metadata(self, session_key: str) -> dict[str, Any]:
        if ":" not in session_key:
            return {"source_session_key": session_key}

        bound_endpoint_ids = [item["id"] for item in self._list_bound_channel_endpoints()]
        channel_instance_id, chat_id = parse_session_key_with_known_routes(
            session_key,
            known_route_keys=bound_endpoint_ids,
        )
        metadata: dict[str, Any] = {
            "source_session_key": session_key,
            "source_channel_instance_id": channel_instance_id,
            "source_chat_id": chat_id,
        }
        if channel_instance_id in {"web", "cli", "system"}:
            metadata["source_channel_type"] = channel_instance_id
            metadata["source_chat_kind"] = "dm" if channel_instance_id == "web" else "system"
            return metadata

        for endpoint in self._list_bound_channel_endpoints():
            if endpoint["id"] != channel_instance_id:
                continue
            metadata["source_channel_type"] = endpoint["channel"]
            metadata["source_endpoint_name"] = endpoint["name"]
            break

        normalized_chat_id = chat_id.lower()
        if any(token in normalized_chat_id for token in ("group", "room", "channel")):
            metadata["source_chat_kind"] = "group"
        elif any(token in normalized_chat_id for token in ("dm", "direct", "user")):
            metadata["source_chat_kind"] = "dm"
        else:
            metadata["source_chat_kind"] = "external"
        return metadata

    def _build_execution_outbound_metadata(self) -> dict[str, Any]:
        message_tool = self.tools.get("message")
        if not isinstance(message_tool, MessageTool):
            return {}

        traces = message_tool.get_outbound_traces()
        if not traces:
            return {}

        latest = traces[-1]
        metadata: dict[str, Any] = {
            "outbound_count": len(traces),
            "outbound_messages": traces,
        }
        for key, value in latest.items():
            if key.startswith("outbound_"):
                metadata[key] = value
        return metadata

    @staticmethod
    def _strip_think(text: str | None) -> str | None:
        """Remove <think…</think > blocks that some models embed in content."""
        if not text:
            return None
        return re.sub(r"<think[\s\S]*?</think >", "", text).strip() or None

    @staticmethod
    def _extract_think(text: str | None) -> str | None:
        """Extract <think…</think > blocks from content."""
        if not text:
            return None
        matches = re.findall(r"<think[\s\S]*?</think >", text)
        if matches:
            # Remove the <think > tags and join multiple thinking blocks
            content = "\n\n".join(re.sub(r"</?think[^>]*>", "", m).strip() for m in matches)
            return content or None
        return None

    @staticmethod
    def _tool_hint(tool_calls: list) -> str:
        """Format tool calls as concise hint, e.g. 'web_search("query")'."""
        def _fmt(tc):
            val = next(iter(tc.arguments.values()), None) if tc.arguments else None
            if not isinstance(val, str):
                return tc.name
            return f'{tc.name}("{val[:40]}…")' if len(val) > 40 else f'{tc.name}("{val}")'
        return ", ".join(_fmt(tc) for tc in tool_calls)

    @staticmethod
    def _fallback_from_recent_tool_result(messages: list[dict[str, Any]]) -> str:
        """Use the most recent tool output as the final reply when the model returns nothing."""
        for message in reversed(messages):
            if message.get("role") != "tool":
                continue
            content = str(message.get("content") or "").strip()
            if not content:
                continue
            return content
        return ""

    def _should_skip_planning_for_message(self, msg: InboundMessage) -> bool:
        """Skip planning for file-heavy chat requests that should go direct."""
        has_file_ids = bool(msg.metadata and msg.metadata.get("file_ids"))
        has_files = bool(msg.metadata and msg.metadata.get("files"))
        has_embedded_document = "---\n**文档:" in (msg.content or "")
        conversation_ctx = msg.metadata.get("conversation_context") if msg.metadata else None
        conversation_type = ""
        trigger_message = ""
        if isinstance(conversation_ctx, dict):
            conversation_type = str(conversation_ctx.get("conversation_type") or "").strip()
            trigger_message = str(conversation_ctx.get("trigger_message") or "").strip()

        if conversation_type == "agent_to_agent":
            logger.info("Skipping planning for agent-to-agent relay turn")
            return True

        if (
            conversation_type == "user_to_agent"
            and bool(msg.metadata and msg.metadata.get("group_chat"))
            and "请基于当前团队对话历史" in trigger_message
        ):
            logger.info("Skipping planning for user-summary return turn")
            return True

        if has_file_ids or has_files or has_embedded_document:
            logger.info(
                "Skipping planning for file upload scenario: has_file_ids={}, has_files={}, has_embedded_document={}",
                has_file_ids,
                has_files,
                has_embedded_document,
            )
            return True

        return False

    def _resolve_planning_mode(self, msg: InboundMessage) -> tuple[bool, bool]:
        """Return (should_run_planning, force_legacy_mode)."""
        content = msg.content.strip() if msg.content else ""
        force_legacy = False

        if content.lower().startswith("/plan "):
            msg.content = content[6:].strip()
            force_legacy = True
            logger.info("User explicitly requested planning mode with /plan prefix")

        if self._should_skip_planning_for_message(msg):
            return False, force_legacy

        if force_legacy:
            return True, True

        if not self._planning_enabled:
            return False, False

        analysis = self._task_analyzer.analyze(msg.content, use_llm=False)
        logger.info(
            "Planning analysis: needs_planning={}, score={:.2f}, estimated_steps={}, plan_type={}, content='{}'",
            analysis.needs_planning,
            analysis.score,
            analysis.estimated_steps,
            analysis.plan_type,
            (msg.content or "")[:80],
        )

        should_run_planning = analysis.needs_planning and analysis.estimated_steps >= 3
        use_legacy_mode = should_run_planning and analysis.plan_type == "informational"
        return should_run_planning, use_legacy_mode

    async def _run_agent_loop(
        self,
        initial_messages: list[dict],
        on_progress: Callable[..., Awaitable[None]] | None = None,
        pending_confirmations: dict[str, dict[str, Any]] | None = None,
        on_tool_start: Callable[..., Awaitable[None]] | None = None,
        on_tool_result: Callable[..., Awaitable[None]] | None = None,
        on_status: Callable[..., Awaitable[None]] | None = None,
        on_thinking: Callable[..., Awaitable[None]] | None = None,
        on_step_start: Callable[..., Awaitable[None]] | None = None,
        on_step_complete: Callable[..., Awaitable[None]] | None = None,
        session_key: str | None = None,
        file_ids: list[str] | None = None,
        web_search: bool = False,
        files: list[dict] | None = None,
        tool_mode: str = "smart",
        max_tokens_override: int | None = None,
    ) -> tuple[str | None, list[str], list[dict], dict[str, dict[str, Any]], dict[str, Any] | None]:
        """Run the agent iteration loop. Returns (final_content, tools_used, messages, pending_confirmations, error_info).
        
        Args:
            web_search: When True, web_search tool is always available for the AI to use.
        """
        messages = initial_messages
        error_info: dict[str, Any] | None = None
        
        # DEBUG: Log the complete messages being sent to LLM
        logger.info(f"[_run_agent_loop] Agent {self._agent_name} (ID: {self._agent_id}) - Messages to LLM:")
        for i, msg in enumerate(messages):
            content_preview = msg.get('content', '')[:200] if msg.get('content') else 'None'
            logger.info(f"[_run_agent_loop] Message[{i}]: role={msg.get('role')}, content_preview={content_preview}...")
        
        iteration = 0
        final_content = None
        tools_used: list[str] = []
        confirmations = pending_confirmations or {}
        reset_count = 0
        max_resets = 3
        
        self.tools.set_web_search_enabled(web_search)
        
        user_message = None
        for msg in reversed(initial_messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break

        # Detect file types for model selection
        has_image = False
        has_audio = False
        has_video = False
        has_file = bool(file_ids)
        
        if files:
            for f in files:
                category = f.get("category", "")
                if category == "image":
                    has_image = True
                elif category == "audio":
                    has_audio = True
                elif category == "video":
                    has_video = True
        
        # Select model based on context
        selected_model = self._get_model_for_context(
            has_image=has_image,
            has_audio=has_audio,
            has_video=has_video,
            has_file=has_file,
            is_planning=False,
        )
        
        if selected_model != self.model:
            logger.info(
                "Model switched from {} to {} for context: image={}, audio={}, video={}, file={}",
                self.model, selected_model, has_image, has_audio, has_video, has_file
            )

        selected_max_tokens = max_tokens_override or self.max_tokens

        while True:
            iteration += 1
            
            if iteration > self.max_iterations:
                if reset_count < max_resets:
                    reset_count += 1
                    logger.warning("达到最大迭代次数 ({}), 自动重置 (重置次数: {}/{})", 
                                  self.max_iterations, reset_count, max_resets)
                    iteration = 1
                else:
                    logger.warning("已达到最大重置次数 ({}), 停止执行", max_resets)
                    break
            
            # Step 1: Thinking
            thinking_step_id = f"thinking_{iteration}"
            if on_step_start:
                logger.info(f"[_run_agent_loop] Calling on_step_start for thinking step: {thinking_step_id}")
                await on_step_start(thinking_step_id, "thinking", "思考中...")
            
            if on_status:
                await on_status("正在思考...")

            # Apply context compression if enabled
            config = self._get_config()
            compact_config = getattr(config.agents.defaults, 'context_compact', None)
            if compact_config and compact_config.enabled:
                compression_result = compact_context(
                    messages=messages,
                    max_tokens=compact_config.max_tokens,
                    preserve_recent=compact_config.preserve_recent,
                    compress_tool_results_flag=compact_config.compress_tool_results,
                    return_details=True,
                )
                if isinstance(compression_result, CompressionResult):
                    messages = compression_result.messages
                    if compression_result.was_compressed and on_step_start and on_step_complete:
                        compression_step_id = f"compression_{iteration}"
                        await on_step_start(compression_step_id, "compression", "上下文压缩中...")
                        await on_step_complete(compression_step_id, "completed", {
                            "original_tokens": compression_result.original_tokens,
                            "compressed_tokens": compression_result.compressed_tokens,
                            "reduction_percent": compression_result.reduction_percent,
                        })
                else:
                    messages = compression_result

            import time
            llm_start = time.time()
            tools = None
            if tool_mode != "none":
                tools = self.tools.get_definitions_smart(
                    user_message,
                    include_web_search=web_search,
                )
            response = await self.provider.chat(
                messages=messages,
                tools=tools,
                model=selected_model,
                temperature=self.temperature,
                max_tokens=selected_max_tokens,
                file_ids=file_ids,
                files=files,
                on_content_delta=on_progress,
            )
            llm_elapsed = time.time() - llm_start
            logger.info("LLM call took {:.2f}s (iteration {})", llm_elapsed, iteration)

            if response.usage:
                try:
                    tracker = get_token_tracker()
                    tracker.record(
                        provider=self.provider.__class__.__name__.replace("Provider", "").lower(),
                        model=selected_model or "unknown",
                        prompt_tokens=response.usage.get("prompt_tokens", 0),
                        completion_tokens=response.usage.get("completion_tokens", 0),
                        total_tokens=response.usage.get("total_tokens", 0),
                        session_id=session_key,
                    )
                    logger.debug("Recorded token usage: prompt={}, completion={}", 
                                 response.usage.get("prompt_tokens", 0),
                                 response.usage.get("completion_tokens", 0))
                except Exception as e:
                    logger.warning("Failed to record token usage: {}", e)
            else:
                logger.debug("No usage info in response")

            if response.has_tool_calls:
                # Check if any tool requires confirmation before sending progress
                requires_confirmation = False
                confirmation_tool = None
                for tc in response.tool_calls:
                    if self.tools.requires_confirmation(tc.name, tc.arguments):
                        requires_confirmation = True
                        confirmation_tool = tc
                        break
                
                # Complete thinking step with content (avoid duplicate on_thinking call)
                if on_step_complete:
                    thinking = response.reasoning_content or self._extract_think(response.content)
                    await on_step_complete(thinking_step_id, "completed", {
                        "thinking": thinking or ""
                    })
                
                # Only send progress if no confirmation required
                if on_progress and not requires_confirmation:
                    clean = self._strip_think(response.content)
                    if clean:
                        await on_progress(clean)
                    await on_progress(self._tool_hint(response.tool_calls), tool_hint=True)

                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False)
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                )

                result = await self._tool_executor.execute_tool_calls(
                    tool_calls=response.tool_calls,
                    messages=messages,
                    tools_used=tools_used,
                    iteration=iteration,
                    on_step_start=on_step_start,
                    on_tool_start=on_tool_start,
                    on_status=on_status,
                    on_tool_result=on_tool_result,
                    on_step_complete=on_step_complete,
                )
                messages = result.messages
                tools_used = result.tools_used
                if result.confirmations:
                    confirmations.update(result.confirmations)
                    final_content = result.final_content
                    return final_content, tools_used, messages, confirmations, error_info
                if result.should_break:
                    final_content = result.final_content
                    break
            else:
                # Complete thinking step
                # Complete thinking step with content (avoid duplicate on_thinking call)
                if on_step_complete:
                    thinking = response.reasoning_content or self._extract_think(response.content)
                    await on_step_complete(thinking_step_id, "success", {
                        "thinking": thinking or ""
                    })
                
                # Step 3: Generate Response
                response_step_id = f"response_{iteration}"
                if on_step_start:
                    await on_step_start(response_step_id, "response", "生成回复")
                
                clean = self._strip_think(response.content) or ""
                if not clean:
                    clean = self._fallback_from_recent_tool_result(messages)
                messages = self.context.add_assistant_message(
                    messages, clean, reasoning_content=response.reasoning_content,
                )
                final_content = clean
                error_info = response.error_info
                
                # Send progress update for the final response
                if on_progress and clean:
                    await on_progress(clean)
                
                # Complete response step
                if on_step_complete:
                    await on_step_complete(response_step_id, "success", {
                        "content": clean[:200] + "..." if len(clean) > 200 else clean
                    })
                
                break

        if final_content is None:
            total_iterations = self.max_iterations * max_resets + (iteration if reset_count >= max_resets else 0)
            logger.warning("Max iterations reached after {} resets", reset_count)
            final_content = (
                f"I reached the maximum number of tool call iterations ({self.max_iterations}) "
                f"after {max_resets} automatic resets without completing the task. "
                "You can try breaking the task into smaller steps."
            )

        return final_content, tools_used, messages, confirmations, error_info

    async def run(self) -> None:
        """Run the agent loop, dispatching messages as tasks to stay responsive to /stop."""
        self._running = True
        await self._connect_mcp()
        
        if self.enable_hot_reload:
            await self._start_config_watcher()
        
        logger.info("Agent loop started")

        while self._running:
            try:
                msg = await asyncio.wait_for(self.bus.consume_inbound(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            if msg.content.strip().lower() == "/stop":
                await self._handle_stop(msg)
            else:
                task = asyncio.create_task(self._dispatch(msg))
                self._active_tasks.setdefault(msg.session_key, []).append(task)
                task.add_done_callback(lambda t, k=msg.session_key: self._active_tasks.get(k, []) and self._active_tasks[k].remove(t) if t in self._active_tasks.get(k, []) else None)

    async def _handle_stop(self, msg: InboundMessage) -> None:
        """Cancel all active tasks and subagents for the session."""
        tasks = self._active_tasks.pop(msg.session_key, [])
        cancelled = sum(1 for t in tasks if not t.done() and t.cancel())
        for t in tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        sub_cancelled = await self.subagents.cancel_by_session(msg.session_key)
        total = cancelled + sub_cancelled
        content = f"⏹ Stopped {total} task(s)." if total else "No active task to stop."
        await self.bus.publish_outbound(OutboundMessage(
            channel=msg.channel, chat_id=msg.chat_id, content=content,
        ))

    async def _dispatch(self, msg: InboundMessage) -> None:
        """Process a message under the global lock."""
        await self._message_processor.dispatch(msg)

    async def process_message(
        self,
        msg: InboundMessage,
        session_key: str | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
        on_tool_start: Callable[..., Awaitable[None]] | None = None,
        on_tool_result: Callable[..., Awaitable[None]] | None = None,
        on_status: Callable[..., Awaitable[None]] | None = None,
        on_thinking: Callable[..., Awaitable[None]] | None = None,
        on_step_start: Callable[..., Awaitable[None]] | None = None,
        on_step_complete: Callable[..., Awaitable[None]] | None = None,
        on_plan_created: Callable[..., Awaitable[None]] | None = None,
        on_plan_generating: Callable[..., Awaitable[None]] | None = None,
        on_plan_skipped: Callable[..., Awaitable[None]] | None = None,
        on_plan_progress: Callable[[str, str, str | None], Awaitable[None]] | None = None,
        speaking_to: str | None = None,
        conversation_type: str | None = None,
    ) -> OutboundMessage | None:
        """Public message-processing entrypoint used by Web/CLI integrations."""
        resolved_session_key = session_key or msg.session_key
        lock = self._get_message_lock(resolved_session_key)
        async with lock:
            try:
                return await self._message_processor.process_message(
                    msg,
                    session_key=resolved_session_key,
                    on_progress=on_progress,
                    on_tool_start=on_tool_start,
                    on_tool_result=on_tool_result,
                    on_status=on_status,
                    on_thinking=on_thinking,
                    on_step_start=on_step_start,
                    on_step_complete=on_step_complete,
                    on_plan_created=on_plan_created,
                    on_plan_generating=on_plan_generating,
                    on_plan_skipped=on_plan_skipped,
                    on_plan_progress=on_plan_progress,
                    speaking_to=speaking_to,
                    conversation_type=conversation_type,
                )
            finally:
                self._prune_message_lock(resolved_session_key, lock)

    async def close_mcp(self) -> None:
        """Close MCP connections and reset state."""
        if self._mcp_stack:
            try:
                await self._mcp_stack.aclose()
            except (RuntimeError, BaseExceptionGroup):
                pass  # MCP SDK cancel scope cleanup is noisy but harmless
            self._mcp_stack = None
        self._mcp_connected = False
        self._mcp_connecting = False
    
    async def cleanup(self) -> None:
        """Cleanup resources before shutdown."""
        logger.info("Cleaning up AgentLoop resources...")

        for task in list(self._skill_review_tasks):
            task.cancel()
        self._skill_review_tasks.clear()
        
        if self.enable_hot_reload:
            await self._stop_config_watcher()
        
        await self.close_mcp()
        
        logger.info("AgentLoop cleanup completed")

    async def reload_mcp(self, new_servers: dict) -> None:
        """
        Hot-reload MCP servers.
        
        Args:
            new_servers: New MCP server configuration dict
        """
        logger.info("Reloading MCP servers...")
        
        await self.close_mcp()
        
        self._mcp_servers = new_servers or {}
        self._mcp_connected = False
        self._mcp_connecting = False
        
        if self._mcp_servers:
            await self._connect_mcp()
            logger.info("MCP servers reloaded successfully")
        else:
            logger.info("MCP servers cleared")

    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")
    
    async def _start_config_watcher(self) -> None:
        """Start the configuration file watcher."""
        from horbot.config.watcher import ConfigWatcher
        
        if not hasattr(self, '_config_watcher'):
            self._config_watcher = ConfigWatcher()
        
        await self._config_watcher.start()
        logger.info("Config watcher started")
    
    async def _stop_config_watcher(self) -> None:
        """Stop the configuration file watcher."""
        if hasattr(self, '_config_watcher') and self._config_watcher:
            await self._config_watcher.stop()
            logger.info("Config watcher stopped")

    def _get_consolidation_lock(self, session_key: str) -> asyncio.Lock:
        lock = self._consolidation_locks.get(session_key)
        if lock is None:
            lock = asyncio.Lock()
            self._consolidation_locks[session_key] = lock
        return lock

    def _prune_consolidation_lock(self, session_key: str, lock: asyncio.Lock) -> None:
        """Drop lock entry if no longer in use."""
        if not lock.locked():
            self._consolidation_locks.pop(session_key, None)

    def _get_message_lock(self, session_key: str) -> asyncio.Lock:
        lock = self._message_locks.get(session_key)
        if lock is None:
            lock = asyncio.Lock()
            self._message_locks[session_key] = lock
        return lock

    def _prune_message_lock(self, session_key: str, lock: asyncio.Lock) -> None:
        if not lock.locked():
            self._message_locks.pop(session_key, None)

    async def _process_message(
        self,
        msg: InboundMessage,
        session_key: str | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
        on_tool_start: Callable[..., Awaitable[None]] | None = None,
        on_tool_result: Callable[..., Awaitable[None]] | None = None,
        on_status: Callable[..., Awaitable[None]] | None = None,
        on_thinking: Callable[..., Awaitable[None]] | None = None,
        on_step_start: Callable[..., Awaitable[None]] | None = None,
        on_step_complete: Callable[..., Awaitable[None]] | None = None,
        on_plan_created: Callable[..., Awaitable[None]] | None = None,
        on_plan_generating: Callable[..., Awaitable[None]] | None = None,
        on_plan_skipped: Callable[..., Awaitable[None]] | None = None,
        on_plan_progress: Callable[[str, str, str | None], Awaitable[None]] | None = None,
        speaking_to: str | None = None,
        conversation_type: str | None = None,
    ) -> OutboundMessage | None:
        """Process a single inbound message and return the response.
        
        Args:
            msg: The inbound message to process
            session_key: Optional session key override
            on_progress: Progress callback
            on_tool_start: Tool start callback
            on_tool_result: Tool result callback
            on_status: Status callback
            on_thinking: Thinking callback
            on_step_start: Step start callback
            on_step_complete: Step complete callback
            on_plan_created: Plan created callback
            on_plan_generating: Plan generating callback
            on_plan_skipped: Plan skipped callback
            on_plan_progress: Plan progress callback
            speaking_to: Who the agent is speaking to (e.g., "用户", "小项 🐎")
            conversation_type: Type of conversation ("user_to_agent" or "agent_to_agent")
        """
        # System messages: parse origin from chat_id ("channel:chat_id")
        if msg.channel == "system":
            channel, chat_id = (
                parse_session_key_with_known_routes(msg.chat_id)
                if ":" in msg.chat_id
                else ("cli", msg.chat_id)
            )
            logger.info("Processing system message from {}", msg.sender_id)
            key = f"{channel}:{chat_id}"
            session = self.sessions.get_or_create(key)
            self._set_tool_context(channel, chat_id, msg.metadata.get("message_id") if msg.metadata else None)
            history = session.get_history(max_messages=self.memory_window)
            messages = self.context.build_messages(
                history=history,
                current_message=msg.content, channel=channel, chat_id=chat_id,
                session_key=key,
            )
            final_content, _, all_msgs, _, _ = await self._run_agent_loop(messages, session_key=key)
            self._save_turn(session, all_msgs, 1 + len(history))
            self.sessions.save(session)
            return OutboundMessage(channel=channel, chat_id=chat_id,
                                  content=final_content or "Background task completed.")

        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        logger.info("Processing message from {}:{}: {}", msg.channel, msg.sender_id, preview)

        key = session_key or msg.session_key
        session = self.sessions.get_or_create(key)
        
        # Clear previous planning context when starting a new task
        # This ensures new tasks don't get polluted by previous task's context
        if key in self._active_plans:
            logger.info("Clearing previous planning context for session: {}", key)
            self._active_plans.pop(key, None)

        # Smart detection of new task - auto clear context if user starts a new task
        if self._is_new_task(msg.content, session):
            logger.info("Detected new task, clearing session context for: {}", key)
            session.clear()
            self.sessions.save(session)
            if self.use_hierarchical_context:
                self.context.clear_session_context(key)

        # Slash commands
        cmd = msg.content.strip().lower()
        if cmd == "/new":
            lock = self._get_consolidation_lock(session.key)
            self._consolidating.add(session.key)
            try:
                async with lock:
                    snapshot = session.messages[session.last_consolidated:]
                    if snapshot:
                        temp = Session(key=session.key)
                        temp.messages = list(snapshot)
                        if not await self._consolidate_memory(temp, archive_all=True):
                            return OutboundMessage(
                                channel=msg.channel, chat_id=msg.chat_id,
                                content="Memory archival failed, session not cleared. Please try again.",
                            )
            except Exception:
                logger.exception("/new archival failed for {}", session.key)
                return OutboundMessage(
                    channel=msg.channel, chat_id=msg.chat_id,
                    content="Memory archival failed, session not cleared. Please try again.",
                )
            finally:
                self._consolidating.discard(session.key)
                self._prune_consolidation_lock(session.key, lock)

            session.clear()
            self.sessions.save(session)
            self.sessions.invalidate(session.key)
            
            if self.use_hierarchical_context:
                self.context.clear_session_context(session.key)
            
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                  content="New session started.")
        if cmd == "/help":
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                  content="🐈 horbot commands:\n/new — Start a new conversation\n/stop — Stop the current task\n/plan — Toggle planning mode for complex tasks\n/help — Show available commands")
        
        # Planning mode toggle
        if cmd == "/plan":
            self._planning_enabled = not self._planning_enabled
            status = "enabled" if self._planning_enabled else "disabled"
            return OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id,
                content=f"📋 Planning mode {status}."
            )
        
        # Check for plan confirmation
        if cmd in ("yes", "ok", "confirm") and session.key in self._active_plans:
            plan = self._active_plans.pop(session.key)
            return await self._execute_plan(plan, msg, session)
        
        if cmd in ("no", "cancel") and session.key in self._active_plans:
            self._active_plans.pop(session.key)
            return OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id,
                content="📋 Plan cancelled."
            )

        # Check for tool confirmation
        pending_confirmations = getattr(session, '_pending_confirmations', {})
        confirmation_match = re.match(r'^(yes|no)\s+([a-f0-9]{8})$', cmd)
        if confirmation_match and pending_confirmations:
            action, confirm_id = confirmation_match.groups()
            if confirm_id in pending_confirmations:
                conf = pending_confirmations.pop(confirm_id)
                if action == "yes":
                    tool_name = conf["tool_name"]
                    arguments = conf["arguments"]
                    tool_call_id = conf["tool_call_id"]
                    messages = conf["messages"]
                    
                    logger.info("Tool {} confirmed by user: {}", tool_name, confirm_id)
                    result = await self.tools.execute(tool_name, arguments)
                    messages = self.context.add_tool_result(
                        messages, tool_call_id, tool_name, result
                    )
                    
                    final_content, _, all_msgs, _, error_info = await self._run_agent_loop(
                        messages, on_progress=on_progress or _bus_progress,
                        pending_confirmations=pending_confirmations,
                        session_key=session.key,
                    )
                    
                    if final_content is None:
                        final_content = "I've completed processing but have no response to give."
                    
                    session._pending_confirmations = pending_confirmations
                    self._save_turn(session, all_msgs, 1 + len(history))
                    self.sessions.save(session)
                    
                    return OutboundMessage(
                        channel=msg.channel, chat_id=msg.chat_id, content=final_content,
                        metadata={
                            **(msg.metadata or {}),
                            **({"_provider_error": error_info} if error_info else {}),
                        },
                    )
                else:
                    logger.info("Tool {} cancelled by user: {}", conf["tool_name"], confirm_id)
                    pending_confirmations.pop(confirm_id, None)
                    session._pending_confirmations = pending_confirmations
                    self.sessions.save(session)
                    return OutboundMessage(
                        channel=msg.channel, chat_id=msg.chat_id,
                        content=f"❌ Tool `{conf['tool_name']}` execution cancelled."
                    )

        unconsolidated = len(session.messages) - session.last_consolidated
        if (unconsolidated >= self.memory_window and session.key not in self._consolidating):
            self._consolidating.add(session.key)
            lock = self._get_consolidation_lock(session.key)

            async def _consolidate_and_unlock():
                try:
                    async with lock:
                        await self._consolidate_memory(session)
                finally:
                    self._consolidating.discard(session.key)
                    self._prune_consolidation_lock(session.key, lock)
                    _task = asyncio.current_task()
                    if _task is not None:
                        self._consolidation_tasks.discard(_task)

            _task = asyncio.create_task(_consolidate_and_unlock())
            self._consolidation_tasks.add(_task)

        should_run_planning, force_legacy_planning = self._resolve_planning_mode(msg)

        if should_run_planning:
            logger.info(
                "Planning mode triggered for message: legacy_mode={}, content='{}'",
                force_legacy_planning,
                (msg.content or "")[:80],
            )
            plan_result = await self._run_planning_mode(
                msg, session, 
                on_plan_created=on_plan_created,
                on_plan_generating=on_plan_generating,
                on_plan_progress=on_plan_progress,
                on_progress=on_progress,
                on_thinking=on_thinking,
                on_step_start=on_step_start,
                on_step_complete=on_step_complete,
                force_legacy=force_legacy_planning,
            )
            # If plan was generated, return early and wait for user confirmation
            if plan_result is None and session.key in self._active_plans:
                # Plan was generated successfully, stop here and wait for confirmation
                return None
            if plan_result is not None:
                return plan_result
            # If plan generation failed (returned None but no active plan), 
            # return an error message instead of continuing with normal execution
            logger.warning("Plan generation failed for task: {}", msg.content[:50])
            return OutboundMessage(
                channel=msg.channel, 
                chat_id=msg.chat_id,
                content="❌ 计划生成失败。请重试或简化您的请求。"
            )
        else:
            # Notify frontend that planning was skipped
            if on_plan_skipped:
                await on_plan_skipped()

        self._set_tool_context(
            msg.channel,
            msg.chat_id,
            msg.metadata.get("message_id") if msg.metadata else None,
            channel_instance_id=msg.channel_instance_id,
            target_agent_id=msg.target_agent_id,
        )
        if message_tool := self.tools.get("message"):
            if isinstance(message_tool, MessageTool):
                message_tool.start_turn()

        raw_history = session.get_history(max_messages=self.memory_window)
        
        conversation_ctx = None
        if msg.metadata and "conversation_context" in msg.metadata:
            from horbot.agent.conversation import ConversationContext
            try:
                conversation_ctx = ConversationContext.from_dict(msg.metadata["conversation_context"])
            except Exception as e:
                logger.warning(f"Failed to parse conversation_context: {e}")
        
        from horbot.agent.conversation import format_history_for_agent, ConversationType
        
        is_group_chat = (
            conversation_type == "group_chat"
            or (bool(msg.metadata.get("group_chat")) if msg.metadata else False)
            or (conversation_ctx and conversation_ctx.conversation_type == ConversationType.AGENT_TO_AGENT)
        )
        
        history = format_history_for_agent(
            raw_history,
            target_agent_id=self._agent_id,
            target_agent_name=self._agent_name or "horbot",
            conversation_ctx=conversation_ctx,
            is_group_chat=is_group_chat,
        )
        
        logger.info(f"[DEBUG] Agent {self._agent_name} processing message. Raw history: {len(raw_history)}, Filtered history: {len(history)}, speaking_to={speaking_to}, conversation_type={conversation_type}")
        for i, h in enumerate(history[-5:]):
            if h.get("role") == "assistant":
                logger.info(f"[DEBUG] History[{i}]: role={h['role']}, content_preview={h.get('content', '')[:100]}...")
        
        initial_messages = self.context.build_messages(
            history=history,
            current_message=msg.content,
            media=msg.media if msg.media else None,
            files=msg.metadata.get("files") if msg.metadata else None,
            channel=msg.channel, chat_id=msg.chat_id,
            session_key=session.key,
            speaking_to=speaking_to,
            conversation_type=conversation_type,
            runtime_hints=self._build_bound_channel_runtime_hints(msg),
        )
        memory_sources = self.context.get_last_memory_trace()
        memory_recall = self.context.memory.get_last_recall_metrics()

        async def _bus_progress(content: str, *, tool_hint: bool = False) -> None:
            meta = dict(msg.metadata or {})
            meta["_progress"] = True
            meta["_tool_hint"] = tool_hint
            await self.bus.publish_outbound(OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id, content=content, metadata=meta,
            ))

        final_content, _, all_msgs, confirmations, error_info = await self._run_agent_loop(
            initial_messages, 
            on_progress=on_progress or _bus_progress,
            on_tool_start=on_tool_start,
            on_tool_result=on_tool_result,
            on_status=on_status,
            on_thinking=on_thinking,
            on_step_start=on_step_start,
            on_step_complete=on_step_complete,
            session_key=session.key,
            file_ids=msg.metadata.get("file_ids") if msg.metadata else None,
            web_search=msg.metadata.get("web_search", False) if msg.metadata else False,
            files=msg.metadata.get("files") if msg.metadata else None,
        )
        
        if confirmations:
            session._pending_confirmations = confirmations
            self.sessions.save(session)
            
            # Return confirmation message with metadata for UI buttons
            confirm_id = list(confirmations.keys())[0]
            conf = confirmations[confirm_id]
            return OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id, content=final_content or "",
                metadata={
                    **(msg.metadata or {}),
                    "_confirmation_required": True,
                    "confirmation_id": confirm_id,
                    "tool_name": conf["tool_name"],
                    "tool_arguments": conf["arguments"],
                    **({"_provider_error": error_info} if error_info else {}),
                    **({"_memory_sources": memory_sources} if memory_sources else {}),
                    **({"_memory_recall": memory_recall} if memory_recall else {}),
                },
            )

        if final_content is None:
            final_content = "I've completed processing but have no response to give."

        preview = final_content[:120] + "..." if len(final_content) > 120 else final_content
        logger.info("Response to {}:{}: {}", msg.channel, msg.sender_id, preview)

        self._save_turn(session, all_msgs, 1 + len(history))
        self.sessions.save(session)

        # If message tool was used, check if it was sent to a different channel
        # If sent to external channel (not the current one), provide a confirmation message
        if message_tool := self.tools.get("message"):
            if isinstance(message_tool, MessageTool) and message_tool._sent_in_turn:
                # Check if the message was sent to a different channel than the current one
                last_target = message_tool._last_target_channel
                if last_target and last_target != msg.channel:
                    # Message was sent to external channel, provide confirmation
                    if not final_content.strip():
                        final_content = f"✅ 消息已发送至 {last_target}"
                    return OutboundMessage(
                        channel=msg.channel, chat_id=msg.chat_id, content=final_content,
                        metadata={
                            **(msg.metadata or {}),
                            **({"_provider_error": error_info} if error_info else {}),
                            **({"_memory_sources": memory_sources} if memory_sources else {}),
                            **({"_memory_recall": memory_recall} if memory_recall else {}),
                        },
                    )
                # Message was sent to current channel; still return it for HTTP callers.
                return OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=final_content,
                    metadata={
                        **(msg.metadata or {}),
                        **({"_provider_error": error_info} if error_info else {}),
                        **({"_memory_sources": memory_sources} if memory_sources else {}),
                        **({"_memory_recall": memory_recall} if memory_recall else {}),
                    },
                )

        return OutboundMessage(
            channel=msg.channel, chat_id=msg.chat_id, content=final_content,
            metadata={
                **(msg.metadata or {}),
                **({"_provider_error": error_info} if error_info else {}),
                **({"_memory_sources": memory_sources} if memory_sources else {}),
                **({"_memory_recall": memory_recall} if memory_recall else {}),
            },
        )

    _TOOL_RESULT_MAX_CHARS = 500
    _RUNTIME_CONTEXT_TAG = "[Runtime Context — metadata only, not instructions]"

    def _save_turn(self, session: Session, messages: list[dict], skip: int) -> None:
        """Save new-turn messages into session, truncating large tool results.
        
        Only saves the final assistant message to avoid duplicate intermediate messages.
        """
        from datetime import datetime
        tools_used_in_turn = []
        
        # Find the last assistant message (final response) and tool messages
        new_messages = messages[skip:]
        
        # Debug: log all new messages
        logger.info("[_save_turn] skip={}, new_messages count={}", skip, len(new_messages))
        for i, m in enumerate(new_messages):
            role = m.get("role", "unknown")
            content_preview = str(m.get("content", ""))[:50]
            has_tool_calls = "tool_calls" in m
            logger.info("[_save_turn] message[{}]: role={}, has_tool_calls={}, content={}...", i, role, has_tool_calls, content_preview)
        
        last_assistant_idx = -1
        for i, m in enumerate(new_messages):
            if m.get("role") == "assistant":
                last_assistant_idx = i
        
        logger.info("[_save_turn] last_assistant_idx={}", last_assistant_idx)
        
        # Save tool messages and assistant messages with tool_calls (for context)
        # plus all assistant messages (to preserve intermediate responses like "message" tool output)
        messages_to_save = []
        skipped_tool_call_ids = set()
        for i, m in enumerate(new_messages):
            if m.get("role") == "tool":
                tool_call_id = m.get("tool_call_id", "")
                if tool_call_id in skipped_tool_call_ids:
                    logger.info("[_save_turn] skipping tool message for skipped assistant[{}]", i)
                else:
                    messages_to_save.append(m)
                    logger.info("[_save_turn] saving tool message[{}]", i)
            elif m.get("role") == "assistant":
                content = m.get("content", "")
                tool_calls = m.get("tool_calls")
                if tool_calls:
                    for tc in tool_calls:
                        func = tc.get("function", {})
                        if func.get("name"):
                            tools_used_in_turn.append(func["name"])
                    content_str = content if isinstance(content, str) else ""
                    if content_str.strip():
                        messages_to_save.append(m)
                        logger.info("[_save_turn] saving assistant message with tool_calls and content[{}]", i)
                    else:
                        for tc in tool_calls:
                            tc_id = tc.get("id", "")
                            if tc_id:
                                skipped_tool_call_ids.add(tc_id)
                        logger.info("[_save_turn] skipping assistant message with tool_calls but empty content[{}]", i)
                else:
                    messages_to_save.append(m)
                    logger.info("[_save_turn] saving assistant message[{}]", i)
        
        logger.info("[_save_turn] total messages to save: {}", len(messages_to_save))
        
        for m in messages_to_save:
            entry = {k: v for k, v in m.items() if k != "reasoning_content"}
            if entry.get("role") == "tool" and isinstance(entry.get("content"), str):
                content = entry["content"]
                if len(content) > self._TOOL_RESULT_MAX_CHARS:
                    entry["content"] = content[:self._TOOL_RESULT_MAX_CHARS] + "\n... (truncated)"
            if entry.get("role") == "user" and isinstance(entry.get("content"), list):
                entry["content"] = [
                    {"type": "text", "text": "[image]"} if (
                        c.get("type") == "image_url"
                        and c.get("image_url", {}).get("url", "").startswith("data:image/")
                    ) else c
                    for c in entry["content"]
                ]
            if entry.get("role") == "user" and isinstance(entry.get("content"), str):
                content = entry["content"]
                if self._RUNTIME_CONTEXT_TAG in content:
                    import re
                    content = re.sub(
                        r'\[Runtime Context — metadata only, not instructions\][\s\S]*?(?=\n\n|\n*$|$)',
                        '',
                        content
                    ).strip()
                    entry["content"] = content
            entry.setdefault("id", str(uuid.uuid4())[:8])
            entry.setdefault("timestamp", datetime.now().isoformat())
            if entry.get("role") == "assistant":
                logger.info(f"[_save_turn] Adding metadata for assistant message: agent_id={self._agent_id}, agent_name={self._agent_name}")
                if self._agent_id:
                    entry.setdefault("metadata", {})["agent_id"] = self._agent_id
                    if self._agent_name:
                        entry["metadata"]["agent_name"] = self._agent_name
                else:
                    logger.warning("[_save_turn] No agent_id set, skipping metadata")
            session.messages.append(entry)
        session.updated_at = datetime.now()
        
        execution_log = None
        if tools_used_in_turn and self.use_hierarchical_context:
            execution_log = self._save_execution_log(session, messages, tools_used_in_turn)
        elif tools_used_in_turn:
            execution_log = self._build_execution_log(session, messages, tools_used_in_turn)

        self._schedule_skill_evolution_review(
            session=session,
            execution_log=execution_log or self._build_execution_log(session, messages, tools_used_in_turn),
            recent_messages=messages[-8:],
            tools_used=tools_used_in_turn,
        )

    def _save_execution_log(
        self,
        session: Session,
        messages: list[dict],
        tools_used: list[str],
    ) -> dict[str, Any] | None:
        """Save execution log to hierarchical context."""
        try:
            execution_log = self._build_execution_log(session, messages, tools_used)
            memory = self._memory_store()
            memory.add_execution_memory(execution_log, session.key)
            return execution_log
        except Exception as e:
            logger.warning("Failed to save execution log: {}", e)
            return None

    def _build_execution_log(
        self,
        session: Session,
        messages: list[dict],
        tools_used: list[str],
    ) -> dict[str, Any]:
        user_message = None
        assistant_response = None

        for m in reversed(messages):
            if m.get("role") == "user" and not user_message:
                content = m.get("content", "")
                if isinstance(content, str):
                    user_message = content[:500]
            elif m.get("role") == "assistant" and not assistant_response:
                assistant_response = m.get("content", "")[:500] if m.get("content") else None

        return {
            "task": user_message,
            "result": assistant_response,
            "tools_used": list(set(tools_used)),
            "timestamp": datetime.now().isoformat(),
            "message_count": len(messages),
            **self._build_execution_source_metadata(session.key),
            **self._build_execution_outbound_metadata(),
        }

    def _skill_evolution_settings(self) -> dict[str, Any]:
        config = self._get_config()
        if not config or not self._agent_id:
            return {}
        agent_config = getattr(getattr(config, "agents", None), "instances", {}).get(self._agent_id)
        if agent_config is None:
            return {}
        return dict(getattr(agent_config, "skill_evolution", {}) or {})

    def _skill_learning_enabled(self) -> bool:
        config = self._get_config()
        if not config or not self._agent_id:
            return True
        agent_config = getattr(getattr(config, "agents", None), "instances", {}).get(self._agent_id)
        if agent_config is None:
            return True
        if not getattr(agent_config, "learning_enabled", True):
            return False
        settings = dict(getattr(agent_config, "skill_evolution", {}) or {})
        return bool(settings.get("enabled", True))

    def _schedule_skill_evolution_review(
        self,
        *,
        session: Session,
        execution_log: dict[str, Any] | None,
        recent_messages: list[dict[str, Any]],
        tools_used: list[str],
    ) -> None:
        if not self._skill_learning_enabled():
            return
        if execution_log is None:
            return

        settings = self._skill_evolution_settings()
        if not tools_used and not settings.get("review_without_tools", False):
            return

        min_result_chars = int(settings.get("min_result_chars", 80) or 80)
        result_text = str(execution_log.get("result") or "").strip()
        if len(result_text) < min_result_chars:
            return

        async def _run_review() -> None:
            try:
                engine = SkillEvolutionEngine(
                    workspace=self.workspace,
                    provider=self.provider,
                    model=self.model,
                    agent_id=self._agent_id,
                    memory_store=self._memory_store(),
                )
                await engine.review_execution(
                    execution_log,
                    recent_messages=recent_messages,
                    trigger=f"session:{session.key}",
                )
            except Exception:
                logger.exception("Skill evolution review failed for session {}", session.key)
            finally:
                task = asyncio.current_task()
                if task is not None:
                    self._skill_review_tasks.discard(task)

        task = asyncio.create_task(_run_review())
        self._skill_review_tasks.add(task)

    async def _consolidate_memory(self, session, archive_all: bool = False) -> bool:
        """Delegate to MemoryStore.consolidate(). Returns True on success."""
        return await self._memory_store().consolidate(
            session, self.provider, self.model,
            archive_all=archive_all, memory_window=self.memory_window,
        )

    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        """Process a message directly (for CLI or cron usage)."""
        await self._connect_mcp()
        msg = InboundMessage(channel=channel, sender_id="user", chat_id=chat_id, content=content)
        response = await self.process_message(msg, session_key=session_key, on_progress=on_progress)
        return response.content if response else ""

    async def _run_unified_planning_mode(
        self,
        msg: InboundMessage,
        session: Session,
        on_plan_created: Callable[..., Awaitable[None]] | None = None,
        on_plan_generating: Callable[..., Awaitable[None]] | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
        on_thinking: Callable[..., Awaitable[None]] | None = None,
    ) -> OutboundMessage | None:
        """Run unified planning mode - single prompt, model decides everything.
        
        Based on learn-claude-code theory:
        - Agent IS the Model
        - Agency is learned, not programmed
        - Single prompt, not prompt chains
        """
        from horbot.agent.planner.unified_generator import (
            UnifiedPlanGenerator,
            get_default_tools,
        )
        from horbot.agent.planner import get_plan_storage, ExecutionPlan, SubTask
        
        if on_plan_generating:
            await on_plan_generating()
        
        tools = get_default_tools()
        
        config = self._get_config()
        if config and hasattr(config, 'agents') and hasattr(config.agents, 'defaults'):
            planning_model = config.agents.defaults.planning_model
            planning_provider = config.agents.defaults.planning_provider
        else:
            planning_model = None
            planning_provider = None
        
        logger.info(f"Unified planning: model={planning_model}, provider={planning_provider}")
        
        generator = UnifiedPlanGenerator(
            provider=self.provider,
            model=planning_model,
            tools=tools,
        )
        
        try:
            plan = await generator.generate(task=msg.content)
        except Exception as e:
            logger.error(f"Unified planning failed: {e}")
            import traceback
            traceback.print_exc()
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=f"规划生成失败: {str(e)}",
            )
        
        if plan is None:
            logger.info("Model decided no plan is needed for: {}", msg.content[:50])
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="模型判断此任务不需要规划。请直接描述您的需求，我会帮您完成。",
            )
        
        self._active_plans[session.key] = plan
        
        storage = get_plan_storage()
        execution_plan = ExecutionPlan(
            id=plan.id,
            title=plan.title,
            description=plan.description or "",
            subtasks=[
                SubTask(
                    id=step.id,
                    title=step.description[:100] if step.description else f"步骤 {i+1}",
                    description=step.description,
                    status="pending",
                    tools=[step.tool_name] if step.tool_name else [],
                )
                for i, step in enumerate(plan.steps)
            ],
            status="pending",
        )
        storage.save_plan(execution_plan)
        
        if on_plan_created:
            plan_dict = {
                "id": execution_plan.id,
                "title": execution_plan.title,
                "description": execution_plan.description,
                "status": execution_plan.status,
                "subtasks": [
                    {
                        "id": st.id,
                        "title": st.title,
                        "description": st.description,
                        "status": st.status,
                        "tools": st.tools,
                    }
                    for st in execution_plan.subtasks
                ],
            }
            await on_plan_created(plan_dict)
        
        plan_display = f"## 📋 {plan.title}\n\n"
        plan_display += f"**任务理解**: {plan.description}\n\n"
        plan_display += "### 执行步骤\n\n"
        for i, step in enumerate(plan.steps, 1):
            deps = f" (依赖: {', '.join(step.dependencies)})" if step.dependencies else ""
            plan_display += f"{i}. {step.description}{deps}\n"
        
        validation = plan.metadata.get("validation", [])
        if validation:
            plan_display += "\n### 验收标准\n\n"
            for v in validation:
                plan_display += f"- {v}\n"
        
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=plan_display,
            metadata={
                "plan_id": plan.id,
                "plan_status": "pending_confirmation",
            },
        )

    async def _run_planning_mode(
        self,
        msg: InboundMessage,
        session: Session,
        on_plan_created: Callable[..., Awaitable[None]] | None = None,
        on_plan_generating: Callable[..., Awaitable[None]] | None = None,
        on_plan_progress: Callable[[str, str, str | None], Awaitable[None]] | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
        on_thinking: Callable[..., Awaitable[None]] | None = None,
        on_step_start: Callable[..., Awaitable[None]] | None = None,
        on_step_complete: Callable[..., Awaitable[None]] | None = None,
        force_legacy: bool = False,
    ) -> OutboundMessage | None:
        """Run in planning mode for complex tasks.
        
        Supports two modes:
        - unified: Single prompt, model decides everything (default)
        - legacy: Three-stage prompt chain (spec -> tasks -> checklist)
        
        Args:
            force_legacy: If True, always use legacy mode (for /plan command)
        """
        from horbot.agent.planner import get_plan_storage, ExecutionPlan, SubTask
        
        config = self._get_config()
        planning_mode = 'legacy' if force_legacy else getattr(config, 'planning_mode', 'unified') if config else 'unified'
        
        if planning_mode == 'unified':
            return await self._run_unified_planning_mode(
                msg, session,
                on_plan_created=on_plan_created,
                on_plan_generating=on_plan_generating,
                on_progress=on_progress,
                on_thinking=on_thinking,
            )
        
        # Legacy mode below
        if on_plan_generating:
            await on_plan_generating()
        
        analysis = self._task_analyzer.analyze(msg.content)

        # For informational plans, use direct chat mode instead of execution plan
        if analysis.plan_type == "informational":
            logger.info("Informational plan detected, using direct chat mode")
            # Use a specialized prompt for informational planning
            informational_prompt = f"""请为以下请求提供详细的规划建议：

{msg.content}

请直接给出你的建议和规划，包括：
1. 整体思路
2. 具体步骤或建议
3. 注意事项

请用清晰、有条理的方式回复。"""
            
            # Create messages in the expected format for _run_agent_loop
            messages = [
                {"role": "user", "content": informational_prompt}
            ]
            
            # Run in direct mode to get the response
            result = await self._run_agent_loop(
                messages,
                on_progress=on_progress,
                on_thinking=on_thinking,
                on_step_start=on_step_start,
                on_step_complete=on_step_complete,
                session_key=session.key,
            )
            
            # Create outbound message with the result
            final_content, tools_used, _, _, _ = result
            if final_content:
                return OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=final_content,
                )
            return None

        generation = await self._plan_generator.generate(
            task=msg.content,
            available_tools=self.tools.tool_names,
            session_id=session.key,
            on_progress=on_plan_progress,
            available_skills=self._get_available_skills(),
            available_mcp_tools=self._get_available_mcp_tools(),
        )

        logger.info("Plan generation result - success: {}, error: {}", generation.success, generation.error)
        logger.info("Plan generation result - spec_content length: {}", len(generation.spec_content) if generation.spec_content else 0)
        logger.info("Plan generation result - tasks_content length: {}", len(generation.tasks_content) if generation.tasks_content else 0)
        logger.info("Plan generation result - checklist_content length: {}", len(generation.checklist_content) if generation.checklist_content else 0)

        if not generation.success or not generation.plan:
            logger.warning("Plan generation failed: success={}, plan={}", generation.success, generation.plan)
            return None

        plan = generation.plan
        self._active_plans[session.key] = plan

        # Store plan content for informational plans
        plan_content = ""
        if analysis.plan_type == "informational":
            # For informational plans, store the AI's raw response as content
            # This contains the actual advice/suggestions from the AI
            plan_content = generation.raw_response or generation.spec_content or ""

        storage = get_plan_storage()
        execution_plan = ExecutionPlan(
            id=plan.id,
            title=plan.title,
            description=plan.description or "",
            subtasks=[
                SubTask(
                    id=step.id,
                    title=step.description[:100] if step.description else f"步骤 {i+1}",
                    description=step.description or "",
                    status="pending",
                    tools=[step.tool_name] if step.tool_name else [],
                )
                for i, step in enumerate(plan.steps)
            ],
            status="pending",
            session_key=session.key,
            spec_content=generation.spec_content or "",
            tasks_content=generation.tasks_content or "",
            checklist_content=generation.checklist_content or "",
            plan_type=analysis.plan_type,
            content=plan_content,
        )
        storage.save_plan(execution_plan)
        
        plan_dict = {
            "id": plan.id,
            "title": plan.title,
            "description": plan.description,
            "status": "pending",
            "created_at": plan.created_at,
            "session_key": session.key,
            "plan_type": analysis.plan_type,
            "content": plan_content,
            "subtasks": [
                {
                    "id": step.id,
                    "title": step.description[:100] if step.description else f"步骤 {i+1}",
                    "description": step.description or "",
                    "status": "pending",
                    "tools": [step.tool_name] if step.tool_name else [],
                }
                for i, step in enumerate(plan.steps)
            ],
            "spec_content": generation.spec_content or "",
            "tasks_content": generation.tasks_content or "",
            "checklist_content": generation.checklist_content or "",
        }
        
        message_id = session.add_message(
            role="assistant",
            content=f"📋 **执行计划**: {plan.title}\n\n{plan.description or ''}\n\n共 {len(plan.steps)} 个步骤，等待确认执行。",
            metadata={"type": "plan", "plan": plan_dict},
        )
        
        from horbot.agent.planner import get_plan_storage
        plan_storage = get_plan_storage()
        execution_plan = plan_storage.load_plan(plan.id)
        if execution_plan:
            execution_plan.message_id = message_id
            plan_storage.save_plan(execution_plan)
        
        self.sessions.save(session)
        logger.debug("Plan saved to session history: {} with message_id: {}", plan.id, message_id)
        
        if on_plan_created:
            await on_plan_created(plan_dict)
        
        return None

    async def execute_plan_by_id(
        self,
        plan_id: str,
        session_key: str,
        on_subtask_start: Callable[..., Awaitable[None]] | None = None,
        on_subtask_complete: Callable[..., Awaitable[None]] | None = None,
    ) -> OutboundMessage | None:
        """Execute a plan by its ID after confirmation.
        
        Loads the plan from storage (including spec.md, tasks.md, checklist.md content)
        and executes it with full context awareness.
        """
        from horbot.agent.planner import get_plan_storage, ExecutionPlan, SubTask
        from horbot.agent.planner.models import PlanStep, StepStatus
        
        storage = get_plan_storage()
        execution_plan = storage.load_plan(plan_id)
        
        if not execution_plan:
            logger.warning("Plan not found in storage: {}", plan_id)
            return OutboundMessage(
                channel="web",
                chat_id=session_key,
                content=f"❌ 未找到计划: {plan_id}",
            )
        
        logger.info("=" * 60)
        logger.info("📋 开始执行规划: {}", execution_plan.title)
        logger.info("规划ID: {}", plan_id)
        logger.info("会话ID: {}", session_key)
        logger.info("=" * 60)
        
        logger.info("📄 规划包含以下文件内容:")
        if execution_plan.spec_content:
            logger.info("  - spec.md: {} 字符", len(execution_plan.spec_content))
        if execution_plan.tasks_content:
            logger.info("  - tasks.md: {} 字符", len(execution_plan.tasks_content))
        if execution_plan.checklist_content:
            logger.info("  - checklist.md: {} 字符", len(execution_plan.checklist_content))
        
        plan = self._active_plans.get(session_key)
        if not plan or plan.id != plan_id:
            plan = Plan(
                id=execution_plan.id,
                title=execution_plan.title,
                description=execution_plan.description,
                steps=[
                    PlanStep(
                        id=st.id,
                        description=st.description or st.title,
                        tool_name=st.tools[0] if st.tools else None,
                        status=StepStatus.PENDING,
                    )
                    for st in execution_plan.subtasks
                ],
                status=PlanStatus.PENDING,
            )
        
        plan.status = PlanStatus.RUNNING
        storage.update_plan_status(plan_id, "running")
        
        # Collect all required skills and MCP tools from plan steps
        all_required_skills = set()
        all_required_mcp_tools = set()
        for step in plan.steps:
            if step.required_skills:
                all_required_skills.update(step.required_skills)
            if step.required_mcp_tools:
                all_required_mcp_tools.update(step.required_mcp_tools)
        
        logger.info("📋 规划所需 Skills: {}", list(all_required_skills) if all_required_skills else "无")
        logger.info("📋 规划所需 MCP 工具: {}", list(all_required_mcp_tools) if all_required_mcp_tools else "无")
        
        plan_context = self._build_plan_context(
            execution_plan,
            required_skills=list(all_required_skills),
            required_mcp_tools=list(all_required_mcp_tools),
        )
        
        total_steps = len(plan.steps)
        completed_steps = 0
        failed_steps = 0
        total_input_tokens = 0
        total_output_tokens = 0
        
        execution_steps_for_message: list[dict] = []
        
        logger.info("🚀 开始执行 {} 个步骤", total_steps)
        
        # Use PlanExecutor for parallel execution
        from horbot.agent.plan_executor import PlanExecutor
        
        executor = PlanExecutor(
            provider=self.provider,
            tools=self.tools,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            max_iterations=self.max_iterations,
            session_key=session_key,
        )
        
        # Save executor to active plans for stop functionality
        self._active_plans[session_key] = {
            "plan_id": plan_id,
            "executor": executor,
        }
        
        # Define callbacks for step execution
        async def on_step_start(step_id: str, step_type: str, title: str):
            logger.info("📌 开始执行步骤: {}", title[:100])
            
            step_entry = {
                "id": step_id,
                "type": step_type,
                "title": title[:100],
                "status": "running",
                "timestamp": datetime.now().isoformat(),
            }
            execution_steps_for_message.append(step_entry)
            logger.debug("Added step to execution_steps_for_message: {} (total: {})", step_id, len(execution_steps_for_message))
            
            if on_subtask_start:
                await on_subtask_start(
                    plan_id=plan_id,
                    subtask_id=step_id,
                    title=title[:100],
                )
        
        async def on_step_complete(step_id: str, status: str, result: str, execution_time: float, logs: list, input_tokens: int = 0, output_tokens: int = 0):
            nonlocal completed_steps, failed_steps, total_input_tokens, total_output_tokens
            
            # Accumulate token usage
            total_input_tokens += input_tokens
            total_output_tokens += output_tokens
            
            # Find the step
            step = next((s for s in plan.steps if s.id == step_id), None)
            if not step:
                return
            
            if status == "completed":
                step.status = StepStatus.COMPLETED
                completed_steps += 1
                storage.update_subtask_status(plan_id, step_id, "completed")
                logger.info("✅ 步骤完成: {} (耗时 {:.2f}s, tokens: {}/{})", 
                           step.description[:50], execution_time, input_tokens, output_tokens)
            else:
                step.status = StepStatus.FAILED
                failed_steps += 1
                storage.update_subtask_status(plan_id, step_id, "failed")
                logger.error("❌ 步骤失败: {}", step.description[:50])
            
            # Update execution step status
            for step_entry in execution_steps_for_message:
                if step_entry["id"] == step_id:
                    step_entry["status"] = status
                    step_entry["details"] = {
                        "result": result[:500] if result else "",
                        "executionTime": execution_time,
                    }
                    break
            
            # Save execution logs to storage
            logs_dict = [log.to_dict() if hasattr(log, 'to_dict') else log for log in logs]
            storage.save_execution_logs(plan_id, step_id, logs_dict)
            logger.debug("Saved execution logs for step: {}", step_id)
            
            if on_subtask_complete:
                await on_subtask_complete(
                    plan_id=plan_id,
                    subtask_id=step_id,
                    status=status,
                    result=result,
                    execution_time=execution_time,
                    logs=logs_dict,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
        
        # Execute all steps
        results = await executor.execute_plan(
            steps=plan.steps,
            plan_context=plan_context,
            on_step_start=on_step_start,
            on_step_complete=on_step_complete,
        )
        
        plan.status = PlanStatus.COMPLETED
        storage.update_plan_status(plan_id, "completed")
        self._active_plans.pop(session_key, None)
        
        # Update checklist.md file based on execution results
        if execution_plan.checklist_content:
            updated_checklist = self._update_checklist_from_execution(
                execution_plan.checklist_content, 
                completed_steps, 
                total_steps
            )
            plan_dir = storage.plans_path / plan_id
            checklist_file = plan_dir / "checklist.md"
            with open(checklist_file, "w", encoding="utf-8") as f:
                f.write(updated_checklist)
            logger.debug("Updated checklist.md file for plan: {}", plan_id)
        
        logger.info("=" * 60)
        logger.info("🎉 规划执行完成: {}", execution_plan.title)
        logger.info("   总步骤: {}", total_steps)
        logger.info("   成功: {}", completed_steps)
        logger.info("   失败: {}", failed_steps)
        logger.info("   Token使用量: 输入={}, 输出={}", total_input_tokens, total_output_tokens)
        logger.info("=" * 60)
        
        # Save execution result to session history
        session = self.sessions.get(session_key)
        if session:
            # Update the original plan message status to completed
            for msg in session.messages:
                if (msg.get("metadata", {}).get("type") == "plan" and 
                    msg.get("metadata", {}).get("plan", {}).get("id") == plan_id):
                    msg["metadata"]["plan"]["status"] = "completed"
                    # Update subtasks status
                    for i, step in enumerate(plan.steps):
                        if i < len(msg["metadata"]["plan"].get("subtasks", [])):
                            msg["metadata"]["plan"]["subtasks"][i]["status"] = step.status.value if hasattr(step.status, 'value') else str(step.status)
                    logger.debug("Updated plan status in session history: {}", plan_id)
                    break
            
            session.add_message(
                role="assistant",
                content=f"✅ 计划执行完成: {plan.title}\n\n📊 统计: {completed_steps}/{total_steps} 步骤成功" + (f"\n❌ {failed_steps} 步骤失败" if failed_steps > 0 else ""),
                execution_steps=execution_steps_for_message,
                metadata={
                    "type": "plan_result",
                    "plan_id": plan_id,
                    "completed_steps": completed_steps,
                    "failed_steps": failed_steps,
                    "total_steps": total_steps,
                },
            )
            self.sessions.save(session)
            logger.info("Plan execution result saved to session history: {} with {} execution steps", plan_id, len(execution_steps_for_message))
        
        return OutboundMessage(
            channel="web",
            chat_id=session_key,
            content=f"✅ 计划执行完成: {plan.title}\n\n📊 统计: {completed_steps}/{total_steps} 步骤成功" + (f"\n❌ {failed_steps} 步骤失败" if failed_steps > 0 else ""),
        )
    
    def stop_plan_execution(self, session_key: str) -> bool:
        """Stop the execution of a plan.
        
        Args:
            session_key: The session key to identify the active plan
            
        Returns:
            True if the plan was stopped, False if no active plan was found
        """
        logger.info("stop_plan_execution called with session_key: {}, active_plans keys: {}", session_key, list(self._active_plans.keys()))
        
        if session_key not in self._active_plans:
            logger.warning("No active plan found for session: {}, active_plans: {}", session_key, list(self._active_plans.keys()))
            return False
        
        plan_info = self._active_plans[session_key]
        
        # Check if plan_info is a dict with executor or just a plan object
        if isinstance(plan_info, dict):
            executor = plan_info.get("executor")
            if executor and hasattr(executor, 'request_stop'):
                executor.request_stop()
                logger.info("Stop request sent to plan executor for session: {}", session_key)
                return True
        elif hasattr(plan_info, 'status'):
            # It's a plan object, we can update its status
            plan_info.status = "stopped"
            logger.info("Stop request sent for plan (not yet executing) for session: {}", session_key)
            return True
        
        logger.warning("Executor does not support stop functionality for session: {}", session_key)
        return False
    
    def _build_plan_context(self, execution_plan, required_skills: list[str] | None = None, required_mcp_tools: list[str] | None = None) -> str:
        """Build context string from plan's three files content.
        
        Args:
            execution_plan: The execution plan object
            required_skills: List of skills required by the plan steps
            required_mcp_tools: List of MCP tools required by the plan steps
        """
        context_parts = []
        
        if execution_plan.spec_content:
            context_parts.append("## 规划说明 (spec.md)\n" + execution_plan.spec_content)
        
        if execution_plan.tasks_content:
            context_parts.append("## 任务列表 (tasks.md)\n" + execution_plan.tasks_content)
        
        if execution_plan.checklist_content:
            context_parts.append("## 检查清单 (checklist.md)\n" + execution_plan.checklist_content)
        
        # Add required skills information
        if required_skills:
            skills_info = "## 所需 Skills\n\n以下 Skills 将指导任务执行:\n"
            for skill in required_skills:
                skills_info += f"- {skill}\n"
            context_parts.append(skills_info)
        
        # Add required MCP tools information
        if required_mcp_tools:
            mcp_info = "## 所需 MCP 工具\n\n以下 MCP 工具将用于任务执行:\n"
            for tool in required_mcp_tools:
                mcp_info += f"- {tool}\n"
            context_parts.append(mcp_info)
        
        return "\n\n".join(context_parts)
    
    def _update_checklist_from_execution(self, checklist_content: str, completed_steps: int, total_steps: int) -> str:
        """Update checklist.md content based on execution results."""
        lines = checklist_content.split("\n")
        result_lines = []
        
        # Calculate completion percentage
        completion_rate = completed_steps / total_steps if total_steps > 0 else 0
        
        for line in lines:
            # Update unchecked items to checked if execution is complete
            if "[ ]" in line:
                # If all steps completed, check all items
                if completion_rate == 1.0:
                    line = line.replace("[ ]", "[x]")
                # If most steps completed, check most items
                elif completion_rate >= 0.8:
                    # Check items that don't contain "失败" or "错误"
                    if "失败" not in line and "错误" not in line:
                        line = line.replace("[ ]", "[x]")
            
            result_lines.append(line)
        
        # Add execution summary at the end
        result_lines.append("")
        result_lines.append("---")
        result_lines.append(f"**执行完成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        result_lines.append(f"**执行统计**: {completed_steps}/{total_steps} 步骤成功")
        if completed_steps < total_steps:
            result_lines.append(f"**失败步骤**: {total_steps - completed_steps} 步骤失败")
        
        return "\n".join(result_lines)
    
    async def _execute_step_with_context(
        self,
        step,
        session_key: str,
        plan_context: str,
        execution_plan,
    ) -> str:
        """Execute a step with full plan context awareness and quality validation."""
        logger.debug("执行步骤: {} (工具: {})", step.description[:50], step.tool_name or "无")
        
        if not step.tool_name:
            return await self._execute_step_via_llm(step, session_key, plan_context, execution_plan)
        
        try:
            # Try to execute with existing parameters
            result = await self.tools.execute(step.tool_name, step.parameters or {})
            logger.debug("步骤执行结果: {}", result[:200] if len(result) > 200 else result)
            
            # Validate result quality even for successful tool execution
            if self._validate_result_quality(result):
                logger.debug("工具执行结果质量验证通过")
                return result
            else:
                logger.warning("工具执行结果质量验证失败，尝试使用LLM改进结果")
                # Try to enhance the result using LLM
                enhanced_result = await self._enhance_tool_result_with_llm(
                    step, result, plan_context, execution_plan
                )
                return enhanced_result
                
        except Exception as e:
            error_msg = str(e)
            logger.warning("步骤执行失败: {} - {}. 尝试使用LLM推断参数或执行步骤。", step.description[:50], error_msg)
            
            # Check if it's a parameter error
            if "missing required" in error_msg.lower() or "invalid parameters" in error_msg.lower():
                logger.info("检测到参数缺失，尝试使用LLM推断参数...")
                
                # Try to infer parameters using LLM
                inferred_params = await self._infer_parameters_with_llm(
                    step, plan_context, execution_plan, error_msg
                )
                
                if inferred_params:
                    logger.info("LLM推断参数成功，重新执行步骤...")
                    try:
                        result = await self.tools.execute(step.tool_name, inferred_params)
                        logger.debug("步骤执行结果: {}", result[:200] if len(result) > 200 else result)
                        
                        # Validate result quality for inferred parameters execution
                        if self._validate_result_quality(result):
                            logger.debug("使用推断参数的执行结果质量验证通过")
                            return result
                        else:
                            logger.warning("使用推断参数的执行结果质量验证失败，尝试使用LLM改进结果")
                            # Try to enhance the result using LLM
                            enhanced_result = await self._enhance_tool_result_with_llm(
                                step, result, plan_context, execution_plan
                            )
                            return enhanced_result
                            
                    except Exception as retry_error:
                        logger.warning("使用推断参数执行仍然失败: {}", str(retry_error))
            
            # Fallback to LLM execution
            logger.info("回退到使用LLM执行步骤...")
            return await self._execute_step_via_llm(step, session_key, plan_context, execution_plan)
    
    async def _enhance_tool_result_with_llm(
        self,
        step,
        tool_result: str,
        plan_context: str,
        execution_plan,
    ) -> str:
        """Enhance tool execution result using LLM if quality is not satisfactory."""
        messages = [
            {
                "role": "system",
                "content": f"""你是一个结果优化助手。工具执行的结果质量不达标，请根据以下信息优化结果。

{plan_context}

当前任务信息:
- 规划标题: {execution_plan.title}
- 规划描述: {execution_plan.description}
- 当前步骤: {step.description}

工具执行结果:
{tool_result}

优化要求:
1. 提供更详细的解释和分析
2. 如果结果是错误信息，提供详细的错误分析和解决方案
3. 如果结果过于简单，补充相关的背景信息和执行过程
4. 确保优化后的结果至少100个字符
5. 提供清晰的结构和逻辑

请优化上述工具执行结果。"""
            },
            {
                "role": "user",
                "content": "请优化工具执行结果，提供更详细、更有价值的内容。"
            }
        ]
        
        try:
            response = await self.provider.chat(
                messages=messages,
                tools=None,
                model=self.model,
                temperature=0.7,
                max_tokens=self.max_tokens,
            )
            
            enhanced_result = response.content or tool_result
            logger.debug("结果优化完成: {}", enhanced_result[:200] if len(enhanced_result) > 200 else enhanced_result)
            return enhanced_result
            
        except Exception as e:
            logger.warning("结果优化失败: {}, 返回原始结果", str(e))
            return tool_result
    
    async def _infer_parameters_with_llm(
        self,
        step,
        plan_context: str,
        execution_plan,
        error_msg: str,
    ) -> dict | None:
        """Infer missing parameters using LLM."""
        try:
            messages = [
                {
                    "role": "system",
                    "content": f"""你是一个参数推断助手。根据步骤描述和错误信息，推断缺失的工具参数。

规划上下文:
{plan_context}

规划标题: {execution_plan.title}
规划描述: {execution_plan.description}
"""
                },
                {
                    "role": "user",
                    "content": f"""请为以下步骤推断缺失的参数:

步骤描述: {step.description}
工具名称: {step.tool_name}
当前参数: {step.parameters or {}}
错误信息: {error_msg}

请返回一个JSON对象，包含所有必需的参数。例如:
{{"filepath": "/path/to/file.xlsx", "sheet_name": "Sheet1"}}

只返回JSON对象，不要包含其他内容。"""
                }
            ]
            
            response = await self.provider.chat(
                messages=messages,
                tools=None,
                temperature=0.3,
                max_tokens=500,
            )
            
            content = response.content or ""
            
            # Try to parse JSON from response
            import json
            import re
            
            # Remove markdown code blocks if present
            content = re.sub(r'^```json\s*', '', content)
            content = re.sub(r'\s*```$', '', content)
            content = content.strip()
            
            # Try to parse as JSON
            try:
                params = json.loads(content)
                logger.debug("推断的参数: {}", params)
                return params
            except json.JSONDecodeError:
                logger.warning("无法解析LLM返回的参数JSON: {}", content)
                return None
                
        except Exception as e:
            logger.error("推断参数失败: {}", str(e))
            return None
    
    async def _execute_step_via_llm(
        self,
        step,
        session_key: str,
        plan_context: str,
        execution_plan,
    ) -> str:
        """Execute a step by calling LLM with enhanced context and quality requirements."""
        from horbot.agent.planner.models import StepStatus
        
        step.status = StepStatus.RUNNING
        
        # Build enhanced system prompt with detailed execution requirements
        system_prompt = f"""你是一个专业的任务执行助手。请按照以下规划文件执行当前步骤。

{plan_context}

当前任务信息:
- 规划标题: {execution_plan.title}
- 规划描述: {execution_plan.description}
- 当前步骤: {step.description}

执行要求:
1. 执行结果必须详细、具体、有价值
2. 执行结果长度至少100个字符
3. 如果是创建文件，必须包含完整的文件内容
4. 如果是分析任务，必须包含详细的分析过程和结论
5. 如果是代码实现，必须包含完整的代码和注释
6. 避免简单的"完成"、"成功"等无意义的回复
7. 如果需要使用工具，请详细说明工具的使用方式和参数
8. 提供清晰的执行步骤和结果说明

请执行当前步骤并返回详细的执行结果。"""

        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": f"请执行步骤: {step.description}\n\n请提供详细、有价值的执行结果。"
            }
        ]
        
        # Execute with retry mechanism for quality validation
        max_retries = 3
        last_result = None
        
        for attempt in range(max_retries):
            try:
                logger.debug("执行步骤尝试 {}/{}", attempt + 1, max_retries)
                
                response = await self.provider.chat(
                    messages=messages,
                    tools=self.tools.get_definitions_smart(step.description),
                    model=self.model,
                    temperature=0.7,  # Use higher temperature for more creative and detailed responses
                    max_tokens=self.max_tokens,
                )
                
                # Process response
                if response.has_tool_calls:
                    results = []
                    for tool_call in response.tool_calls:
                        logger.info("LLM 调用工具: {}({})", tool_call.name, 
                                   str(tool_call.arguments)[:100])
                        result = await self.tools.execute(tool_call.name, tool_call.arguments)
                        results.append(f"工具 {tool_call.name}: {result}")
                    result = "\n".join(results)
                else:
                    result = response.content or ""
                
                last_result = result
                
                # Validate result quality
                if self._validate_result_quality(result):
                    logger.debug("执行结果质量验证通过")
                    return result
                
                # Quality validation failed, add feedback and retry
                logger.warning("执行结果质量验证失败，尝试重新执行（{}/{}）", attempt + 1, max_retries)
                
                # Add feedback to messages
                messages.append({
                    "role": "assistant",
                    "content": result
                })
                
                feedback = self._get_quality_feedback(result)
                messages.append({
                    "role": "user",
                    "content": f"执行结果质量不达标，原因: {feedback}\n\n请重新执行并提供更详细、更有价值的结果。确保结果包含具体的执行过程、分析结果或产出物。"
                })
                
            except Exception as e:
                logger.error("LLM 执行步骤失败: {}", str(e))
                if attempt == max_retries - 1:
                    raise
        
        # Return the last result even if quality validation failed
        logger.warning("执行结果质量验证未通过，返回最后一次执行结果")
        return last_result or "步骤执行完成，但结果质量不达标"
    
    def _validate_result_quality(self, result: str) -> bool:
        """验证执行结果的质量是否达标."""
        if not result or not result.strip():
            logger.debug("执行结果质量验证失败: 结果为空")
            return False
        
        stripped_result = result.strip()
        
        # 检查结果长度
        if len(stripped_result) < 50:
            logger.debug("执行结果质量验证失败: 结果过短（{}个字符）", len(stripped_result))
            return False
        
        # 检查是否只包含简单的词语
        simple_words = ['完成', '成功', 'done', 'success', 'ok', 'yes', 'no', 'ok.', 'done.', 'success.']
        if stripped_result.lower() in simple_words:
            logger.debug("执行结果质量验证失败: 结果过于简单（{}）", stripped_result)
            return False
        
        # 检查是否只包含错误信息
        error_indicators = ['error:', '错误:', '失败:', 'failed:', 'exception:']
        if any(indicator in stripped_result.lower() for indicator in error_indicators):
            # 如果结果只包含错误信息，也认为质量不达标
            if len(stripped_result) < 200:
                logger.debug("执行结果质量验证失败: 结果只包含错误信息")
                return False
        
        logger.debug("执行结果质量验证通过")
        return True
    
    def _get_quality_feedback(self, result: str) -> str:
        """获取执行结果质量不达标的具体反馈."""
        if not result or not result.strip():
            return "执行结果为空，需要提供详细的执行过程和结果"
        
        stripped_result = result.strip()
        
        if len(stripped_result) < 50:
            return f"执行结果过短（仅{len(stripped_result)}个字符），需要提供更详细的内容，包括执行过程、分析结果和具体产出"
        
        simple_words = ['完成', '成功', 'done', 'success', 'ok', 'yes', 'no', 'ok.', 'done.', 'success.']
        if stripped_result.lower() in simple_words:
            return "执行结果过于简单，缺乏实质性内容。请提供详细的执行过程、分析结果或具体的产出物"
        
        error_indicators = ['error:', '错误:', '失败:', 'failed:', 'exception:']
        if any(indicator in stripped_result.lower() for indicator in error_indicators):
            if len(stripped_result) < 200:
                return "执行结果只包含错误信息，需要提供更详细的错误分析和解决方案"
        
        return "执行结果质量不达标，需要提供更详细、更有价值的内容"

    def get_active_plan(self, session_key: str) -> dict | None:
        """Get the active plan for a session."""
        plan = self._active_plans.get(session_key)
        if not plan:
            return None
        
        return {
            "id": plan.id,
            "title": plan.title,
            "description": plan.description,
            "status": plan.status.value if hasattr(plan.status, 'value') else str(plan.status),
            "created_at": plan.created_at,
            "session_key": session_key,
            "steps": [
                {
                    "id": step.id,
                    "description": step.description,
                    "tool_name": step.tool_name,
                    "status": step.status.value if hasattr(step.status, 'value') else str(step.status),
                }
                for step in plan.steps
            ]
        }

    async def _execute_plan(
        self,
        plan: Plan,
        msg: InboundMessage,
        session: Session,
    ) -> OutboundMessage:
        """Execute a plan step by step."""
        plan.status = PlanStatus.RUNNING
        
        async def progress_callback(progress):
            await self.bus.publish_outbound(OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=f"⏳ 执行中... {progress.completed_steps}/{progress.total_steps} ({progress.percent_complete:.0f}%)",
            ))
        
        self._plan_executor._progress_callback = progress_callback
        
        result = await self._plan_executor.execute(
            plan=plan,
            session_id=session.key,
        )
        
        if result.success:
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=f"✅ {result.message}",
            )
        else:
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=f"❌ {result.message}",
            )
