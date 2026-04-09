"""HTTP ingress for gateway-side control operations."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from horbot.bus.events import OutboundMessage
from horbot.channels.manager import ChannelManager
from horbot.channels.telemetry import record_channel_event
from horbot.web.security import authorize_http_request


class GatewayOutboundDispatchRequest(BaseModel):
    """Payload for forwarding outbound messages into the gateway process."""

    channel: str
    chat_id: str
    content: str
    channel_instance_id: str | None = None
    target_agent_id: str | None = None
    reply_to: str | None = None
    media: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def build_gateway_http_app(channel_manager: ChannelManager) -> FastAPI:
    """Create a minimal HTTP app for outbound dispatch into the gateway."""

    app = FastAPI(title="Horbot Gateway Control")
    router = APIRouter(prefix="/api/gateway")

    @router.get("/health")
    async def health(request: Request) -> dict[str, Any]:
        authorize_http_request(request)
        return {
            "status": "ok",
            "channels": channel_manager.enabled_channels,
        }

    @router.post("/outbound")
    async def dispatch_outbound(
        payload: GatewayOutboundDispatchRequest,
        request: Request,
    ) -> dict[str, Any]:
        authorize_http_request(request)

        msg = OutboundMessage(
            channel=payload.channel,
            chat_id=payload.chat_id,
            content=payload.content,
            channel_instance_id=payload.channel_instance_id,
            target_agent_id=payload.target_agent_id,
            reply_to=payload.reply_to,
            media=list(payload.media or []),
            metadata=dict(payload.metadata or {}),
        )

        channel = channel_manager._resolve_outbound_channel(msg)
        if channel is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error_code": "CHANNEL_ENDPOINT_NOT_FOUND",
                    "message": "No matching channel endpoint found for outbound dispatch.",
                    "channel": msg.channel,
                    "channel_instance_id": msg.channel_instance_id,
                    "target_agent_id": msg.target_agent_id,
                },
            )

        await channel.send(msg)
        endpoint_id = getattr(channel, "endpoint_id", msg.channel)
        record_channel_event(
            endpoint_id,
            channel_type=getattr(channel, "name", msg.channel),
            event_type="outbound",
            status="ok",
            message=f"Dispatched outbound message to {msg.chat_id}",
            details={
                "chat_id": msg.chat_id,
                "target_agent_id": msg.target_agent_id,
                "media_count": len(msg.media or []),
                "via": "gateway_http",
            },
        )
        return {
            "status": "sent",
            "endpoint_id": endpoint_id,
            "channel": getattr(channel, "name", msg.channel),
            "chat_id": msg.chat_id,
        }

    app.include_router(router)
    return app
