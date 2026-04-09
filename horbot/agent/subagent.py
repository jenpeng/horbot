"""Subagent manager for background task execution."""

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any

from loguru import logger

from horbot.bus.events import InboundMessage
from horbot.bus.queue import MessageBus
from horbot.providers.base import LLMProvider
from horbot.agent.tools.registry import ToolRegistry
from horbot.agent.tools.filesystem import ReadFileTool, ListDirTool
from horbot.agent.tools.safe_editor import SafeWriteFileTool, SafeEditFileTool
from horbot.agent.tools.shell import ExecTool
from horbot.agent.tools.web import WebSearchTool, WebFetchTool


class SubagentInfo:
    """Information about a running subagent."""
    
    def __init__(
        self,
        task_id: str,
        label: str,
        task: str,
        status: str,
        started_at: float,
        session_key: str | None = None,
        origin: dict[str, str] | None = None,
    ):
        self.task_id = task_id
        self.label = label
        self.task = task
        self.status = status
        self.started_at = started_at
        self.session_key = session_key
        self.origin = origin or {}
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": self.task_id,
            "label": self.label,
            "task": self.task,
            "status": self.status,
            "started_at": self.started_at,
            "running_seconds": time.time() - self.started_at,
            "session_key": self.session_key,
            "origin": self.origin,
        }


