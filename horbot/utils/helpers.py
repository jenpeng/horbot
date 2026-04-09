"""Utility functions for horbot."""

from pathlib import Path
from datetime import datetime
import os
from typing import Iterable


def ensure_dir(path: Path) -> Path:
    """Ensure a directory exists, creating it if necessary."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_project_root() -> Path:
    """Get the project root directory."""
    env_root = os.environ.get("HORBOT_PROJECT_ROOT")
    if env_root:
        return Path(env_root)

    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".horbot").exists():
            return parent

    return current


def get_data_path() -> Path:
    """Get the horbot data directory."""
    from horbot.utils.paths import get_active_data_root

    return get_active_data_root()


def get_logs_path() -> Path:
    """Get the logs directory."""
    project_root = get_project_root()
    return ensure_dir(project_root / "logs")


def get_workspace_path() -> Path:
    """Get the default workspace directory."""
    from horbot.utils.paths import get_workspace_dir

    return get_workspace_dir()


def get_sessions_path() -> Path:
    """Get the sessions storage directory."""
    from horbot.utils.paths import get_sessions_active_dir

    return get_sessions_active_dir()


def get_cron_store_path() -> Path:
    """Get the cron store path."""
    from horbot.utils.paths import get_cron_dir

    return get_cron_dir() / "jobs.json"


def get_skills_path(workspace: Path | None = None) -> Path:
    """Get the skills directory within the workspace."""
    from horbot.utils.paths import get_skills_dir

    return get_skills_dir()


def timestamp() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now().isoformat()


def truncate_string(s: str, max_len: int = 100, suffix: str = "...") -> str:
    """Truncate a string to max length, adding suffix if truncated."""
    if len(s) <= max_len:
        return s
    return s[: max_len - len(suffix)] + suffix


def safe_filename(name: str) -> str:
    """Convert a string to a safe filename."""
    unsafe = '<>:"/\\|?*'
    for char in unsafe:
        name = name.replace(char, "_")
    return name.strip()


def parse_session_key(key: str) -> tuple[str, str]:
    """Parse a session key into routing key and chat_id."""
    return parse_session_key_with_known_routes(key)


def parse_session_key_with_known_routes(
    key: str,
    known_route_keys: Iterable[str] | None = None,
) -> tuple[str, str]:
    """Parse a session key using the longest matching known route prefix."""
    if ":" not in key:
        raise ValueError(f"Invalid session key: {key}")

    route_keys: list[str] = []
    seen: set[str] = set()

    def _add(candidate: str | None) -> None:
        value = str(candidate or "").strip()
        if not value or value in seen:
            return
        seen.add(value)
        route_keys.append(value)

    for default_key in ("web", "cli", "system", "cron"):
        _add(default_key)

    try:
        from horbot.channels.endpoints import CHANNEL_TYPE_MODELS, list_channel_endpoints
        from horbot.config.loader import get_cached_config

        for channel_type in CHANNEL_TYPE_MODELS:
            _add(channel_type)

        config = get_cached_config()
        for endpoint in list_channel_endpoints(config):
            _add(endpoint.id)
    except Exception:
        pass

    for candidate in known_route_keys or []:
        _add(candidate)

    for route_key in sorted(route_keys, key=len, reverse=True):
        prefix = f"{route_key}:"
        if key.startswith(prefix):
            chat_id = key[len(prefix):]
            if chat_id:
                return route_key, chat_id

    parts = key.split(":", 1)
    return parts[0], parts[1]
