"""Horbot inbound bot channel endpoint.

This channel is served by FastAPI inbound routes instead of a long-running
vendor socket. The ChannelManager still owns a lightweight instance so outbound
routing and runtime status do not report it as unsupported.
"""

from __future__ import annotations

import asyncio

from loguru import logger

from horbot.bus.events import OutboundMessage
from horbot.channels.base import BaseChannel


class HorbotInboundBotChannel(BaseChannel):
    """No-op runtime channel for Horbot-issued inbound bot endpoints."""

    name = "horbot-inbound-bot"

    async def start(self) -> None:
        self._running = True
        while self._running:
            await asyncio.sleep(3600)

    async def stop(self) -> None:
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        logger.info(
            "Horbot inbound bot response retained in session: endpoint={}, chat_id={}, chars={}",
            self.endpoint_id,
            msg.chat_id,
            len(msg.content or ""),
        )
