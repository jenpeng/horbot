"""Configuration loading utilities."""

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger

from horbot.config.normalizer import normalize_config
from horbot.config.schema import Config

import threading

_cached_config: Config | None = None
_config_callbacks: list[Callable[[Config, Config], None]] = []
_watcher_thread: threading.Thread | None = None


def _start_config_watcher(config_path: Path) -> None:
    """Start a background thread to watch for config file changes."""
    global _watcher_thread
    if _watcher_thread is not None and _watcher_thread.is_alive():
        return

    def watch_loop() -> None:
        try:
            from watchfiles import watch, Change
            import time
        except ImportError:
            logger.warning("watchfiles not installed, event-driven config hot-reloading disabled")
            return

        last_reload_time = 0.0
        debounce_seconds = 1.0

        try:
            # Watch the parent directory to handle file deletion/recreation
            for changes in watch(config_path.parent):
                should_reload = False
                for change_type, path in changes:
                    try:
                        changed_path = Path(path).resolve()
                        target_path = config_path.resolve()
                    except OSError:
                        continue
                        
                    if changed_path == target_path:
                        if change_type in (Change.modified, Change.added):
                            should_reload = True
                            break
                            
                if should_reload:
                    current_time = time.time()
                    if current_time - last_reload_time < debounce_seconds:
                        time.sleep(debounce_seconds - (current_time - last_reload_time))
                        
                    logger.info(f"Config file changed, reloading...")
                    try:
                        reload_config()
                    except Exception as e:
                        logger.error(f"Failed to reload config: {e}")
                    last_reload_time = time.time()
        except Exception as e:
            logger.error(f"Config watcher error: {e}")

    _watcher_thread = threading.Thread(
        target=watch_loop,
        daemon=True,
        name="HorbotConfigWatcher"
    )
    _watcher_thread.start()


def get_config_path() -> Path:
    """Get the default configuration file path.
    
    Uses the unified paths module.
    """
    from horbot.utils.paths import get_config_path as _get_config_path
    return _get_config_path()


def get_writable_config_path() -> Path:
    """Get a writable configuration file path.
    
    Tries to find a writable location for the config file.
    Falls back to current working directory if home directory is not writable.
    """
    from horbot.utils.paths import get_config_path as _get_config_path
    default_path = _get_config_path()
    
    try:
        default_path.parent.mkdir(parents=True, exist_ok=True)
        test_file = default_path.parent / ".write_test"
        test_file.touch()
        test_file.unlink()
        return default_path
    except (PermissionError, OSError):
        pass
    
    cwd_path = Path.cwd() / ".horbot" / "config.json"
    try:
        cwd_path.parent.mkdir(parents=True, exist_ok=True)
        return cwd_path
    except (PermissionError, OSError):
        pass
    
    import tempfile
    return Path(tempfile.gettempdir()) / "horbot" / "config.json"


def get_data_dir() -> Path:
    """Get the horbot data directory."""
    from horbot.utils.paths import get_horbot_root
    return get_horbot_root()


def load_config(config_path: Path | None = None) -> Config:
    """
    Load configuration from file or create default.

    Args:
        config_path: Optional path to config file. Uses default if not provided.

    Returns:
        Loaded configuration object.
    """
    # List of paths to try in order
    paths_to_try = []
    
    if config_path:
        paths_to_try.append(config_path)
    else:
        # Priority: explicit path > env var > project config
        env_path = os.environ.get("HORBOT_CONFIG_PATH")
        if env_path:
            paths_to_try.append(Path(env_path))

        project_config = Path.cwd() / ".horbot" / "config.json"
        if project_config not in paths_to_try:
            paths_to_try.append(project_config)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_paths = []
    for p in paths_to_try:
        if p not in seen:
            seen.add(p)
            unique_paths.append(p)
    
    # Try each path
    for path in unique_paths:
        # Try to ensure config directory exists
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError):
            pass

        # Try to load from the path
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                data = _migrate_config(data)
                config = normalize_config(Config.model_validate(data))
                print(f"Loaded config from: {path}")
                return config
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Warning: Failed to load config from {path}: {e}")
            except PermissionError as e:
                print(f"Warning: Permission denied reading {path}: {e}")

    print("Using default configuration.")
    return Config()


