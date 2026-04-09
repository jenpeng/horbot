"""Configuration migration module.

Handles version-to-version configuration migrations to maintain
backward compatibility as the configuration schema evolves.
"""

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class MigrationChange:
    """Represents a single migration change."""
    description: str
    field_path: str | None = None
    old_value: Any = None
    new_value: Any = None


@dataclass
class MigrationResult:
    """Result of a configuration migration."""
    success: bool
    data: dict[str, Any]
    version_from: str
    version_to: str
    changes: list[MigrationChange] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        """Check if any changes were made."""
        return len(self.changes) > 0

    def format_report(self) -> str:
        """Format a human-readable migration report."""
        lines = []

        if not self.success:
            lines.append("Migration FAILED")
            lines.append("=" * 40)
            for error in self.errors:
                lines.append(f"  ERROR: {error}")
            return "\n".join(lines)

        if not self.has_changes:
            lines.append(f"Configuration is already at version {self.version_to}")
            return "\n".join(lines)

        lines.append(f"Migration: {self.version_from} -> {self.version_to}")
        lines.append("=" * 40)
        lines.append("")
        lines.append("Changes:")
        for change in self.changes:
            lines.append(f"  - {change.description}")
            if change.field_path:
                lines.append(f"    Field: {change.field_path}")

        if self.warnings:
            lines.append("")
            lines.append("Warnings:")
            for warning in self.warnings:
                lines.append(f"  - {warning}")

        return "\n".join(lines)


MigrationFunc = Callable[[dict[str, Any]], tuple[dict[str, Any], list[MigrationChange]]]


class MigrationRegistry:
    """Registry for migration functions."""

    def __init__(self):
        self._migrations: dict[str, MigrationFunc] = {}
        self._version_order: list[str] = []

    def register(
        self,
        from_version: str,
        to_version: str,
        migration_func: MigrationFunc,
    ) -> None:
        """Register a migration function."""
        key = f"{from_version}->{to_version}"
        self._migrations[key] = migration_func
        if to_version not in self._version_order:
            self._version_order.append(to_version)

    def get(self, from_version: str, to_version: str) -> MigrationFunc | None:
        """Get a migration function."""
        key = f"{from_version}->{to_version}"
        return self._migrations.get(key)

    def get_next_version(self, current: str) -> str | None:
        """Get the next version in the migration chain."""
        try:
            idx = self._version_order.index(current)
            if idx + 1 < len(self._version_order):
                return self._version_order[idx + 1]
        except ValueError:
            pass
        return None


