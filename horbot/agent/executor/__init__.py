"""Plan executor for running multi-step plans with full monitoring."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from horbot.agent.planner.models import Plan, PlanStep, PlanStatus, StepStatus
from horbot.agent.planner.validator import PlanValidator
from horbot.agent.tools.registry import ToolRegistry
from horbot.agent.audit import AuditLogger, get_audit_logger
from horbot.agent.executor.state import StateManager, ExecutionState
from horbot.agent.executor.checkpoint import CheckpointManager, register_default_rollback_handlers


@dataclass
class ExecutionProgress:
    """Progress information for plan execution."""
    plan_id: str
    total_steps: int
    completed_steps: int
    failed_steps: int
    current_step: str | None
    status: PlanStatus
    started_at: str | None = None
    estimated_remaining_seconds: int | None = None
    
    @property
    def percent_complete(self) -> float:
        if self.total_steps == 0:
            return 0.0
        return (self.completed_steps / self.total_steps) * 100


@dataclass
class ExecutionResult:
    """Result of plan execution."""
    success: bool
    plan: Plan
    message: str
    execution_time_seconds: float = 0.0
    steps_executed: int = 0
    steps_failed: int = 0


class PlanExecutor:
    """
    Executes multi-step plans with monitoring and error handling.
    
    Features:
    - Sequential and parallel step execution
    - Progress tracking and reporting
    - Error recovery with retries
    - Timeout handling
    - Audit logging
    - State persistence and recovery
    - Checkpoint-based rollback
    """
    
    def __init__(
        self,
        tool_registry: ToolRegistry,
        validator: PlanValidator | None = None,
        audit_logger: AuditLogger | None = None,
        max_retries: int = 3,
        step_timeout: int = 300,
        total_timeout: int = 3600,
        confirm_callback: Callable[[str, dict], Awaitable[bool]] | None = None,
        progress_callback: Callable[[ExecutionProgress], Awaitable[None]] | None = None,
        state_dir: Path | str | None = None,
        checkpoint_dir: Path | str | None = None,
    ):
        self._tools = tool_registry
        self._validator = validator or PlanValidator()
        self._audit = audit_logger or get_audit_logger()
        self._max_retries = max_retries
        self._step_timeout = step_timeout
        self._total_timeout = total_timeout
        self._confirm_callback = confirm_callback
        self._progress_callback = progress_callback
        
        self._state_manager = StateManager(state_dir=state_dir)
        self._checkpoint_manager = CheckpointManager(checkpoint_dir=checkpoint_dir)
        
        register_default_rollback_handlers(self._checkpoint_manager)
        
        self._running_plans: dict[str, asyncio.Task] = {}
        self._paused_plans: set[str] = set()
        self._plan_states: dict[str, ExecutionState] = {}
    
    async def execute(
        self,
        plan: Plan,
        session_id: str | None = None,
        auto_confirm: bool = False,
        resume_from: str | None = None,
    ) -> ExecutionResult:
        """
        Execute a plan step by step.
        
        Args:
            plan: The plan to execute
            session_id: Optional session ID for audit logging
            auto_confirm: If True, automatically confirm steps needing confirmation
            resume_from: Optional state ID to resume from
        
        Returns:
            ExecutionResult with outcome details
        """
        start_time = datetime.now()
        plan.status = PlanStatus.RUNNING
        plan.started_at = start_time.isoformat()
        
        validation = self._validator.validate(plan)
        if not validation.valid:
            return ExecutionResult(
                success=False,
                plan=plan,
                message=f"Plan validation failed: {'; '.join(validation.errors)}",
            )
        
        steps_needing_confirmation = set(validation.steps_needing_confirmation)
        
        state_id = resume_from
        if not state_id:
            state = self._state_manager.create_state(
                plan_data=plan.to_dict(),
                metadata={"session_id": session_id},
            )
            state_id = state.id
            self._plan_states[state_id] = state
        
        self._state_manager.mark_started(state_id)
        
        try:
            execution_order = self._validator.get_execution_order(plan)
            
            for batch in execution_order:
                if plan.status == PlanStatus.CANCELLED:
                    break
                
                while plan.id in self._paused_plans:
                    await asyncio.sleep(0.5)
                    if plan.status == PlanStatus.CANCELLED:
                        break
                
                if len(batch) == 1:
                    await self._execute_step(
                        batch[0], plan, steps_needing_confirmation,
                        auto_confirm, session_id, state_id
                    )
                else:
                    tasks = [
                        self._execute_step(
                            step, plan, steps_needing_confirmation,
                            auto_confirm, session_id, state_id
                        )
                        for step in batch
                    ]
                    await asyncio.gather(*tasks)
                
                plan.update_progress()
                
                if self._progress_callback:
                    progress = self._get_progress(plan, state_id)
                    await self._progress_callback(progress)
            
            plan.update_progress()
            
        except asyncio.CancelledError:
            plan.status = PlanStatus.CANCELLED
            self._state_manager.mark_paused(state_id)
            raise
        except Exception as e:
            plan.status = PlanStatus.FAILED
            self._state_manager.mark_completed(state_id, success=False)
            return ExecutionResult(
                success=False,
                plan=plan,
                message=f"Execution failed: {str(e)}",
            )
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        if plan.status == PlanStatus.COMPLETED:
            self._state_manager.mark_completed(state_id, success=True)
            return ExecutionResult(
                success=True,
                plan=plan,
                message=f"Plan completed successfully. {plan.completed_steps}/{plan.total_steps} steps executed.",
                execution_time_seconds=execution_time,
                steps_executed=plan.completed_steps,
                steps_failed=plan.failed_steps,
            )
        else:
            return ExecutionResult(
                success=False,
                plan=plan,
                message=f"Plan {plan.status.value}. {plan.completed_steps}/{plan.total_steps} steps executed.",
                execution_time_seconds=execution_time,
                steps_executed=plan.completed_steps,
                steps_failed=plan.failed_steps,
            )
    
    async def _execute_step(
        self,
        step: PlanStep,
        plan: Plan,
        steps_needing_confirmation: set[str],
        auto_confirm: bool,
        session_id: str | None,
        state_id: str,
    ) -> None:
        """Execute a single step with retries, checkpoints, and error handling."""
        step.status = StepStatus.RUNNING
        step.started_at = datetime.now().isoformat()
        
        if not step.tool_name:
            step.status = StepStatus.COMPLETED
            step.result = "Step completed (no tool execution required)"
            step.completed_at = datetime.now().isoformat()
            self._state_manager.update_state(
                state_id,
                step_result=(step.id, step.result),
            )
            return
        
        if step.id in steps_needing_confirmation and self._confirm_callback and not auto_confirm:
            confirmed = await self._confirm_callback(step.id, {
                "description": step.description,
                "tool": step.tool_name,
                "parameters": step.parameters,
            })
            if not confirmed:
                step.status = StepStatus.SKIPPED
                step.error = "User declined confirmation"
                step.completed_at = datetime.now().isoformat()
                self._state_manager.update_state(
                    state_id,
                    step_error=(step.id, step.error),
                )
                return
        
        for attempt in range(step.max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    self._tools.execute(step.tool_name, step.parameters),
                    timeout=self._step_timeout,
                )
                
                if result.startswith("Error:"):
                    if attempt < step.max_retries:
                        step.retry_count += 1
                        await asyncio.sleep(2 ** attempt)
                        continue
                    
                    step.status = StepStatus.FAILED
                    step.error = result
                    step.completed_at = datetime.now().isoformat()
                    self._state_manager.update_state(
                        state_id,
                        step_error=(step.id, step.error),
                    )
                else:
                    step.status = StepStatus.COMPLETED
                    step.result = result
                    step.completed_at = datetime.now().isoformat()
                    self._state_manager.update_state(
                        state_id,
                        step_result=(step.id, step.result),
                    )
                
                self._audit.log(
                    tool_name=step.tool_name,
                    params=step.parameters,
                    result=step.result,
                    error=step.error,
                    session_id=session_id,
                )
                
                return
                
            except asyncio.TimeoutError:
                step.retry_count += 1
                if attempt >= step.max_retries:
                    step.status = StepStatus.FAILED
                    step.error = f"Step timed out after {self._step_timeout} seconds"
                    step.completed_at = datetime.now().isoformat()
                    self._state_manager.update_state(
                        state_id,
                        step_error=(step.id, step.error),
                    )
                    return
                await asyncio.sleep(2 ** attempt)
            
            except Exception as e:
                step.retry_count += 1
                if attempt >= step.max_retries:
                    step.status = StepStatus.FAILED
                    step.error = str(e)
                    step.completed_at = datetime.now().isoformat()
                    self._state_manager.update_state(
                        state_id,
                        step_error=(step.id, step.error),
                    )
                    return
                await asyncio.sleep(2 ** attempt)
    
    def _get_progress(self, plan: Plan, state_id: str) -> ExecutionProgress:
        """Get current execution progress."""
        state = self._plan_states.get(state_id)
        current_step = None
        if state:
            for step in plan.steps:
                if step.id == plan.steps[state.current_step_index].id if state.current_step_index < len(plan.steps) else None:
                    if step.status == StepStatus.RUNNING:
                        current_step = step.description
                        break
        
        return ExecutionProgress(
            plan_id=plan.id,
            total_steps=plan.total_steps,
            completed_steps=plan.completed_steps,
            failed_steps=plan.failed_steps,
            current_step=current_step,
            status=plan.status,
            started_at=state.started_at if state else None,
        )
    
    def pause(self, plan_id: str) -> bool:
        """Pause a running plan."""
        if plan_id in self._running_plans:
            self._paused_plans.add(plan_id)
            for state_id, state in self._plan_states.items():
                if state.plan_id == plan_id:
                    self._state_manager.mark_paused(state_id)
            return True
        return False
    
    def resume(self, plan_id: str) -> bool:
        """Resume a paused plan."""
        if plan_id in self._paused_plans:
            self._paused_plans.discard(plan_id)
            
            for state_id, state in self._plan_states.items():
                if state.plan_id == plan_id:
                    self._state_manager.mark_started(state_id)
            return True
        return False
    
    def cancel(self, plan_id: str) -> bool:
        """Cancel a running plan."""
        if plan_id in self._running_plans:
            task = self._running_plans[plan_id]
            task.cancel()
            return True
        return False
    
    def get_status(self, plan_id: str) -> ExecutionProgress | None:
        """Get current status of a plan."""
        for state_id, state in self._plan_states.items():
            if state.plan_id == plan_id:
                return self._get_progress(state.plan, state_id)
        return None
    
    def get_active_plans(self) -> list[ExecutionState]:
        """Get all active plan states."""
        return list(self._plan_states.values())
    
    def cleanup_old_states(self, max_age_hours: int = 24) -> int:
        """Clean up old execution states."""
        return self._state_manager.cleanup_completed(max_age_hours)
