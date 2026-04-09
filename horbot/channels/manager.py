"""Channel manager for coordinating chat channels."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from horbot.bus.events import OutboundMessage
from horbot.bus.queue import MessageBus
from horbot.channels.base import BaseChannel
from horbot.channels.endpoints import build_runtime_channel_config, list_channel_endpoints
from horbot.channels.telemetry import record_channel_event
from horbot.config.schema import Config


class ChannelManager:
    """
    Manages chat channels and coordinates message routing.
    
    Responsibilities:
    - Initialize enabled channels (Telegram, WhatsApp, etc.)
    - Start/stop channels
    - Route outbound messages
    """
    
    def __init__(self, config: Config, bus: MessageBus):
        self.config = config
        self.bus = bus
        self.channels: dict[str, BaseChannel] = {}
        self._dispatch_task: asyncio.Task | None = None
        
        self._init_channels()
    
    def _init_channels(self) -> None:
        """Initialize channels based on config."""
        channel_factories = {
            "telegram": self._build_telegram_channel,
            "whatsapp": self._build_whatsapp_channel,
            "discord": self._build_discord_channel,
            "feishu": self._build_feishu_channel,
            "mochat": self._build_mochat_channel,
            "dingtalk": self._build_dingtalk_channel,
            "email": self._build_email_channel,
            "slack": self._build_slack_channel,
            "qq": self._build_qq_channel,
            "sharecrm": self._build_sharecrm_channel,
        }

        for endpoint in list_channel_endpoints(self.config):
            if not endpoint.enabled:
                continue
            factory = channel_factories.get(endpoint.type)
            if factory is None:
                logger.warning("Unsupported channel type for endpoint {}: {}", endpoint.id, endpoint.type)
                continue
            try:
                channel = factory(endpoint)
                if channel is None:
                    continue
                self.channels[endpoint.id] = channel
                record_channel_event(
                    endpoint.id,
                    channel_type=endpoint.type,
                    event_type="lifecycle",
                    status="ok",
                    message=f"Endpoint loaded for agent {endpoint.agent_id or 'unbound'}",
                    details={"source": endpoint.source, "agent_id": endpoint.agent_id},
                )
                logger.info(
                    "Channel endpoint enabled: id={}, type={}, agent_id={}, source={}",
                    endpoint.id,
                    endpoint.type,
                    endpoint.agent_id or "-",
                    endpoint.source,
                )
            except ImportError as e:
                logger.warning("{} channel not available: {}", endpoint.type, e)

    def _channel_common_kwargs(self, endpoint) -> dict[str, Any]:
        return {
            "endpoint_id": endpoint.id,
            "target_agent_id": endpoint.agent_id or None,
            "endpoint_name": endpoint.name,
        }

    def _build_telegram_channel(self, endpoint) -> BaseChannel:
        from horbot.channels.telegram import TelegramChannel

        runtime_config = build_runtime_channel_config(self.config.channels, endpoint)
        return TelegramChannel(
            runtime_config,
            self.bus,
            groq_api_key=self.config.providers.groq.api_key,
            **self._channel_common_kwargs(endpoint),
        )

    def _build_whatsapp_channel(self, endpoint) -> BaseChannel:
        from horbot.channels.whatsapp import WhatsAppChannel

        runtime_config = build_runtime_channel_config(self.config.channels, endpoint)
        return WhatsAppChannel(runtime_config, self.bus, **self._channel_common_kwargs(endpoint))

    def _build_discord_channel(self, endpoint) -> BaseChannel:
        from horbot.channels.discord import DiscordChannel

        runtime_config = build_runtime_channel_config(self.config.channels, endpoint)
        return DiscordChannel(runtime_config, self.bus, **self._channel_common_kwargs(endpoint))

    def _build_feishu_channel(self, endpoint) -> BaseChannel:
        from horbot.channels.feishu import FeishuChannel

        runtime_config = build_runtime_channel_config(self.config.channels, endpoint)
        return FeishuChannel(runtime_config, self.bus, **self._channel_common_kwargs(endpoint))

    def _build_mochat_channel(self, endpoint) -> BaseChannel:
        from horbot.channels.mochat import MochatChannel

        runtime_config = build_runtime_channel_config(self.config.channels, endpoint)
        return MochatChannel(runtime_config, self.bus, **self._channel_common_kwargs(endpoint))

    def _build_dingtalk_channel(self, endpoint) -> BaseChannel:
        from horbot.channels.dingtalk import DingTalkChannel

        runtime_config = build_runtime_channel_config(self.config.channels, endpoint)
        return DingTalkChannel(runtime_config, self.bus, **self._channel_common_kwargs(endpoint))

    def _build_email_channel(self, endpoint) -> BaseChannel:
        from horbot.channels.email import EmailChannel

        runtime_config = build_runtime_channel_config(self.config.channels, endpoint)
        return EmailChannel(runtime_config, self.bus, **self._channel_common_kwargs(endpoint))

    def _build_slack_channel(self, endpoint) -> BaseChannel:
        from horbot.channels.slack import SlackChannel

        runtime_config = build_runtime_channel_config(self.config.channels, endpoint)
        return SlackChannel(runtime_config, self.bus, **self._channel_common_kwargs(endpoint))

    def _build_qq_channel(self, endpoint) -> BaseChannel:
        from horbot.channels.qq import QQChannel

        runtime_config = build_runtime_channel_config(self.config.channels, endpoint)
        return QQChannel(runtime_config, self.bus, **self._channel_common_kwargs(endpoint))

    def _build_sharecrm_channel(self, endpoint) -> BaseChannel:
        from horbot.channels.sharecrm import ShareCrmChannel

        runtime_config = build_runtime_channel_config(self.config.channels, endpoint)
        return ShareCrmChannel(runtime_config, self.bus, **self._channel_common_kwargs(endpoint))
    
    async def _start_channel(self, name: str, channel: BaseChannel) -> None:
        """Start a channel and log any exceptions."""
        try:
            record_channel_event(
                name,
                channel_type=channel.name,
                event_type="lifecycle",
                status="ok",
                message="Starting channel endpoint",
            )
            await channel.start()
        except Exception as e:
            record_channel_event(
                name,
                channel_type=channel.name,
                event_type="lifecycle",
                status="error",
                message=f"Failed to start channel endpoint: {e}",
            )
            logger.error("Failed to start channel {}: {}", name, e)

    async def start_all(self) -> None:
        """Start all channels and the outbound dispatcher."""
        if not self.channels:
            logger.warning("No channels enabled")
            return
        
        # Start outbound dispatcher
        self._dispatch_task = asyncio.create_task(self._dispatch_outbound())
        
        # Start channels
        tasks = []
        for name, channel in self.channels.items():
            logger.info("Starting {} channel...", name)
            tasks.append(asyncio.create_task(self._start_channel(name, channel)))
        
        # Wait for all to complete (they should run forever)
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop_all(self) -> None:
        """Stop all channels and the dispatcher."""
        logger.info("Stopping all channels...")
        
        # Stop dispatcher
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass
        
        # Stop all channels
        for name, channel in self.channels.items():
            try:
                await channel.stop()
                logger.info("Stopped {} channel", name)
            except Exception as e:
                logger.error("Error stopping {}: {}", name, e)
    
    async def _dispatch_outbound(self) -> None:
        """Dispatch outbound messages to the appropriate channel."""
        logger.info("Outbound dispatcher started")
        
        while True:
            try:
                msg = await asyncio.wait_for(
                    self.bus.consume_outbound(),
                    timeout=1.0
                )
                
                logger.debug("Dispatching outbound message to channel: {}", msg.channel)
                
                if msg.metadata.get("_progress"):
                    if msg.metadata.get("_tool_hint") and not self.config.channels.send_tool_hints:
                        continue
                    if not msg.metadata.get("_tool_hint") and not self.config.channels.send_progress:
                        continue

                channel = self._resolve_outbound_channel(msg)
                if channel:
                    try:
                        await channel.send(msg)
                        record_channel_event(
                            getattr(channel, "endpoint_id", msg.channel),
                            channel_type=channel.name,
                            event_type="outbound",
                            status="ok",
                            message=f"Sent outbound message to {msg.chat_id}",
                            details={"chat_id": msg.chat_id},
                        )
                        logger.info(
                            "Message sent successfully via channel endpoint {} (type={})",
                            getattr(channel, "endpoint_id", msg.channel),
                            msg.channel,
                        )
                    except Exception as e:
                        record_channel_event(
                            getattr(channel, "endpoint_id", msg.channel),
                            channel_type=channel.name,
                            event_type="outbound",
                            status="error",
                            message=f"Failed to send outbound message: {e}",
                            details={"chat_id": msg.chat_id},
                        )
                        logger.error("Error sending to {}: {}", getattr(channel, "endpoint_id", msg.channel), e)
                else:
                    logger.warning(
                        "Unknown channel endpoint for outbound message: channel={}, endpoint_id={}, target_agent_id={}",
                        msg.channel,
                        msg.channel_instance_id,
                        msg.target_agent_id,
                    )
                    
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
    
    def get_channel(self, name: str) -> BaseChannel | None:
        """Get a channel by name."""
        return self.channels.get(name)
    
    def get_status(self) -> dict[str, Any]:
        """Get status of all channels."""
        return {
            name: {
                "enabled": True,
                "running": channel.is_running,
                "type": channel.name,
                "agent_id": getattr(channel, "target_agent_id", None),
            }
            for name, channel in self.channels.items()
        }
    
    @property
    def enabled_channels(self) -> list[str]:
        """Get list of enabled channel names."""
        return list(self.channels.keys())

    def _resolve_outbound_channel(self, msg: OutboundMessage) -> BaseChannel | None:
        if msg.channel_instance_id:
            return self.channels.get(msg.channel_instance_id)

        candidates = [
            channel
            for channel in self.channels.values()
            if channel.name == msg.channel
        ]
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        if msg.target_agent_id:
            for channel in candidates:
                if getattr(channel, "target_agent_id", None) == msg.target_agent_id:
                    return channel
        metadata_endpoint_id = msg.metadata.get("channel_instance_id") if msg.metadata else None
        if metadata_endpoint_id:
            return self.channels.get(metadata_endpoint_id)
        return None
