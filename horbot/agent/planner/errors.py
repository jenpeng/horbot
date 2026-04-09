"""Error types for the planner module."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PlannerErrorCode(Enum):
    """Error codes for planner operations."""
    GENERATION_FAILED = "generation_failed"
    VALIDATION_FAILED = "validation_failed"
    PARSE_ERROR = "parse_error"
    INVALID_PLAN = "invalid_plan"
    TOOL_UNAVAILABLE = "tool_unavailable"
    PERMISSION_DENIED = "permission_denied"
    DEPENDENCY_ERROR = "dependency_error"
    CYCLE_DETECTED = "cycle_detected"
    EXECUTION_FAILED = "execution_failed"
    TIMEOUT = "timeout"
    PROVIDER_ERROR = "provider_error"
    STRATEGY_ERROR = "strategy_error"


class PlannerError(Exception):
    """Base exception for planner errors."""
    
    def __init__(
        self,
        message: str,
        code: PlannerErrorCode = PlannerErrorCode.GENERATION_FAILED,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.details = details or {}
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.code.value,
            "message": str(self),
            "details": self.details,
        }


class PlanGenerationError(PlannerError):
    """Error during plan generation."""
    
    def __init__(
        self,
        message: str,
        raw_response: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message,
            code=PlannerErrorCode.GENERATION_FAILED,
            details=details,
        )
        self.raw_response = raw_response
    
    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        if self.raw_response:
            result["raw_response"] = self.raw_response[:500]
        return result


class PlanParseError(PlannerError):
    """Error parsing LLM response into a plan."""
    
    def __init__(
        self,
        message: str,
        raw_response: str | None = None,
        parse_position: int | None = None,
    ):
        super().__init__(
            message,
            code=PlannerErrorCode.PARSE_ERROR,
        )
        self.raw_response = raw_response
        self.parse_position = parse_position
    
    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        if self.raw_response:
            result["raw_response"] = self.raw_response[:500]
        if self.parse_position is not None:
            result["parse_position"] = self.parse_position
        return result


class PlanValidationError(PlannerError):
    """Error during plan validation."""
    
    def __init__(
        self,
        message: str,
        errors: list[str] | None = None,
        warnings: list[str] | None = None,
    ):
        super().__init__(
            message,
            code=PlannerErrorCode.VALIDATION_FAILED,
        )
        self.errors = errors or []
        self.warnings = warnings or []
    
    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result["errors"] = self.errors
        result["warnings"] = self.warnings
        return result


class DependencyCycleError(PlannerError):
    """Error when circular dependencies are detected."""
    
    def __init__(
        self,
        message: str,
        cycle_path: list[str] | None = None,
    ):
        super().__init__(
            message,
            code=PlannerErrorCode.CYCLE_DETECTED,
        )
        self.cycle_path = cycle_path or []
    
    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result["cycle_path"] = self.cycle_path
        return result


class ToolUnavailableError(PlannerError):
    """Error when a required tool is not available."""
    
    def __init__(
        self,
        tool_name: str,
        step_id: str | None = None,
    ):
        super().__init__(
            f"Tool '{tool_name}' is not available",
            code=PlannerErrorCode.TOOL_UNAVAILABLE,
            details={"tool_name": tool_name, "step_id": step_id},
        )
        self.tool_name = tool_name
        self.step_id = step_id


class PermissionDeniedError(PlannerError):
    """Error when permission is denied for an operation."""
    
    def __init__(
        self,
        operation: str,
        resource: str | None = None,
        reason: str | None = None,
    ):
        super().__init__(
            f"Permission denied for operation '{operation}'",
            code=PlannerErrorCode.PERMISSION_DENIED,
            details={
                "operation": operation,
                "resource": resource,
                "reason": reason,
            },
        )
        self.operation = operation
        self.resource = resource
        self.reason = reason


class StrategyError(PlannerError):
    """Error in planning strategy execution."""
    
    def __init__(
        self,
        strategy_name: str,
        message: str,
        original_error: Exception | None = None,
    ):
        super().__init__(
            f"Strategy '{strategy_name}' failed: {message}",
            code=PlannerErrorCode.STRATEGY_ERROR,
            details={"strategy_name": strategy_name},
        )
        self.strategy_name = strategy_name
        self.original_error = original_error


@dataclass
class ErrorContext:
    """Context for error reporting and recovery."""
    operation: str
    step_id: str | None = None
    plan_id: str | None = None
    timestamp: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    recoverable: bool = True
    recovery_suggestions: list[str] = field(default_factory=list)
    
    def add_suggestion(self, suggestion: str) -> None:
        self.recovery_suggestions.append(suggestion)
    
    def can_retry(self) -> bool:
        return self.recoverable and self.retry_count < self.max_retries


class ErrorRecovery:
    """Handles error recovery strategies."""
    
    @staticmethod
    def get_recovery_suggestions(error: PlannerError) -> list[str]:
        """Get recovery suggestions for an error."""
        suggestions = []
        
        if error.code == PlannerErrorCode.GENERATION_FAILED:
            suggestions.extend([
                "Try simplifying the task description",
                "Break the task into smaller subtasks",
                "Use a rule-based strategy instead",
            ])
        
        elif error.code == PlannerErrorCode.PARSE_ERROR:
            suggestions.extend([
                "Check the LLM response format",
                "Try with a different model",
                "Use a simpler prompt template",
            ])
        
        elif error.code == PlannerErrorCode.VALIDATION_FAILED:
            suggestions.extend([
                "Review the validation errors",
                "Fix the identified issues",
                "Simplify the plan structure",
            ])
        
        elif error.code == PlannerErrorCode.CYCLE_DETECTED:
            suggestions.extend([
                "Review step dependencies",
                "Remove circular references",
                "Restructure the plan order",
            ])
        
        elif error.code == PlannerErrorCode.TOOL_UNAVAILABLE:
            suggestions.extend([
                "Check if the tool is registered",
                "Use an alternative tool",
                "Skip steps that require unavailable tools",
            ])
        
        elif error.code == PlannerErrorCode.PERMISSION_DENIED:
            suggestions.extend([
                "Check permission settings",
                "Request user confirmation",
                "Use a different approach",
            ])
        
        return suggestions
    
    @staticmethod
    def should_retry(error: PlannerError) -> bool:
        """Determine if the operation should be retried."""
        retryable_codes = {
            PlannerErrorCode.TIMEOUT,
            PlannerErrorCode.PROVIDER_ERROR,
        }
        return error.code in retryable_codes
    
    @staticmethod
    def get_fallback_strategy(error: PlannerError) -> str | None:
        """Get a fallback strategy name for the error."""
        if error.code in {
            PlannerErrorCode.GENERATION_FAILED,
            PlannerErrorCode.PARSE_ERROR,
            PlannerErrorCode.PROVIDER_ERROR,
        }:
            return "rule_based"
        return None
