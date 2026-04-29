"""External agent API routes."""

from __future__ import annotations

import re
import secrets
import uuid
from typing import Any, Callable
from urllib.parse import urlparse

from fastapi import APIRouter, Header, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from horbot.config.normalizer import remove_external_agent_references


class CreateExternalAgentRequest(BaseModel):
    id: str
    name: str
    description: str = ""
    avatar: str = ""
    adapter: str = "generic-agent-api"
    transport: str = "http_sse"
    endpoint: str = ""
    auth_type: str = "none"
    auth_secret: str = ""
    auth_header: str = "Authorization"
    capabilities: list[str] = Field(default_factory=list)
    dm_enabled: bool = True
    team_enabled: bool = False
    mention_required: bool = True
    timeout_s: int = 90
    max_turn_chars: int = 12000
    context_scope: str = "recent_turns"
    memory_access: str = "none"
    file_access: str = "none"
    adapter_config: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExternalAgentInboundRequest(BaseModel):
    content: str
    token: str = ""
    chat_id: str = ""
    session_key: str = ""
    sender_id: str = ""
    message_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


def _normalize_string_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _normalize_external_agent_id(value: str) -> str:
    return value.strip().lower()


def _validate_external_agent_transport(value: str) -> str:
    transport = value.strip().lower()
    allowed = {"http", "http_sse", "websocket"}
    if transport not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported external agent transport: {value}")
    return transport


def _validate_external_agent_adapter(value: str) -> str:
    adapter = (value or "generic-agent-api").strip().lower()
    aliases = {
        "generic": "generic-agent-api",
        "http": "generic-agent-api",
        "http_sse": "generic-agent-api",
        "sse-chat": "generic-agent-api",
        "websocket": "generic-agent-api",
        "websocket-chat": "generic-agent-api",
        "openai": "openai-compatible",
        "openai-chat-completions": "openai-compatible",
        "channel-backed-agent": "inbound-bot",
        "web-ui-bridge": "inbound-bot",
    }
    adapter = aliases.get(adapter, adapter)
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", adapter):
        raise HTTPException(status_code=400, detail=f"Invalid external agent adapter: {value}")
    return adapter


def _validate_external_agent_endpoint(value: str, transport: str, adapter: str) -> str:
    endpoint = value.strip()
    endpoint_required = adapter in {"generic-agent-api", "openai-compatible"}
    if not endpoint:
        if endpoint_required:
            raise HTTPException(status_code=400, detail="External agent endpoint is required")
        return ""

    parsed = urlparse(endpoint)
    if adapter == "openai-compatible" or transport in {"http", "http_sse"}:
        allowed_schemes = {"http", "https"}
    else:
        allowed_schemes = {"ws", "wss", "http", "https"}
    if parsed.scheme not in allowed_schemes or not parsed.netloc:
        raise HTTPException(status_code=400, detail="External agent endpoint must be a valid absolute URL")
    return endpoint


def _validate_external_agent_auth_type(value: str) -> str:
    auth_type = value.strip().lower()
    allowed = {"none", "bearer", "header"}
    if auth_type not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported external agent auth type: {value}")
    return auth_type


def _validate_external_agent_context_scope(value: str) -> str:
    scope = value.strip().lower()
    allowed = {"message_only", "recent_turns", "dm_summary"}
    if scope not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported external agent context scope: {value}")
    return scope


def _validate_external_agent_memory_access(value: str) -> str:
    access = value.strip().lower()
    allowed = {"none", "summary_only"}
    if access not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported external agent memory access: {value}")
    return access


def _validate_external_agent_file_access(value: str) -> str:
    access = value.strip().lower()
    allowed = {"none", "referenced_only"}
    if access not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported external agent file access: {value}")
    return access


