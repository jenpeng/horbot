"""Configuration file watcher for hot-reload support."""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger
from watchfiles import awatch, Change

from horbot.config.loader import reload_config, get_config_path


class ConfigChangeType(Enum):
    """Type of configuration change."""
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"


@dataclass
class ConfigChangeEvent:
    """Event fired when configuration changes."""
    change_type: ConfigChangeType
    config_path: Path
    old_config: Any = None
    new_config: Any = None
    changed_keys: list[str] = field(default_factory=list)
    error: str | None = None


class ConfigWatcher:
    """Watch configuration file for changes and notify listeners.
    
    Features:
    - Debounce mechanism to avoid frequent reloads
    - Async event handling
    - Multiple listener support
    - Graceful error handling for corrupted files
    - Uses watchfiles for efficient file watching
    
    Usage:
        watcher = ConfigWatcher(config_path)
        watcher.add_listener(on_config_change)
        await watcher.start()
        
        # Later...
        await watcher.stop()
    """
    
    def __init__(
        self,
        config_path: Path | None = None,
        debounce_seconds: float = 1.0,
    ):
        """Initialize the config watcher.
        
        Args:
            config_path: Path to the configuration file to watch. Uses default if None.
            debounce_seconds: Minimum time between reloads (default: 1.0s).
        """
        self.config_path = config_path or get_config_path()
        self.debounce_seconds = debounce_seconds
        self._listeners: list[Callable[[ConfigChangeEvent], None]] = []
        self._async_listeners: list[Callable[[ConfigChangeEvent], Any]] = []
        self._running = False
        self._watch_task: asyncio.Task | None = None
        self._last_reload_time: float = 0.0
        self._old_config: Any = None
    
    def add_listener(
        self,
        callback: Callable[[ConfigChangeEvent], None] | Callable[[ConfigChangeEvent], Any],
    ) -> None:
        """Add a listener to be notified on config changes.
        
        Args:
            callback: Function to call when config changes.
                     Can be sync or async.
        """
        if asyncio.iscoroutinefunction(callback):
            self._async_listeners.append(callback)
        else:
            self._listeners.append(callback)
        logger.debug(f"Added config change listener: {callback.__name__}")
    
    def remove_listener(
        self,
        callback: Callable[[ConfigChangeEvent], None] | Callable[[ConfigChangeEvent], Any],
    ) -> bool:
        """Remove a previously added listener.
        
        Args:
            callback: The callback to remove.
            
        Returns:
            True if the listener was found and removed, False otherwise.
        """
        if callback in self._listeners:
            self._listeners.remove(callback)
            return True
        if callback in self._async_listeners:
            self._async_listeners.remove(callback)
            return True
        return False
    
    async def start(self) -> None:
        """Start watching the configuration file."""
        if self._running:
            logger.warning("ConfigWatcher already running")
            return
        
        if not self.config_path.exists():
            logger.warning(f"Config file does not exist: {self.config_path}")
            return
        
        self._running = True
        self._watch_task = asyncio.create_task(self._watch_loop())
        logger.info(f"Started watching config file: {self.config_path}")
    
    async def stop(self) -> None:
        """Stop watching the configuration file."""
        if not self._running:
            return
        
        self._running = False
        
        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
            self._watch_task = None
        
        logger.info("Stopped config watcher")
    
    async def _watch_loop(self) -> None:
        """Main watch loop using watchfiles."""
        try:
            async for changes in awatch(self.config_path.parent):
                if not self._running:
                    break
                
                for change_type, path in changes:
                    path_obj = Path(path)
                    if path_obj.resolve() != self.config_path.resolve():
                        continue
                    
                    if change_type == Change.added:
                        logger.debug(f"Config file created: {path}")
                        await self._handle_change(ConfigChangeType.CREATED)
                    elif change_type == Change.modified:
                        logger.debug(f"Config file modified: {path}")
                        await self._handle_change(ConfigChangeType.MODIFIED)
                    elif change_type == Change.deleted:
                        logger.warning(f"Config file deleted: {path}")
                        event = ConfigChangeEvent(
                            change_type=ConfigChangeType.DELETED,
                            config_path=self.config_path,
                        )
                        await self._notify_listeners(event)
        
        except asyncio.CancelledError:
            logger.debug("Config watch loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in config watch loop: {e}")
    
    async def _handle_change(self, change_type: ConfigChangeType) -> None:
        """Handle a configuration file change with debouncing."""
        import time
        
        current_time = time.time()
        time_since_last = current_time - self._last_reload_time
        
        if time_since_last < self.debounce_seconds:
            logger.debug(
                f"Debouncing config reload (last reload {time_since_last:.2f}s ago)"
            )
            await asyncio.sleep(self.debounce_seconds - time_since_last)
        
        await self._reload_config(change_type)
        self._last_reload_time = time.time()
    
    async def _reload_config(self, change_type: ConfigChangeType) -> None:
        """Reload configuration and notify listeners."""
        try:
            from horbot.config.loader import get_cached_config
            
            old_config = get_cached_config()
            self._old_config = old_config
            
            try:
                new_config = reload_config()
            except Exception as e:
                logger.error(f"Failed to reload config: {e}")
                event = ConfigChangeEvent(
                    change_type=change_type,
                    config_path=self.config_path,
                    old_config=old_config,
                    error=str(e),
                )
                await self._notify_listeners(event)
                return
            
            changed_keys = self._find_changed_keys(old_config, new_config)
            
            event = ConfigChangeEvent(
                change_type=change_type,
                config_path=self.config_path,
                old_config=old_config,
                new_config=new_config,
                changed_keys=changed_keys,
            )
            
            await self._notify_listeners(event)
            
        except Exception as e:
            logger.error(f"Error during config reload: {e}")
    
    def _find_changed_keys(self, old_config: Any, new_config: Any) -> list[str]:
        """Find keys that changed between old and new config."""
        changed = []
        
        if not hasattr(old_config, "__dict__") or not hasattr(new_config, "__dict__"):
            return changed
        
        old_dict = old_config.__dict__
        new_dict = new_config.__dict__
        
        all_keys = set(old_dict.keys()) | set(new_dict.keys())
        
        for key in all_keys:
            if key.startswith("_"):
                continue
            
            old_val = old_dict.get(key)
            new_val = new_dict.get(key)
            
            if old_val != new_val:
                changed.append(key)
        
        return changed
    
    async def _notify_listeners(self, event: ConfigChangeEvent) -> None:
        """Notify all listeners of a config change."""
        for callback in self._listeners:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in config change listener: {e}")
        
        for callback in self._async_listeners:
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Error in async config change listener: {e}")
    
    async def __aenter__(self) -> "ConfigWatcher":
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.stop()


