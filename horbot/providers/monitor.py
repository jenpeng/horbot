"""Provider monitor for health checking and alerting."""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class AlertConfig:
    """Configuration for provider alerts."""
    error_rate_threshold: float = 0.2
    latency_threshold_ms: float = 5000.0
    consecutive_failures_threshold: int = 3
    check_interval: float = 60.0
    alert_cooldown: float = 300.0


@dataclass
class ProviderAlert:
    """An alert for a provider."""
    provider_name: str
    alert_type: str
    message: str
    timestamp: float
    details: dict[str, Any] = field(default_factory=dict)


class ProviderMonitor:
    """Monitor provider health and generate alerts.
    
    Features:
    - Periodic health checks
    - Error rate monitoring
    - Latency monitoring
    - Alert callbacks
    
    Usage:
        monitor = ProviderMonitor(
            providers=[openai_provider, anthropic_provider],
            alert_config=AlertConfig(error_rate_threshold=0.1),
        )
        
        monitor.on_alert = my_alert_handler
        await monitor.start()
        
        # Later...
        await monitor.stop()
    """
    
    def __init__(
        self,
        providers: list[Any],
        alert_config: AlertConfig | None = None,
    ):
        """Initialize the provider monitor.
        
        Args:
            providers: List of provider instances to monitor.
            alert_config: Alert configuration.
        """
        self.providers = {p.name: p for p in providers}
        self.alert_config = alert_config or AlertConfig()
        
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_alert_time: dict[str, float] = {}
        self._error_counts: dict[str, int] = {}
        self._success_counts: dict[str, int] = {}
        self._latencies: dict[str, list[float]] = {}
        
        self.on_alert: Callable[[ProviderAlert], None] | None = None
        self.on_high_error_rate: Callable[[str, float], None] | None = None
        self.on_high_latency: Callable[[str, float], None] | None = None
        self.on_unhealthy: Callable[[str], None] | None = None
    
    async def start(self) -> None:
        """Start the monitor."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Provider monitor started")
    
    async def stop(self) -> None:
        """Stop the monitor."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Provider monitor stopped")
    
    def record_success(self, name: str, latency_ms: float) -> None:
        """Record a successful request.
        
        Args:
            name: Provider name.
            latency_ms: Request latency in milliseconds.
        """
        self._success_counts[name] = self._success_counts.get(name, 0) + 1
        
        if name not in self._latencies:
            self._latencies[name] = []
        self._latencies[name].append(latency_ms)
        
        if len(self._latencies[name]) > 100:
            self._latencies[name] = self._latencies[name][-100:]
    
    def record_error(self, name: str) -> None:
        """Record a failed request.
        
        Args:
            name: Provider name.
        """
        self._error_counts[name] = self._error_counts.get(name, 0) + 1
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await self._check_all_providers()
                await asyncio.sleep(self.alert_config.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(5.0)
    
    async def _check_all_providers(self) -> None:
        """Check all providers."""
        for name, provider in self.providers.items():
            try:
                await self._check_provider(name, provider)
            except Exception as e:
                logger.error(f"Error checking provider {name}: {e}")
    
    async def _check_provider(self, name: str, provider: Any) -> None:
        """Check a single provider.
        
        Args:
            name: Provider name.
            provider: Provider instance.
        """
        await self._check_error_rate(name)
        await self._check_latency(name)
        
        if hasattr(provider, 'health_check'):
            try:
                healthy = await provider.health_check()
                if not healthy:
                    self._emit_alert(ProviderAlert(
                        provider_name=name,
                        alert_type="unhealthy",
                        message=f"Provider {name} health check failed",
                        timestamp=time.time(),
                    ))
                    if self.on_unhealthy:
                        self._call_callback(self.on_unhealthy, name)
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
    
    async def _check_error_rate(self, name: str) -> None:
        """Check error rate for a provider.
        
        Args:
            name: Provider name.
        """
        errors = self._error_counts.get(name, 0)
        successes = self._success_counts.get(name, 0)
        total = errors + successes
        
        if total > 0:
            error_rate = errors / total
            
            if error_rate > self.alert_config.error_rate_threshold:
                self._emit_alert(ProviderAlert(
                    provider_name=name,
                    alert_type="high_error_rate",
                    message=f"Provider {name} error rate: {error_rate:.1%}",
                    timestamp=time.time(),
                    details={"error_rate": error_rate, "errors": errors, "total": total},
                ))
                if self.on_high_error_rate:
                    self._call_callback(self.on_high_error_rate, name, error_rate)
    
    async def _check_latency(self, name: str) -> None:
        """Check latency for a provider.
        
        Args:
            name: Provider name.
        """
        latencies = self._latencies.get(name, [])
        
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            
            if avg_latency > self.alert_config.latency_threshold_ms:
                self._emit_alert(ProviderAlert(
                    provider_name=name,
                    alert_type="high_latency",
                    message=f"Provider {name} avg latency: {avg_latency:.0f}ms",
                    timestamp=time.time(),
                    details={"avg_latency_ms": avg_latency},
                ))
                if self.on_high_latency:
                    self._call_callback(self.on_high_latency, name, avg_latency)
    
    def _emit_alert(self, alert: ProviderAlert) -> None:
        """Emit an alert.
        
        Args:
            alert: Alert to emit.
        """
        now = time.time()
        last_alert = self._last_alert_time.get(alert.provider_name, 0)
        
        if now - last_alert < self.alert_config.alert_cooldown:
            return
        
        self._last_alert_time[alert.provider_name] = now
        
        logger.warning(
            f"Provider alert: {alert.provider_name} - {alert.alert_type}: {alert.message}"
        )
        
        if self.on_alert:
            self._call_callback(self.on_alert, alert)
    
    def _call_callback(self, callback: Any, *args: Any) -> None:
        """Call a callback safely."""
        try:
            if asyncio.iscoroutinefunction(callback):
                asyncio.create_task(callback(*args))
            else:
                callback(*args)
        except Exception as e:
            logger.error(f"Error in callback: {e}")
    
    def get_aggregated_metrics(self) -> dict[str, Any]:
        """Get aggregated metrics for all providers."""
        metrics = {}
        
        for name in self.providers:
            errors = self._error_counts.get(name, 0)
            successes = self._success_counts.get(name, 0)
            total = errors + successes
            
            latencies = self._latencies.get(name, [])
            avg_latency = sum(latencies) / len(latencies) if latencies else None
            
            metrics[name] = {
                "total_requests": total,
                "errors": errors,
                "successes": successes,
                "error_rate": errors / total if total > 0 else 0,
                "avg_latency_ms": avg_latency,
                "recent_latencies": latencies[-10:] if latencies else [],
            }
        
        return metrics
    
    def get_status_report(self) -> dict[str, Any]:
        """Get a comprehensive status report."""
        return {
            "running": self._running,
            "check_interval": self.alert_config.check_interval,
            "providers": self.get_aggregated_metrics(),
        }
    
    def reset_counters(self, name: str | None = None) -> None:
        """Reset error/success counters.
        
        Args:
            name: Provider name, or None to reset all.
        """
        if name:
            self._error_counts[name] = 0
            self._success_counts[name] = 0
            self._latencies[name] = []
        else:
            self._error_counts.clear()
            self._success_counts.clear()
            self._latencies.clear()
