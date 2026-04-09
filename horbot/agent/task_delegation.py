"""Task delegation for multi-agent system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import uuid

from loguru import logger

from horbot.agent.team_protocols import (
    ActionType,
    AgentMessage,
    TeamCoordinator,
)


@dataclass
class DelegatedTask:
    """Represents a delegated task."""
    id: str
    description: str
    target_agent_id: str
    source_agent_id: str
    status: str = "pending"
    result: Any = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    context: dict = field(default_factory=dict)
    priority: str = "normal"


class TaskDelegator:
    """Handles task delegation between agents.
    
    Responsibilities:
    - Delegate tasks to specific agents
    - Track delegated task status
    - Collect and aggregate results
    """
    
    _instance: Optional["TaskDelegator"] = None
    
    def __new__(cls, coordinator: TeamCoordinator | None = None) -> "TaskDelegator":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._coordinator = coordinator
            cls._instance._delegated_tasks: dict[str, DelegatedTask] = {}
            cls._instance._initialized = False
        return cls._instance
    
    @classmethod
    def get_instance(cls) -> "TaskDelegator":
        return cls()
    
    def initialize(self, coordinator: TeamCoordinator) -> None:
        """Initialize with a coordinator."""
        if self._initialized:
            return
        self._coordinator = coordinator
        self._initialized = True
    
    async def delegate_task(
        self,
        description: str,
        target_agent_id: str,
        source_agent_id: str,
        context: dict | None = None,
        priority: str = "normal",
    ) -> str:
        """Delegate a task to another agent.
        
        Args:
            description: Task description
            target_agent_id: Target agent ID
            source_agent_id: Source agent ID
            context: Additional context
            priority: Task priority
            
        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())[:8]
        
        task = DelegatedTask(
            id=task_id,
            description=description,
            target_agent_id=target_agent_id,
            source_agent_id=source_agent_id,
            context=context or {},
            priority=priority,
        )
        
        self._delegated_tasks[task_id] = task
        
        if self._coordinator:
            message = AgentMessage(
                sender=source_agent_id,
                receiver=target_agent_id,
                action=ActionType.TASK_ASSIGN,
                payload={
                    "task_id": task_id,
                    "description": description,
                    "context": context or {},
                    "priority": priority,
                }
            )
            await self._coordinator.send_message(message)
        
        logger.info(f"Delegated task {task_id} to {target_agent_id}")
        return task_id
    
    async def delegate_to_capability(
        self,
        description: str,
        required_capability: str,
        source_agent_id: str,
        context: dict | None = None,
    ) -> str | None:
        """Delegate a task to an agent with specific capability.
        
        Args:
            description: Task description
            required_capability: Required capability
            source_agent_id: Source agent ID
            context: Additional context
            
        Returns:
            Task ID or None if no capable agent
        """
        if not self._coordinator:
            logger.warning("No coordinator set for delegation")
            return None
        
        capable_agents = self._coordinator.find_capable_agents({required_capability})
        idle_agents = self._coordinator.get_idle_agents()
        
        available = [a for a in capable_agents if a in idle_agents and a != source_agent_id]
        
        if not available:
            logger.warning(f"No available agent with capability: {required_capability}")
            return None
        
        return await self.delegate_task(
            description=description,
            target_agent_id=available[0],
            source_agent_id=source_agent_id,
            context=context,
        )
    
    def get_task(self, task_id: str) -> DelegatedTask | None:
        """Get a delegated task by ID."""
        return self._delegated_tasks.get(task_id)
    
    def complete_task(self, task_id: str, result: Any) -> bool:
        """Mark a task as completed with result."""
        task = self._delegated_tasks.get(task_id)
        if task:
            task.status = "completed"
            task.result = result
            task.completed_at = datetime.now()
            logger.info(f"Task {task_id} completed")
            return True
        return False
    
    async def complete_task_async(self, task_id: str, result: Any) -> bool:
        """Mark a task as completed with result (async version)."""
        return self.complete_task(task_id, result)
    
    def fail_task(self, task_id: str, error: str) -> bool:
        """Mark a task as failed."""
        task = self._delegated_tasks.get(task_id)
        if task:
            task.status = "failed"
            task.error = error
            task.completed_at = datetime.now()
            logger.warning(f"Task {task_id} failed: {error}")
            return True
        return False
    
    def get_pending_tasks(self) -> list[DelegatedTask]:
        """Get all pending tasks."""
        return [t for t in self._delegated_tasks.values() if t.status == "pending"]
    
    def get_completed_tasks(self) -> list[DelegatedTask]:
        """Get all completed tasks."""
        return [t for t in self._delegated_tasks.values() if t.status == "completed"]
    
    def get_failed_tasks(self) -> list[DelegatedTask]:
        """Get all failed tasks."""
        return [t for t in self._delegated_tasks.values() if t.status == "failed"]
    
    def get_tasks_for_agent(self, agent_id: str) -> list[DelegatedTask]:
        """Get all tasks for a specific agent."""
        return [t for t in self._delegated_tasks.values() if t.target_agent_id == agent_id]
    
    def get_tasks_from_agent(self, agent_id: str) -> list[DelegatedTask]:
        """Get all tasks from a specific agent."""
        return [t for t in self._delegated_tasks.values() if t.source_agent_id == agent_id]
    
    def aggregate_results(self) -> dict[str, Any]:
        """Aggregate results from all completed tasks."""
        completed = self.get_completed_tasks()
        return {
            task.id: {
                "result": task.result,
                "target_agent": task.target_agent_id,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            }
            for task in completed
            if task.result is not None
        }
    
    def get_status_summary(self) -> dict[str, int]:
        """Get summary of task statuses."""
        return {
            "pending": len(self.get_pending_tasks()),
            "completed": len(self.get_completed_tasks()),
            "failed": len(self.get_failed_tasks()),
            "total": len(self._delegated_tasks),
        }
    
    def clear_completed(self) -> int:
        """Clear completed and failed tasks.
        
        Returns:
            Number of tasks cleared
        """
        to_remove = [
            task_id for task_id, task in self._delegated_tasks.items()
            if task.status in ("completed", "failed")
        ]
        for task_id in to_remove:
            del self._delegated_tasks[task_id]
        return len(to_remove)


