"""Channel endpoint API routes."""

from datetime import datetime
from typing import Any, Awaitable, Callable, Dict
import re
import secrets
import uuid

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from horbot.bus.events import InboundMessage
from horbot.channels.endpoints import (
    CHANNEL_TYPE_MODELS,
    build_legacy_endpoint,
    build_custom_endpoint,
    build_runtime_channel_config,
    find_channel_endpoint,
    get_channel_catalog,
    list_channel_endpoints,
)
from horbot.channels.telemetry import get_channel_events, get_channel_summary, record_channel_event
from horbot.config.schema import ChannelEndpointConfig, Config


class ChannelUpdateRequest(BaseModel):
    """Supported dashboard channel updates."""

    enabled: bool | None = None


class ChannelEndpointUpsertRequest(BaseModel):
    """Create or update a channel endpoint."""

    id: str | None = None
    type: str
    name: str = ""
    agent_id: str = ""
    enabled: bool = True
    allow_from: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)


class ChannelInboundBotRequest(BaseModel):
    """Message pushed to a Horbot-issued channel inbound bot."""

    content: str
    token: str = ""
    chat_id: str = ""
    sender_id: str = ""
    message_id: str = ""
    target_agent_id: str = ""
    agent_id: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _normalize_string_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values or []:
        item = str(value).strip()
        if item and item not in seen:
            normalized.append(item)
            seen.add(item)
    return normalized


def _serialize_channel_endpoint(endpoint) -> dict[str, Any]:
    data = endpoint.to_dict() if hasattr(endpoint, "to_dict") else endpoint
    endpoint_id = data.get("id")
    if endpoint_id:
        data["runtime"] = get_channel_summary(endpoint_id)
    return data


def _normalize_channel_endpoint_payload(request: ChannelEndpointUpsertRequest) -> ChannelEndpointUpsertRequest:
    request.type = request.type.strip().lower()
    request.name = request.name.strip()
    request.agent_id = request.agent_id.strip()
    request.allow_from = _normalize_string_list(request.allow_from)
    request.config = {
        str(key): value
        for key, value in (request.config or {}).items()
        if key is not None
    }
    if request.id is not None:
        request.id = request.id.strip()
    return request


def _is_horbot_inbound_channel_type(channel_type: str) -> bool:
    return channel_type.strip().lower() == "horbot-inbound-bot"