def get_cached_config(reload: bool = False) -> Config:
    """Get cached configuration, loading from disk only if not cached.
    
    Args:
        reload: If True, force reload from disk.
    
    Returns:
        Configuration object.
    """
    global _cached_config
    
    config_path = get_config_path()
    
    if _cached_config is None or reload:
        _cached_config = load_config()
        _start_config_watcher(config_path)
        
    return _cached_config


def invalidate_config_cache() -> None:
    """Invalidate the configuration cache, forcing next read from disk."""
    global _cached_config
    _cached_config = None


def on_config_change(callback: Callable[[Config, Config], None]) -> None:
    """Register a callback to be notified when configuration changes.
    
    Args:
        callback: Function to call with (old_config, new_config) when config changes.
    """
    _config_callbacks.append(callback)
    logger.debug(f"Registered config change callback: {callback.__name__}")


def remove_config_callback(callback: Callable[[Config, Config], None]) -> bool:
    """Remove a previously registered config change callback.
    
    Args:
        callback: The callback to remove.
        
    Returns:
        True if the callback was found and removed, False otherwise.
    """
    if callback in _config_callbacks:
        _config_callbacks.remove(callback)
        return True
    return False


def _notify_config_change(old_config: Config | None, new_config: Config) -> None:
    """Notify all registered callbacks of a configuration change.
    
    Args:
        old_config: The previous configuration (may be None if first load).
        new_config: The new configuration.
    """
    _handle_managers_reload(old_config, new_config)
    
    for callback in _config_callbacks:
        try:
            callback(old_config, new_config)
        except Exception as e:
            logger.error(f"Error in config change callback {callback.__name__}: {e}")


def _handle_managers_reload(old_config: Config | None, new_config: Config) -> None:
    """Handle AgentManager and TeamManager reload on config change.
    
    Args:
        old_config: The previous configuration (may be None if first load).
        new_config: The new configuration.
    """
    agents_changed = False
    teams_changed = False
    
    if old_config is None:
        agents_changed = True
        teams_changed = True
    else:
        if hasattr(old_config, 'agents') and hasattr(new_config, 'agents'):
            old_agents = old_config.agents.model_dump() if old_config.agents else {}
            new_agents = new_config.agents.model_dump() if new_config.agents else {}
            if old_agents != new_agents:
                agents_changed = True
        
        if hasattr(old_config, 'teams') and hasattr(new_config, 'teams'):
            old_teams = old_config.teams.model_dump() if old_config.teams else {}
            new_teams = new_config.teams.model_dump() if new_config.teams else {}
            if old_teams != new_teams:
                teams_changed = True
    
    if agents_changed:
        try:
            from horbot.agent.manager import get_agent_manager
            manager = get_agent_manager()
            manager.reload(new_config)
            logger.info("AgentManager reloaded due to config change")
        except Exception as e:
            logger.error(f"Failed to reload AgentManager: {e}")
    
    if teams_changed:
        try:
            from horbot.team.manager import get_team_manager
            manager = get_team_manager()
            manager.reload(new_config)
            logger.info("TeamManager reloaded due to config change")
        except Exception as e:
            logger.error(f"Failed to reload TeamManager: {e}")


def reload_config() -> Config:
    """Force reload configuration from disk and notify callbacks.
    
    Returns:
        The newly loaded configuration.
        
    Raises:
        ValueError: If the configuration file is invalid.
        PermissionError: If the configuration file cannot be read.
    """
    global _cached_config
    
    old_config = _cached_config
    config_path = get_config_path()
    
    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        data = _migrate_config(data)
        new_config = normalize_config(Config.model_validate(data))
        
        _cached_config = new_config
        
        logger.info(f"Configuration reloaded from: {config_path}")
        _notify_config_change(old_config, new_config)
        
        return new_config
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse config file {config_path}: {e}")
        raise ValueError(f"Invalid JSON in config file: {e}") from e
    except ValueError as e:
        logger.error(f"Config validation failed for {config_path}: {e}")
        raise
    except PermissionError as e:
        logger.error(f"Permission denied reading config file {config_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error loading config from {config_path}: {e}")
        raise


