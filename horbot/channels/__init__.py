"""Chat channels module with plugin architecture."""

from horbot.channels.base import BaseChannel
from horbot.channels.manager import ChannelManager
from horbot.channels.monitor import ChannelMonitor, ChannelState, ChannelMetrics, HealthCheckResult

__all__ = [
    "BaseChannel",
    "ChannelManager",
    "ChannelMonitor",
    "ChannelState",
    "ChannelMetrics",
    "HealthCheckResult",
]