def _normalize_external_agent_metadata(value: dict[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


def _normalize_external_agent_adapter_config(value: dict[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


def _is_inbound_external_agent_adapter(adapter: str) -> bool:
    return adapter in {"inbound-bot", "channel-backed-agent", "web-ui-bridge"}


def _ensure_external_agent_inbound_credentials(
    adapter: str,
    adapter_config: dict[str, Any],
    external_agent_id: str,
) -> dict[str, Any]:
    normalized_config = dict(adapter_config or {})
    if not _is_inbound_external_agent_adapter(adapter):
        return normalized_config

    safe_id = re.sub(r"[^a-z0-9_-]+", "-", external_agent_id.strip().lower()).strip("-") or "external"
    if not str(normalized_config.get("bot_app_id") or "").strip():
        normalized_config["bot_app_id"] = f"hbot_{safe_id}_{secrets.token_hex(4)}"
    if not str(normalized_config.get("bot_token") or "").strip():
        normalized_config["bot_token"] = secrets.token_urlsafe(32)
    return normalized_config


def _build_external_agent_config(
    request: CreateExternalAgentRequest,
    *,
    persisted_secret: str = "",
):
    from horbot.config.schema import ExternalAgentConfig

    request_name = request.name.strip()
    if not request_name:
        raise HTTPException(status_code=400, detail="External agent name is required")

    adapter = _validate_external_agent_adapter(request.adapter)
    transport = _validate_external_agent_transport(request.transport)
    auth_type = _validate_external_agent_auth_type(request.auth_type)
    endpoint = _validate_external_agent_endpoint(request.endpoint, transport, adapter)
    timeout_s = max(5, min(int(request.timeout_s or 90), 600))
    max_turn_chars = max(1000, min(int(request.max_turn_chars or 12000), 100000))
    auth_header = (request.auth_header or "Authorization").strip() or "Authorization"
    auth_secret = request.auth_secret.strip() or persisted_secret
    adapter_config = _ensure_external_agent_inbound_credentials(
        adapter,
        _normalize_external_agent_adapter_config(request.adapter_config),
        request.id.strip(),
    )

    return ExternalAgentConfig(
        id=request.id.strip(),
        name=request_name,
        description=request.description.strip(),
        avatar=request.avatar.strip(),
        adapter=adapter,
        transport=transport,
        endpoint=endpoint,
        auth_type=auth_type,
        auth_secret=auth_secret,
        auth_header=auth_header,
        capabilities=_normalize_string_list(request.capabilities),
        dm_enabled=bool(request.dm_enabled),
        team_enabled=bool(request.team_enabled),
        mention_required=bool(request.mention_required),
        timeout_s=timeout_s,
        max_turn_chars=max_turn_chars,
        context_scope=_validate_external_agent_context_scope(request.context_scope),
        memory_access=_validate_external_agent_memory_access(request.memory_access),
        file_access=_validate_external_agent_file_access(request.file_access),
        adapter_config=adapter_config,
        metadata=_normalize_external_agent_metadata(request.metadata),
    )


def create_external_agent_router(
    get_config: Callable[[], Any],
    get_session_manager_fn: Callable[[], Any],
    build_chat_stream_event_fn: Callable[..., dict[str, Any]],
) -> APIRouter:
    """Create external agent routes."""

    router = APIRouter()

    @router.get("/external-agents")
    async def list_external_agents():
        """List all configured external third-party agents."""
        from horbot.external_agents.manager import get_external_agent_manager

        manager = get_external_agent_manager()
        agents = manager.get_all_external_agents()
        return {
            "external_agents": [agent.to_dict() for agent in agents],
            "count": len(agents),
        }

    @router.post("/external-agents/inbound/{app_id}/messages")
    async def receive_external_agent_inbound_message(
        app_id: str,
        request: ExternalAgentInboundRequest,
        authorization: str = Header(default=""),
        x_horbot_bot_token: str = Header(default="", alias="X-Horbot-Bot-Token"),
    ):
        """Receive a message pushed by a vendor/local agent using Horbot-issued bot credentials."""
        config = get_config()
        matched_agent_id = ""
        matched_agent = None
        for external_agent_id, external_agent_config in config.external_agents.instances.items():
            adapter_config = dict(external_agent_config.adapter_config or {})
            if str(adapter_config.get("bot_app_id") or "").strip() == app_id:
                matched_agent_id = external_agent_id
                matched_agent = external_agent_config
                break

        if matched_agent is None:
            raise HTTPException(status_code=404, detail="External agent bot app_id was not found")

        adapter_config = dict(matched_agent.adapter_config or {})
        expected_token = str(adapter_config.get("bot_token") or "")
        bearer_token = authorization.removeprefix("Bearer ").strip() if authorization.lower().startswith("bearer ") else ""
        provided_token = request.token.strip() or x_horbot_bot_token.strip() or bearer_token
        if not expected_token or not provided_token or not secrets.compare_digest(expected_token, provided_token):
            raise HTTPException(status_code=401, detail="Invalid external agent bot token")

        content = request.content.strip()
        if not content:
            raise HTTPException(status_code=400, detail="Content is required")

        session_key = request.session_key.strip()
        if not session_key:
            chat_id = request.chat_id.strip() or f"dm_{matched_agent_id}"
            session_key = chat_id if chat_id.startswith("web:") else f"web:{chat_id}"
        elif not session_key.startswith("web:"):
            session_key = f"web:{session_key}"

        request_id = str(uuid.uuid4())
        session_manager = get_session_manager_fn()
        session = session_manager.get_or_create(session_key)
        message_id = session.add_message(
            "assistant",
            content,
            dedup=True,
            metadata={
                "request_id": request_id,
                "agent_id": matched_agent_id,
                "agent_name": matched_agent.name,
                "agent_type": "external",
                "source": "external_agent_inbound",
                "inbound_app_id": app_id,
                "inbound_sender_id": request.sender_id.strip(),
                "inbound_message_id": request.message_id.strip(),
                **dict(request.metadata or {}),
            },
        )
        session_manager.save(session)
        from horbot.web.websocket import broadcast_to_session

        await broadcast_to_session(
            session_key,
            build_chat_stream_event_fn(
                "agent_done",
                agent_id=matched_agent_id,
                agent_name=matched_agent.name,
                content=content,
                message_id=message_id,
                request_id=request_id,
                agent_type="external",
                source="external_agent_inbound",
                inbound_app_id=app_id,
                inbound_sender_id=request.sender_id.strip(),
                inbound_message_id=request.message_id.strip(),
            ),
        )

        return {
            "ok": True,
            "external_agent_id": matched_agent_id,
            "session_key": session_key,
            "message_id": message_id,
            "request_id": request_id,
        }

    @router.get("/external-agents/{external_agent_id}")
    async def get_external_agent(external_agent_id: str):
        """Get one external third-party agent."""
        from horbot.external_agents.manager import get_external_agent_manager

        manager = get_external_agent_manager()
        agent = manager.get_external_agent(external_agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"External agent '{external_agent_id}' not found")
        return agent.to_dict()

    @router.post("/external-agents")
    async def create_external_agent(request: CreateExternalAgentRequest):
        """Create a new external third-party agent."""
        from horbot.config.loader import load_config, save_config

        config = load_config()
        request_id = request.id.strip()
        normalized_request_id = _normalize_external_agent_id(request_id)
        if not request_id:
            raise HTTPException(status_code=400, detail="External agent ID is required")

        existing_agent_id = next(
            (
                existing_id
                for existing_id in config.external_agents.instances
                if _normalize_external_agent_id(existing_id) == normalized_request_id
            ),
            None,
        )
        if existing_agent_id is not None:
            raise HTTPException(status_code=400, detail=f"External agent ID '{request_id}' already exists")

        external_agent_config = _build_external_agent_config(request)
        config.external_agents.instances[request_id] = external_agent_config

        try:
            save_config(config)
            return {
                "status": "created",
                "external_agent_id": request_id,
                "message": f"External agent '{external_agent_config.name}' created successfully",
            }
        except Exception as exc:
            logger.error("Failed to create external agent: {}", exc)
            raise HTTPException(status_code=500, detail=f"Failed to create external agent: {str(exc)}")

    @router.put("/external-agents/{external_agent_id}")
    async def update_external_agent(external_agent_id: str, request: CreateExternalAgentRequest):
        """Update an external third-party agent."""
        from horbot.config.loader import load_config, save_config

        config = load_config()
        existing = config.external_agents.instances.get(external_agent_id)
        if existing is None:
            raise HTTPException(status_code=404, detail=f"External agent '{external_agent_id}' not found")

        external_agent_config = _build_external_agent_config(
            request,
            persisted_secret=str(existing.auth_secret or ""),
        )
        external_agent_config.id = external_agent_id
        config.external_agents.instances[external_agent_id] = external_agent_config
        if not external_agent_config.team_enabled:
            remove_external_agent_references(config, external_agent_id)

        try:
            save_config(config)
            return {
                "status": "updated",
                "external_agent_id": external_agent_id,
                "message": f"External agent '{external_agent_config.name}' updated successfully",
            }
        except Exception as exc:
            logger.error("Failed to update external agent: {}", exc)
            raise HTTPException(status_code=500, detail=f"Failed to update external agent: {str(exc)}")

    @router.delete("/external-agents/{external_agent_id}")
    async def delete_external_agent(external_agent_id: str):
        """Delete an external third-party agent."""
        from horbot.config.loader import load_config, save_config

        config = load_config()
        if external_agent_id not in config.external_agents.instances:
            raise HTTPException(status_code=404, detail=f"External agent '{external_agent_id}' not found")

        remove_external_agent_references(config, external_agent_id)
        del config.external_agents.instances[external_agent_id]
        try:
            save_config(config)
            return {
                "status": "deleted",
                "external_agent_id": external_agent_id,
                "message": f"External agent '{external_agent_id}' deleted successfully",
            }
        except Exception as exc:
            logger.error("Failed to delete external agent: {}", exc)
            raise HTTPException(status_code=500, detail=f"Failed to delete external agent: {str(exc)}")

    @router.post("/external-agents/{external_agent_id}/test")
    async def test_external_agent(external_agent_id: str):
        """Probe an external third-party agent endpoint."""
        from horbot.external_agents.manager import get_external_agent_manager
        from horbot.external_agents.runtime import get_external_agent_runtime

        manager = get_external_agent_manager()
        agent = manager.get_external_agent(external_agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"External agent '{external_agent_id}' not found")

        result = await get_external_agent_runtime().probe(agent)
        return {
            "external_agent_id": external_agent_id,
            **result,
        }

    return router
