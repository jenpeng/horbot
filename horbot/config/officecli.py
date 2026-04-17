"""Helpers for bootstrapping OfficeCLI defaults in Horbot config files."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

OFFICECLI_SERVER_NAMES = (
    "officecli",
    "office-word",
    "office-excel",
    "office-powerpoint",
)
DEFAULT_OFFICECLI_TIMEOUT = 120


def detect_officecli_command(
    *,
    path_env: str | None = None,
    home: str | Path | None = None,
) -> str:
    """Resolve the OfficeCLI executable path if it is already installed."""
    resolved = shutil.which("officecli", path=path_env)
    if resolved:
        return resolved

    home_path = Path(home).expanduser() if home is not None else Path.home()
    candidate = home_path / ".local" / "bin" / "officecli"
    if candidate.exists() and os.access(candidate, os.X_OK):
        return str(candidate)

    return "officecli"


def detect_officecli_bin_dir(
    *,
    path_env: str | None = None,
    home: str | Path | None = None,
) -> str:
    """Return the directory containing OfficeCLI when it can be determined."""
    command = detect_officecli_command(path_env=path_env, home=home)
    if command == "officecli":
        return ""
    return str(Path(command).expanduser().resolve().parent)


def build_default_officecli_server(command: str | None = None) -> dict[str, Any]:
    """Build the default OfficeCLI MCP server config."""
    return {
        "command": command or detect_officecli_command(),
        "args": ["mcp"],
        "env": {},
        "toolTimeout": DEFAULT_OFFICECLI_TIMEOUT,
    }


def _get_or_create_mapping(
    container: dict[str, Any],
    camel_key: str,
    snake_key: str,
) -> tuple[dict[str, Any], str]:
    camel_value = container.get(camel_key)
    if isinstance(camel_value, dict):
        return camel_value, camel_key

    snake_value = container.get(snake_key)
    if isinstance(snake_value, dict):
        return snake_value, snake_key

    created: dict[str, Any] = {}
    container[camel_key] = created
    return created, camel_key


def _append_path_if_missing(existing: str, extra_dir: str) -> str:
    if not extra_dir:
        return existing

    parts = [part for part in existing.split(os.pathsep) if part]
    if extra_dir in parts:
        return existing

    parts.append(extra_dir)
    return os.pathsep.join(parts)


def _merge_officecli_server_defaults(
    server_config: dict[str, Any],
    *,
    officecli_command: str,
) -> bool:
    changed = False

    current_command = str(server_config.get("command", "") or "").strip()
    if officecli_command != "officecli" and current_command in {"", "officecli"}:
        server_config["command"] = officecli_command
        changed = True

    current_args = server_config.get("args")
    if not isinstance(current_args, list) or not current_args:
        server_config["args"] = ["mcp"]
        changed = True

    if not isinstance(server_config.get("env"), dict):
        server_config["env"] = {}
        changed = True

    if "toolTimeout" not in server_config and "tool_timeout" not in server_config:
        server_config["toolTimeout"] = DEFAULT_OFFICECLI_TIMEOUT
        changed = True

    return changed


def ensure_officecli_defaults(
    config_data: dict[str, Any],
    *,
    officecli_command: str | None = None,
    officecli_bin_dir: str | None = None,
) -> bool:
    """Ensure the config contains sane OfficeCLI defaults."""
    if not isinstance(config_data, dict):
        raise TypeError("config_data must be a dict")

    resolved_command = officecli_command or detect_officecli_command()
    resolved_bin_dir = officecli_bin_dir
    if resolved_bin_dir is None:
        resolved_bin_dir = (
            str(Path(resolved_command).expanduser().resolve().parent)
            if resolved_command != "officecli"
            else detect_officecli_bin_dir()
        )

    changed = False
    tools, _ = _get_or_create_mapping(config_data, "tools", "tools")
    mcp_servers, _ = _get_or_create_mapping(tools, "mcpServers", "mcp_servers")

    if not any(name in mcp_servers for name in OFFICECLI_SERVER_NAMES):
        mcp_servers["officecli"] = build_default_officecli_server(resolved_command)
        changed = True
    else:
        for name in OFFICECLI_SERVER_NAMES:
            server_config = mcp_servers.get(name)
            if isinstance(server_config, dict):
                if _merge_officecli_server_defaults(
                    server_config,
                    officecli_command=resolved_command,
                ):
                    changed = True

    exec_config, _ = _get_or_create_mapping(tools, "exec", "exec")
    path_key = "pathAppend" if "pathAppend" in exec_config or "path_append" not in exec_config else "path_append"
    existing_path_append = exec_config.get(path_key, "")
    if not isinstance(existing_path_append, str):
        existing_path_append = ""
    new_path_append = _append_path_if_missing(existing_path_append, resolved_bin_dir or "")
    if new_path_append != existing_path_append:
        exec_config[path_key] = new_path_append
        changed = True

    return changed


def ensure_officecli_defaults_in_file(
    config_path: str | Path,
    *,
    officecli_command: str | None = None,
    officecli_bin_dir: str | None = None,
) -> dict[str, Any]:
    """Apply OfficeCLI defaults to a config file if needed."""
    path = Path(config_path)
    data = json.loads(path.read_text(encoding="utf-8"))

    resolved_command = officecli_command or detect_officecli_command()
    resolved_bin_dir = officecli_bin_dir
    if resolved_bin_dir is None:
        resolved_bin_dir = (
            str(Path(resolved_command).expanduser().resolve().parent)
            if resolved_command != "officecli"
            else detect_officecli_bin_dir()
        )

    changed = ensure_officecli_defaults(
        data,
        officecli_command=resolved_command,
        officecli_bin_dir=resolved_bin_dir,
    )
    if changed:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    return {
        "changed": changed,
        "command": resolved_command,
        "bin_dir": resolved_bin_dir or "",
        "server_names": list(OFFICECLI_SERVER_NAMES),
    }
