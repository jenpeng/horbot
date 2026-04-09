"""Configuration validation module.

Provides comprehensive validation for horbot configuration with
support for error/warning severity levels and detailed error messages.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from horbot.agent.tools.permission import PROFILES
from horbot.config.schema import Config


class ValidationSeverity(Enum):
    """Validation severity levels."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationMessage:
    """A single validation message."""
    severity: ValidationSeverity
    code: str
    message: str
    field_path: str | None = None
    suggestion: str | None = None

    def __str__(self) -> str:
        parts = [f"[{self.severity.value.upper()}] {self.code}"]
        if self.field_path:
            parts.append(f" (field: {self.field_path})")
        parts.append(f": {self.message}")
        if self.suggestion:
            parts.append(f"\n  Suggestion: {self.suggestion}")
        return "".join(parts)


@dataclass
class ValidationResult:
    """Result of configuration validation."""
    valid: bool
    messages: list[ValidationMessage] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationMessage]:
        """Get all error messages."""
        return [m for m in self.messages if m.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> list[ValidationMessage]:
        """Get all warning messages."""
        return [m for m in self.messages if m.severity == ValidationSeverity.WARNING]

    @property
    def infos(self) -> list[ValidationMessage]:
        """Get all info messages."""
        return [m for m in self.messages if m.severity == ValidationSeverity.INFO]

    @classmethod
    def success(cls) -> "ValidationResult":
        """Create a successful validation result."""
        return cls(valid=True, messages=[])

    def add_error(
        self,
        code: str,
        message: str,
        field_path: str | None = None,
        suggestion: str | None = None,
    ) -> "ValidationResult":
        """Add an error message."""
        self.messages.append(ValidationMessage(
            severity=ValidationSeverity.ERROR,
            code=code,
            message=message,
            field_path=field_path,
            suggestion=suggestion,
        ))
        self.valid = False
        return self

    def add_warning(
        self,
        code: str,
        message: str,
        field_path: str | None = None,
        suggestion: str | None = None,
    ) -> "ValidationResult":
        """Add a warning message."""
        self.messages.append(ValidationMessage(
            severity=ValidationSeverity.WARNING,
            code=code,
            message=message,
            field_path=field_path,
            suggestion=suggestion,
        ))
        return self

    def add_info(
        self,
        code: str,
        message: str,
        field_path: str | None = None,
        suggestion: str | None = None,
    ) -> "ValidationResult":
        """Add an info message."""
        self.messages.append(ValidationMessage(
            severity=ValidationSeverity.INFO,
            code=code,
            message=message,
            field_path=field_path,
            suggestion=suggestion,
        ))
        return self

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        """Merge another validation result into this one."""
        self.messages.extend(other.messages)
        if not other.valid:
            self.valid = False
        return self

    def format_report(self) -> str:
        """Format a human-readable validation report."""
        lines = []

        if self.valid and not self.warnings and not self.infos:
            return "Configuration is valid."

        if not self.valid:
            lines.append("Configuration validation FAILED")
            lines.append("=" * 40)
            for msg in self.errors:
                lines.append(str(msg))
        else:
            lines.append("Configuration validation passed with warnings/info")
            lines.append("=" * 40)

        if self.warnings:
            lines.append("")
            lines.append("Warnings:")
            for msg in self.warnings:
                lines.append(f"  {msg}")

        if self.infos:
            lines.append("")
            lines.append("Info:")
            for msg in self.infos:
                lines.append(f"  {msg}")

        return "\n".join(lines)


class ValidationRule(ABC):
    """Base class for validation rules."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Rule name for identification."""
        pass

    @property
    def description(self) -> str:
        """Human-readable rule description."""
        return ""

    @abstractmethod
    def validate(self, config: Config) -> ValidationResult:
        """Execute validation rule."""
        pass


class ProviderKeyRule(ValidationRule):
    """Validate provider API key configuration."""

    name = "provider_key"
    description = "Validates that at least one provider has an API key configured"

    OAUTH_PROVIDERS = {"openai_codex", "github_copilot"}
    STANDARD_PROVIDERS = {
        "anthropic", "openai", "openrouter", "deepseek", "gemini",
        "zhipu", "dashscope", "moonshot", "minimax", "groq", "vllm",
        "siliconflow", "volcengine", "aihubmix", "custom",
    }

    def validate(self, config: Config) -> ValidationResult:
        result = ValidationResult.success()

        has_key = False
        for provider_name in self.STANDARD_PROVIDERS:
            provider = getattr(config.providers, provider_name, None)
            if provider and provider.api_key:
                has_key = True
                break

        if not has_key:
            result.add_warning(
                code="NO_API_KEY",
                message="No API key configured for any provider",
                field_path="providers",
                suggestion=(
                    "Set at least one provider's API key in config.json, e.g.:\n"
                    '  "providers": { "anthropic": { "apiKey": "sk-..." } }\n'
                    "Or set environment variable: ANTHROPIC_API_KEY, OPENAI_API_KEY, etc."
                ),
            )

        for oauth_provider in self.OAUTH_PROVIDERS:
            provider = getattr(config.providers, oauth_provider, None)
            if provider and provider.api_key:
                result.add_error(
                    code="OAUTH_PROVIDER_HAS_KEY",
                    message=f"OAuth provider '{oauth_provider}' should not have API key set",
                    field_path=f"providers.{oauth_provider}.apiKey",
                    suggestion=(
                        f"'{oauth_provider}' uses OAuth authentication. "
                        "Remove the apiKey field and use OAuth login instead."
                    ),
                )

        return result


class ModelNameRule(ValidationRule):
    """Validate model name configuration."""

    name = "model_name"
    description = "Validates that the configured model name is recognized"

    KNOWN_MODELS: dict[str, list[str]] = {
        "anthropic": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku", "claude-3-5-sonnet", "claude-opus-4", "claude-sonnet-4", "claude-opus-4-5"],
        "openai": ["gpt-4", "gpt-4-turbo", "gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo", "o1", "o1-mini", "o1-preview", "o3", "o3-mini"],
        "deepseek": ["deepseek-chat", "deepseek-reasoner", "deepseek-coder"],
        "gemini": ["gemini-pro", "gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash"],
        "zhipu": ["glm-4", "glm-4-flash", "glm-4-plus"],
        "moonshot": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "minimax": ["abab6.5-chat", "abab6.5s-chat","MiniMax-M2.5"],
        "groq": ["llama-3.1-", "llama-3.2-", "mixtral", "gemma2"],
        "dashscope": ["qwen-", "qwen2.5-", "qwen-max", "qwen-plus"],
    }

    def validate(self, config: Config) -> ValidationResult:
        result = ValidationResult.success()
        model = config.agents.defaults.model

        if not model:
            result.add_error(
                code="EMPTY_MODEL",
                message="Model name is not configured",
                field_path="agents.defaults.model",
                suggestion="Set a model name, e.g., 'anthropic/claude-opus-4-5' or 'openai/gpt-4o'",
            )
            return result

        provider_name = config.get_provider_name(model)
        if not provider_name:
            result.add_warning(
                code="UNKNOWN_PROVIDER",
                message=f"Cannot determine provider for model '{model}'",
                field_path="agents.defaults.model",
                suggestion=(
                    "Use a model name with provider prefix, e.g., 'anthropic/claude-opus-4-5'. "
                    "Or configure the provider explicitly in agents.defaults.provider."
                ),
            )
            return result

        if provider_name in self.KNOWN_MODELS:
            known = self.KNOWN_MODELS[provider_name]
            model_base = model.split("/")[-1] if "/" in model else model
            if not any(kw in model_base.lower() for kw in known):
                result.add_info(
                    code="UNKNOWN_MODEL_VARIANT",
                    message=f"Model '{model}' may not be a known variant for provider '{provider_name}'",
                    field_path="agents.defaults.model",
                    suggestion=f"Known models for {provider_name}: {', '.join(known[:5])}...",
                )

        return result


class ChannelConfigRule(ValidationRule):
    """Validate channel configurations."""

    name = "channel_config"
    description = "Validates enabled channels have required configuration"

    CHANNEL_REQUIREMENTS: dict[str, dict[str, Any]] = {
        "telegram": {"fields": ["token"], "display_name": "Telegram"},
        "discord": {"fields": ["token"], "display_name": "Discord"},
        "feishu": {"fields": ["app_id", "app_secret"], "display_name": "Feishu"},
        "dingtalk": {"fields": ["client_id", "client_secret"], "display_name": "DingTalk"},
        "slack": {"fields": ["bot_token", "app_token"], "display_name": "Slack"},
        "qq": {"fields": ["app_id", "secret"], "display_name": "QQ"},
        "email": {"fields": ["imap_host", "smtp_host"], "display_name": "Email"},
        "matrix": {"fields": ["homeserver", "access_token", "user_id"], "display_name": "Matrix"},
        "mochat": {"fields": ["claw_token", "agent_user_id"], "display_name": "Mochat"},
    }

    def validate(self, config: Config) -> ValidationResult:
        result = ValidationResult.success()

        for channel_name, requirements in self.CHANNEL_REQUIREMENTS.items():
            channel = getattr(config.channels, channel_name, None)
            if not channel:
                continue

            if not getattr(channel, "enabled", False):
                continue

            missing_fields = []
            for field_name in requirements["fields"]:
                value = getattr(channel, field_name, None)
                if not value:
                    missing_fields.append(field_name)

            if missing_fields:
                result.add_warning(
                    code="CHANNEL_MISSING_CONFIG",
                    message=(
                        f"{requirements['display_name']} channel is enabled but missing required fields: "
                        f"{', '.join(missing_fields)}"
                    ),
                    field_path=f"channels.{channel_name}",
                    suggestion=(
                        f"Either disable the {requirements['display_name']} channel by setting "
                        f"'enabled: false', or provide the required configuration fields."
                    ),
                )

        enabled_count = sum(
            1 for ch_name in self.CHANNEL_REQUIREMENTS
            if getattr(getattr(config.channels, ch_name, None), "enabled", False)
        )

        if enabled_count == 0:
            result.add_info(
                code="NO_CHANNELS_ENABLED",
                message="No chat channels are enabled",
                field_path="channels",
                suggestion=(
                    "Enable at least one channel to interact with horbot. "
                    "For example, set 'channels.telegram.enabled: true' and configure the token."
                ),
            )

        return result


class WorkspacePathRule(ValidationRule):
    """Validate workspace path configuration."""

    name = "workspace_path"
    description = "Validates workspace path is accessible and writable"

    def validate(self, config: Config) -> ValidationResult:
        result = ValidationResult.success()
        workspace = config.agents.defaults.workspace

        if not workspace:
            result.add_error(
                code="EMPTY_WORKSPACE",
                message="Workspace path is not configured",
                field_path="agents.defaults.workspace",
                suggestion="Set a workspace path, e.g., '.horbot/agents/main/workspace' or an absolute path.",
            )
            return result

        try:
            path = config.workspace_path
        except Exception as e:
            result.add_error(
                code="INVALID_WORKSPACE_PATH",
                message=f"Failed to resolve workspace path: {e}",
                field_path="agents.defaults.workspace",
                suggestion="Ensure the workspace path is a valid file system path.",
            )
            return result

        if path.exists():
            if not path.is_dir():
                result.add_error(
                    code="WORKSPACE_NOT_DIR",
                    message=f"Workspace path exists but is not a directory: {path}",
                    field_path="agents.defaults.workspace",
                    suggestion="Remove the file or choose a different workspace path.",
                )
            else:
                import os
                if not os.access(path, os.W_OK):
                    result.add_warning(
                        code="WORKSPACE_NOT_WRITABLE",
                        message=f"Workspace directory is not writable: {path}",
                        field_path="agents.defaults.workspace",
                        suggestion="Ensure the application has write permissions to the workspace directory.",
                    )

        return result


class PermissionRule(ValidationRule):
    """Validate permission configuration."""

    name = "permission_config"
    description = "Validates tool permission configuration"

    VALID_PROFILES = set(PROFILES.keys())

    def validate(self, config: Config) -> ValidationResult:
        result = ValidationResult.success()
        perm = config.tools.permission

        if perm.profile not in self.VALID_PROFILES:
            result.add_warning(
                code="UNKNOWN_PERMISSION_PROFILE",
                message=f"Unknown permission profile: '{perm.profile}'",
                field_path="tools.permission.profile",
                suggestion=f"Valid profiles: {', '.join(sorted(self.VALID_PROFILES))}",
            )

        for tool_name in perm.deny:
            if tool_name in perm.allow:
                result.add_warning(
                    code="CONFLICTING_PERMISSION",
                    message=f"Tool '{tool_name}' is in both 'allow' and 'deny' lists",
                    field_path="tools.permission",
                    suggestion="Remove the tool from one of the lists to avoid ambiguity.",
                )

        return result


class AutonomousConfigRule(ValidationRule):
    """Validate autonomous execution configuration."""

    name = "autonomous_config"
    description = "Validates autonomous execution settings"

    def validate(self, config: Config) -> ValidationResult:
        result = ValidationResult.success()
        auto = config.autonomous

        if not auto.enabled:
            return result

        if auto.max_plan_steps < 1:
            result.add_error(
                code="INVALID_MAX_PLAN_STEPS",
                message=f"max_plan_steps must be at least 1, got {auto.max_plan_steps}",
                field_path="autonomous.max_plan_steps",
                suggestion="Set max_plan_steps to a positive integer.",
            )

        if auto.step_timeout < 10:
            result.add_warning(
                code="LOW_STEP_TIMEOUT",
                message=f"step_timeout is very low ({auto.step_timeout}s), may cause premature timeouts",
                field_path="autonomous.step_timeout",
                suggestion="Consider increasing step_timeout to at least 60 seconds.",
            )

        if auto.retry_count < 0:
            result.add_error(
                code="INVALID_RETRY_COUNT",
                message=f"retry_count cannot be negative: {auto.retry_count}",
                field_path="autonomous.retry_count",
                suggestion="Set retry_count to 0 or a positive integer.",
            )

        if auto.confirm_sensitive and not auto.sensitive_operations:
            result.add_warning(
                code="NO_SENSITIVE_OPERATIONS",
                message="confirm_sensitive is true but sensitive_operations list is empty",
                field_path="autonomous.sensitive_operations",
                suggestion="Add operations that require confirmation, or disable confirm_sensitive.",
            )

        return result


class GatewayConfigRule(ValidationRule):
    """Validate gateway configuration."""

    name = "gateway_config"
    description = "Validates gateway server settings"

    def validate(self, config: Config) -> ValidationResult:
        result = ValidationResult.success()
        gateway = config.gateway

        if gateway.port < 1 or gateway.port > 65535:
            result.add_error(
                code="INVALID_PORT",
                message=f"Invalid port number: {gateway.port}",
                field_path="gateway.port",
                suggestion="Port must be between 1 and 65535.",
            )
        elif gateway.port < 1024:
            result.add_warning(
                code="PRIVILEGED_PORT",
                message=f"Port {gateway.port} is a privileged port, may require root/admin access",
                field_path="gateway.port",
                suggestion="Consider using a port above 1024, e.g., 18790 (default).",
            )

        if gateway.heartbeat.interval_s < 60:
            result.add_warning(
                code="HEARTBEAT_TOO_FREQUENT",
                message=f"Heartbeat interval is very short ({gateway.heartbeat.interval_s}s)",
                field_path="gateway.heartbeat.interval_s",
                suggestion="Consider setting interval to at least 60 seconds to reduce load.",
            )

        return result


class ConfigValidator:
    """Main configuration validator.

    Orchestrates validation rules and aggregates results.
    """

    def __init__(self):
        self._rules: list[ValidationRule] = []
        self._register_builtin_rules()

    def _register_builtin_rules(self) -> None:
        """Register built-in validation rules."""
        self._rules = [
            ProviderKeyRule(),
            ModelNameRule(),
            ChannelConfigRule(),
            WorkspacePathRule(),
            PermissionRule(),
            AutonomousConfigRule(),
            GatewayConfigRule(),
        ]

    def register_rule(self, rule: ValidationRule) -> None:
        """Register a custom validation rule."""
        self._rules.append(rule)

    def validate(self, config: Config) -> ValidationResult:
        """Validate configuration using all registered rules."""
        result = ValidationResult.success()

        for rule in self._rules:
            try:
                rule_result = rule.validate(config)
                result.merge(rule_result)
            except Exception as e:
                result.add_error(
                    code="RULE_EXECUTION_ERROR",
                    message=f"Validation rule '{rule.name}' failed: {e}",
                    field_path=None,
                    suggestion="This is an internal error. Please report this issue.",
                )

        return result

    def validate_quick(self, config: Config) -> bool:
        """Quick validation check - returns True if no errors."""
        result = self.validate(config)
        return result.valid


def validate_config(config: Config) -> ValidationResult:
    """Convenience function to validate a configuration.

    Args:
        config: Configuration to validate

    Returns:
        Validation result with any errors, warnings, or info messages
    """
    validator = ConfigValidator()
    return validator.validate(config)
