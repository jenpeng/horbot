"""Data models for execution plans."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
import uuid


class PlanStatus(Enum):
    """Status of a plan or step."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(Enum):
    """Status of a single step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PlanType(Enum):
    """Type of plan - informational or actionable."""
    INFORMATIONAL = "informational"  # 信息提供型，如假期建议
    ACTIONABLE = "actionable"  # 任务执行型，如代码重构


@dataclass
class PlanStep:
    """A single step in an execution plan."""
    id: str
    description: str
    tool_name: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    result: str | None = None
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    required_skills: list[str] = field(default_factory=list)
    required_mcp_tools: list[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "description": self.description,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "required_skills": self.required_skills,
            "required_mcp_tools": self.required_mcp_tools,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanStep":
        """Create from dictionary."""
        return cls(
            id=data.get("id", ""),
            description=data.get("description", ""),
            tool_name=data.get("tool_name"),
            parameters=data.get("parameters", {}),
            dependencies=data.get("dependencies", []),
            status=StepStatus(data.get("status", "pending")),
            result=data.get("result"),
            error=data.get("error"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            required_skills=data.get("required_skills", []),
            required_mcp_tools=data.get("required_mcp_tools", []),
        )


@dataclass
class PlanSpec:
    """Specification details for a plan."""
    why: str = ""
    what_changes: list[str] = field(default_factory=list)
    impact: dict[str, Any] = field(default_factory=dict)
    added_requirements: list[dict[str, str]] = field(default_factory=list)
    modified_requirements: list[dict[str, str]] = field(default_factory=list)
    removed_requirements: list[dict[str, str]] = field(default_factory=list)


@dataclass
class PlanChecklistItem:
    """A single checklist item."""
    id: str
    description: str
    category: str = "implementation"
    checked: bool = False


@dataclass
class PlanChecklist:
    """Checklist for plan verification."""
    items: list[PlanChecklistItem] = field(default_factory=list)


@dataclass
class Plan:
    """An execution plan consisting of multiple steps."""
    id: str
    title: str
    description: str
    steps: list[PlanStep] = field(default_factory=list)
    status: PlanStatus = PlanStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: str | None = None
    completed_at: str | None = None
    current_step_index: int = 0
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    spec: PlanSpec = field(default_factory=PlanSpec)
    checklist: PlanChecklist = field(default_factory=PlanChecklist)
    plan_type: PlanType = PlanType.ACTIONABLE  # 规划类型：信息提供型或任务执行型
    content: str = ""  # 规划内容，用于信息提供型规划
    spec_content: str = ""  # spec.md 内容
    tasks_content: str = ""  # tasks.md 内容
    checklist_content: str = ""  # checklist.md 内容
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
        self.total_steps = len(self.steps)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "current_step_index": self.current_step_index,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "metadata": self.metadata,
            "plan_type": self.plan_type.value,
            "content": self.content,
            "spec_content": self.spec_content,
            "tasks_content": self.tasks_content,
            "checklist_content": self.checklist_content,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Plan":
        """Create from dictionary."""
        steps = [PlanStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            steps=steps,
            status=PlanStatus(data.get("status", "pending")),
            created_at=data.get("created_at", datetime.now().isoformat()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            current_step_index=data.get("current_step_index", 0),
            total_steps=data.get("total_steps", len(steps)),
            completed_steps=data.get("completed_steps", 0),
            failed_steps=data.get("failed_steps", 0),
            metadata=data.get("metadata", {}),
            plan_type=PlanType(data.get("plan_type", "actionable")),
            content=data.get("content", ""),
            spec_content=data.get("spec_content", ""),
            tasks_content=data.get("tasks_content", ""),
            checklist_content=data.get("checklist_content", ""),
        )
    
    def get_step(self, step_id: str) -> PlanStep | None:
        """Get a step by ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None
    
    def get_pending_steps(self) -> list[PlanStep]:
        """Get all pending steps whose dependencies are satisfied."""
        completed_ids = {s.id for s in self.steps if s.status == StepStatus.COMPLETED}
        pending = []
        for step in self.steps:
            if step.status != StepStatus.PENDING:
                continue
            if all(dep in completed_ids for dep in step.dependencies):
                pending.append(step)
        return pending
    
    def get_parallel_steps(self) -> list[PlanStep]:
        """Get steps that can be executed in parallel (no dependencies on each other)."""
        pending = self.get_pending_steps()
        if not pending:
            return []
        
        parallel = [pending[0]]
        for step in pending[1:]:
            can_parallel = True
            for existing in parallel:
                if step.id in existing.dependencies or existing.id in step.dependencies:
                    can_parallel = False
                    break
            if can_parallel:
                parallel.append(step)
        
        return parallel
    
    def update_progress(self) -> None:
        """Update progress counters."""
        self.completed_steps = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        self.failed_steps = sum(1 for s in self.steps if s.status == StepStatus.FAILED)
        
        if self.completed_steps + self.failed_steps == self.total_steps:
            if self.failed_steps > 0:
                self.status = PlanStatus.FAILED
            else:
                self.status = PlanStatus.COMPLETED
            self.completed_at = datetime.now().isoformat()
    
    def get_progress_percent(self) -> float:
        """Get completion percentage."""
        if self.total_steps == 0:
            return 0.0
        return (self.completed_steps / self.total_steps) * 100
    
    def format_summary(self) -> str:
        """Format a summary of the plan."""
        lines = [
            f"📋 **Plan: {self.title}**",
            f"",
            f"Status: {self.status.value}",
            f"Progress: {self.completed_steps}/{self.total_steps} ({self.get_progress_percent():.0f}%)",
            f"",
            f"**Steps:**",
        ]
        
        for i, step in enumerate(self.steps):
            status_icon = {
                StepStatus.PENDING: "⏳",
                StepStatus.RUNNING: "🔄",
                StepStatus.COMPLETED: "✅",
                StepStatus.FAILED: "❌",
                StepStatus.SKIPPED: "⏭️",
            }.get(step.status, "❓")
            
            lines.append(f"  {i+1}. {status_icon} {step.description}")
            if step.error:
                lines.append(f"     Error: {step.error[:100]}")
        
        return "\n".join(lines)
