"""Plan executor with parallel step execution support."""

import asyncio
from typing import Any, Optional, List, Dict, Callable, Tuple
from loguru import logger

from horbot.agent.plan_step_subagent import PlanStepSubagent, StepExecutionResult
from horbot.agent.planner.models import PlanStep
from horbot.providers.base import LLMProvider
from horbot.agent.tools.registry import ToolRegistry


class StepDependencyAnalyzer:
    """Analyzes step dependencies to identify parallelizable steps."""
    
    def __init__(self, steps: List[PlanStep]):
        self.steps = steps
        self.dependency_graph = self._build_dependency_graph()
    
    def _build_dependency_graph(self) -> Dict[str, set]:
        """Build dependency graph from step dependencies."""
        graph = {}
        for step in self.steps:
            graph[step.id] = set(step.dependencies or [])
        return graph
    
    def get_execution_groups(self) -> List[List[PlanStep]]:
        """
        Group steps into execution groups where steps in the same group
        can be executed in parallel.
        
        Returns a list of groups, where each group is a list of steps
        that can be executed in parallel.
        """
        if not self.steps:
            return []
        
        # Create a mapping from step_id to step
        step_map = {step.id: step for step in self.steps}
        
        # Track completed steps
        completed = set()
        groups = []
        remaining = set(step.id for step in self.steps)
        
        while remaining:
            # Find steps that can be executed (all dependencies are completed)
            executable = []
            for step_id in remaining:
                deps = self.dependency_graph.get(step_id, set())
                if deps.issubset(completed):
                    executable.append(step_id)
            
            if not executable:
                # Circular dependency or invalid dependency
                logger.warning("Circular dependency detected or invalid dependencies")
                # Add remaining steps as a single group to avoid infinite loop
                executable = list(remaining)
            
            # Create a group from executable steps
            group = [step_map[step_id] for step_id in executable]
            groups.append(group)
            
            # Mark these steps as completed
            for step_id in executable:
                completed.add(step_id)
                remaining.remove(step_id)
        
        return groups