class SubagentManager:
    """Manages background subagent execution."""
    
    def __init__(
        self,
        provider: LLMProvider,
        bus: MessageBus,
        workspace: Path | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        brave_api_key: str | None = None,
        exec_config: "ExecToolConfig | None" = None,
        restrict_to_workspace: bool = False,
    ):
        from horbot.config.schema import ExecToolConfig
        if workspace is None:
            from horbot.utils.paths import get_workspace_dir
            workspace = get_workspace_dir()
        self.provider = provider
        self.workspace = workspace
        self.bus = bus
        self.model = model or provider.get_default_model()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.restrict_to_workspace = restrict_to_workspace
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
        self._session_tasks: dict[str, set[str]] = {}  # session_key -> {task_id, ...}
        self._task_info: dict[str, SubagentInfo] = {}  # task_id -> SubagentInfo
    
    async def spawn(
        self,
        task: str,
        label: str | None = None,
        origin_channel: str = "cli",
        origin_chat_id: str = "direct",
        session_key: str | None = None,
    ) -> str:
        """Spawn a subagent to execute a task in the background."""
        task_id = str(uuid.uuid4())[:8]
        display_label = label or task[:30] + ("..." if len(task) > 30 else "")
        origin = {"channel": origin_channel, "chat_id": origin_chat_id}

        # Store task info
        self._task_info[task_id] = SubagentInfo(
            task_id=task_id,
            label=display_label,
            task=task,
            status="running",
            started_at=time.time(),
            session_key=session_key,
            origin=origin,
        )

        bg_task = asyncio.create_task(
            self._run_subagent(task_id, task, display_label, origin)
        )
        self._running_tasks[task_id] = bg_task
        if session_key:
            self._session_tasks.setdefault(session_key, set()).add(task_id)

        def _cleanup(_: asyncio.Task) -> None:
            self._running_tasks.pop(task_id, None)
            if session_key and (ids := self._session_tasks.get(session_key)):
                ids.discard(task_id)
                if not ids:
                    del self._session_tasks[session_key]
            # Update task info status
            if task_id in self._task_info:
                self._task_info[task_id].status = "completed"

        bg_task.add_done_callback(_cleanup)
        
        logger.info("Spawned subagent [{}]: {}", task_id, display_label)
        return f"Subagent [{display_label}] started (id: {task_id}). I'll notify you when it completes."
    
    async def _run_subagent(
        self,
        task_id: str,
        task: str,
        label: str,
        origin: dict[str, str],
    ) -> None:
        """Execute the subagent task and announce the result."""
        logger.info("Subagent [{}] starting task: {}", task_id, label)
        
        try:
            # Build subagent tools (no message tool, no spawn tool)
            tools = ToolRegistry()
            allowed_dir = self.workspace if self.restrict_to_workspace else None
            tools.register(ReadFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
            tools.register(SafeWriteFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
            tools.register(SafeEditFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
            tools.register(ListDirTool(workspace=self.workspace, allowed_dir=allowed_dir))
            tools.register(ExecTool(
                working_dir=str(self.workspace),
                timeout=self.exec_config.timeout,
                restrict_to_workspace=self.restrict_to_workspace,
                path_append=self.exec_config.path_append,
            ))
            tools.register(WebSearchTool(api_key=self.brave_api_key))
            tools.register(WebFetchTool())
            
            # Build messages with subagent-specific prompt
            system_prompt = self._build_subagent_prompt(task)
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task},
            ]
            
            # Run agent loop (limited iterations)
            max_iterations = 15
            iteration = 0
            final_result: str | None = None
            
            while iteration < max_iterations:
                iteration += 1
                
                response = await self.provider.chat(
                    messages=messages,
                    tools=tools.get_definitions(),
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                
                if response.has_tool_calls:
                    # Add assistant message with tool calls
                    tool_call_dicts = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                            },
                        }
                        for tc in response.tool_calls
                    ]
                    messages.append({
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": tool_call_dicts,
                    })
                    
                    # Execute tools
                    for tool_call in response.tool_calls:
                        args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                        logger.debug("Subagent [{}] executing: {} with arguments: {}", task_id, tool_call.name, args_str)
                        result = await tools.execute(tool_call.name, tool_call.arguments)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call.name,
                            "content": result,
                        })
                else:
                    final_result = response.content
                    break
            
            if final_result is None:
                final_result = "Task completed but no final response was generated."
            
            logger.info("Subagent [{}] completed successfully", task_id)
            await self._announce_result(task_id, label, task, final_result, origin, "ok")
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error("Subagent [{}] failed: {}", task_id, e)
            await self._announce_result(task_id, label, task, error_msg, origin, "error")
    
    async def _announce_result(
        self,
        task_id: str,
        label: str,
        task: str,
        result: str,
        origin: dict[str, str],
        status: str,
    ) -> None:
        """Announce the subagent result to the main agent via the message bus."""
        status_text = "completed successfully" if status == "ok" else "failed"
        
        announce_content = f"""[Subagent '{label}' {status_text}]

Task: {task}

Result:
{result}

Summarize this naturally for the user. Keep it brief (1-2 sentences). Do not mention technical details like "subagent" or task IDs."""
        
        # Inject as system message to trigger main agent
        msg = InboundMessage(
            channel="system",
            sender_id="subagent",
            chat_id=f"{origin['channel']}:{origin['chat_id']}",
            content=announce_content,
        )
        
        await self.bus.publish_inbound(msg)
        logger.debug("Subagent [{}] announced result to {}:{}", task_id, origin['channel'], origin['chat_id'])
    
    def _build_subagent_prompt(self, task: str) -> str:
        """Build a focused system prompt for the subagent."""
        from datetime import datetime
        import time as _time
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        tz = _time.strftime("%Z") or "UTC"

        return f"""# Subagent

## Current Time
{now} ({tz})

You are a subagent spawned by the main agent to complete a specific task.

## Rules
1. Stay focused - complete only the assigned task, nothing else
2. Your final response will be reported back to the main agent
3. Do not initiate conversations or take on side tasks
4. Be concise but informative in your findings

## What You Can Do
- Read and write files in the workspace
- Execute shell commands
- Search the web and fetch web pages
- Complete the task thoroughly

## What You Cannot Do
- Send messages directly to users (no message tool available)
- Spawn other subagents
- Access the main agent's conversation history

## Workspace
Your workspace is at: {self.workspace}
Skills are available at: {self.workspace}/skills/ (read SKILL.md files as needed)

When you have completed the task, provide a clear summary of your findings or actions."""
    
    async def cancel_by_session(self, session_key: str) -> int:
        """Cancel all subagents for the given session. Returns count cancelled."""
        tasks = [self._running_tasks[tid] for tid in self._session_tasks.get(session_key, [])
                 if tid in self._running_tasks and not self._running_tasks[tid].done()]
        for t in tasks:
            t.cancel()
            # Update task info status
            for task_id in self._session_tasks.get(session_key, []):
                if task_id in self._task_info:
                    self._task_info[task_id].status = "cancelled"
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        return len(tasks)

    def get_running_count(self) -> int:
        """Return the number of currently running subagents."""
        return len([t for t in self._running_tasks.values() if not t.done()])

    def list_subagents(self, session_key: str | None = None) -> list[SubagentInfo]:
        """List all running subagents, optionally filtered by session."""
        result = []
        for task_id, info in self._task_info.items():
            # Only include running tasks
            if task_id in self._running_tasks:
                task = self._running_tasks[task_id]
                if task.done():
                    continue
            else:
                continue
            
            # Filter by session if provided
            if session_key and info.session_key != session_key:
                continue
            
            result.append(info)
        
        return result

    async def cancel(self, task_id: str) -> bool:
        """Cancel a specific subagent by task_id. Returns True if cancelled."""
        if task_id not in self._running_tasks:
            return False
        
        task = self._running_tasks[task_id]
        if task.done():
            return False
        
        task.cancel()
        
        # Update task info status
        if task_id in self._task_info:
            self._task_info[task_id].status = "cancelled"
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        return True

    async def cancel_all(self) -> int:
        """Cancel all running subagents. Returns count cancelled."""
        cancelled = 0
        for task_id, task in list(self._running_tasks.items()):
            if not task.done():
                task.cancel()
                # Update task info status
                if task_id in self._task_info:
                    self._task_info[task_id].status = "cancelled"
                cancelled += 1
        
        # Wait for all cancelled tasks
        if cancelled > 0:
            await asyncio.gather(*[t for t in self._running_tasks.values() if t.cancelled()], return_exceptions=True)
        
        return cancelled

    def get_subagent_info(self, task_id: str) -> SubagentInfo | None:
        """Get information about a specific subagent."""
        return self._task_info.get(task_id)
