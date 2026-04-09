"""Plan validator for checking feasibility and safety."""

from dataclasses import dataclass
from typing import Any

from horbot.agent.planner.models import Plan, PlanStep
from horbot.agent.tools.permission import PermissionManager, PermissionLevel
from horbot.agent.sandbox import PathGuard, CommandFilter


@dataclass
class ValidationResult:
    """Result of plan validation."""
    valid: bool
    errors: list[str]
    warnings: list[str]
    suggestions: list[str]
    steps_needing_confirmation: list[str]
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
            "steps_needing_confirmation": self.steps_needing_confirmation,
        }


class PlanValidator:
    """
    Validates execution plans for feasibility and safety.
    
    Checks:
    - Tool availability and permissions
    - Parameter validity
    - Dependency graph integrity
    - Security constraints
    """
    
    def __init__(
        self,
        permission_manager: PermissionManager | None = None,
        available_tools: list[str] | None = None,
        workspace: Any = None,
    ):
        self._permission_manager = permission_manager or PermissionManager()
        self._available_tools = set(available_tools or [])
        self._path_guard = PathGuard(workspace) if workspace else None
        self._command_filter = CommandFilter()
    
    def validate(self, plan: Plan) -> ValidationResult:
        """
        Validate a plan for feasibility and safety.
        
        Args:
            plan: The plan to validate
        
        Returns:
            ValidationResult with errors, warnings, and suggestions
        """
        errors = []
        warnings = []
        suggestions = []
        steps_needing_confirmation = []
        
        if not plan.steps:
            errors.append("Plan has no steps")
            return ValidationResult(
                valid=False,
                errors=errors,
                warnings=warnings,
                suggestions=suggestions,
                steps_needing_confirmation=steps_needing_confirmation,
            )
        
        step_ids = {s.id for s in plan.steps}
        
        for step in plan.steps:
            for dep in step.dependencies:
                if dep not in step_ids:
                    errors.append(f"Step '{step.id}' has invalid dependency '{dep}'")
        
            if step.tool_name:
                if self._available_tools and step.tool_name not in self._available_tools:
                    errors.append(f"Step '{step.id}' uses unavailable tool '{step.tool_name}'")
                
                permission = self._permission_manager.check_permission(step.tool_name)
                
                if permission == PermissionLevel.DENY:
                    errors.append(f"Step '{step.id}' uses denied tool '{step.tool_name}'")
                elif permission == PermissionLevel.CONFIRM:
                    steps_needing_confirmation.append(step.id)
                    warnings.append(f"Step '{step.id}' requires user confirmation")
            
            param_errors = self._validate_parameters(step)
            errors.extend(param_errors)
            
            security_warnings = self._check_security(step)
            warnings.extend(security_warnings)
        
        has_cycles = self._check_cycles(plan)
        if has_cycles:
            errors.append("Plan contains circular dependencies")
        
        if len(plan.steps) > 10:
            warnings.append(f"Plan has {len(plan.steps)} steps, consider breaking into smaller plans")
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
            steps_needing_confirmation=steps_needing_confirmation,
        )
    
    def _validate_parameters(self, step: PlanStep) -> list[str]:
        """Validate step parameters."""
        errors = []
        
        if not step.tool_name:
            return errors
        
        params = step.parameters
        
        if step.tool_name in ("read_file", "write_file", "edit_file", "list_dir"):
            path = params.get("path", "")
            if not path:
                errors.append(f"Step '{step.id}': missing 'path' parameter")
            elif self._path_guard:
                allowed, msg = self._path_guard.check_read_access(path)
                if not allowed:
                    errors.append(f"Step '{step.id}': {msg}")
        
        if step.tool_name == "write_file":
            if "content" not in params:
                errors.append(f"Step '{step.id}': missing 'content' parameter for write_file")
        
        if step.tool_name == "edit_file":
            if "old_text" not in params:
                errors.append(f"Step '{step.id}': missing 'old_text' parameter for edit_file")
            if "new_text" not in params:
                errors.append(f"Step '{step.id}': missing 'new_text' parameter for edit_file")
        
        if step.tool_name == "exec":
            command = params.get("command", "")
            if not command:
                errors.append(f"Step '{step.id}': missing 'command' parameter for exec")
            else:
                safe, level, reason = self._command_filter.check_command(command)
                if not safe:
                    errors.append(f"Step '{step.id}': dangerous command - {reason}")
        
        if step.tool_name == "web_search":
            if "query" not in params:
                errors.append(f"Step '{step.id}': missing 'query' parameter for web_search")
        
        if step.tool_name == "web_fetch":
            url = params.get("url", "")
            if not url:
                errors.append(f"Step '{step.id}': missing 'url' parameter for web_fetch")
            elif not url.startswith(("http://", "https://")):
                errors.append(f"Step '{step.id}': invalid URL format")
        
        return errors
    
    def _check_security(self, step: PlanStep) -> list[str]:
        """Check for security concerns."""
        warnings = []
        
        params = step.parameters
        
        if step.tool_name in ("write_file", "edit_file"):
            path = params.get("path", "")
            sensitive_patterns = [".env", "config", "secret", "key", "credential", "password"]
            for pattern in sensitive_patterns:
                if pattern in path.lower():
                    warnings.append(f"Step '{step.id}' modifies potentially sensitive file: {path}")
                    break
        
        if step.tool_name == "exec":
            command = params.get("command", "")
            dangerous_patterns = ["rm ", "del ", "sudo ", "chmod ", "chown ", "> /"]
            for pattern in dangerous_patterns:
                if pattern in command.lower():
                    warnings.append(f"Step '{step.id}' contains potentially dangerous operation: {pattern.strip()}")
                    break
        
        return warnings
    
    def _check_cycles(self, plan: Plan) -> bool:
        """Check for circular dependencies using DFS."""
        step_map = {s.id: s for s in plan.steps}
        visited = set()
        rec_stack = set()
        
        def has_cycle(step_id: str) -> bool:
            visited.add(step_id)
            rec_stack.add(step_id)
            
            step = step_map.get(step_id)
            if step:
                for dep in step.dependencies:
                    if dep not in visited:
                        if has_cycle(dep):
                            return True
                    elif dep in rec_stack:
                        return True
            
            rec_stack.remove(step_id)
            return False
        
        for step in plan.steps:
            if step.id not in visited:
                if has_cycle(step.id):
                    return True
        
        return False
    
    def get_execution_order(self, plan: Plan) -> list[list[PlanStep]]:
        """
        Get the execution order with parallel steps grouped.
        
        Returns a list of batches, where each batch can be executed in parallel.
        """
        if not self.validate(plan).valid:
            return []
        
        remaining = {s.id: s for s in plan.steps}
        completed = set()
        order = []
        
        while remaining:
            batch = []
            to_remove = []
            
            for step_id, step in remaining.items():
                if all(dep in completed for dep in step.dependencies):
                    batch.append(step)
                    to_remove.append(step_id)
            
            if not batch:
                break
            
            order.append(batch)
            
            for step_id in to_remove:
                completed.add(step_id)
                del remaining[step_id]
        
        return order