class PlanExecutor:
    """Executes plan steps with support for parallel execution."""
    
    def __init__(
        self,
        provider: LLMProvider,
        tools: ToolRegistry,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        max_iterations: int = 40,
        session_key: Optional[str] = None,
    ):
        self.provider = provider
        self.tools = tools
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_iterations = max_iterations
        self.session_key = session_key
        self._running_subagents: Dict[str, PlanStepSubagent] = {}
        self._execution_results: Dict[str, StepExecutionResult] = {}
        self._stop_requested = False
    
    def request_stop(self):
        """Request to stop execution."""
        self._stop_requested = True
        logger.info("Stop requested for plan execution")
        
        # Cancel all running subagents
        for step_id, subagent in self._running_subagents.items():
            logger.info("Cancelling subagent for step: {}", step_id)
            if hasattr(subagent, 'request_stop'):
                subagent.request_stop()
            # We'll add this functionality later
    
    async def execute_plan(
        self,
        steps: List[PlanStep],
        plan_context: str,
        on_step_start: Optional[Callable] = None,
        on_step_complete: Optional[Callable] = None,
    ) -> Dict[str, StepExecutionResult]:
        """
        Execute all plan steps with parallel execution support.
        
        Args:
            steps: List of plan steps to execute
            plan_context: Context from plan files (spec, tasks, checklist)
            on_step_start: Callback when a step starts
            on_step_complete: Callback when a step completes
            
        Returns:
            Dictionary mapping step_id to execution result
        """
        # Analyze dependencies and group steps
        analyzer = StepDependencyAnalyzer(steps)
        execution_groups = analyzer.get_execution_groups()
        
        logger.info("Plan execution: {} steps grouped into {} execution groups", 
                   len(steps), len(execution_groups))
        
        # Execute each group
        for group_idx, group in enumerate(execution_groups, 1):
            # Check if stop was requested
            if self._stop_requested:
                logger.info("Execution stopped by user request at group {}/{}", 
                           group_idx, len(execution_groups))
                break
            
            logger.info("Executing group {}/{} with {} steps", 
                       group_idx, len(execution_groups), len(group))
            
            if len(group) == 1:
                # Single step - execute directly
                step = group[0]
                result = await self._execute_single_step(
                    step, plan_context, on_step_start, on_step_complete
                )
                self._execution_results[step.id] = result
            else:
                # Multiple steps - execute in parallel
                results = await self._execute_steps_in_parallel(
                    group, plan_context, on_step_start, on_step_complete
                )
                for step_id, result in results.items():
                    self._execution_results[step_id] = result
        
        return self._execution_results
    
    async def _execute_single_step(
        self,
        step: PlanStep,
        plan_context: str,
        on_step_start: Optional[Callable] = None,
        on_step_complete: Optional[Callable] = None,
    ) -> StepExecutionResult:
        """Execute a single plan step."""
        # Create subagent for this step
        subagent = PlanStepSubagent(
            step_id=step.id,
            step_description=step.description or "",
            plan_context=plan_context,
            provider=self.provider,
            tools=self.tools,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            max_iterations=self.max_iterations,
            session_key=self.session_key,
            required_skills=step.required_skills,
            required_mcp_tools=step.required_mcp_tools,
        )
        
        self._running_subagents[step.id] = subagent
        
        # Notify start
        if on_step_start:
            await on_step_start(step.id, "tool_call", step.description or "")
        
        # Execute
        result = await subagent.execute()
        
        # Notify complete
        if on_step_complete:
            await on_step_complete(
                step_id=step.id,
                status=result.status.value,
                result=result.result,
                execution_time=result.execution_time,
                logs=result.logs,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
            )
        
        # Clean up
        del self._running_subagents[step.id]
        
        return result
    
    async def _execute_steps_in_parallel(
        self,
        steps: List[PlanStep],
        plan_context: str,
        on_step_start: Optional[Callable] = None,
        on_step_complete: Optional[Callable] = None,
    ) -> Dict[str, StepExecutionResult]:
        """Execute multiple steps in parallel."""
        # Create subagents for all steps
        subagents = {}
        for step in steps:
            subagent = PlanStepSubagent(
                step_id=step.id,
                step_description=step.description or "",
                plan_context=plan_context,
                provider=self.provider,
                tools=self.tools,
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                max_iterations=self.max_iterations,
                session_key=self.session_key,
            )
            subagents[step.id] = subagent
            self._running_subagents[step.id] = subagent
        
        # Create tasks for all steps
        async def execute_step_with_callbacks(step: PlanStep) -> Tuple[str, StepExecutionResult]:
            subagent = subagents[step.id]
            
            # Notify start
            if on_step_start:
                await on_step_start(step.id, "tool_call", step.description or "")
            
            # Execute
            result = await subagent.execute()
            
            # Notify complete
            if on_step_complete:
                await on_step_complete(
                    step_id=step.id,
                    status=result.status.value,
                    result=result.result,
                    execution_time=result.execution_time,
                    logs=result.logs,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                )
            
            return step.id, result
        
        # Execute all steps in parallel
        tasks = [execute_step_with_callbacks(step) for step in steps]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        results = {}
        for item in results_list:
            if isinstance(item, Exception):
                logger.error("Step execution failed with exception: {}", item)
                continue
            step_id, result = item
            results[step_id] = result
            # Clean up
            if step_id in self._running_subagents:
                del self._running_subagents[step_id]
        
        return results
    
    def get_running_subagents(self) -> Dict[str, PlanStepSubagent]:
        """Get all currently running subagents."""
        return self._running_subagents.copy()
    
    def get_execution_results(self) -> Dict[str, StepExecutionResult]:
        """Get all execution results."""
        return self._execution_results.copy()
    
    def get_step_status(self, step_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific step."""
        if step_id in self._running_subagents:
            return self._running_subagents[step_id].get_current_status()
        elif step_id in self._execution_results:
            result = self._execution_results[step_id]
            return {
                "step_id": step_id,
                "status": result.status.value,
                "execution_time": result.execution_time,
                "log_count": len(result.logs),
            }
        return None