class ConfigMigrator:
    """Configuration version migrator.

    Handles automatic migration of configuration files from older
    versions to the current version.
    """

    CURRENT_VERSION = "1.1.0"
    VERSION_FIELD = "_version"

    def __init__(self):
        self._registry = MigrationRegistry()
        self._register_migrations()

    def _register_migrations(self) -> None:
        """Register all known migrations."""
        self._registry.register("1.0.0", "1.1.0", self._migrate_1_0_to_1_1)

    def get_version(self, data: dict[str, Any]) -> str:
        """Extract version from configuration data."""
        return data.get(self.VERSION_FIELD, "1.0.0")

    def set_version(self, data: dict[str, Any], version: str) -> None:
        """Set version in configuration data."""
        data[self.VERSION_FIELD] = version

    def needs_migration(self, data: dict[str, Any]) -> bool:
        """Check if configuration needs migration."""
        version = self.get_version(data)
        return version != self.CURRENT_VERSION

    def migrate(self, data: dict[str, Any]) -> MigrationResult:
        """Execute configuration migration.

        Args:
            data: Raw configuration dictionary

        Returns:
            MigrationResult with migrated data and change log
        """
        from_version = self.get_version(data)
        changes: list[MigrationChange] = []
        warnings: list[str] = []
        errors: list[str] = []

        if from_version == self.CURRENT_VERSION:
            return MigrationResult(
                success=True,
                data=data,
                version_from=from_version,
                version_to=self.CURRENT_VERSION,
                changes=[],
                warnings=[],
                errors=[],
            )

        current_data = data.copy()
        current_version = from_version

        max_iterations = 10
        iteration = 0

        while current_version != self.CURRENT_VERSION:
            iteration += 1
            if iteration > max_iterations:
                errors.append(
                    f"Migration chain too long or circular. "
                    f"Current version: {current_version}, Target: {self.CURRENT_VERSION}"
                )
                break

            next_version = self._registry.get_next_version(current_version)
            if not next_version:
                next_version = self.CURRENT_VERSION

            migration_func = self._registry.get(current_version, next_version)
            if not migration_func:
                warnings.append(
                    f"No migration path from {current_version} to {next_version}. "
                    f"Attempting to use configuration as-is."
                )
                current_version = next_version
                continue

            try:
                current_data, migration_changes = migration_func(current_data)
                changes.extend(migration_changes)
                current_version = next_version
            except Exception as e:
                errors.append(f"Migration from {current_version} to {next_version} failed: {e}")
                break

        if not errors:
            self.set_version(current_data, self.CURRENT_VERSION)

        return MigrationResult(
            success=len(errors) == 0,
            data=current_data,
            version_from=from_version,
            version_to=self.CURRENT_VERSION if not errors else current_version,
            changes=changes,
            warnings=warnings,
            errors=errors,
        )

    def _migrate_1_0_to_1_1(self, data: dict[str, Any]) -> tuple[dict[str, Any], list[MigrationChange]]:
        """Migrate from version 1.0.0 to 1.1.0.

        Changes:
        - Move tools.exec.restrictToWorkspace to tools.restrictToWorkspace
        - Add autonomous config with default values if missing
        - Add gateway.heartbeat config if missing
        """
        changes = []

        tools = data.get("tools", {})
        if not isinstance(tools, dict):
            tools = {}
            data["tools"] = tools

        exec_cfg = tools.get("exec", {})
        if isinstance(exec_cfg, dict) and "restrictToWorkspace" in exec_cfg:
            if "restrictToWorkspace" not in tools:
                tools["restrictToWorkspace"] = exec_cfg.pop("restrictToWorkspace")
                changes.append(MigrationChange(
                    description="Moved tools.exec.restrictToWorkspace to tools.restrictToWorkspace",
                    field_path="tools.restrictToWorkspace",
                    old_value=f"tools.exec.restrictToWorkspace",
                    new_value=f"tools.restrictToWorkspace",
                ))

        if "autonomous" not in data:
            data["autonomous"] = {
                "enabled": False,
                "max_plan_steps": 10,
                "step_timeout": 300,
                "total_timeout": 3600,
                "retry_count": 3,
                "retry_delay": 5,
                "confirm_sensitive": True,
                "sensitive_operations": ["write_file", "edit_file", "exec", "spawn", "cron"],
                "protected_paths": ["~/.ssh", "~/.env", "**/config.json", "**/.env"],
            }
            changes.append(MigrationChange(
                description="Added autonomous configuration with default values",
                field_path="autonomous",
            ))

        gateway = data.get("gateway", {})
        if not isinstance(gateway, dict):
            gateway = {}
            data["gateway"] = gateway

        if "heartbeat" not in gateway:
            gateway["heartbeat"] = {
                "enabled": True,
                "interval_s": 1800,
            }
            changes.append(MigrationChange(
                description="Added gateway.heartbeat configuration with default values",
                field_path="gateway.heartbeat",
            ))

        return data, changes


def migrate_config(data: dict[str, Any]) -> MigrationResult:
    """Convenience function to migrate configuration data.

    Args:
        data: Raw configuration dictionary

    Returns:
        MigrationResult with migrated data and change log
    """
    migrator = ConfigMigrator()
    return migrator.migrate(data)


def get_config_version(data: dict[str, Any]) -> str:
    """Get the version of a configuration.

    Args:
        data: Configuration dictionary

    Returns:
        Version string, defaults to "1.0.0" if not specified
    """
    return data.get(ConfigMigrator.VERSION_FIELD, "1.0.0")
