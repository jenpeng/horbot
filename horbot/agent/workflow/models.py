"""Workflow definition models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StepType(Enum):
    """Types of workflow steps."""
    ACTION = "action"
    CONDITION = "condition"
    LOOP = "loop"
    PARALLEL = "parallel"


@dataclass
class WorkflowStep:
    """A single step in a workflow."""
    id: str
    name: str
    type: StepType = StepType.ACTION
    tool: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    condition: str | None = None
    loop_var: str | None = None
    loop_over: str | None = None
    steps: list["WorkflowStep"] = field(default_factory=list)
    on_success: str | None = None
    on_failure: str | None = None
    retry_count: int = 0
    timeout: int = 300
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "tool": self.tool,
            "parameters": self.parameters,
            "condition": self.condition,
            "loop_var": self.loop_var,
            "loop_over": self.loop_over,
            "steps": [s.to_dict() for s in self.steps],
            "on_success": self.on_success,
            "on_failure": self.on_failure,
            "retry_count": self.retry_count,
            "timeout": self.timeout,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowStep":
        """Create from dictionary."""
        steps = [WorkflowStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            type=StepType(data.get("type", "action")),
            tool=data.get("tool"),
            parameters=data.get("parameters", {}),
            condition=data.get("condition"),
            loop_var=data.get("loop_var"),
            loop_over=data.get("loop_over"),
            steps=steps,
            on_success=data.get("on_success"),
            on_failure=data.get("on_failure"),
            retry_count=data.get("retry_count", 0),
            timeout=data.get("timeout", 300),
        )


@dataclass
class WorkflowVariable:
    """A variable in a workflow."""
    name: str
    default: Any = None
    description: str = ""
    required: bool = False
    type: str = "string"
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "default": self.default,
            "description": self.description,
            "required": self.required,
            "type": self.type,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowVariable":
        return cls(
            name=data.get("name", ""),
            default=data.get("default"),
            description=data.get("description", ""),
            required=data.get("required", False),
            type=data.get("type", "string"),
        )


@dataclass
class Workflow:
    """A complete workflow definition."""
    id: str
    name: str
    description: str = ""
    version: str = "1.0"
    variables: list[WorkflowVariable] = field(default_factory=list)
    steps: list[WorkflowStep] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "variables": [v.to_dict() for v in self.variables],
            "steps": [s.to_dict() for s in self.steps],
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Workflow":
        """Create from dictionary."""
        variables = [WorkflowVariable.from_dict(v) for v in data.get("variables", [])]
        steps = [WorkflowStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            variables=variables,
            steps=steps,
            metadata=data.get("metadata", {}),
        )
    
    def get_required_variables(self) -> list[str]:
        """Get list of required variable names."""
        return [v.name for v in self.variables if v.required]
    
    def validate_variables(self, provided: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate that all required variables are provided."""
        errors = []
        for var in self.variables:
            if var.required and var.name not in provided:
                errors.append(f"Required variable '{var.name}' not provided")
        return len(errors) == 0, errors
    
    def resolve_variables(self, context: dict[str, Any]) -> dict[str, Any]:
        """Resolve variables with defaults and provided values."""
        resolved = {}
        for var in self.variables:
            if var.name in context:
                resolved[var.name] = context[var.name]
            elif var.default is not None:
                resolved[var.name] = var.default
        return resolved
