"""Channel monitor for health checking and automatic recovery."""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ChannelState(Enum):
    """Channel connection state."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    ERROR = "error"


@dataclass
class ChannelMetrics:
    """Metrics for a channel."""
    messages_sent: int = 0
    messages_received: int = 0
    errors: int = 0
    last_message_time: float | None = None
    last_error_time: float | None = None
    last_error_message: str | None = None
    connection_count: int = 0
    disconnection_count: int = 0
    total_uptime_seconds: float = 0.0
    reconnect_attempts: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "errors": self.errors,
            "last_message_time": self.last_message_time,
            "last_error_time": self.last_error_time,
            "last_error_message": self.last_error_message,
            "connection_count": self.connection_count,
            "disconnection_count": self.disconnection_count,
            "total_uptime_seconds": self.total_uptime_seconds,
            "reconnect_attempts": self.reconnect_attempts,
        }


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    healthy: bool
    latency_ms: float | None = None
    error_message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class ChannelMonitor:
    """Monitor channels for health and automatic recovery.
    
    Features:
    - Periodic health checks
    - Automatic restart of unhealthy channels
    - Metrics collection
    - Alert callbacks
    
    Usage:
        monitor = ChannelMonitor(check_interval=60)
        monitor.add_channel(channel)
        monitor.on_unhealthy = my_callback
        await monitor.start()
        
        # Later...
        await monitor.stop()
    """
    
    def __init__(
        self,
        check_interval: float = 60.0,
        unhealthy_threshold: int = 3,
        restart_delay: float = 5.0,
        max_restart_attempts: int = 5,
    ):
        """Initialize the channel monitor.
        
        Args:
            check_interval: Seconds between health checks.
            unhealthy_threshold: Number of failed checks before marking unhealthy.
            restart_delay: Seconds to wait before restarting a channel.
            max_restart_attempts: Maximum restart attempts before giving up.
        """
        self.check_interval = check_interval
        self.unhealthy_threshold = unhealthy_threshold
        self.restart_delay = restart_delay
        self.max_restart_attempts = max_restart_attempts
        
        self._channels: dict[str, Any] = {}
        self._states: dict[str, ChannelState] = {}
        self._metrics: dict[str, ChannelMetrics] = {}
        self._health_status: dict[str, int] = {}  # consecutive failures
        self._restart_counts: dict[str, int] = {}
        self._running = False
        self._task: asyncio.Task | None = None
        
        self.on_unhealthy: Any = None
        self.on_recovered: Any = None
        self.on_restart_failed: Any = None
    
    def add_channel(self, channel: Any) -> None:
        """Add a channel to monitor.
        
        Args:
            channel: Channel instance to monitor.
        """
        name = channel.name
        self._channels[name] = channel
        self._states[name] = ChannelState.DISCONNECTED
        self._metrics[name] = ChannelMetrics()
        self._health_status[name] = 0
        self._restart_counts[name] = 0
        logger.info(f"Added channel to monitor: {name}")
    
    def remove_channel(self, name: str) -> bool:
        """Remove a channel from monitoring.
        
        Args:
            name: Channel name to remove.
            
        Returns:
            True if channel was removed, False if not found.
        """
        if name in self._channels:
            del self._channels[name]
            del self._states[name]
            del self._metrics[name]
            del self._health_status[name]
            del self._restart_counts[name]
            logger.info(f"Removed channel from monitor: {name}")
            return True
        return False
    
    def get_state(self, name: str) -> ChannelState | None:
        """Get the current state of a channel."""
        return self._states.get(name)
    
    def get_metrics(self, name: str) -> ChannelMetrics | None:
        """Get metrics for a channel."""
        return self._metrics.get(name)
    
    def get_all_metrics(self) -> dict[str, ChannelMetrics]:
        """Get metrics for all channels."""
        return dict(self._metrics)
    
    def update_state(self, name: str, state: ChannelState) -> None:
        """Update channel state.
        
        Args:
            name: Channel name.
            state: New state.
        """
        old_state = self._states.get(name)
        self._states[name] = state
        
        if state == ChannelState.CONNECTED and old_state != ChannelState.CONNECTED:
            self._metrics[name].connection_count += 1
        elif state == ChannelState.DISCONNECTED and old_state != ChannelState.DISCONNECTED:
            self._metrics[name].disconnection_count += 1
        
        logger.debug(f"Channel {name} state: {old_state} -> {state}")
    
    def record_message_sent(self, name: str) -> None:
        """Record a sent message."""
        if name in self._metrics:
            self._metrics[name].messages_sent += 1
            self._metrics[name].last_message_time = time.time()
    
    def record_message_received(self, name: str) -> None:
        """Record a received message."""
        if name in self._metrics:
            self._metrics[name].messages_received += 1
            self._metrics[name].last_message_time = time.time()
    
    def record_error(self, name: str, error_message: str) -> None:
        """Record an error."""
        if name in self._metrics:
            self._metrics[name].errors += 1
            self._metrics[name].last_error_time = time.time()
            self._metrics[name].last_error_message = error_message
    
    async def start(self) -> None:
        """Start the monitor."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Channel monitor started")
    
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
        logger.info("Channel monitor stopped")
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await self._check_all_channels()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(5.0)
    
    async def _check_all_channels(self) -> None:
        """Check health of all channels."""
        for name, channel in list(self._channels.items()):
            try:
                result = await self._check_channel_health(channel)
                
                if result.healthy:
                    self._health_status[name] = 0
                    
                    if self._states[name] == ChannelState.ERROR:
                        self.update_state(name, ChannelState.CONNECTED)
                        if self.on_recovered:
                            await self._call_callback(self.on_recovered, name)
                else:
                    self._health_status[name] += 1
                    logger.warning(
                        f"Channel {name} health check failed "
                        f"({self._health_status[name]}/{self.unhealthy_threshold}): "
                        f"{result.error_message}"
                    )
                    
                    if self._health_status[name] >= self.unhealthy_threshold:
                        await self._handle_unhealthy_channel(name, channel)
                        
            except Exception as e:
                logger.error(f"Error checking channel {name}: {e}")
                self._health_status[name] += 1
    
    async def _check_channel_health(self, channel: Any) -> HealthCheckResult:
        """Check health of a single channel.
        
        Args:
            channel: Channel to check.
            
        Returns:
            Health check result.
        """
        name = channel.name
        
        if not hasattr(channel, 'health_check'):
            if channel.is_running:
                return HealthCheckResult(healthy=True)
            return HealthCheckResult(
                healthy=False,
                error_message="Channel not running",
            )
        
        try:
            start_time = time.time()
            healthy = await channel.health_check()
            latency = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                healthy=healthy,
                latency_ms=latency,
            )
        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                error_message=str(e),
            )
    
    async def _handle_unhealthy_channel(self, name: str, channel: Any) -> None:
        """Handle an unhealthy channel.
        
        Args:
            name: Channel name.
            channel: Channel instance.
        """
        self.update_state(name, ChannelState.ERROR)
        
        if self.on_unhealthy:
            await self._call_callback(self.on_unhealthy, name)
        
        if self._restart_counts[name] < self.max_restart_attempts:
            logger.info(f"Attempting to restart channel {name}")
            await asyncio.sleep(self.restart_delay)
            
            try:
                await channel.stop()
                await asyncio.sleep(1.0)
                await channel.start()
                
                self._restart_counts[name] += 1
                self._metrics[name].reconnect_attempts += 1
                self._health_status[name] = 0
                
                logger.info(f"Channel {name} restarted successfully")
                
            except Exception as e:
                logger.error(f"Failed to restart channel {name}: {e}")
                self.record_error(name, f"Restart failed: {e}")
        else:
            logger.error(
                f"Channel {name} exceeded max restart attempts "
                f"({self.max_restart_attempts})"
            )
            if self.on_restart_failed:
                await self._call_callback(self.on_restart_failed, name)
    
    async def _call_callback(self, callback: Any, *args: Any) -> None:
        """Call a callback function safely."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
        except Exception as e:
            logger.error(f"Error in callback: {e}")
    
    def get_status_report(self) -> dict[str, Any]:
        """Get a comprehensive status report."""
        return {
            "running": self._running,
            "check_interval": self.check_interval,
            "channels": {
                name: {
                    "state": self._states[name].value,
                    "health_failures": self._health_status[name],
                    "restart_count": self._restart_counts[name],
                    "metrics": self._metrics[name].to_dict(),
                }
                for name in self._channels
            },
        }
