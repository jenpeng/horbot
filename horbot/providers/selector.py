"""Provider selector with fallback and load balancing support."""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SelectionStrategy(Enum):
    """Provider selection strategy."""
    PRIORITY = "priority"
    ROUND_ROBIN = "round_robin"
    LEAST_LATENCY = "least_latency"
    WEIGHTED = "weighted"


@dataclass
class ProviderInfo:
    """Information about a provider for selection."""
    provider: Any
    priority: int = 0
    weight: float = 1.0
    models: list[str] = field(default_factory=list)
    enabled: bool = True
    
    def supports_model(self, model: str) -> bool:
        """Check if this provider supports a model.
        
        Args:
            model: Model name to check.
            
        Returns:
            True if provider supports the model.
        """
        if not self.models:
            return True
        for pattern in self.models:
            if pattern.endswith("*"):
                if model.startswith(pattern[:-1]):
                    return True
            elif model == pattern:
                return True
        return False


@dataclass
class ProviderStatus:
    """Runtime status of a provider."""
    healthy: bool = True
    latency_ms: float | None = None
    error_count: int = 0
    last_error: str | None = None
    last_success: float | None = None


class ProviderSelector:
    """Select providers based on strategy with fallback support.
    
    Features:
    - Multiple selection strategies
    - Health-aware selection
    - Automatic fallback on failure
    - Model-based routing
    
    Usage:
        selector = ProviderSelector(
            providers=[
                ProviderInfo(provider=openai, priority=0, models=["gpt-*"]),
                ProviderInfo(provider=anthropic, priority=1, models=["claude-*"]),
            ],
            strategy=SelectionStrategy.PRIORITY,
            fallback_enabled=True,
        )
        
        response = await selector.execute_with_fallback(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-4",
        )
    """
    
    def __init__(
        self,
        providers: list[ProviderInfo],
        strategy: SelectionStrategy = SelectionStrategy.PRIORITY,
        fallback_enabled: bool = True,
        max_fallback_attempts: int = 3,
    ):
        """Initialize the provider selector.
        
        Args:
            providers: List of provider info objects.
            strategy: Selection strategy to use.
            fallback_enabled: Whether to fallback on failure.
            max_fallback_attempts: Maximum fallback attempts.
        """
        self.providers = providers
        self.strategy = strategy
        self.fallback_enabled = fallback_enabled
        self.max_fallback_attempts = max_fallback_attempts
        
        self._status: dict[str, ProviderStatus] = {
            p.provider.name: ProviderStatus() for p in providers
        }
        self._round_robin_index = 0
    
    def get_provider_for_model(self, model: str) -> Any | None:
        """Get the best provider for a model.
        
        Args:
            model: Model name.
            
        Returns:
            Provider instance or None if no suitable provider.
        """
        candidates = [
            p for p in self.providers
            if p.enabled and p.supports_model(model) and self._status[p.provider.name].healthy
        ]
        
        if not candidates:
            candidates = [
                p for p in self.providers
                if p.enabled and p.supports_model(model)
            ]
        
        if not candidates:
            return None
        
        return self._select_provider(candidates).provider
    
    def _select_provider(self, candidates: list[ProviderInfo]) -> ProviderInfo:
        """Select a provider from candidates based on strategy.
        
        Args:
            candidates: List of candidate providers.
            
        Returns:
            Selected provider info.
        """
        if self.strategy == SelectionStrategy.PRIORITY:
            return min(candidates, key=lambda p: p.priority)
        
        elif self.strategy == SelectionStrategy.ROUND_ROBIN:
            self._round_robin_index = (self._round_robin_index + 1) % len(candidates)
            return candidates[self._round_robin_index]
        
        elif self.strategy == SelectionStrategy.LEAST_LATENCY:
            valid = [p for p in candidates if self._status[p.provider.name].latency_ms is not None]
            if valid:
                return min(valid, key=lambda p: self._status[p.provider.name].latency_ms or float('inf'))
            return candidates[0]
        
        elif self.strategy == SelectionStrategy.WEIGHTED:
            total_weight = sum(p.weight for p in candidates)
            r = random.uniform(0, total_weight)
            cumulative = 0.0
            for p in candidates:
                cumulative += p.weight
                if r <= cumulative:
                    return p
            return candidates[-1]
        
        return candidates[0]
    
    async def execute_with_fallback(
        self,
        messages: list[dict],
        model: str,
        **kwargs: Any,
    ) -> Any:
        """Execute a request with automatic fallback.
        
        Args:
            messages: Chat messages.
            model: Model name.
            **kwargs: Additional arguments for the provider.
            
        Returns:
            Response from the provider.
            
        Raises:
            Exception: If all providers fail.
        """
        candidates = [
            p for p in self.providers
            if p.enabled and p.supports_model(model)
        ]
        
        if not candidates:
            raise ValueError(f"No provider available for model: {model}")
        
        candidates = self._sort_candidates(candidates)
        
        errors = []
        for attempt, provider_info in enumerate(candidates[:self.max_fallback_attempts]):
            provider = provider_info.provider
            name = provider.name
            
            try:
                start_time = time.time()
                response = await provider.chat(messages, model=model, **kwargs)
                latency = (time.time() - start_time) * 1000
                
                self._status[name].healthy = True
                self._status[name].latency_ms = latency
                self._status[name].last_success = time.time()
                self._status[name].error_count = 0
                
                return response
                
            except Exception as e:
                errors.append((name, str(e)))
                self._status[name].healthy = False
                self._status[name].error_count += 1
                self._status[name].last_error = str(e)
                
                logger.warning(
                    f"Provider {name} failed (attempt {attempt + 1}): {e}"
                )
                
                if not self.fallback_enabled:
                    raise
        
        error_msg = "; ".join(f"{n}: {e}" for n, e in errors)
        raise Exception(f"All providers failed: {error_msg}")
    
    def _sort_candidates(self, candidates: list[ProviderInfo]) -> list[ProviderInfo]:
        """Sort candidates by health and priority.
        
        Args:
            candidates: List of candidates.
            
        Returns:
            Sorted list with healthy providers first.
        """
        def sort_key(p: ProviderInfo) -> tuple:
            healthy = 0 if self._status[p.provider.name].healthy else 1
            return (healthy, p.priority)
        
        return sorted(candidates, key=sort_key)
    
    def mark_healthy(self, name: str) -> None:
        """Mark a provider as healthy.
        
        Args:
            name: Provider name.
        """
        if name in self._status:
            self._status[name].healthy = True
            self._status[name].error_count = 0
    
    def mark_unhealthy(self, name: str, error: str | None = None) -> None:
        """Mark a provider as unhealthy.
        
        Args:
            name: Provider name.
            error: Optional error message.
        """
        if name in self._status:
            self._status[name].healthy = False
            self._status[name].error_count += 1
            if error:
                self._status[name].last_error = error
    
    def get_status_report(self) -> dict[str, Any]:
        """Get a status report for all providers."""
        return {
            "strategy": self.strategy.value,
            "fallback_enabled": self.fallback_enabled,
            "providers": {
                p.provider.name: {
                    "priority": p.priority,
                    "weight": p.weight,
                    "models": p.models,
                    "enabled": p.enabled,
                    "healthy": self._status[p.provider.name].healthy,
                    "latency_ms": self._status[p.provider.name].latency_ms,
                    "error_count": self._status[p.provider.name].error_count,
                    "last_error": self._status[p.provider.name].last_error,
                }
                for p in self.providers
            },
        }
