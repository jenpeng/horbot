"""Path management for horbot data directories."""

from pathlib import Path
import os

HORBOT_ROOT_DIRNAME = ".horbot"
HORBOT_ROOT_ENV = "HORBOT_ROOT"
HORBOT_CONFIG_ENV = "HORBOT_CONFIG_PATH"


def _search_upward_for_dir(dirname: str) -> Path | None:
    current = Path.cwd()
    for parent in [current, *current.parents]:
        candidate = parent / dirname
        if candidate.exists():
            return candidate
    return None


def get_horbot_root() -> Path:
    """Get the active horbot data root."""
    env_root = os.environ.get(HORBOT_ROOT_ENV)
    if env_root:
        return Path(env_root).expanduser()

    discovered = _search_upward_for_dir(HORBOT_ROOT_DIRNAME)
    if discovered is not None:
        return discovered

    return Path.cwd() / HORBOT_ROOT_DIRNAME


def get_active_data_root() -> Path:
    """Return the active horbot data root."""
    return get_horbot_root()


def get_config_path() -> Path:
    """Get the configuration file path."""
    env_path = os.environ.get(HORBOT_CONFIG_ENV)
    if env_path:
        return Path(env_path).expanduser()
    return get_horbot_root() / "config.json"


def get_runtime_dir() -> Path:
    """Get the runtime directory (logs, pids)."""
    return get_horbot_root() / "runtime"


def get_logs_dir() -> Path:
    """Get the logs directory."""
    path = get_runtime_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_pids_dir() -> Path:
    """Get the PIDs directory."""
    path = get_runtime_dir() / "pids"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_data_dir() -> Path:
    """Get the persistent data directory."""
    return get_horbot_root() / "data"


def get_sessions_dir() -> Path:
    """Get the sessions directory."""
    path = get_data_dir() / "sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_sessions_archived_dir() -> Path:
    """Get the archived sessions directory."""
    path = get_sessions_dir() / "archived"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_sessions_recent_dir() -> Path:
    """Get the recent sessions directory."""
    path = get_sessions_dir() / "recent"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_sessions_active_dir() -> Path:
    """Get the active sessions directory (JSONL files)."""
    path = get_sessions_dir() / "active"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_memories_dir() -> Path:
    """Get the memories directory."""
    path = get_data_dir() / "memories"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_memory_dir(level: str = "L1") -> Path:
    """Get a specific memory level directory."""
    path = get_memories_dir() / level
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_plans_dir() -> Path:
    """Get the plans directory."""
    path = get_data_dir() / "plans"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_cron_dir() -> Path:
    """Get the cron jobs directory."""
    path = get_data_dir() / "cron"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_uploads_dir() -> Path:
    """Get the uploads directory for file uploads."""
    path = get_data_dir() / "uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_agents_dir() -> Path:
    """Get the agents directory."""
    path = get_horbot_root() / "agents"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_agent_dir(agent_id: str) -> Path:
    """Get a specific agent root directory."""
    path = get_agents_dir() / agent_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_main_agent_dir() -> Path:
    """Get the main agent root directory."""
    return get_agent_dir("main")


def get_main_agent_workspace_dir() -> Path:
    """Get the main agent workspace directory."""
    path = get_main_agent_dir() / "workspace"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_main_agent_memory_dir() -> Path:
    """Get the main agent memory directory."""
    path = get_main_agent_dir() / "memory"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_main_agent_sessions_dir() -> Path:
    """Get the main agent sessions directory."""
    path = get_main_agent_dir() / "sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_main_agent_skills_dir() -> Path:
    """Get the main agent skills directory."""
    path = get_main_agent_dir() / "skills"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_workspace_dir() -> Path:
    """Get the default user workspace directory."""
    return get_main_agent_workspace_dir()


def get_skills_dir() -> Path:
    """Get the workspace skills directory."""
    path = get_workspace_dir() / "skills"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_scripts_dir() -> Path:
    """Get the workspace scripts directory."""
    path = get_workspace_dir() / "scripts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_token_usage_dir() -> Path:
    """Get the token usage directory."""
    path = get_workspace_dir() / "token_usage"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_soul_path() -> Path:
    """Get the SOUL.md path."""
    return get_workspace_dir() / "SOUL.md"


def get_user_path() -> Path:
    """Get the USER.md path."""
    return get_workspace_dir() / "USER.md"


def get_log_path(name: str) -> Path:
    """Get a log file path."""
    return get_logs_dir() / f"{name}.log"


def get_pid_path(name: str) -> Path:
    """Get a PID file path."""
    return get_pids_dir() / f"{name}.pid"


def ensure_all_dirs() -> None:
    """Ensure all standard directories exist."""
    get_logs_dir()
    get_pids_dir()
    get_sessions_dir()
    get_sessions_archived_dir()
    get_sessions_recent_dir()
    get_sessions_active_dir()
    get_memories_dir()
    get_memory_dir("L0")
    get_memory_dir("L1")
    get_memory_dir("L2")
    get_plans_dir()
    get_cron_dir()
    get_uploads_dir()
    get_workspace_dir()
    get_skills_dir()
    get_scripts_dir()
    get_token_usage_dir()
    get_agents_dir()
    get_teams_dir()
    get_shared_resources_dir()


def get_agent_workspace_dir(agent_id: str) -> Path:
    """Get an agent workspace directory."""
    path = get_agent_dir(agent_id) / "workspace"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_agent_memory_dir(agent_id: str) -> Path:
    """Get an agent memory directory."""
    path = get_agent_dir(agent_id) / "memory"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_agent_sessions_dir(agent_id: str) -> Path:
    """Get an agent sessions directory."""
    path = get_agent_dir(agent_id) / "sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_agent_skills_dir(agent_id: str) -> Path:
    """Get an agent skills directory."""
    path = get_agent_dir(agent_id) / "skills"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_teams_dir() -> Path:
    """Get the teams directory."""
    path = get_horbot_root() / "teams"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_team_dir(team_id: str) -> Path:
    """Get a specific team root directory."""
    path = get_teams_dir() / team_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_team_workspace_dir(team_id: str) -> Path:
    """Get a team workspace directory."""
    path = get_team_dir(team_id) / "workspace"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_team_shared_memory_dir(team_id: str) -> Path:
    """Get a team shared memory directory."""
    path = get_team_dir(team_id) / "shared_memory"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_team_taskboard_dir(team_id: str) -> Path:
    """Get a team taskboard directory."""
    path = get_team_dir(team_id) / "taskboard"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_shared_resources_dir() -> Path:
    """Get the global shared resources directory."""
    path = get_horbot_root() / "shared"
    path.mkdir(parents=True, exist_ok=True)
    return path
