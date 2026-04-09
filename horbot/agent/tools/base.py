"""Base class for agent tools."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class ToolCategory(Enum):
    """Categories for tool classification."""
    FILESYSTEM = "filesystem"
    WEB = "web"
    RUNTIME = "runtime"
    AUTOMATION = "automation"
    MESSAGING = "messaging"
    MCP = "mcp"
    OTHER = "other"


class ToolError(Exception):
    """Base exception for tool execution errors."""
    
    def __init__(self, message: str, tool_name: str = "", recoverable: bool = True):
        self.message = message
        self.tool_name = tool_name
        self.recoverable = recoverable
        super().__init__(self.message)
    
    def to_result(self) -> str:
        """Convert error to tool result string."""
        hint = "\n\n[Analyze the error above and try a different approach.]" if self.recoverable else ""
        return f"Error: {self.message}{hint}"


class ValidationError(ToolError):
    """Raised when tool parameters validation fails."""
    
    def __init__(self, errors: list[str], tool_name: str = ""):
        self.errors = errors
        message = f"Invalid parameters: {'; '.join(errors)}"
        super().__init__(message, tool_name, recoverable=True)


class PermissionError(ToolError):
    """Raised when tool execution is denied by permission policy."""
    
    def __init__(self, message: str, tool_name: str = ""):
        super().__init__(message, tool_name, recoverable=False)


class ExecutionError(ToolError):
    """Raised when tool execution fails."""
    
    def __init__(self, message: str, tool_name: str = "", recoverable: bool = True):
        super().__init__(message, tool_name, recoverable)


@dataclass
class ToolMetadata:
    """Metadata for tool registration and display."""
    name: str
    description: str
    category: ToolCategory = ToolCategory.OTHER
    tags: list[str] = field(default_factory=list)
    requires_confirmation: bool = False
    dangerous: bool = False
    version: str = "1.0.0"
    author: str = ""
    examples: list[dict[str, Any]] = field(default_factory=list)


class Tool(ABC):
    """
    Abstract base class for agent tools.
    
    Tools are capabilities that the agent can use to interact with
    the environment, such as reading files, executing commands, etc.
    
    All tools must implement:
    - name: Unique identifier for the tool
    - description: Human-readable description
    - parameters: JSON Schema for parameters
    - execute: Async execution method
    
    Optional overrides:
    - metadata: Tool metadata for registration
    - validate_params: Custom parameter validation
    - on_error: Custom error handling
    """
    
    _TYPE_MAP = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name used in function calls."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what the tool does."""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema for tool parameters."""
        pass
    
    @property
    def metadata(self) -> ToolMetadata:
        """Tool metadata for registration and display."""
        return ToolMetadata(
            name=self.name,
            description=self.description,
        )
    
    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """
        Execute the tool with given parameters.
        
        Args:
            **kwargs: Tool-specific parameters.
        
        Returns:
            String result of the tool execution.
        """
        pass
    
    async def safe_execute(self, **kwargs: Any) -> str:
        """
        Execute the tool with error handling wrapper.
        
        This method wraps execute() with standardized error handling.
        Override on_error() for custom error handling behavior.
        
        Args:
            **kwargs: Tool-specific parameters.
        
        Returns:
            String result of the tool execution or error message.
        """
        try:
            errors = self.validate_params(kwargs)
            if errors:
                raise ValidationError(errors, self.name)
            
            result = await self.execute(**kwargs)
            
            if isinstance(result, str) and result.startswith("Error"):
                raise ExecutionError(result[6:].strip(), self.name)
            
            return result
        except ToolError as e:
            return self.on_error(e)
        except Exception as e:
            error = ExecutionError(str(e), self.name)
            return self.on_error(error)
    
    def on_error(self, error: ToolError) -> str:
        """
        Handle tool execution errors.
        
        Override this method to customize error handling behavior.
        
        Args:
            error: The tool error that occurred.
        
        Returns:
            Error message string to return to the agent.
        """
        return error.to_result()

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate tool parameters against JSON schema. Returns error list (empty if valid)."""
        schema = self.parameters or {}
        if schema.get("type", "object") != "object":
            raise ValueError(f"Schema must be object type, got {schema.get('type')!r}")
        return self._validate(params, {**schema, "type": "object"}, "")

    def _validate(self, val: Any, schema: dict[str, Any], path: str) -> list[str]:
        t, label = schema.get("type"), path or "parameter"
        if t in self._TYPE_MAP and not isinstance(val, self._TYPE_MAP[t]):
            return [f"{label} should be {t}"]
        
        errors = []
        if "enum" in schema and val not in schema["enum"]:
            errors.append(f"{label} must be one of {schema['enum']}")
        if t in ("integer", "number"):
            if "minimum" in schema and val < schema["minimum"]:
                errors.append(f"{label} must be >= {schema['minimum']}")
            if "maximum" in schema and val > schema["maximum"]:
                errors.append(f"{label} must be <= {schema['maximum']}")
        if t == "string":
            if "minLength" in schema and len(val) < schema["minLength"]:
                errors.append(f"{label} must be at least {schema['minLength']} chars")
            if "maxLength" in schema and len(val) > schema["maxLength"]:
                errors.append(f"{label} must be at most {schema['maxLength']} chars")
        if t == "object":
            props = schema.get("properties", {})
            for k in schema.get("required", []):
                if k not in val:
                    errors.append(f"missing required {path + '.' + k if path else k}")
            for k, v in val.items():
                if k in props:
                    errors.extend(self._validate(v, props[k], path + '.' + k if path else k))
        if t == "array" and "items" in schema:
            for i, item in enumerate(val):
                errors.extend(self._validate(item, schema["items"], f"{path}[{i}]" if path else f"[{i}]"))
        return errors
    
    def to_schema(self) -> dict[str, Any]:
        """Convert tool to OpenAI function schema format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }
    
    def __repr__(self) -> str:
        return f"<Tool:{self.name}>"


_TOOL_REGISTRY: dict[str, type[Tool]] = {}


def register_tool(
    name: str | None = None,
    category: ToolCategory = ToolCategory.OTHER,
    tags: list[str] | None = None,
    requires_confirmation: bool = False,
    dangerous: bool = False,
) -> Callable[[type[Tool]], type[Tool]]:
    """
    Decorator to register a tool class.
    
    Usage:
        @register_tool(category=ToolCategory.FILESYSTEM)
        class MyTool(Tool):
            ...
    
    Args:
        name: Optional custom name (defaults to class name in snake_case)
        category: Tool category for classification
        tags: List of tags for search and filtering
        requires_confirmation: Whether the tool requires user confirmation
        dangerous: Whether the tool performs dangerous operations
    
    Returns:
        Decorator function
    """
    def decorator(cls: type[Tool]) -> type[Tool]:
        tool_name = name or _to_snake_case(cls.__name__.replace("Tool", ""))
        _TOOL_REGISTRY[tool_name] = cls
        
        original_metadata = cls.metadata.fget if hasattr(cls, 'metadata') and isinstance(getattr(cls, 'metadata', None), property) else None
        
        @property
        def metadata(self) -> ToolMetadata:
            base_metadata = original_metadata(self) if original_metadata else ToolMetadata(
                name=self.name,
                description=self.description,
            )
            return ToolMetadata(
                name=base_metadata.name,
                description=base_metadata.description,
                category=category,
                tags=tags or base_metadata.tags,
                requires_confirmation=requires_confirmation or base_metadata.requires_confirmation,
                dangerous=dangerous or base_metadata.dangerous,
                version=base_metadata.version,
                author=base_metadata.author,
                examples=base_metadata.examples,
            )
        
        cls.metadata = metadata
        return cls
    
    return decorator


def _to_snake_case(name: str) -> str:
    """Convert CamelCase to snake_case."""
    result = []
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            result.append('_')
        result.append(char.lower())
    return ''.join(result)


def get_registered_tools() -> dict[str, type[Tool]]:
    """Get all registered tool classes."""
    return dict(_TOOL_REGISTRY)


def create_tool(name: str, *args: Any, **kwargs: Any) -> Tool | None:
    """
    Create a tool instance by name.
    
    Args:
        name: The registered tool name
        *args: Arguments to pass to the tool constructor
        **kwargs: Keyword arguments to pass to the tool constructor
    
    Returns:
        Tool instance or None if not found
    """
    tool_cls = _TOOL_REGISTRY.get(name)
    if tool_cls:
        return tool_cls(*args, **kwargs)
    return None