def _ensure_channel_inbound_bot_credentials(
    channel_type: str,
    endpoint_id: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    next_config = dict(config or {})
    if not _is_horbot_inbound_channel_type(channel_type):
        return next_config

    safe_id = re.sub(r"[^a-z0-9_-]+", "-", endpoint_id.strip().lower()).strip("-") or "channel"
    if not str(next_config.get("bot_app_id") or "").strip():
        next_config["bot_app_id"] = f"hbot_ch_{safe_id}_{secrets.token_hex(4)}"
    bot_app_id = str(next_config.get("bot_app_id") or "").strip()
    if not str(next_config.get("bot_token") or "").strip():
        next_config["bot_token"] = secrets.token_urlsafe(32)
    next_config["inbound_url_path"] = f"/api/channels/inbound/{bot_app_id}/messages"
    return next_config


def _apply_endpoint_binding(config: Config, endpoint_id: str, agent_id: str) -> None:
    for current_agent in config.agents.instances.values():
        current_agent.channel_bindings = [
            binding for binding in current_agent.channel_bindings
            if binding != endpoint_id
        ]
    if agent_id and agent_id in config.agents.instances:
        config.agents.instances[agent_id].channel_bindings = _normalize_string_list([
            *config.agents.instances[agent_id].channel_bindings,
            endpoint_id,
        ])


def _string_metadata_value(metadata: dict[str, Any], key: str) -> str:
    value = metadata.get(key)
    return value.strip() if isinstance(value, str) else ""


def _resolve_channel_inbound_target_agent_id(
    config: Config,
    endpoint,
    request: ChannelInboundBotRequest,
) -> str:
    if endpoint.agent_id:
        return endpoint.agent_id

    metadata = dict(request.metadata or {})
    requested_agent_id = (
        request.target_agent_id.strip()
        or request.agent_id.strip()
        or _string_metadata_value(metadata, "target_agent_id")
        or _string_metadata_value(metadata, "agent_id")
    )
    return requested_agent_id


def _channel_agents_payload(config: Config) -> list[dict[str, str]]:
    from horbot.agent.manager import get_agent_manager

    agent_manager = get_agent_manager()
    agent_manager.reload(config)
    payload: list[dict[str, str]] = []
    for agent in agent_manager.get_all_agents():
        payload.append({
            "id": agent.id,
            "name": agent.name,
            "model": agent.model,
            "provider": agent.provider,
        })
    return payload


def _channel_endpoints_payload(config: Config) -> dict[str, Any]:
    endpoints = [_serialize_channel_endpoint(endpoint) for endpoint in list_channel_endpoints(config)]
    return {
        "endpoints": endpoints,
        "catalog": get_channel_catalog(),
        "agents": _channel_agents_payload(config),
        "counts": {
            "total": len(endpoints),
            "enabled": sum(1 for endpoint in endpoints if endpoint["enabled"]),
            "ready": sum(1 for endpoint in endpoints if endpoint["status"] == "ready"),
            "incomplete": sum(1 for endpoint in endpoints if endpoint["status"] == "incomplete"),
        },
    }


def create_channel_router(
    *,
    get_config: Callable[[], Config],
    save_config_fn: Callable[[Config], Any],
    reset_agent_loop_fn: Callable[[], Awaitable[Any]],
    get_agent_loop_fn: Callable[[str], Awaitable[Any]],
    test_channel_connection_fn: Callable[[str, Any], Awaitable[dict[str, Any]]],
) -> APIRouter:
    router = APIRouter()

    @router.get("/channels")
    async def get_channels():
        """Get all channels status."""
        config = get_config()
        data = config.channels.model_dump(by_alias=True)
        data.pop("endpoints", None)
        return data

    @router.get("/channels/catalog")
    async def get_channels_catalog():
        """Return channel catalog metadata and agent choices for the channels UI."""
        config = get_config()
        return {
            "catalog": get_channel_catalog(),
            "agents": _channel_agents_payload(config),
        }

    @router.get("/channels/endpoints")
    async def get_channel_endpoints():
        """Return channel endpoints, including legacy global configs projected as endpoints."""
        config = get_config()
        return _channel_endpoints_payload(config)

    @router.post("/channels/inbound/{app_id}/messages")
    async def receive_channel_inbound_bot_message(
        app_id: str,
        request: ChannelInboundBotRequest,
        authorization: str = Header(default=""),
        x_horbot_bot_token: str = Header(default="", alias="X-Horbot-Bot-Token"),
    ):
        """Receive a message pushed through a Horbot-issued channel inbound bot."""
        config = get_config()
        endpoint = None
        for candidate in list_channel_endpoints(config):
            if candidate.type != "horbot-inbound-bot":
                continue
            if str((candidate.config or {}).get("bot_app_id") or "").strip() == app_id:
                endpoint = candidate
                break

        if endpoint is None:
            raise HTTPException(status_code=404, detail="Channel inbound bot app_id was not found")
        if not endpoint.enabled:
            raise HTTPException(status_code=403, detail="Channel inbound bot endpoint is disabled")

        expected_token = str((endpoint.config or {}).get("bot_token") or "")
        bearer_token = authorization.removeprefix("Bearer ").strip() if authorization.lower().startswith("bearer ") else ""
        provided_token = request.token.strip() or x_horbot_bot_token.strip() or bearer_token
        if not expected_token or not provided_token or not secrets.compare_digest(expected_token, provided_token):
            raise HTTPException(status_code=401, detail="Invalid channel inbound bot token")

        content = request.content.strip()
        if not content:
            raise HTTPException(status_code=400, detail="Content is required")

        sender_id = request.sender_id.strip() or "external-agent"
        if endpoint.allow_from and sender_id not in endpoint.allow_from:
            raise HTTPException(status_code=403, detail="Sender is not allowed for this channel endpoint")

        target_agent_id = _resolve_channel_inbound_target_agent_id(config, endpoint, request)
        if not target_agent_id or target_agent_id not in config.agents.instances:
            raise HTTPException(status_code=400, detail="Channel inbound bot endpoint is not bound to a valid agent")

        chat_id = request.chat_id.strip() or f"dm_{endpoint.id}"
        metadata = {
            "channel_instance_id": endpoint.id,
            "target_agent_id": target_agent_id,
            "channel_type": endpoint.type,
            "channel_endpoint_name": endpoint.name,
            "inbound_app_id": app_id,
            "inbound_sender_id": sender_id,
            "inbound_message_id": request.message_id.strip(),
            **dict(request.metadata or {}),
        }
        msg = InboundMessage(
            channel=endpoint.type,
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            channel_instance_id=endpoint.id,
            target_agent_id=target_agent_id,
            metadata=metadata,
        )

        record_channel_event(
            endpoint.id,
            channel_type=endpoint.type,
            event_type="inbound",
            status="ok",
            message=f"Received inbound bot message from {sender_id}",
            details={"chat_id": chat_id, "message_id": request.message_id.strip()},
        )

        agent_loop = await get_agent_loop_fn(target_agent_id)
        response = await agent_loop.process_message(msg)
        response_content = response.content if response else ""

        if response_content:
            record_channel_event(
                endpoint.id,
                channel_type=endpoint.type,
                event_type="outbound",
                status="ok",
                message=f"Generated response for {chat_id}",
                details={"chat_id": chat_id},
            )

        return {
            "ok": True,
            "endpoint_id": endpoint.id,
            "agent_id": target_agent_id,
            "session_key": msg.session_key,
            "content": response_content,
        }

    @router.get("/channels/endpoints/{endpoint_id}/events")
    async def get_channel_endpoint_events(endpoint_id: str, limit: int = 20):
        """Return recent runtime events for one channel endpoint."""
        config = get_config()
        endpoint = find_channel_endpoint(config, endpoint_id)
        if endpoint is None:
            raise HTTPException(status_code=404, detail=f"Endpoint not found: {endpoint_id}")
        return {
            "endpoint": _serialize_channel_endpoint(endpoint),
            "summary": get_channel_summary(endpoint_id),
            "events": get_channel_events(endpoint_id, limit=max(1, min(limit, 100))),
        }

    @router.post("/channels/endpoints/{endpoint_id}/test")
    async def test_channel_endpoint(endpoint_id: str):
        """Run a connection test for one channel endpoint."""
        config = get_config()
        endpoint = find_channel_endpoint(config, endpoint_id)
        if endpoint is None:
            raise HTTPException(status_code=404, detail=f"Endpoint not found: {endpoint_id}")

        runtime_config = build_runtime_channel_config(config.channels, endpoint)
        result = await test_channel_connection_fn(endpoint.type, runtime_config)
        tested_at = datetime.now().isoformat()

        record_channel_event(
            endpoint.id,
            channel_type=endpoint.type,
            event_type="healthcheck",
            status="ok" if result.get("status") == "ok" else "error",
            message="Connection test passed" if result.get("status") == "ok" else f"Connection test failed: {result.get('error') or 'Unknown error'}",
            details={"latency_ms": result.get("latency_ms", 0)},
        )

        return {
            "endpoint": _serialize_channel_endpoint(endpoint),
            "tested_at": tested_at,
            "result": result,
            "summary": get_channel_summary(endpoint_id),
            "events": get_channel_events(endpoint_id, limit=10),
        }

    @router.post("/channels/draft-test")
    async def test_draft_channel_endpoint(request: ChannelEndpointUpsertRequest):
        """Run a connection test for an unsaved channel endpoint draft."""
        config = get_config()
        request = _normalize_channel_endpoint_payload(request)

        if request.type not in CHANNEL_TYPE_MODELS:
            raise HTTPException(status_code=400, detail=f"Unsupported channel type: {request.type}")
        if request.agent_id and request.agent_id not in config.agents.instances:
            raise HTTPException(status_code=400, detail=f"Agent not found: {request.agent_id}")

        draft_endpoint = ChannelEndpointConfig(
            id=request.id or f"draft:{request.type}",
            type=request.type,
            name=request.name,
            agent_id=request.agent_id,
            enabled=request.enabled,
            allow_from=request.allow_from,
            config=_ensure_channel_inbound_bot_credentials(request.type, request.id or f"draft:{request.type}", request.config),
        )
        resolved = build_custom_endpoint(config, draft_endpoint)
        runtime_config = build_runtime_channel_config(config.channels, resolved)
        result = await test_channel_connection_fn(request.type, runtime_config)

        return {
            "endpoint": _serialize_channel_endpoint(resolved),
            "tested_at": datetime.now().isoformat(),
            "result": result,
        }

    @router.post("/channels/endpoints")
    async def create_channel_endpoint(request: ChannelEndpointUpsertRequest):
        """Create a custom channel endpoint bound to a specific agent."""
        config = get_config()
        request = _normalize_channel_endpoint_payload(request)

        if request.type not in CHANNEL_TYPE_MODELS:
            raise HTTPException(status_code=400, detail=f"Unsupported channel type: {request.type}")
        if request.agent_id and request.agent_id not in config.agents.instances:
            raise HTTPException(status_code=400, detail=f"Agent not found: {request.agent_id}")

        endpoint_id = request.id or f"{request.type}-{uuid.uuid4().hex[:8]}"
        if endpoint_id.startswith("legacy:"):
            raise HTTPException(status_code=400, detail="Custom endpoint ID cannot use the reserved legacy:* prefix")
        if find_channel_endpoint(config, endpoint_id) is not None:
            raise HTTPException(status_code=400, detail=f"Endpoint already exists: {endpoint_id}")

        request.config = _ensure_channel_inbound_bot_credentials(request.type, endpoint_id, request.config)

        endpoint = ChannelEndpointConfig(
            id=endpoint_id,
            type=request.type,
            name=request.name,
            agent_id=request.agent_id,
            enabled=request.enabled,
            allow_from=request.allow_from,
            config=request.config,
        )
        config.channels.endpoints.append(endpoint)
        _apply_endpoint_binding(config, endpoint_id, request.agent_id)

        try:
            save_config_fn(config)
            await reset_agent_loop_fn()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create channel endpoint: {str(e)}")

        saved = build_custom_endpoint(config, endpoint)
        return {
            "status": "created",
            "endpoint": _serialize_channel_endpoint(saved),
        }

    @router.put("/channels/endpoints/{endpoint_id}")
    async def update_channel_endpoint(endpoint_id: str, request: ChannelEndpointUpsertRequest):
        """Update a custom endpoint or a projected legacy channel endpoint."""
        config = get_config()
        request = _normalize_channel_endpoint_payload(request)

        if request.agent_id and request.agent_id not in config.agents.instances:
            raise HTTPException(status_code=400, detail=f"Agent not found: {request.agent_id}")

        if endpoint_id.startswith("legacy:"):
            channel_type = endpoint_id.split(":", 1)[1]
            if channel_type not in CHANNEL_TYPE_MODELS:
                raise HTTPException(status_code=404, detail=f"Legacy endpoint not found: {endpoint_id}")
            if request.type and request.type != channel_type:
                raise HTTPException(status_code=400, detail="Legacy endpoint type cannot be changed")

            legacy_config = getattr(config.channels, channel_type)
            payload = legacy_config.model_dump()
            payload.update(request.config or {})
            payload["enabled"] = request.enabled
            payload["allow_from"] = request.allow_from
            setattr(config.channels, channel_type, CHANNEL_TYPE_MODELS[channel_type].model_validate(payload))
            _apply_endpoint_binding(config, endpoint_id, request.agent_id)

            try:
                save_config_fn(config)
                await reset_agent_loop_fn()
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to update legacy channel endpoint: {str(e)}")

            resolved = build_legacy_endpoint(config, channel_type)
            return {
                "status": "updated",
                "endpoint": _serialize_channel_endpoint(resolved) if resolved else None,
            }

        target = next((item for item in config.channels.endpoints if item.id == endpoint_id), None)
        if target is None:
            raise HTTPException(status_code=404, detail=f"Endpoint not found: {endpoint_id}")
        if request.type and request.type != target.type:
            raise HTTPException(status_code=400, detail="Endpoint type cannot be changed")

        target.name = request.name
        target.agent_id = request.agent_id
        target.enabled = request.enabled
        target.allow_from = request.allow_from
        target.config = _ensure_channel_inbound_bot_credentials(target.type, endpoint_id, request.config)
        _apply_endpoint_binding(config, endpoint_id, request.agent_id)

        try:
            save_config_fn(config)
            await reset_agent_loop_fn()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update channel endpoint: {str(e)}")

        return {
            "status": "updated",
            "endpoint": _serialize_channel_endpoint(build_custom_endpoint(config, target)),
        }

    @router.delete("/channels/endpoints/{endpoint_id}")
    async def delete_channel_endpoint(endpoint_id: str):
        """Delete a custom channel endpoint."""
        if endpoint_id.startswith("legacy:"):
            raise HTTPException(
                status_code=400,
                detail="Legacy channel endpoint cannot be deleted. Disable it or clear its credentials instead.",
            )

        config = get_config()
        before_count = len(config.channels.endpoints)
        config.channels.endpoints = [
            endpoint for endpoint in config.channels.endpoints
            if endpoint.id != endpoint_id
        ]
        if len(config.channels.endpoints) == before_count:
            raise HTTPException(status_code=404, detail=f"Endpoint not found: {endpoint_id}")

        _apply_endpoint_binding(config, endpoint_id, "")

        try:
            save_config_fn(config)
            await reset_agent_loop_fn()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete channel endpoint: {str(e)}")

        return {"status": "deleted", "endpoint_id": endpoint_id}

    @router.patch("/channels/{channel_name}")
    async def update_channel(channel_name: str, channel_data: ChannelUpdateRequest):
        """Update a single channel's lightweight dashboard fields."""
        config = get_config()
        channels = config.channels

        if not hasattr(channels, channel_name):
            raise HTTPException(status_code=404, detail=f"Channel not found: {channel_name}")

        channel = getattr(channels, channel_name)
        if not hasattr(channel, "enabled"):
            raise HTTPException(status_code=400, detail=f"Channel does not support dashboard updates: {channel_name}")

        if channel_data.enabled is None:
            raise HTTPException(status_code=400, detail="No supported channel fields were provided")

        channel.enabled = channel_data.enabled

        try:
            save_config_fn(config)
            await reset_agent_loop_fn()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update channel: {str(e)}")

        return channel.model_dump(by_alias=True)

    return router
