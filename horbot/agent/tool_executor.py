import asyncio
import json
import time
import uuid
from typing import Any, Awaitable, Callable

from loguru import logger

from horbot.agent.tools.permission import PermissionLevel
from horbot.agent.tools.registry import ToolRegistry
from horbot.agent.context import ContextBuilder


class ToolExecutionResult:
    def __init__(
        self,
        messages: list[dict],
        tools_used: list[str],
        final_content: str | None = None,
        confirmations: dict[str, dict[str, Any]] | None = None,
        should_break: bool = False,
    ):
        self.messages = messages
        self.tools_used = tools_used
        self.final_content = final_content
        self.confirmations = confirmations or {}
        self.should_break = should_break


class ToolExecutor:
    def __init__(self, tools: ToolRegistry, context: ContextBuilder):
        self.tools = tools
        self.context = context

    async def execute_tool_calls(
        self,
        tool_calls: list[Any],
        messages: list[dict],
        tools_used: list[str],
        iteration: int,
        on_step_start: Callable[..., Awaitable[None]] | None = None,
        on_tool_start: Callable[..., Awaitable[None]] | None = None,
        on_status: Callable[..., Awaitable[None]] | None = None,
        on_tool_result: Callable[..., Awaitable[None]] | None = None,
        on_step_complete: Callable[..., Awaitable[None]] | None = None,
    ) -> ToolExecutionResult:
        """Execute a list of tool calls and update messages/context."""
        should_break_outer = False
        final_content = None
        confirmations: dict[str, dict[str, Any]] = {}

        tools_to_execute = []

        for tool_idx, tool_call in enumerate(tool_calls):
            args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
            logger.info("Tool call: {}({})", tool_call.name, args_str[:200])
            logger.debug("tools_used before check: {}, iteration: {}", tools_used, iteration)
            
            # Enforce: message tool can only be called once per turn
            if tool_call.name == "message" and "message" in tools_used:
                logger.warning("Message tool already called in this turn (iteration {}), forcing completion", iteration)
                # Add a fake tool result for this skipped tool call
                messages = self.context.add_tool_result(
                    messages, tool_call.id, tool_call.name, 
                    "Message already sent. Task complete."
                )
                # Force completion - set final content and break out of both loops
                if not final_content:
                    final_content = "Message sent."
                should_break_outer = True
                continue
            
            tools_used.append(tool_call.name)
            logger.debug("tools_used after append: {}", tools_used)
            
            permission = self.tools.check_permission(tool_call.name)
            
            if permission == PermissionLevel.CONFIRM:
                confirmation_id = str(uuid.uuid4())[:8]
                confirmations[confirmation_id] = {
                    "tool_name": tool_call.name,
                    "arguments": tool_call.arguments,
                    "tool_call_id": tool_call.id,
                }
                logger.info("Tool {} requires confirmation: {}", tool_call.name, confirmation_id)
            else:
                tools_to_execute.append((tool_idx, tool_call))

        async def _execute_single_tool(tool_idx: int, tool_call: Any) -> tuple[int, Any, str]:
            tool_step_id = f"tool_{tool_call.name}_{iteration}_{tool_idx}"
            if on_step_start:
                await on_step_start(tool_step_id, "tool_call", f"执行 {tool_call.name}")
            
            if on_tool_start:
                await on_tool_start(tool_call.name, tool_call.arguments)
            if on_status:
                await on_status(f"正在执行工具: {tool_call.name}")
            
            start_time = time.time()
            result = await self.tools.execute(tool_call.name, tool_call.arguments)
            execution_time = time.time() - start_time
            
            if on_tool_result:
                await on_tool_result(tool_call.name, result, execution_time)
            
            # Complete tool step
            if on_step_complete:
                status = "error" if result.startswith("Error") else "success"
                await on_step_complete(tool_step_id, status, {
                    "toolName": tool_call.name,
                    "arguments": tool_call.arguments,
                    "result": result,
                    "executionTime": execution_time
                })
            
            return tool_idx, tool_call, result

        # Execute all non-confirm tools in parallel
        results_dict = {}
        if tools_to_execute:
            tasks = [_execute_single_tool(idx, tc) for idx, tc in tools_to_execute]
            results = await asyncio.gather(*tasks)
            for idx, tc, res in results:
                results_dict[idx] = res

        # Update messages in original order
        for tool_idx, tool_call in enumerate(tool_calls):
            if tool_idx in results_dict:
                result = results_dict[tool_idx]
                messages = self.context.add_tool_result(
                    messages, tool_call.id, tool_call.name, result
                )
                
                # If message tool was executed successfully, we're done
                if tool_call.name == "message":
                    final_content = result or "Message sent."
                    should_break_outer = True

        if confirmations:
            for conf_data in confirmations.values():
                conf_data["messages"] = messages.copy()
                
            tool_names = [data["tool_name"] for data in confirmations.values()]
            names_str = ", ".join(f"`{name}`" for name in tool_names)
            final_content = f"⚠️ **需要确认**\n\nAI 想要执行工具 {names_str}\n\n请确认是否执行此操作。"
            should_break_outer = True

        return ToolExecutionResult(
            messages=messages,
            tools_used=tools_used,
            final_content=final_content,
            confirmations=confirmations,
            should_break=should_break_outer
        )
