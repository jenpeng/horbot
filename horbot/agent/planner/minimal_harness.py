"""Minimal harness for unified planning approach.

Based on learn-claude-code theory:
- Harness provides ONLY perception/action interfaces
- No decision logic in harness
- No complexity analysis
- No strategy selection
- Model is the agent, harness is just infrastructure

The minimal harness:
1. Provides tool descriptions (perception)
2. Executes tools (action)
3. Manages execution context
4. Handles errors
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Awaitable
import asyncio
import traceback


@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    output: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionContext:
    """Execution context for the harness."""
    workspace: Path
    variables: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    
    def add_to_history(self, action: str, result: Any) -> None:
        """Add an action to history."""
        self.history.append({
            "action": action,
            "result": result,
        })


class MinimalHarness:
    """
    Minimal harness that provides only perception/action interfaces.
    
    Responsibilities:
    - Provide tool descriptions to the model
    - Execute tools when the model chooses them
    - Manage execution context
    - Handle errors and recovery
    
    NOT responsible for:
    - Complexity analysis
    - Strategy selection
    - Task decomposition
    - Decision making
    """
    
    def __init__(
        self,
        tools: dict[str, Callable[..., Awaitable[ToolResult]]],
        workspace: Path | None = None,
        on_error: Callable[[Exception], Awaitable[None]] | None = None,
    ):
        self.tools = tools
        self.workspace = workspace or Path.cwd()
        self.on_error = on_error
        self._context = ExecutionContext(workspace=self.workspace)
    
    def get_tool_descriptions(self) -> list[dict[str, Any]]:
        """
        Get descriptions of all available tools.
        
        This is the "perception" interface - lets the model know
        what actions are available.
        """
        descriptions = []
        for name, func in self.tools.items():
            desc = {
                "name": name,
                "description": func.__doc__ or f"Tool: {name}",
                "parameters": {},
            }
            
            if hasattr(func, "_tool_schema"):
                desc["parameters"] = func._tool_schema.get("parameters", {})
            
            descriptions.append(desc)
        
        return descriptions
    
    async def execute_tool(
        self,
        tool_name: str,
        parameters: dict[str, Any],
    ) -> ToolResult:
        """
        Execute a tool with the given parameters.
        
        This is the "action" interface - executes what the model chose.
        """
        if tool_name not in self.tools:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool: {tool_name}",
            )
        
        tool = self.tools[tool_name]
        
        try:
            result = await tool(**parameters)
            
            self._context.add_to_history(
                f"{tool_name}({parameters})",
                result,
            )
            
            if isinstance(result, ToolResult):
                return result
            
            return ToolResult(
                success=True,
                output=str(result),
            )
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            traceback.print_exc()
            
            if self.on_error:
                await self.on_error(e)
            
            return ToolResult(
                success=False,
                output="",
                error=error_msg,
            )
    
    def get_context(self) -> ExecutionContext:
        """Get the current execution context."""
        return self._context
    
    def set_variable(self, key: str, value: Any) -> None:
        """Set a variable in the execution context."""
        self._context.variables[key] = value
    
    def get_variable(self, key: str, default: Any = None) -> Any:
        """Get a variable from the execution context."""
        return self._context.variables.get(key, default)
    
    async def execute_plan(
        self,
        steps: list[dict[str, Any]],
        on_step_start: Callable[[dict], Awaitable[None]] | None = None,
        on_step_complete: Callable[[dict, ToolResult], Awaitable[None]] | None = None,
    ) -> list[ToolResult]:
        """
        Execute a sequence of steps.
        
        The model decides the order and tools.
        The harness just executes them.
        """
        results = []
        
        for step in steps:
            if on_step_start:
                await on_step_start(step)
            
            tool_name = step.get("tool") or step.get("tool_name")
            parameters = step.get("parameters", {})
            
            if not tool_name:
                result = ToolResult(
                    success=False,
                    output="",
                    error="No tool specified for step",
                )
            else:
                result = await self.execute_tool(tool_name, parameters)
            
            results.append(result)
            
            if on_step_complete:
                await on_step_complete(step, result)
            
            if not result.success and step.get("stop_on_error", True):
                break
        
        return results


def create_harness_from_registry(tools_registry: Any, workspace: Path | None = None) -> MinimalHarness:
    """
    Create a minimal harness from an existing tools registry.
    
    This allows integration with existing tool infrastructure
    while providing the minimal harness interface.
    """
    async def tool_wrapper(name: str, **kwargs) -> ToolResult:
        result = await tools_registry.execute(name, kwargs)
        return ToolResult(
            success=result.success,
            output=result.output if hasattr(result, "output") else str(result),
            error=result.error if hasattr(result, "error") else None,
        )
    
    tools = {}
    for tool_name in tools_registry.tool_names:
        def make_tool(name: str):
            async def execute(**kwargs):
                return await tool_wrapper(name, **kwargs)
            return execute
        tools[tool_name] = make_tool(tool_name)
    
    return MinimalHarness(tools=tools, workspace=workspace)