def save_config(config: Config, config_path: Path | None = None) -> Path:
    """
    Save configuration to file.

    Args:
        config: Configuration to save.
        config_path: Optional path to save to. Uses default if not provided.

    Returns:
        The path where the configuration was saved.

    Raises:
        PermissionError: If the config file cannot be written due to permission issues.
        OSError: If there are other file system errors.
    """
    global _cached_config
    
    path = config_path or get_config_path()
    
    old_config = _cached_config
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            old_data = json.load(f)
        old_config = Config.model_validate(old_data)
    except (FileNotFoundError, json.JSONDecodeError, Exception):
        old_config = None
    
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        path = get_writable_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)

    config = normalize_config(config)
    data = config.model_dump(by_alias=True)

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        _cached_config = config
        
        _notify_config_change(old_config, config)
        
        return path
    except PermissionError:
        alt_path = get_writable_config_path()
        if alt_path != path:
            try:
                alt_path.parent.mkdir(parents=True, exist_ok=True)
                with open(alt_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                _cached_config = config
                print(f"Warning: Config saved to alternative location: {alt_path}")
                
                _notify_config_change(old_config, config)
                
                return alt_path
            except (PermissionError, OSError) as e:
                raise PermissionError(
                    f"Cannot write to config file. Tried both '{path}' and '{alt_path}'. "
                    f"The application may be running in a restricted environment (sandbox). "
                    f"Please set HORBOT_CONFIG_PATH to a writable location. Error: {e}"
                ) from e
        raise PermissionError(
            f"Cannot write to config file '{path}'. "
            f"The file may be locked or the application may be running in a restricted environment (sandbox). "
            f"Please set HORBOT_CONFIG_PATH to a writable location."
        ) from None
    except OSError as e:
        raise OSError(f"Failed to save configuration to '{path}': {e}") from e


def _migrate_config(data: dict) -> dict:
    """Migrate old config formats to current."""
    # Move tools.exec.restrictToWorkspace → tools.restrictToWorkspace
    tools = data.get("tools", {})
    exec_cfg = tools.get("exec", {})
    if "restrictToWorkspace" in exec_cfg and "restrictToWorkspace" not in tools:
        tools["restrictToWorkspace"] = exec_cfg.pop("restrictToWorkspace")

    # Move top-level models → agents.defaults.models
    if "models" in data:
        agents = data.setdefault("agents", {})
        defaults = agents.setdefault("defaults", {})
        if "models" not in defaults:
            defaults["models"] = data.pop("models")
        else:
            data.pop("models")

    # Migrate old model/provider fields to models config
    agents = data.get("agents", {})
    defaults = agents.get("defaults", {})
    models = defaults.setdefault("models", {})

    # Migrate and remove old main model/provider fields
    if "model" in defaults:
        main = models.setdefault("main", {})
        if "model" not in main:
            main["model"] = defaults["model"]
        defaults.pop("model")
    if "provider" in defaults:
        main = models.setdefault("main", {})
        if "provider" not in main:
            main["provider"] = defaults["provider"]
        defaults.pop("provider")

    # Migrate and remove old planning model/provider fields
    if "planningModel" in defaults:
        planning = models.setdefault("planning", {})
        if "model" not in planning:
            planning["model"] = defaults["planningModel"]
        defaults.pop("planningModel")
    if "planningProvider" in defaults:
        planning = models.setdefault("planning", {})
        if "provider" not in planning:
            planning["provider"] = defaults["planningProvider"]
        defaults.pop("planningProvider")

    return data