class ConfigManager:
    """Manages configuration with hot-reload support.
    
    Provides a high-level interface for configuration management:
    - Load and cache configuration
    - Hot-reload on file changes
    - Notify subscribers of changes
    - Validate configuration changes
    
    Usage:
        manager = ConfigManager(config_path)
        manager.subscribe(on_config_change)
        await manager.start()
        
        config = manager.config
        
        await manager.stop()
    """
    
    def __init__(
        self,
        config_path: Path | None = None,
        auto_reload: bool = True,
        debounce_seconds: float = 1.0,
    ):
        """Initialize the config manager.
        
        Args:
            config_path: Path to config file. Uses default if None.
            auto_reload: Whether to automatically reload on file changes.
            debounce_seconds: Debounce time for file changes.
        """
        from horbot.config.loader import load_config
        
        self.config_path = config_path or get_config_path()
        self.auto_reload = auto_reload
        self.debounce_seconds = debounce_seconds
        
        self._config = load_config(self.config_path)
        self._watcher: ConfigWatcher | None = None
        self._subscribers: list[Callable[[Any, Any], None]] = []
    
    @property
    def config(self) -> Any:
        """Get the current configuration."""
        return self._config
    
    def subscribe(self, callback: Callable[[Any, Any], None]) -> None:
        """Subscribe to configuration changes.
        
        Args:
            callback: Function called with (old_config, new_config).
        """
        self._subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable[[Any, Any], None]) -> bool:
        """Unsubscribe from configuration changes."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)
            return True
        return False
    
    async def start(self) -> None:
        """Start the config manager with hot-reload."""
        if not self.auto_reload:
            return
        
        self._watcher = ConfigWatcher(
            self.config_path,
            debounce_seconds=self.debounce_seconds,
        )
        self._watcher.add_listener(self._on_config_change)
        await self._watcher.start()
    
    async def stop(self) -> None:
        """Stop the config manager."""
        if self._watcher:
            await self._watcher.stop()
            self._watcher = None
    
    async def _on_config_change(self, event: ConfigChangeEvent) -> None:
        """Handle configuration file changes."""
        if event.change_type == ConfigChangeType.DELETED:
            logger.warning("Configuration file was deleted")
            return
        
        if event.error:
            logger.error(f"Configuration reload failed: {event.error}")
            return
        
        old_config = self._config
        self._config = event.new_config
        
        for callback in self._subscribers:
            try:
                callback(old_config, self._config)
            except Exception as e:
                logger.error(f"Error in config subscriber: {e}")
    
    def reload(self) -> None:
        """Force reload configuration from disk."""
        from horbot.config.loader import load_config
        
        old_config = self._config
        self._config = load_config(self.config_path)
        
        for callback in self._subscribers:
            try:
                callback(old_config, self._config)
            except Exception as e:
                logger.error(f"Error in config subscriber: {e}")
    
    def save(self) -> None:
        """Save current configuration to disk."""
        from horbot.config.loader import save_config
        save_config(self._config, self.config_path)