def get_task_delegator() -> TaskDelegator:
    """Get the singleton TaskDelegator instance."""
    return TaskDelegator.get_instance()


class SmartTaskRouter:
    """Intelligent task routing for master+specialist mode.
    
    Features:
    - Analyze task requirements and match to best agent
    - Decompose complex tasks into subtasks
    - Load balance across agents
    - Track agent performance metrics
    """
    
    _instance: Optional["SmartTaskRouter"] = None
    
    def __new__(cls) -> "SmartTaskRouter":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agent_metrics: dict[str, dict] = {}
            cls._instance._task_patterns: dict[str, list[str]] = {}
            cls._instance._initialized = False
        return cls._instance
    
    @classmethod
    def get_instance(cls) -> "SmartTaskRouter":
        return cls()
    
    def initialize(self) -> None:
        """Initialize the router."""
        if self._initialized:
            return
        self._agent_metrics = {}
        self._task_patterns = {}
        self._initialized = True
    
    def analyze_task(self, description: str, context: dict | None = None) -> dict:
        """Analyze a task to determine requirements.
        
        Returns:
            Dict with required capabilities, complexity, and suggested approach
        """
        description_lower = description.lower()
        
        capability_keywords = {
            "code": ["代码", "code", "编程", "programming", "函数", "function", "调试", "debug", "重构", "refactor"],
            "research": ["研究", "research", "分析", "analysis", "调查", "investigate", "搜索", "search"],
            "writing": ["写作", "writing", "文档", "document", "文章", "article", "报告", "report"],
            "data": ["数据", "data", "统计", "statistics", "分析", "analysis", "可视化", "visualization"],
            "planning": ["计划", "plan", "规划", "规划", "策略", "strategy", "安排", "schedule"],
            "communication": ["沟通", "communicate", "回复", "reply", "邮件", "email", "消息", "message"],
            "testing": ["测试", "test", "验证", "verify", "检查", "check", "qa"],
            "design": ["设计", "design", "ui", "ux", "界面", "interface", "原型", "prototype"],
        }
        
        detected_capabilities = []
        for capability, keywords in capability_keywords.items():
            if any(kw in description_lower for kw in keywords):
                detected_capabilities.append(capability)
        
        complexity = "simple"
        word_count = len(description.split())
        if word_count > 50 or len(detected_capabilities) > 2:
            complexity = "complex"
        elif word_count > 20 or len(detected_capabilities) > 1:
            complexity = "medium"
        
        return {
            "required_capabilities": detected_capabilities,
            "complexity": complexity,
            "word_count": word_count,
            "suggested_approach": "decompose" if complexity == "complex" else "direct",
        }
    
    def find_best_agent(
        self,
        task_analysis: dict,
        available_agents: list[dict],
        exclude_agents: list[str] | None = None,
    ) -> str | None:
        """Find the best agent for a task based on analysis.
        
        Args:
            task_analysis: Result from analyze_task
            available_agents: List of agent dicts with id, capabilities, is_main
            exclude_agents: Agent IDs to exclude
            
        Returns:
            Best agent ID or None
        """
        exclude_agents = exclude_agents or []
        required_caps = set(task_analysis.get("required_capabilities", []))
        
        candidates = [
            a for a in available_agents
            if a.get("id") not in exclude_agents
        ]
        
        if not candidates:
            return None
        
        if not required_caps:
            main_agents = [a for a in candidates if a.get("is_main")]
            if main_agents:
                return main_agents[0].get("id")
            return candidates[0].get("id")
        
        scored_candidates = []
        for agent in candidates:
            agent_caps = set(agent.get("capabilities", []))
            match_score = len(required_caps & agent_caps)
            
            performance_score = self._agent_metrics.get(agent.get("id", ""), {}).get("success_rate", 0.5)
            
            load_score = 1.0 - self._agent_metrics.get(agent.get("id", ""), {}).get("current_load", 0)
            
            total_score = match_score * 10 + performance_score * 5 + load_score * 3
            
            if agent.get("is_main"):
                total_score -= 2
            
            scored_candidates.append((agent.get("id"), total_score))
        
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        
        return scored_candidates[0][0] if scored_candidates else None
    
    def decompose_task(
        self,
        description: str,
        task_analysis: dict,
        available_agents: list[dict],
    ) -> list[dict]:
        """Decompose a complex task into subtasks.
        
        Returns:
            List of subtask dicts with description and suggested agent
        """
        if task_analysis.get("complexity") != "complex":
            return [{
                "description": description,
                "agent_id": self.find_best_agent(task_analysis, available_agents),
            }]
        
        subtasks = []
        capabilities = task_analysis.get("required_capabilities", [])
        
        if "planning" in capabilities:
            subtasks.append({
                "description": f"制定计划: {description}",
                "capability": "planning",
                "agent_id": self.find_best_agent(
                    {"required_capabilities": ["planning"]},
                    available_agents
                ),
            })
        
        if "research" in capabilities:
            subtasks.append({
                "description": f"研究分析: {description}",
                "capability": "research",
                "agent_id": self.find_best_agent(
                    {"required_capabilities": ["research"]},
                    available_agents,
                    exclude_agents=[s.get("agent_id") for s in subtasks if s.get("agent_id")]
                ),
            })
        
        if "code" in capabilities:
            subtasks.append({
                "description": f"代码实现: {description}",
                "capability": "code",
                "agent_id": self.find_best_agent(
                    {"required_capabilities": ["code"]},
                    available_agents,
                    exclude_agents=[s.get("agent_id") for s in subtasks if s.get("agent_id")]
                ),
            })
        
        if "testing" in capabilities:
            subtasks.append({
                "description": f"测试验证: {description}",
                "capability": "testing",
                "agent_id": self.find_best_agent(
                    {"required_capabilities": ["testing"]},
                    available_agents,
                    exclude_agents=[s.get("agent_id") for s in subtasks if s.get("agent_id")]
                ),
            })
        
        if not subtasks:
            main_agent = next((a for a in available_agents if a.get("is_main")), None)
            subtasks.append({
                "description": description,
                "agent_id": main_agent.get("id") if main_agent else None,
            })
        
        return subtasks
    
    def update_agent_metrics(
        self,
        agent_id: str,
        task_completed: bool,
        execution_time: float | None = None,
    ) -> None:
        """Update performance metrics for an agent."""
        if agent_id not in self._agent_metrics:
            self._agent_metrics[agent_id] = {
                "total_tasks": 0,
                "successful_tasks": 0,
                "failed_tasks": 0,
                "total_time": 0.0,
                "success_rate": 0.5,
                "current_load": 0.0,
            }
        
        metrics = self._agent_metrics[agent_id]
        metrics["total_tasks"] += 1
        
        if task_completed:
            metrics["successful_tasks"] += 1
        else:
            metrics["failed_tasks"] += 1
        
        if execution_time:
            metrics["total_time"] += execution_time
        
        metrics["success_rate"] = metrics["successful_tasks"] / metrics["total_tasks"]
    
    def increment_agent_load(self, agent_id: str) -> None:
        """Increment the current load for an agent."""
        if agent_id not in self._agent_metrics:
            self._agent_metrics[agent_id] = {"current_load": 0.0}
        self._agent_metrics[agent_id]["current_load"] = min(
            1.0,
            self._agent_metrics[agent_id].get("current_load", 0) + 0.2
        )
    
    def decrement_agent_load(self, agent_id: str) -> None:
        """Decrement the current load for an agent."""
        if agent_id in self._agent_metrics:
            self._agent_metrics[agent_id]["current_load"] = max(
                0.0,
                self._agent_metrics[agent_id].get("current_load", 0) - 0.2
            )
    
    def get_agent_metrics(self, agent_id: str) -> dict:
        """Get metrics for a specific agent."""
        return self._agent_metrics.get(agent_id, {
            "total_tasks": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "success_rate": 0.5,
            "current_load": 0.0,
        })
    
    def get_all_metrics(self) -> dict[str, dict]:
        """Get all agent metrics."""
        return self._agent_metrics.copy()


def get_smart_router() -> SmartTaskRouter:
    """Get the singleton SmartTaskRouter instance."""
    return SmartTaskRouter.get_instance()
