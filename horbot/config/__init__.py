"""Configuration module for horbot."""

from horbot.config.loader import load_config, get_config_path, get_cached_config, save_config
from horbot.config.schema import Config
from horbot.config.validator import ConfigValidator
from horbot.config.migrator import ConfigMigrator

try:
    from horbot.config.watcher import ConfigWatcher, ConfigManager, ConfigChangeEvent, ConfigChangeType
    WATCHER_AVAILABLE = True
except ImportError:
    WATCHER_AVAILABLE = False

__all__ = [
    "Config",
    "load_config",
    "get_config_path",
    "get_cached_config",
    "save_config",
    "ConfigValidator",
    "ConfigMigrator",
]

if WATCHER_AVAILABLE:
    __all__.extend([
        "ConfigWatcher",
        "ConfigManager",
        "ConfigChangeEvent",
        "ConfigChangeType",
    ])
