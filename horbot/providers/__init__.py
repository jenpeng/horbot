"""LLM provider abstraction module."""

from horbot.providers.base import LLMProvider, LLMResponse
from horbot.providers.litellm_provider import LiteLLMProvider
from horbot.providers.openai_codex_provider import OpenAICodexProvider

try:
    from horbot.providers.selector import ProviderSelector, ProviderInfo, SelectionStrategy
    from horbot.providers.monitor import ProviderMonitor, ProviderMetrics, AlertConfig, HealthStatus
    SELECTOR_AVAILABLE = True
except ImportError:
    SELECTOR_AVAILABLE = False

__all__ = [
    "LLMProvider",
    "LLMResponse",
    "LiteLLMProvider",
    "OpenAICodexProvider",
]

if SELECTOR_AVAILABLE:
    __all__.extend([
        "ProviderSelector",
        "ProviderInfo",
        "SelectionStrategy",
        "ProviderMonitor",
        "ProviderMetrics",
        "AlertConfig",
        "HealthStatus",
    ])
