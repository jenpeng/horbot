"""API routes."""

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, AsyncGenerator, Optional, Callable
from datetime import datetime
import asyncio
import html
import json
import uuid
import os
import re
import threading
import time
from loguru import logger

from horbot.config.loader import get_cached_config, save_config
from horbot.config.schema import Config
from horbot.config.validator import validate_config
from horbot.agent.loop import AgentLoop
from horbot.bus.queue import MessageBus
from horbot.bus.events import InboundMessage, OutboundMessage
from horbot.agent.tools.permission import PermissionManager, PermissionLevel, PROFILES, TOOL_GROUPS
from horbot.agent.tools.message import MessageTool
from horbot.providers.base import LLMProvider
from horbot.providers.registry import create_provider
from horbot.cron.service import CronService
from horbot.session.manager import SessionManager
from horbot.web.security import (
    redact_sensitive_data,
    sanitize_config_for_client,
    sanitize_execution_step_details,
    sanitize_execution_steps,
    sanitize_mcp_server_for_client,
)
from horbot.web.dashboard import (
    _build_dashboard_channel_summary,
)
from horbot.web.chat_history import (
    DEFAULT_CONVERSATION_AROUND_CONTEXT,
    DEFAULT_CONVERSATION_HISTORY_LIMIT,
    _find_session_message_index,
    _legacy_agent_session_managers,
    _load_merged_session_messages,
    _merge_history_messages,
    _prepare_conversation_history_messages,
    _slice_history_window,
    _unique_session_managers,
    ensure_history_message_id,
)
from horbot.web.agent_routes import create_agent_router
from horbot.web.chat_session_routes import (
    CreateSessionRequest,
    create_chat_session_router,
    create_new_session_payload,
    delete_session_payload,
    list_chat_sessions_payload,
    update_session_title_payload,
)
from horbot.web.chat_control_routes import create_chat_control_router
from horbot.web.config_routes import create_config_router
from horbot.web.conversation_routes import create_conversation_router, get_conversation_messages_payload
from horbot.web.cron_routes import create_cron_router
from horbot.web.external_agent_routes import create_external_agent_router
from horbot.web.message_content import clean_message_content
from horbot.web.memory_routes import _build_memory_store, router as memory_router
from horbot.web.mcp_routes import create_mcp_router
from horbot.web.dashboard_routes import create_dashboard_router
from horbot.web.plan_routes import create_plan_router
from horbot.web.planner_test_routes import create_planner_test_router
from horbot.web.provider_catalog_routes import router as provider_catalog_router
from horbot.web.provider_config_routes import create_provider_config_router
from horbot.web.soul_routes import create_soul_router
from horbot.web.system_routes import build_system_status_payload, create_system_router
from horbot.web.subagent_routes import create_subagent_router
from horbot.web.task_delegation_routes import router as task_delegation_router
from horbot.web.team_routes import create_team_router
from horbot.web.token_usage_routes import router as token_usage_router
from horbot.web import upload_preview as upload_preview_module
from horbot.web.upload_routes import router as upload_router
from horbot.web.upload_preview import (
    _cache_remote_image_file as _upload_cache_remote_image_file,
    _extract_document_content,
    _find_soffice_command,
    _get_upload_dir,
    _normalize_outbound_content_and_files,
    _pptx_visual_preview_plan,
    cleanup_upload_preview_cache,
)
from horbot.utils.error_messages import public_error_message
from horbot.web.channel_routes import create_channel_router
from horbot.web.gateway_diagnostics_routes import create_gateway_diagnostics_router
from horbot.web.skills_routes import create_skills_router
from horbot.channels.diagnostics import test_channel_connection
from horbot.utils.bootstrap import (
    bootstrap_file_needs_setup,
    bootstrap_content_needs_setup,
    build_bootstrap_summary,
    clean_summary_items,
    materialize_bootstrap_from_messages,
    parse_markdown_sections,
    normalize_markdown_items,
    truncate_summary_items,
)
from horbot.security.runtime_guard import inspect_user_input
from horbot.utils.helpers import ensure_dir, safe_filename
from pydantic import BaseModel
from pathlib import Path

_cron_service = None
_session_manager = None
_api_started_at = time.time()

router = APIRouter()
# Preserve legacy tests/extensions that patch horbot.web.api._get_upload_dir
# while upload routes now live in horbot.web.upload_routes.
upload_preview_module._get_upload_dir = lambda: _get_upload_dir()
router.include_router(upload_router)
router.include_router(memory_router)
router.include_router(provider_catalog_router)
router.include_router(token_usage_router)
router.include_router(task_delegation_router)
router.include_router(create_plan_router(lambda agent_id=None: get_agent_loop(agent_id)))
router.include_router(create_planner_test_router(lambda agent_id=None: get_agent_loop(agent_id)))
router.include_router(create_cron_router(lambda: get_cron_service()))
router.include_router(create_subagent_router(lambda agent_id=None: get_agent_loop(agent_id)))
router.include_router(create_config_router(
    get_config=lambda: get_cached_config(),
    save_config_fn=lambda config: save_config(config),
    reset_agent_loop_fn=lambda: reset_agent_loop(),
    sanitize_config_for_client_fn=lambda data: sanitize_config_for_client(data),
    redact_sensitive_data_fn=lambda data: redact_sensitive_data(data),
    validate_config_fn=lambda config: validate_config(config),
))
router.include_router(create_soul_router(
    resolve_agent_workspace_for_request=lambda agent_id=None: _resolve_agent_workspace_for_request(agent_id),
))
router.include_router(create_dashboard_router(
    get_config=lambda: get_cached_config(),
    build_system_status_payload=lambda config: _build_system_status_payload(config),
))
router.include_router(create_channel_router(
    get_config=lambda: get_cached_config(),
    save_config_fn=lambda config: save_config(config),
    reset_agent_loop_fn=lambda: reset_agent_loop(),
    get_agent_loop_fn=lambda agent_id: get_agent_loop(agent_id),
    test_channel_connection_fn=lambda channel_type, runtime_config: test_channel_connection(channel_type, runtime_config),
))
router.include_router(create_system_router(
    get_config=lambda: get_cached_config(),
    started_at=_api_started_at,
    cron_status_fn=lambda: get_cron_service().status(),
    agent_initialized_fn=lambda: len(get_agent_loop_pool()._pools) > 0,
))
router.include_router(create_provider_config_router(
    lambda: get_cached_config(),
    lambda config: save_config(config),
    lambda value: redact_sensitive_data(value),
))
router.include_router(create_gateway_diagnostics_router(
    get_config=lambda: get_cached_config(),
    test_channel_connection_fn=lambda channel_type, runtime_config: test_channel_connection(channel_type, runtime_config),
))
router.include_router(create_skills_router(
    resolve_skill_dir_for_request=lambda agent_id=None: _resolve_skill_dir_for_request(agent_id),
    describe_skill_source=lambda **kwargs: _describe_skill_source(**kwargs),
))
router.include_router(create_mcp_router(
    get_config=lambda: get_cached_config(),
    save_config_fn=lambda config: save_config(config),
    reset_agent_loop_fn=lambda: reset_agent_loop(),
    sanitize_mcp_server_fn=lambda name, cfg: sanitize_mcp_server_for_client(name, cfg),
))
router.include_router(create_team_router(
    reset_agent_loop_fn=lambda: reset_agent_loop(),
))
router.include_router(create_external_agent_router(
    get_config=lambda: get_cached_config(),
    get_session_manager_fn=lambda: get_session_manager(),
    build_chat_stream_event_fn=lambda *args, **kwargs: _build_chat_stream_event(*args, **kwargs),
))
router.include_router(create_agent_router(
    build_agent_runtime_capabilities=lambda agent: _build_agent_runtime_capabilities(agent),
    resolve_agent_workspace_for_request=lambda agent_id=None: _resolve_agent_workspace_for_request(agent_id),
    agent_bootstrap_file_path=lambda agent_id, file_kind: _agent_bootstrap_file_path(agent_id, file_kind),
    read_bootstrap_file=lambda path: _read_bootstrap_file(path),
    build_agent_bootstrap_payload=lambda agent: _build_agent_bootstrap_payload(agent),
    ensure_agent_bootstrap_files=lambda agent: _ensure_agent_bootstrap_files(agent),
    reset_agent_loop_fn=lambda: reset_agent_loop(),
))
router.include_router(create_conversation_router(
    resolve_conversation_for_history=lambda conv_id: _resolve_conversation_for_history(conv_id),
    load_conversation_raw_messages=lambda conv: _load_conversation_raw_messages(conv),
))
router.include_router(create_chat_session_router(
    get_session_manager_fn=lambda: get_session_manager(),
    resolve_chat_session_manager_fn=lambda session_key: _resolve_chat_session_manager(session_key),
))
router.include_router(create_chat_control_router(
    get_config=lambda: get_cached_config(),
    get_stream_manager_fn=lambda: get_stream_manager(),
    get_session_manager_fn=lambda: get_session_manager(),
    get_agent_loop_fn=lambda agent_id=None: get_agent_loop(agent_id),
    resolve_chat_session_manager_fn=lambda session_key: _resolve_chat_session_manager(session_key),
))


def _gateway_base_url(config: Config) -> str:
    host = (getattr(config.gateway, "host", "") or "127.0.0.1").strip()
    port = int(getattr(config.gateway, "port", 18790) or 18790)
    return f"http://{host}:{port}"


async def _dispatch_outbound_via_gateway(msg: OutboundMessage) -> None:
    import httpx

    config = get_cached_config()
    headers: dict[str, str] = {}
    admin_token = (getattr(config.gateway, "admin_token", "") or "").strip()
    if admin_token:
        headers["X-Horbot-Admin-Token"] = admin_token

    payload = {
        "channel": msg.channel,
        "chat_id": msg.chat_id,
        "content": msg.content,
        "channel_instance_id": msg.channel_instance_id,
        "target_agent_id": msg.target_agent_id,
        "reply_to": msg.reply_to,
        "media": list(msg.media or []),
        "metadata": dict(msg.metadata or {}),
    }
    url = f"{_gateway_base_url(config)}/api/gateway/outbound"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()


def _normalize_web_session_key(chat_id: str) -> str:
    return chat_id if chat_id.startswith("web:") else f"web:{chat_id}"


def _extract_team_id_from_chat_id(chat_id: str) -> str | None:
    normalized = chat_id[4:] if chat_id.startswith("web:") else chat_id
    return normalized[5:] if normalized.startswith("team_") else None


def _build_dispatched_message_metadata(
    source_loop: AgentLoop,
    msg: OutboundMessage,
    *,
    request_id: str,
    conversation_type: str,
    source_agent_id: str | None,
    source_agent_name: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = {
        "request_id": request_id,
        "agent_id": source_agent_id or "unknown",
        "agent_name": source_agent_name,
        "conversation_type": conversation_type,
        "dispatch_origin": "message_tool",
        "dispatch_source_channel": (msg.metadata or {}).get("_source_channel"),
        "dispatch_source_chat_id": (msg.metadata or {}).get("_source_chat_id"),
    }
    if extra:
        metadata.update(extra)
    return metadata


async def _get_team_session_manager(team_id: str) -> SessionManager:
    from horbot.workspace.manager import get_workspace_manager

    workspace_manager = get_workspace_manager()
    team_ws = workspace_manager.get_team_workspace(team_id)
    if not team_ws:
        raise HTTPException(status_code=404, detail=f"Team '{team_id}' not found")
    team_sessions_path = Path(team_ws.workspace_path) / "sessions"
    team_sessions_path.mkdir(parents=True, exist_ok=True)
    return SessionManager(workspace=team_sessions_path)


def _get_team_sessions_dir(team_id: str) -> Path:
    from horbot.workspace.manager import get_workspace_manager

    workspace_manager = get_workspace_manager()
    team_ws = workspace_manager.get_team_workspace(team_id)
    if not team_ws:
        raise HTTPException(status_code=404, detail=f"Team '{team_id}' not found")
    team_sessions_path = Path(team_ws.workspace_path) / "sessions"
    team_sessions_path.mkdir(parents=True, exist_ok=True)
    return team_sessions_path


async def _resolve_internal_web_session_manager(
    source_loop: AgentLoop,
    *,
    team_id: str | None,
    session_key: str,
) -> SessionManager:
    if team_id:
        expected_team_dir = _get_team_sessions_dir(team_id)
        current_sessions = getattr(source_loop, "sessions", None)
        current_sessions_dir = Path(getattr(current_sessions, "sessions_dir", "")) if current_sessions else None
        if current_sessions and current_sessions_dir == expected_team_dir:
            return current_sessions
        return await _get_team_session_manager(team_id)

    session_manager, _ = await _resolve_chat_session_manager(session_key)
    return session_manager


def _resolve_team_dispatch_targets(
    *,
    team_id: str,
    source_agent_id: str | None,
    content: str,
    explicit_mentions: list[str] | None = None,
    trigger_group_chat: bool = False,
) -> list[str]:
    from horbot.team.manager import get_team_manager

    team = get_team_manager().get_team(team_id)
    if not team:
        logger.info("[TeamDispatch] team={} not found while resolving targets", team_id)
        return []

    ordered_members = team.get_ordered_member_ids()
    explicit = [
        agent_id
        for agent_id in (explicit_mentions or [])
        if agent_id in ordered_members and agent_id != source_agent_id
    ]
    parsed = [
        agent_id
        for agent_id in parse_agent_mentions(content, ordered_members)
        if agent_id != source_agent_id
    ]

    targets: list[str] = []
    for agent_id in [*explicit, *parsed]:
        if agent_id not in targets:
            targets.append(agent_id)

    if targets:
        logger.info(
            "[TeamDispatch] resolved targets via mention: team={}, source={}, explicit={}, parsed={}, targets={}",
            team_id,
            source_agent_id,
            explicit,
            parsed,
            targets,
        )
        return targets

    if not trigger_group_chat:
        logger.info(
            "[TeamDispatch] no targets resolved and trigger_group_chat disabled: team={}, source={}, explicit={}, parsed={}",
            team_id,
            source_agent_id,
            explicit,
            parsed,
        )
        return []

    for agent_id in ordered_members:
        if agent_id != source_agent_id:
            logger.info(
                "[TeamDispatch] resolved fallback target: team={}, source={}, target={}",
                team_id,
                source_agent_id,
                agent_id,
            )
            return [agent_id]
    return []


async def _dispatch_team_group_followups(
    source_loop: AgentLoop,
    msg: OutboundMessage,
    *,
    team_id: str,
    session_key: str,
    session_manager: SessionManager,
    source_agent_id: str | None,
    source_agent_name: str,
) -> None:
    from horbot.agent.conversation import ConversationType, build_conversation_context
    from horbot.agent.manager import get_agent_manager
    from horbot.web.websocket import broadcast_to_session

    async def mirror_summary_to_source_chat(
        content: str,
        *,
        agent_id: str,
        agent_name: str,
    ) -> None:
        source_chat_id = str((msg.metadata or {}).get("_source_chat_id") or "").strip()
        source_channel = str((msg.metadata or {}).get("_source_channel") or "").strip()
        if source_channel != "web" or not source_chat_id:
            return

        source_session_key = _normalize_web_session_key(source_chat_id)
        if source_session_key == session_key:
            return

        source_session_manager, normalized_source_session_key = await _resolve_chat_session_manager(source_session_key)
        source_session = source_session_manager.get_or_create(normalized_source_session_key)
        assistant_message_id = str(uuid.uuid4())[:8]
        request_id = str(uuid.uuid4())
        source_session.add_message(
            "assistant",
            content,
            dedup=True,
            message_id=assistant_message_id,
            metadata={
                "agent_id": agent_id,
                "agent_name": agent_name,
                "conversation_type": "user_to_agent",
                "dispatch_origin": "message_tool_summary_mirror",
                "source_team_id": team_id,
                "source_session_key": session_key,
                "request_id": request_id,
            },
        )
        await source_session_manager.async_save(source_session)
        await broadcast_to_session(
            normalized_source_session_key,
            _build_chat_stream_event(
                "agent_done",
                agent_id=agent_id,
                agent_name=agent_name,
                content=content,
                message_id=assistant_message_id,
                request_id=request_id,
                dispatch_origin="message_tool_summary_mirror",
                source_team_id=team_id,
                source_session_key=session_key,
            ),
        )

    async def run_followup_turn(
        *,
        loop: AgentLoop,
        agent_id: str,
        agent_name: str,
        inbound_content: str,
        conversation_ctx,
        source_id: str,
        source_name_value: str,
    ) -> str:
        request_id = str(uuid.uuid4())
        turn_id = str(uuid.uuid4())[:8]
        assistant_message_id = str(uuid.uuid4())[:8]
        content_state = {"content": ""}
        last_persist_at = 0.0
        has_real_progress = False
        last_synthetic_progress = ""
        execution_steps: list[dict[str, Any]] = []
        session = session_manager.get_or_create(session_key)

        async def emit(event: str, **payload: Any) -> None:
            await broadcast_to_session(
                session_key,
                _build_chat_stream_event(
                    event,
                    agent_id=agent_id,
                    agent_name=agent_name,
                    turn_id=turn_id,
                    message_id=assistant_message_id,
                    request_id=request_id,
                    **payload,
                ),
            )

        async def persist_content(
            content: str | None,
            *,
            memory_sources: list[dict[str, Any]] | None = None,
            memory_recall: dict[str, Any] | None = None,
            execution_steps_to_save: list[dict[str, Any]] | None = None,
        ) -> None:
            cleaned = clean_message_content(content or "")
            if not cleaned:
                return

            message_metadata = {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "team_id": team_id,
                "source": source_id,
                "source_name": source_name_value,
                "target": agent_id,
                "target_name": agent_name,
                "conversation_type": conversation_ctx.conversation_type.value,
                "dispatch_origin": "message_tool_followup",
                "turn_id": turn_id,
                "request_id": request_id,
                **({"_memory_sources": memory_sources} if memory_sources else {}),
                **({"_memory_recall": memory_recall} if memory_recall else {}),
            }

            existing_idx = _find_session_message_index(
                session,
                message_id=assistant_message_id,
                turn_id=turn_id,
                role="assistant",
            )
            if existing_idx >= 0:
                session.messages[existing_idx]["content"] = cleaned
                if execution_steps_to_save:
                    session.messages[existing_idx]["execution_steps"] = execution_steps_to_save
                session.messages[existing_idx].setdefault("metadata", {}).update(message_metadata)
            else:
                session.add_message(
                    "assistant",
                    cleaned,
                    dedup=True,
                    message_id=assistant_message_id,
                    execution_steps=execution_steps_to_save,
                    metadata=message_metadata,
                )
            session.updated_at = datetime.now()
            await session_manager.async_save(session)

        async def on_progress(content: str, **kwargs: Any) -> None:
            nonlocal last_persist_at, has_real_progress, last_synthetic_progress
            tool_hint = bool(kwargs.get("tool_hint"))
            synthetic_progress = bool(kwargs.get("synthetic_progress"))
            if not tool_hint:
                if synthetic_progress:
                    if has_real_progress:
                        return
                    cleaned_synthetic = clean_message_content(content or "").strip()
                    if not cleaned_synthetic or cleaned_synthetic == last_synthetic_progress:
                        return
                    last_synthetic_progress = cleaned_synthetic
                else:
                    has_real_progress = True
                content_state["content"] = content
                now = time.monotonic()
                if now - last_persist_at >= 0.35:
                    last_persist_at = now
                    await persist_content(content)
            await emit(
                "progress",
                content=content,
                tool_hint=tool_hint,
                synthetic_progress=synthetic_progress,
            )

        async def emit_synthetic_progress(message: str) -> None:
            await on_progress(message, synthetic_progress=True)

        async def on_status(message: str) -> None:
            await emit("status", message=message)

        async def on_thinking(content: str) -> None:
            await emit("thinking")

        async def on_step_start(step_id: str, step_type: str, title: str) -> None:
            execution_steps.append({
                "id": step_id,
                "type": step_type,
                "title": title,
                "status": "running",
                "timestamp": datetime.now().isoformat(),
            })
            if step_type == "thinking":
                await emit_synthetic_progress(f"{agent_name} 正在分析任务与约束...")
            elif step_type == "response":
                await emit_synthetic_progress(f"{agent_name} 正在整理回复...")
            await emit("step_start", step_id=step_id, step_type=step_type, title=title)

        async def on_step_complete(step_id: str, status: str, details: dict) -> None:
            safe_details = sanitize_execution_step_details(
                next((step.get("type") for step in execution_steps if step.get("id") == step_id), ""),
                details,
            )
            step_type = next((step.get("type") for step in execution_steps if step.get("id") == step_id), "")
            for step in execution_steps:
                if step.get("id") == step_id:
                    step["status"] = status
                    step["details"] = safe_details
                    break
            if step_type == "thinking" and status not in {"error", "failed"}:
                await emit_synthetic_progress(f"{agent_name} 正在收束思路，准备给出结论...")
            await emit("step_complete", step_id=step_id, status=status, details=safe_details)

        async def on_tool_start(tool_name: str, arguments: dict) -> None:
            label = str(tool_name or "").strip()
            if label:
                await emit_synthetic_progress(f"{agent_name} 正在调用 {label}...")
            await emit("tool_start", tool_name=tool_name, arguments=arguments)

        async def on_tool_result(tool_name: str, result: str, execution_time: float) -> None:
            label = str(tool_name or "").strip()
            if label:
                await emit_synthetic_progress(f"{agent_name} 已拿到 {label} 结果，继续整理中...")
            await emit("tool_result", tool_name=tool_name, result=result, execution_time=execution_time)

        await emit("agent_start")
        response = await loop.process_message(
            InboundMessage(
                channel="web",
                sender_id="web_user",
                chat_id=session_key[4:] if session_key.startswith("web:") else session_key,
                content=inbound_content,
                metadata={
                    "group_chat": True,
                    "team_id": team_id,
                    "conversation_context": conversation_ctx.to_dict(),
                    "mentioned_agents": target_agent_ids,
                    "turn_id": turn_id,
                    "assistant_message_id": assistant_message_id,
                    "request_id": request_id,
                    "triggered_via": "message_tool_dispatch",
                },
            ),
            session_key=session_key,
            on_progress=on_progress,
            on_status=on_status,
            on_thinking=on_thinking,
            on_step_start=on_step_start,
            on_step_complete=on_step_complete,
            on_tool_start=on_tool_start,
            on_tool_result=on_tool_result,
            speaking_to=conversation_ctx.get_speaking_to(),
            conversation_type=conversation_ctx.conversation_type.value,
        )
        final_content = _resolve_final_agent_display_content(
            response.content if response else "",
            content_state["content"],
        )
        if not final_content:
            logger.info(
                "[TeamDispatch] followup produced no direct assistant content: team={}, source={}, target={}",
                team_id,
                source_agent_id,
                agent_id,
            )
            return ""

        memory_sources = list((response.metadata or {}).get("_memory_sources") or []) if response else []
        memory_recall = dict((response.metadata or {}).get("_memory_recall") or {}) if response else {}
        await persist_content(
            final_content,
            memory_sources=memory_sources,
            memory_recall=memory_recall,
            execution_steps_to_save=sanitize_execution_steps(execution_steps),
        )
        await emit(
            "agent_done",
            content=final_content,
            execution_steps=sanitize_execution_steps(execution_steps),
            memory_sources=memory_sources,
            memory_recall=memory_recall,
        )
        return final_content

    explicit_mentions = list((msg.metadata or {}).get("mentioned_agents") or [])
    trigger_group_chat = bool((msg.metadata or {}).get("trigger_group_chat"))
    target_agent_ids = _resolve_team_dispatch_targets(
        team_id=team_id,
        source_agent_id=source_agent_id,
        content=msg.content,
        explicit_mentions=explicit_mentions,
        trigger_group_chat=trigger_group_chat,
    )
    logger.info(
        "[TeamDispatch] followup dispatch: team={}, source={}, content={!r}, explicit_mentions={}, trigger_group_chat={}, targets={}",
        team_id,
        source_agent_id,
        msg.content,
        explicit_mentions,
        trigger_group_chat,
        target_agent_ids,
    )
    if not target_agent_ids:
        return

    agent_manager = get_agent_manager()
    source_name = source_agent_name or source_agent_id or "Agent"
    produced_followup_content = False

    for target_agent_id in target_agent_ids:
        target_agent = agent_manager.get_agent(target_agent_id)
        if not target_agent:
            continue

        trigger_message = (
            extract_agent_mention_payload(
                msg.content,
                target_agent_id=target_agent_id,
                target_agent_name=target_agent.name,
            )
            or clean_message_content(msg.content)
        )
        relay_trigger_message = _build_team_baton_trigger_message(
            trigger_message,
            mode="relay",
            source_name=source_name,
            target_name=target_agent.name,
        )
        conversation_ctx = build_conversation_context(
            conversation_type=ConversationType.AGENT_TO_AGENT,
            source_id=source_agent_id or "agent_dispatch",
            source_name=source_name,
            target_id=target_agent_id,
            target_name=target_agent.name,
            trigger_message=relay_trigger_message,
        )
        target_loop = await get_agent_loop_with_session_manager(target_agent_id, session_manager)
        final_content = await run_followup_turn(
            loop=target_loop,
            agent_id=target_agent_id,
            agent_name=target_agent.name,
            inbound_content=relay_trigger_message,
            conversation_ctx=conversation_ctx,
            source_id=source_agent_id or "agent_dispatch",
            source_name_value=source_name,
        )
        if final_content:
            produced_followup_content = True

    if source_agent_id and produced_followup_content:
        source_agent = agent_manager.get_agent(source_agent_id)
        if source_agent:
            source_summary_ctx = build_conversation_context(
                conversation_type=ConversationType.USER_TO_AGENT,
                source_id="user",
                source_name="用户",
                target_id=source_agent_id,
                target_name=source_agent.name,
                trigger_message=_build_user_summary_trigger_message(msg.content),
            )
            source_summary_loop = await get_agent_loop_with_session_manager(source_agent_id, session_manager)
            source_summary_content = await run_followup_turn(
                loop=source_summary_loop,
                agent_id=source_agent_id,
                agent_name=source_agent.name,
                inbound_content=source_summary_ctx.trigger_message or _build_user_summary_trigger_message(msg.content),
                conversation_ctx=source_summary_ctx,
                source_id="user",
                source_name_value="用户",
            )
            if source_summary_content:
                await mirror_summary_to_source_chat(
                    source_summary_content,
                    agent_id=source_agent_id,
                    agent_name=source_agent.name,
                )


async def _dispatch_internal_web_outbound(source_loop: AgentLoop, msg: OutboundMessage) -> None:
    from horbot.web.websocket import broadcast_to_session

    session_key = _normalize_web_session_key(msg.chat_id)
    team_id = (
        str((msg.metadata or {}).get("team_id") or "").strip()
        or _extract_team_id_from_chat_id(session_key)
    )
    request_id = str(uuid.uuid4())
    source_agent_id = getattr(source_loop, "_agent_id", None)
    source_agent_name = getattr(source_loop, "_agent_name", None) or source_agent_id or "Agent"

    session_manager = await _resolve_internal_web_session_manager(
        source_loop,
        team_id=team_id or None,
        session_key=session_key,
    )
    logger.info(
        "[InternalWebDispatch] source={}, team={}, session_key={}, sessions_dir={}",
        source_agent_id,
        team_id,
        session_key,
        getattr(session_manager, "sessions_dir", None),
    )

    session = session_manager.get_or_create(session_key)
    normalized_content, outbound_files = _normalize_outbound_content_and_files(msg.content, msg.media)
    message_id = session.add_message(
        "assistant",
        normalized_content,
        dedup=True,
        message_id=str(uuid.uuid4())[:8],
        files=outbound_files or None,
        metadata=_build_dispatched_message_metadata(
            source_loop,
            msg,
            request_id=request_id,
            conversation_type="agent_to_team" if team_id else "agent_dispatch",
            source_agent_id=source_agent_id,
            source_agent_name=source_agent_name,
            extra={
                **({"team_id": team_id} if team_id else {}),
                **({"mentioned_agents": list((msg.metadata or {}).get("mentioned_agents") or [])} if (msg.metadata or {}).get("mentioned_agents") else {}),
            },
        ),
    )
    await session_manager.async_save(session)
    await broadcast_to_session(
        session_key,
        _build_chat_stream_event(
            "agent_done",
            agent_id=source_agent_id,
            agent_name=source_agent_name,
            content=normalized_content,
            message_id=message_id,
            files=outbound_files or None,
        ),
    )

    if team_id:
        await _dispatch_team_group_followups(
            source_loop,
            msg,
            team_id=team_id,
            session_key=session_key,
            session_manager=session_manager,
            source_agent_id=source_agent_id,
            source_agent_name=source_agent_name,
        )


def _build_subagent_chat_content(event: dict[str, Any]) -> str:
    task_id = str(event.get("task_id") or "")
    label = str(event.get("label") or event.get("task") or "后台任务").strip()
    task = str(event.get("task") or "").strip()
    status = str(event.get("status") or "").strip()
    result = clean_message_content(str(event.get("result") or "").strip())
    error = clean_message_content(str(event.get("error") or "").strip())

    if status == "running":
        return f"后台任务 `{task_id}` 已启动，正在执行：{label}"
    if status == "completed":
        return f"后台任务 `{task_id}` 已完成。\n\n{result or '任务已完成，但没有返回额外结果。'}"
    if status == "cancelled":
        return f"后台任务 `{task_id}` 已取消。\n\n任务：{task or label}"
    if status in {"error", "failed"}:
        return f"后台任务 `{task_id}` 执行失败。\n\n{error or '未返回具体错误。'}"
    return f"后台任务 `{task_id}` 状态更新：{status or 'unknown'}"


def _build_subagent_execution_step(event: dict[str, Any]) -> dict[str, Any]:
    task_id = str(event.get("task_id") or "")
    label = str(event.get("label") or event.get("task") or "后台任务").strip()
    status = str(event.get("status") or "").strip()
    step_status = {
        "running": "running",
        "completed": "completed",
        "cancelled": "stopped",
        "error": "error",
        "failed": "failed",
    }.get(status, "running")
    details = {
        "task_id": task_id,
        "label": label,
        "task": event.get("task"),
        "running_seconds": event.get("running_seconds"),
        "result": event.get("result"),
        "error": event.get("error"),
    }
    return {
        "id": f"subagent-{task_id}",
        "type": "background_task",
        "title": f"后台任务：{label}",
        "status": step_status,
        "timestamp": datetime.now().isoformat(),
        "details": {key: value for key, value in details.items() if value not in (None, "")},
    }


async def _persist_and_broadcast_subagent_event(agent_loop: AgentLoop, event: dict[str, Any]) -> None:
    """Persist subagent lifecycle events as visible chat execution bubbles."""
    from horbot.web.websocket import broadcast_to_session

    origin = event.get("origin") if isinstance(event.get("origin"), dict) else {}
    origin_channel = str(origin.get("channel") or "").strip()
    origin_chat_id = str(origin.get("chat_id") or "").strip()
    raw_session_key = str(event.get("session_key") or "").strip()
    if origin_channel != "web" and not raw_session_key.startswith("web:"):
        return

    session_key = raw_session_key or _normalize_web_session_key(origin_chat_id)
    if not session_key:
        return
    normalized_session_key = _normalize_web_session_key(session_key)
    metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
    agent_id = str(metadata.get("agent_id") or getattr(agent_loop, "_agent_id", "") or "").strip() or None
    agent_name = str(metadata.get("agent_name") or getattr(agent_loop, "_agent_name", "") or agent_id or "Agent")
    task_id = str(event.get("task_id") or "").strip()
    if not task_id:
        return

    session_manager, resolved_session_key = await _resolve_chat_session_manager(normalized_session_key)
    session = session_manager.get_or_create(resolved_session_key)
    message_id = str(metadata.get("subagent_message_id") or f"subagent-{task_id}")
    content = _build_subagent_chat_content(event)
    execution_steps = sanitize_execution_steps([_build_subagent_execution_step(event)])
    message_metadata = {
        "agent_id": agent_id,
        "agent_name": agent_name,
        "conversation_type": "user_to_agent",
        "dispatch_origin": "subagent_lifecycle",
        "subagent_task_id": task_id,
        "subagent_status": event.get("status"),
        "subagent_label": event.get("label"),
        "subagent_task": event.get("task"),
        **({"request_id": metadata.get("request_id")} if metadata.get("request_id") else {}),
        **({"turn_id": metadata.get("turn_id")} if metadata.get("turn_id") else {}),
        **({"parent_assistant_message_id": metadata.get("assistant_message_id") or metadata.get("message_id")} if (metadata.get("assistant_message_id") or metadata.get("message_id")) else {}),
    }

    existing_idx = _find_session_message_index(
        session,
        message_id=message_id,
        role="assistant",
    )
    if existing_idx >= 0:
        session.messages[existing_idx]["content"] = content
        session.messages[existing_idx]["execution_steps"] = execution_steps
        session.messages[existing_idx].setdefault("metadata", {}).update(message_metadata)
    else:
        session.add_message(
            "assistant",
            content,
            dedup=True,
            message_id=message_id,
            execution_steps=execution_steps,
            metadata=message_metadata,
        )
    session.updated_at = datetime.now()
    await session_manager.async_save(session)

    await broadcast_to_session(
        resolved_session_key,
        _build_chat_stream_event(
            "subagent_update",
            agent_id=agent_id,
            agent_name=agent_name,
            message_id=message_id,
            content=content,
            execution_steps=execution_steps,
            session_key=resolved_session_key,
            dispatch_origin="subagent_lifecycle",
            subagent_task_id=task_id,
            subagent_status=event.get("status"),
            subagent_label=event.get("label"),
            subagent_task=event.get("task"),
        ),
    )


def _configure_web_subagent_observability(agent_loop: AgentLoop) -> None:
    if not hasattr(agent_loop, "subagents"):
        return

    async def on_subagent_event(event: dict[str, Any]) -> None:
        await _persist_and_broadcast_subagent_event(agent_loop, event)

    agent_loop.subagents.set_event_callback(on_subagent_event)


def _configure_web_agent_loop_message_routing(agent_loop: AgentLoop, bus: MessageBus) -> None:
    message_tool = agent_loop.tools.get("message")
    if not isinstance(message_tool, MessageTool):
        return

    async def _send_outbound(msg: OutboundMessage) -> None:
        msg.metadata = dict(msg.metadata or {})
        msg.metadata.setdefault("outbound_channel_type", msg.channel)
        msg.metadata.setdefault("outbound_chat_id", msg.chat_id)
        if msg.channel_instance_id:
            msg.metadata.setdefault("outbound_channel_instance_id", msg.channel_instance_id)
        if msg.target_agent_id:
            msg.metadata.setdefault("outbound_target_agent_id", msg.target_agent_id)
        if msg.channel == "web":
            target_session_key = _normalize_web_session_key(msg.chat_id)
            target_team_id = (
                str((msg.metadata or {}).get("team_id") or "").strip()
                or _extract_team_id_from_chat_id(target_session_key)
            )
            current_session_key = _normalize_web_session_key(
                str((msg.metadata or {}).get("_source_chat_id") or msg.chat_id)
            )
            if target_session_key == current_session_key:
                msg.metadata.setdefault("outbound_via", "same_session_inline")
                return
            if target_team_id or target_session_key != current_session_key:
                msg.metadata.setdefault("outbound_via", "internal_web_dispatch")
                # Keep cross-session web dispatch alive even if the originating
                # SSE request is cancelled by a page refresh or conversation switch.
                await asyncio.shield(_dispatch_internal_web_outbound(agent_loop, msg))
                return
        route_externally = bool(msg.channel_instance_id) or msg.channel not in {"web", "cli", "system"}
        if route_externally:
            msg.metadata.setdefault("outbound_via", "gateway_http")
            await _dispatch_outbound_via_gateway(msg)
            return
        msg.metadata.setdefault("outbound_via", "bus")
        await bus.publish_outbound(msg)

    message_tool.set_send_callback(_send_outbound)

AGENT_PROFILE_BOOTSTRAP_PRESETS: dict[str, dict[str, Any]] = {
    "generalist": {
        "label": "通用执行者",
        "summary": "适合日常问答、配置确认与稳定执行",
        "checklist": ["核心职责", "默认输出结构", "不确定时如何处理", "需要用户确认的边界"],
        "starter_prompts": [
            "请先介绍你的核心职责、默认输出风格，以及哪些事情需要我先确认。",
            "先和我约定：你收到任务后会如何确认目标、如何组织回答、如何暴露不确定性。",
        ],
    },
    "builder": {
        "label": "工程实现者",
        "summary": "偏开发与落地，适合改代码、修问题、跑验证",
        "checklist": ["如何拆解实现", "默认验证方式", "高风险改动边界", "提交结果格式"],
        "starter_prompts": [
            "请先说明你的工程协作方式：如何拆解、实现、验证，并在什么情况下停下来确认。",
            "以后我让你改代码时，请默认给出思路、风险和验证结果；先把规则讲清楚。",
        ],
    },
    "researcher": {
        "label": "研究分析者",
        "summary": "偏检索、分析、梳理与总结",
        "checklist": ["研究输出结构", "证据与结论如何区分", "对比维度", "何时先补背景"],
        "starter_prompts": [
            "请先定义你的研究输出结构，尤其是结论、证据、假设和待验证项如何区分。",
            "以后我让你做方案对比时，请默认按维度比较并标注不确定性；先把规则说明白。",
        ],
    },
    "coordinator": {
        "label": "协作协调者",
        "summary": "偏任务拆解、团队协同与多 Agent 接力",
        "checklist": ["如何拆解任务", "如何选择下一棒", "何时停止接力", "如何同步状态"],
        "starter_prompts": [
            "请先定义你的协调规则：如何拆解任务、分配下一棒、同步状态，并在什么时候回到我这里确认。",
            "以后你作为协调型 Agent 时，请默认告诉我当前阶段、下一棒和剩余风险。",
        ],
    },
    "companion": {
        "label": "陪伴助理",
        "summary": "偏温和沟通、细致引导与长期陪伴",
        "checklist": ["默认语气", "解释深度", "温和引导方式", "何时主动追问"],
        "starter_prompts": [
            "请先和我约定你的沟通风格：语气、解释深度、引导方式，以及什么时候该更主动地追问。",
            "以后请默认更耐心地解释关键判断，同时避免过度打扰。",
        ],
    },
}

PERMISSION_PROFILE_PRESETS: dict[str, dict[str, str]] = {
    "minimal": {
        "label": "最小权限",
        "summary": "尽量少开权限，适合保守问答场景",
    },
    "balanced": {
        "label": "平衡模式",
        "summary": "文件和网页默认可用，终端需要更谨慎",
    },
    "coding": {
        "label": "工程模式",
        "summary": "适合编码、调试与本地验证",
    },
    "readonly": {
        "label": "只读模式",
        "summary": "允许读取和检索，不允许写入和执行",
    },
    "full": {
        "label": "完全模式",
        "summary": "全部工具可直接使用，适合高自治 Agent",
    },
}


def _tool_allowed(pm: PermissionManager, tool_name: str) -> bool:
    return pm.check_permission(tool_name) != PermissionLevel.DENY


def _resolve_agent_permission_config(agent, config: Config | None = None) -> tuple[Any, str]:
    config = config or get_cached_config()
    base_permission = getattr(getattr(config, "tools", None), "permission", None)
    configured_profile = str(getattr(getattr(agent, "config", None), "permission_profile", "") or "").strip()
    if configured_profile and base_permission is not None:
        permission_type = type(base_permission)
        return permission_type(profile=configured_profile, allow=[], deny=[], confirm=[]), configured_profile
    if base_permission is None:
        class _FallbackPermission:
            profile = configured_profile or "balanced"
            allow: list[str] = []
            deny: list[str] = []
            confirm: list[str] = []
        return _FallbackPermission(), _FallbackPermission.profile
    return base_permission, getattr(base_permission, "profile", "balanced")


def _build_agent_permission_manager(agent, config: Config | None = None) -> tuple[PermissionManager, str]:
    config = config or get_cached_config()
    permission, effective_profile = _resolve_agent_permission_config(agent, config)
    autonomous = getattr(config, "autonomous", None)
    confirm_sensitive = getattr(autonomous, "confirm_sensitive", True)
    pm = PermissionManager(
        profile=getattr(permission, "profile", effective_profile),
        allow=list(getattr(permission, "allow", []) or []),
        deny=list(getattr(permission, "deny", []) or []),
        confirm=list(getattr(permission, "confirm", []) or []),
        confirm_sensitive=confirm_sensitive,
    )
    return pm, effective_profile


def _describe_permission_items(items: list[str]) -> str:
    labels: list[str] = []
    for item in items:
        if item.startswith("group:"):
            group = TOOL_GROUPS.get(item[6:])
            labels.append(group.description if group else item)
        else:
            labels.append(item)
    return "、".join(labels) if labels else "无"


def _bootstrap_file_needs_refresh(path: Path, file_kind: str) -> bool:
    if not path.exists():
        return True

    content = path.read_text(encoding="utf-8")
    if not content.strip():
        return True
    return bootstrap_file_needs_setup(content, file_kind)


def _agent_bootstrap_setup_pending(agent) -> bool:
    if agent is None:
        return False

    from horbot.agent.context import ContextBuilder

    soul_path, _ = _agent_bootstrap_file_path(agent.id, "soul")
    user_path, _ = _agent_bootstrap_file_path(agent.id, "user")
    if not soul_path.exists() or not user_path.exists():
        return True
    soul_content = soul_path.read_text(encoding="utf-8")
    user_content = user_path.read_text(encoding="utf-8")
    return bootstrap_content_needs_setup(soul_content, user_content)


def _build_personalized_bootstrap_content(agent) -> dict[str, str]:
    _, effective_permission_profile = _build_agent_permission_manager(agent)
    profile_id = str(getattr(getattr(agent, "config", None), "profile", "") or "").strip()
    profile_meta = AGENT_PROFILE_BOOTSTRAP_PRESETS.get(profile_id, {})
    permission_meta = PERMISSION_PROFILE_PRESETS.get(effective_permission_profile, {})
    permission_rules = PROFILES.get(effective_permission_profile, {})

    profile_label = profile_meta.get("label", "未设置画像")
    profile_summary = profile_meta.get("summary", "首次私聊时再继续补全职责、语气和协作边界。")
    checklist = profile_meta.get("checklist", ["主要职责", "输出风格", "风险边界", "协作方式"])
    starter_prompts = profile_meta.get(
        "starter_prompts",
        ["请先介绍你的职责、工作边界，以及你收到任务后会如何组织回答。"],
    )
    permission_label = permission_meta.get("label", effective_permission_profile)
    permission_summary = permission_meta.get("summary", "按当前权限档位运行。")

    soul_content = "\n".join([
        "# 灵魂",
        "<!-- HORBOT_SETUP_PENDING -->",
        "",
        f"我是 {agent.name}，运行在 horbot 中的独立 Agent。",
        "",
        "## 当前默认画像",
        f"- **协作画像**：{profile_label}",
        f"- **画像摘要**：{profile_summary}",
        "",
        "## 当前权限边界",
        f"- **权限档位**：{permission_label}",
        f"- **档位说明**：{permission_summary}",
        f"- **默认允许**：{_describe_permission_items(permission_rules.get('allow', []))}",
        f"- **需要确认**：{_describe_permission_items(permission_rules.get('confirm', []))}",
        f"- **默认禁止**：{_describe_permission_items(permission_rules.get('deny', []))}",
        "",
        "## 首次私聊优先确认",
        *(f"- {item}" for item in checklist),
        "",
        "## 工作约束",
        "- 首轮对话时，优先帮助用户明确职责、输出风格、边界和协作方式。",
        "- 完成首次引导后，请主动重写本文件，并移除 `HORBOT_SETUP_PENDING` 标记。",
        "",
        "---",
        "",
        "*这是系统根据当前画像与权限档位生成的初始化版本，可在首次私聊后继续细化。*",
        "",
    ])

    user_content = "\n".join([
        "# 用户档案",
        "<!-- HORBOT_SETUP_PENDING -->",
        "",
        f"这份 USER.md 用于记录用户与 {agent.name} 的专属协作约定。",
        "",
        "## 当前默认协作基线",
        f"- **协作画像**：{profile_label}",
        f"- **权限档位**：{permission_label}",
        "",
        "## 首次私聊待确认",
        "- 用户希望被如何称呼、使用什么语言、处于什么时区",
        "- 用户偏好的回复长度、解释深度、沟通节奏",
        "- 用户希望该 Agent 优先承担什么任务，哪些事情不要擅自做",
        "- 用户是否希望该 Agent 主动发起接力、搜索、终端执行或文件改写",
        "",
        "## 推荐开场",
        *(f"- {prompt}" for prompt in starter_prompts),
        "",
        "## 备注",
        "- 完成首次引导后，请把真实偏好写入本文件，并移除 `HORBOT_SETUP_PENDING` 标记。",
        "",
    ])
    return {"soul": soul_content, "user": user_content}


def _ensure_agent_bootstrap_files(agent) -> None:
    if agent is None:
        return

    content_map = _build_personalized_bootstrap_content(agent)
    for file_kind in ("soul", "user"):
        file_path, _ = _agent_bootstrap_file_path(agent.id, file_kind)
        if not _bootstrap_file_needs_refresh(file_path, file_kind):
            continue
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content_map[file_kind], encoding="utf-8")


def _build_agent_runtime_capabilities(agent) -> dict[str, Any]:
    """Build a user-facing runtime capability summary for one agent."""
    config = get_cached_config()
    pm, effective_profile = _build_agent_permission_manager(agent, config)
    mcp_servers = getattr(getattr(config, "tools", None), "mcp_servers", {}) or {}
    mcp_server_names = sorted(name for name, cfg in mcp_servers.items() if cfg)

    capability_specs = [
        {
            "id": "files",
            "label": "文件",
            "description": "读写与编辑工作区文件",
            "tools": ["read_file", "write_file", "edit_file", "list_dir"],
            "source": "builtin",
        },
        {
            "id": "terminal",
            "label": "终端",
            "description": "执行命令与脚本",
            "tools": ["exec"],
            "source": "builtin",
        },
        {
            "id": "web",
            "label": "网页检索",
            "description": "网页抓取与搜索",
            "tools": ["web_search", "web_fetch"],
            "source": "builtin",
        },
        {
            "id": "browser",
            "label": "浏览器",
            "description": "打开网页、点击、读取页面内容",
            "tools": ["browser"],
            "source": "mcp" if "browser" in mcp_server_names else "builtin",
        },
        {
            "id": "tasks",
            "label": "任务提醒",
            "description": "创建提醒与定时任务",
            "tools": ["task", "cron"],
            "source": "builtin",
        },
        {
            "id": "relay",
            "label": "消息接力",
            "description": "发送消息与触发协作",
            "tools": ["message", "spawn"],
            "source": "builtin",
        },
    ]

    runtime_capabilities = []
    enabled_labels: list[str] = []
    for spec in capability_specs:
        enabled_tools = [tool for tool in spec["tools"] if _tool_allowed(pm, tool)]
        enabled = bool(enabled_tools)
        if spec["id"] == "browser":
            enabled = enabled and ("browser" in mcp_server_names)
        capability = {
            "id": spec["id"],
            "label": spec["label"],
            "description": spec["description"],
            "enabled": enabled,
            "source": spec["source"],
            "tools": enabled_tools if enabled else [],
        }
        runtime_capabilities.append(capability)
        if enabled:
            enabled_labels.append(spec["label"])

    if mcp_server_names:
        runtime_capabilities.append(
            {
                "id": "mcp",
                "label": "扩展工具",
                "description": f"已连接 {len(mcp_server_names)} 个 MCP 服务",
                "enabled": True,
                "source": "mcp",
                "tools": mcp_server_names,
            }
        )

    return {
        "runtime_capabilities": runtime_capabilities,
        "runtime_capability_labels": enabled_labels,
        "tool_permission_profile": effective_profile,
        "mcp_servers": mcp_server_names,
        "setup_required": getattr(agent, "setup_required", False),
        "bootstrap_setup_pending": _agent_bootstrap_setup_pending(agent),
    }


class StreamManager:
    _instance = None
    _lock = None
    _lock_init = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._streams: Dict[str, asyncio.Task] = {}
            cls._instance._stop_flags: Dict[str, bool] = {}
        return cls._instance

    def _get_lock(self):
        with StreamManager._lock_init:
            if StreamManager._lock is None:
                StreamManager._lock = asyncio.Lock()
        return StreamManager._lock

    async def register(self, request_id: str, task: asyncio.Task) -> None:
        async with self._get_lock():
            self._streams[request_id] = task
            self._stop_flags[request_id] = False

    async def unregister(self, request_id: str) -> None:
        async with self._get_lock():
            self._streams.pop(request_id, None)
            self._stop_flags.pop(request_id, None)

    async def cancel(self, request_id: str) -> bool:
        async with self._get_lock():
            if request_id not in self._streams:
                return False
            self._stop_flags[request_id] = True
            task = self._streams.get(request_id)
            if task and not task.done():
                task.cancel()
            return True

    def should_stop(self, request_id: str) -> bool:
        return self._stop_flags.get(request_id, False)

    def get_task(self, request_id: str) -> Optional[asyncio.Task]:
        return self._streams.get(request_id)

    def exists(self, request_id: str) -> bool:
        return request_id in self._stop_flags

    async def cleanup_task(self, request_id: str, task: asyncio.Task) -> None:
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await self.unregister(request_id)


class AgentLoopPool:
    _instance = None
    _lock = None
    _lock_init = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._pools: Dict[str, AgentLoop] = {}
            cls._instance._bus = None
        return cls._instance

    def _get_lock(self):
        with AgentLoopPool._lock_init:
            if AgentLoopPool._lock is None:
                AgentLoopPool._lock = asyncio.Lock()
        return AgentLoopPool._lock

    def _is_healthy(self, loop: AgentLoop) -> bool:
        if loop is None:
            return False
        if not hasattr(loop, 'provider') or loop.provider is None:
            return False
        if not hasattr(loop, '_running'):
            return True
        return True

    def _generate_cache_key(
        self,
        agent_id: str,
        session_manager: Optional[SessionManager] = None
    ) -> str:
        if session_manager:
            sessions_dir = getattr(session_manager, 'sessions_dir', 'default')
            return f"{agent_id}_{sessions_dir}"
        return agent_id

    async def get_or_create(
        self,
        agent_id: str,
        session_manager: Optional[SessionManager] = None
    ) -> AgentLoop:
        from horbot.agent.manager import get_agent_manager

        logger.debug(f"[AgentLoopPool.get_or_create] Starting for agent_id={agent_id}")

        agent_manager = get_agent_manager()
        cache_key = self._generate_cache_key(agent_id, session_manager)

        logger.debug(f"[AgentLoopPool.get_or_create] Acquiring lock for cache_key={cache_key}")
        async with self._get_lock():
            logger.debug(f"[AgentLoopPool.get_or_create] Lock acquired for cache_key={cache_key}")
            if cache_key in self._pools:
                loop = self._pools[cache_key]
                if self._is_healthy(loop):
                    agent_instance = agent_manager.get_agent(agent_id)
                    if agent_instance:
                        if loop._agent_name != agent_instance.name:
                            loop._agent_name = agent_instance.name
                        if hasattr(loop, 'context') and loop.context._agent_name != agent_instance.name:
                            loop.context._agent_name = agent_instance.name
                    if session_manager and loop.sessions != session_manager:
                        loop.sessions = session_manager
                    if self._bus is not None:
                        _configure_web_subagent_observability(loop)
                        _configure_web_agent_loop_message_routing(loop, self._bus)
                    logger.debug(f"[AgentLoopPool.get_or_create] Returning cached loop for cache_key={cache_key}")
                    return loop
                else:
                    logger.warning(f"AgentLoop for {cache_key} is unhealthy, recreating...")
                    del self._pools[cache_key]

            logger.debug(f"[AgentLoopPool.get_or_create] Creating new loop for cache_key={cache_key}")
            loop = await self._create_agent_loop(
                agent_id,
                session_manager,
                agent_manager,
            )
            self._pools[cache_key] = loop
            logger.debug(f"[AgentLoopPool.get_or_create] Created new loop for cache_key={cache_key}")
            return loop

    async def _create_agent_loop(
        self,
        agent_id: str,
        session_manager: Optional[SessionManager],
        agent_manager,
    ) -> AgentLoop:
        if self._bus is None:
            self._bus = MessageBus()

        config = get_cached_config()

        from horbot.utils.paths import get_uploads_dir
        upload_dir = str(get_uploads_dir())

        agent_instance = agent_manager.get_agent(agent_id) or agent_manager.get_default_agent()
        if not agent_instance:
            raise HTTPException(status_code=500, detail="No agent configured")

        agent_workspace = agent_instance.get_workspace()
        agent_model = agent_instance.model
        agent_session_manager = session_manager or SessionManager(workspace=agent_instance.get_sessions_dir())
        agent_config = agent_instance.config
        system_prompt = agent_config.system_prompt if agent_config.system_prompt else None
        personality = agent_config.personality if agent_config.personality else None
        final_agent_id = agent_instance.id
        agent_name = agent_instance.name

        explicit_provider_name = agent_config.provider if agent_config.provider and agent_config.provider != "auto" else None
        if explicit_provider_name:
            provider_name = explicit_provider_name
            provider_config = getattr(config.providers, provider_name, None)
        else:
            provider_name = config.get_provider_name(agent_model)
            provider_config = config.get_provider(agent_model)

        if not agent_model:
            raise HTTPException(
                status_code=409,
                detail=f"Agent '{final_agent_id}' 尚未完成模型配置，请先在多 Agent 管理中选择 provider 和 model。",
            )

        if not provider_name or not provider_config:
            raise HTTPException(
                status_code=409,
                detail=f"Agent '{final_agent_id}' 尚未完成 provider 配置，请先在多 Agent 管理中选择 provider 和 model。",
            )

        if not getattr(provider_config, "api_key", None) and provider_name not in {"openai_codex", "github_copilot"}:
            raise HTTPException(status_code=500, detail=f"Provider '{provider_name}' missing credentials for agent '{final_agent_id}'")

        logger.info(
            "Initializing agent loop: agent_id={}, provider={}, model={}, api_base={}",
            final_agent_id,
            provider_name,
            agent_model,
            getattr(provider_config, "api_base", None),
        )

        provider = create_provider(
            provider_name,
            api_key=provider_config.api_key,
            api_base=provider_config.api_base,
            extra_headers=provider_config.extra_headers,
            compatibility_profile=getattr(provider_config, "compatibility_profile", "auto"),
            default_model=agent_model,
            upload_dir=upload_dir,
        )

        agent_loop = AgentLoop(
            bus=self._bus,
            provider=provider,
            workspace=agent_workspace,
            model=agent_model,
            max_iterations=config.agents.defaults.max_tool_iterations,
            temperature=config.agents.defaults.temperature,
            max_tokens=config.agents.defaults.max_tokens,
            memory_window=config.agents.defaults.memory_window,
            brave_api_key=config.tools.web.search.api_key,
            restrict_to_workspace=config.tools.restrict_to_workspace,
            mcp_servers=config.tools.mcp_servers,
            channels_config=config.channels,
            exec_config=config.tools.exec,
            session_manager=agent_session_manager,
            cron_service=get_cron_service(),
            system_prompt=system_prompt,
            personality=personality,
            agent_id=final_agent_id,
            agent_name=agent_name,
            team_ids=agent_instance.teams,
        )
        _configure_web_subagent_observability(agent_loop)
        _configure_web_agent_loop_message_routing(agent_loop, self._bus)

        asyncio.create_task(agent_loop.run())

        return agent_loop

    async def invalidate(self, agent_id: str) -> None:
        async with self._get_lock():
            keys_to_remove = [k for k in self._pools if k.startswith(agent_id)]
            for key in keys_to_remove:
                logger.info(f"Invalidating AgentLoop for key: {key}")
                del self._pools[key]

    async def invalidate_all(self) -> None:
        async with self._get_lock():
            self._pools.clear()
            logger.info("All AgentLoop instances have been invalidated")


def get_agent_loop_pool() -> AgentLoopPool:
    return AgentLoopPool()


def get_stream_manager() -> StreamManager:
    return StreamManager()


def _normalize_agent_mention_token(text: str) -> str:
    import re

    return re.sub(r"[^\w\u4e00-\u9fff-]+", "", (text or "")).lower()


def _resolve_chat_target(agent_id: str | None) -> tuple[str, Any | None]:
    if not agent_id:
        return "missing", None

    from horbot.agent.manager import get_agent_manager
    from horbot.external_agents.manager import get_external_agent_manager

    internal_agent = get_agent_manager().get_agent(agent_id)
    if internal_agent is not None:
        return "internal", internal_agent

    external_agent = get_external_agent_manager().get_external_agent(agent_id)
    if external_agent is not None:
        return "external", external_agent

    return "missing", None


def _resolve_chat_target_name(agent_id: str | None) -> str:
    target_kind, target = _resolve_chat_target(agent_id)
    if target_kind in {"internal", "external"} and target is not None:
        return getattr(target, "name", None) or (agent_id or "助手")
    return agent_id or "助手"


def parse_agent_mentions(content: str, available_agents: List[str]) -> List[str]:
    """Parse @mentions from content and return list of mentioned agent IDs.

    Supports agent names with spaces (e.g., "@小项 🐎" matches agent named "小项 🐎").
    Priority: exact name match > exact ID match > partial name match
    """
    import re
    mentioned: list[str] = []

    agents_info = []
    for agent_id in available_agents:
        _, agent = _resolve_chat_target(agent_id)
        if agent is not None:
            agents_info.append(
                {
                    "id": agent_id,
                    "name": agent.name,
                    "normalized_id": _normalize_agent_mention_token(agent_id),
                    "normalized_name": _normalize_agent_mention_token(agent.name),
                }
            )

    matched_spans: list[tuple[int, int]] = []
    name_matches: list[tuple[int, int, str]] = []
    for agent_info in agents_info:
        pattern = re.escape(f"@{agent_info['name']}")
        for match in re.finditer(pattern, content):
            start, end = match.start(), match.end()
            if end < len(content) and content[end] not in ' \t\n\r.,!?;:，。！？；：':
                continue
            name_matches.append((start, end, agent_info["id"]))

    # Preserve the order in which mentions appear in the text while still
    # preferring longer exact-name matches when multiple names overlap.
    name_matches.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    for start, end, agent_id in name_matches:
        if any(not (end <= existing_start or start >= existing_end) for existing_start, existing_end in matched_spans):
            continue
        if agent_id not in mentioned:
            mentioned.append(agent_id)
        matched_spans.append((start, end))

    mention_pattern = r'@(\S+)'
    for match in re.finditer(mention_pattern, content):
        start, end = match.start(), match.end()
        if any(not (end <= existing_start or start >= existing_end) for existing_start, existing_end in matched_spans):
            continue

        mention_text = match.group(1)
        normalized_mention = _normalize_agent_mention_token(mention_text)
        for agent_info in agents_info:
            agent_id = agent_info["id"]
            if agent_id in mentioned:
                continue
            if (
                mention_text == agent_id
                or normalized_mention == agent_info["normalized_id"]
                or (
                    agent_info["normalized_name"]
                    and normalized_mention == agent_info["normalized_name"]
                )
            ):
                mentioned.append(agent_id)
                matched_spans.append((start, end))
                break

    return mentioned


def _get_team_member_agent_ids(team_id: str | None) -> List[str]:
    """Return ordered internal member agent ids for a team, or an empty list."""
    if not team_id:
        return []

    from horbot.team.manager import get_team_manager
    from horbot.agent.manager import get_agent_manager

    team = get_team_manager().get_team(team_id)
    if not team:
        return []

    agent_manager = get_agent_manager()
    return [
        member_id
        for member_id in team.get_ordered_member_ids()
        if agent_manager.get_agent(member_id) is not None
    ]


def _get_team_external_agent_ids(team_id: str | None) -> List[str]:
    from horbot.external_agents.manager import get_external_agent_manager
    from horbot.team.manager import get_team_manager

    if not team_id:
        external_agents = get_external_agent_manager().get_all_external_agents()
        return [agent.id for agent in external_agents if bool(agent.config.team_enabled)]

    team = get_team_manager().get_team(team_id)
    if not team:
        return []

    external_agent_manager = get_external_agent_manager()
    return [
        member_id
        for member_id in team.get_ordered_member_ids()
        if (
            (external_agent := external_agent_manager.get_external_agent(member_id)) is not None
            and bool(external_agent.config.team_enabled)
        )
    ]


def _get_group_chat_available_agent_ids(team_id: str | None) -> List[str]:
    from horbot.agent.manager import get_agent_manager

    internal_ids = (
        _get_team_member_agent_ids(team_id)
        if team_id
        else [agent.id for agent in get_agent_manager().get_all_agents()]
    )
    ordered: list[str] = []
    for agent_id in [*internal_ids, *_get_team_external_agent_ids(team_id)]:
        if agent_id not in ordered:
            ordered.append(agent_id)
    return ordered


def _build_external_agent_history(
    session,
    *,
    max_items: int = 12,
) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    for item in list(getattr(session, "messages", []) or [])[-max_items:]:
        role = str(item.get("role") or "").strip()
        content = clean_message_content(str(item.get("content") or "").strip())
        if not role or not content:
            continue
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        history.append(
            {
                "role": role,
                "content": content,
                "agent_id": metadata.get("agent_id"),
                "agent_name": metadata.get("agent_name"),
            }
        )
    return history


def extract_agent_mention_payload(
    content: str,
    *,
    target_agent_id: str,
    target_agent_name: str,
) -> Optional[str]:
    """Extract the message payload intended for a mentioned agent.

    Examples:
    - "@袭人 请只回复自己的名字" -> "请只回复自己的名字"
    - "麻烦 @horbot-02 看一下这个报错" -> "看一下这个报错"

    Returns None if no target-specific payload can be extracted.
    """
    import re

    cleaned = clean_message_content(content or "")
    if not cleaned:
        return None

    mention_tokens = [target_agent_name, target_agent_id]
    for token in mention_tokens:
        if not token:
            continue
        pattern = re.compile(rf"@{re.escape(token)}(?P<suffix>[\s\S]*)")
        match = pattern.search(cleaned)
        if not match:
            continue
        suffix = match.group("suffix").strip()
        suffix = re.sub(r"^[\s,，:：;；\-]+", "", suffix).strip()
        return suffix or None

    return None


def _should_return_to_user_summary_turn(
    *,
    candidate_agent_id: str,
    response_agent_id: str,
    response_context,
    originally_mentioned: set[str],
) -> bool:
    """Decide whether a relay should switch back to the user's summary turn.

    Only the originator's own handoff intent should decide whether the relay
    returns to a user-facing summary turn. This avoids teammates prematurely
    collapsing a deep discussion just by saying "you summarize".
    """
    if (
        response_context is None
        or getattr(response_context.conversation_type, "value", response_context.conversation_type) != "agent_to_agent"
        or candidate_agent_id != response_context.source
        or candidate_agent_id not in originally_mentioned
        or response_agent_id in originally_mentioned
    ):
        return False

    return _get_originator_return_mode(response_context) == "summary"


def _build_user_summary_trigger_message(original_request: str) -> str:
    cleaned_request = clean_message_content(original_request or "").strip()
    if not cleaned_request:
        cleaned_request = "请基于当前团队讨论，直接给用户一个最终总结。"
    return (
        "请基于当前团队对话历史，吸收其他 agent 已经给出的分析，"
        "现在直接面向用户输出最终总结。不要再次点名或 @ 其他 agent，"
        "也不要把任务再分派出去。\n\n"
        f"原始用户问题：{cleaned_request}"
    )


def _build_team_baton_trigger_message(
    original_request: str,
    *,
    mode: str,
    source_name: str | None = None,
    target_name: str | None = None,
) -> str:
    cleaned_request = clean_message_content(original_request or "").strip()
    if not cleaned_request:
        cleaned_request = "请基于当前上下文继续推进团队接力。"

    if mode == "kickoff":
        return (
            "你正在团队接力模式中，当前是首棒/当前主棒。请用更短回合推进：\n"
            "1. 先用 2-4 句快速锁定任务、目标和拆分思路；\n"
            "2. 如果需要其他 agent 参与，尽快把任务拆成一个明确子问题并交给下一棒；\n"
            "3. 每一棒优先只解决一个核心问题，不要一开始就写成长篇最终方案；\n"
            "4. 只有在明确轮到你做最终汇总时，才输出完整终稿。\n\n"
            f"原始用户问题：{cleaned_request}"
        )

    relay_hint = (
        f"当前接力关系：{source_name or '上一棒'} -> {target_name or '当前棒'}。\n"
        if source_name or target_name
        else ""
    )
    return (
        "你正在团队接力中，请保持短回合 baton：\n"
        "1. 只回答当前交给你的一个核心子问题；\n"
        "2. 优先给简短判断、关键风险和下一步建议，不要直接写成长篇总稿；\n"
        "3. 如果需要继续交棒，只交给下一棒一个明确问题；\n"
        "4. 只有明确轮到你回到发起人/用户做总结时，才输出完整汇总。\n\n"
        f"{relay_hint}"
        f"当前交接任务：{cleaned_request}"
    )


def _build_relay_handoff_preview(content: str, *, max_chars: int = 88) -> str:
    cleaned = clean_message_content(content or "").strip()
    if not cleaned:
        return ""
    single_line = re.sub(r"\s+", " ", cleaned).strip()
    if len(single_line) <= max_chars:
        return single_line
    return f"{single_line[:max_chars - 1].rstrip()}…"


def is_stop_discussion_message(content: str) -> bool:
    """Check if user wants to stop the ongoing agent discussion.

    Detects phrases like "停止讨论", "结束讨论", "停", "好了停" etc.
    """
    import re

    if not content:
        return False

    content_lower = content.strip().lower()

    stop_patterns = [
        r'^停止讨论$',
        r'^结束讨论$',
        r'^停$',
        r'^好了停$',
        r'^停吧$',
        r'^别讨论了$',
        r'^不要讨论了$',
        r'^停止$',
        r'^结束$',
        r'^stop$',
        r'^stop discussion$',
    ]

    for pattern in stop_patterns:
        if re.match(pattern, content_lower):
            return True

    return False


def _resolve_final_agent_display_content(
    response_content: str | None,
    streamed_content: str | None,
) -> str:
    """Choose the best displayable content for an agent turn.

    Tool-oriented responses may return a non-empty system string such as
    "Message sent to ...", which gets stripped by `clean_message_content`.
    In that case we should still fall back to the already streamed text.
    """
    cleaned_response = clean_message_content(response_content or "")
    if cleaned_response:
        return cleaned_response
    return clean_message_content(streamed_content or "")


def _get_originator_return_mode(conversation_ctx: "ConversationContext | None") -> str | None:
    if conversation_ctx is None or getattr(conversation_ctx.conversation_type, "value", "") != "agent_to_agent":
        return None

    trigger_message = (conversation_ctx.trigger_message or "").replace(" ", "")
    if not trigger_message:
        return None

    has_return_intent = any(
        token in trigger_message
        for token in (
            "我来总结",
            "我再总结",
            "我再汇总",
            "我来汇总",
            "我再给",
            "我再整理",
            "我再收敛",
            "回给我",
            "回我",
        )
    )
    has_handoff_intent = any(
        token in trigger_message
        for token in (
            "等你",
            "请你先",
            "先帮我",
            "先从",
            "先按",
        )
    )
    if has_return_intent and has_handoff_intent:
        return "summary"

    has_continue_intent = any(
        token in trigger_message
        for token in (
            "我再继续",
            "我继续",
            "继续讨论",
            "继续分析",
            "继续推演",
            "继续往下",
            "继续深挖",
            "继续拆",
            "再补一轮",
            "再来一轮",
            "我们继续",
            "不要急着总结",
            "还不要总结",
            "先别总结",
        )
    )
    if has_continue_intent and has_handoff_intent:
        return "continue"

    # Chinese relay prompts often say "等你回复后我再总结/继续", which doesn't
    # fit the shorter exact tokens above. Preserve the originator's intent so
    # the baton returns after the teammate finishes instead of stalling.
    if has_handoff_intent and any(token in trigger_message for token in ("回复后", "之后", "完后", "说完", "补完")):
        if any(token in trigger_message for token in ("总结", "汇总", "整理", "收敛", "收口", "定稿", "给用户")):
            return "summary"
        if any(token in trigger_message for token in ("继续", "讨论", "分析", "推演", "深挖", "往下", "拆解")):
            return "continue"

    return None


def _team_history_session_managers(team_id: str) -> list[SessionManager]:
    candidates: list[SessionManager] = [get_session_manager()]
    try:
        from horbot.workspace.manager import get_workspace_manager

        workspace_manager = get_workspace_manager()
        team_ws = workspace_manager.get_team_workspace(team_id)
        if team_ws:
            candidates.append(SessionManager(workspace=Path(team_ws.workspace_path) / "sessions"))
    except Exception as exc:
        logger.warning("Failed to resolve team history paths for team {}: {}", team_id, exc)
    return _unique_session_managers(candidates)


def _resolve_conversation_for_history(conv_id: str):
    from horbot.conversation import get_conversation_manager, ConversationType

    conv_manager = get_conversation_manager()
    conv = conv_manager.get(conv_id)
    if conv:
        return conv

    conv_type, target_id = conv_manager.parse_id(conv_id)
    if conv_type == ConversationType.DM:
        from horbot.agent.manager import get_agent_manager
        from horbot.external_agents.manager import get_external_agent_manager

        agent_manager = get_agent_manager()
        agent = agent_manager.get_agent(target_id)
        if agent:
            return conv_manager.get_or_create_dm(target_id, agent.name)

        external_agent = get_external_agent_manager().get_external_agent(target_id)
        if external_agent:
            return conv_manager.get_or_create_dm(target_id, external_agent.name)
    elif conv_type == ConversationType.TEAM:
        from horbot.team.manager import get_team_manager

        team_manager = get_team_manager()
        team = team_manager.get_team(target_id)
        if team:
            return conv_manager.get_or_create_team(target_id, team.name, team.members)

    return None


def _load_conversation_raw_messages(conv) -> list[dict[str, Any]]:
    from horbot.conversation import ConversationType
    from horbot.session.manager import SessionManager

    candidate_managers: list[SessionManager] = []
    if conv.type == ConversationType.TEAM:
        candidate_managers = _team_history_session_managers(conv.target_id)
    elif conv.type == ConversationType.DM:
        from horbot.agent.manager import get_agent_manager

        agent_manager = get_agent_manager()
        agent = agent_manager.get_agent(conv.target_id)
        if agent is not None:
            session_manager = SessionManager(workspace=agent.get_sessions_dir())
            candidate_managers = [
                get_session_manager(),
                *_legacy_agent_session_managers(agent),
                session_manager,
            ]
        else:
            candidate_managers = [get_session_manager()]
    else:
        candidate_managers = [get_session_manager()]

    return _load_merged_session_messages(f"web:{conv.id}", candidate_managers)



class ChatRequest(BaseModel):
    content: str
    session_key: str = "default"
    file_ids: List[str] = []  # MiniMax file IDs for document processing
    web_search: bool = False  # Enable web search for MiniMax
    agent_id: Optional[str] = None  # Target agent ID for multi-agent chat


def get_session_manager():
    """Get session manager instance."""
    global _session_manager
    config = get_cached_config()
    default_agent_id = next(iter(config.agents.instances.keys()), "default")
    from horbot.workspace.manager import get_workspace_manager

    workspace_manager = get_workspace_manager()
    if hasattr(workspace_manager, "get_agent_workspace"):
        expected_sessions_dir = Path(workspace_manager.get_agent_workspace(default_agent_id).sessions_path)
    else:
        expected_sessions_dir = Path(".horbot") / "agents" / default_agent_id / "sessions"

    if _session_manager is None or Path(_session_manager.sessions_dir) != Path(expected_sessions_dir):
        _session_manager = SessionManager(workspace=expected_sessions_dir)
    return _session_manager


async def _resolve_chat_session_manager(
    session_key: str,
    *,
    agent_id: Optional[str] = None,
) -> tuple[SessionManager, str]:
    """Resolve the correct session manager for a chat session key.

    Team conversations persist under the team workspace, while regular web
    conversations stay under the global session manager. Agent-scoped reads can
    still force the agent session manager when `agent_id` is provided.
    """
    from horbot.workspace.manager import get_workspace_manager

    normalized_session_key = session_key if session_key.startswith("web:") else f"web:{session_key}"

    if agent_id:
        target_kind, _ = _resolve_chat_target(agent_id)
        if target_kind == "internal":
            agent_loop = await get_agent_loop(agent_id)
            return agent_loop.sessions, normalized_session_key
        if target_kind == "external":
            return get_session_manager(), normalized_session_key

    raw_session_key = normalized_session_key[4:] if normalized_session_key.startswith("web:") else normalized_session_key

    if raw_session_key.startswith("team_"):
        team_id = raw_session_key[5:]
        from horbot.team.manager import get_team_manager

        team_manager = get_team_manager()
        team = team_manager.get_team(team_id)
        if team:
            workspace_manager = get_workspace_manager()
            team_ws = workspace_manager.get_team_workspace(team_id)
            if team_ws:
                team_sessions_path = Path(team_ws.workspace_path) / "sessions"
                return SessionManager(workspace=team_sessions_path), normalized_session_key

    if raw_session_key.startswith("dm_"):
        extracted_agent_id = raw_session_key[3:]
        target_kind: str | None = None
        try:
            target_kind, _ = _resolve_chat_target(extracted_agent_id)
        except Exception as e:
            logger.warning(
                "[DEBUG] Failed to resolve chat target for {} while resolving DM session manager: {}",
                extracted_agent_id,
                e,
            )
        if target_kind == "external":
            return get_session_manager(), normalized_session_key
        try:
            agent_loop = await get_agent_loop(extracted_agent_id)
            return agent_loop.sessions, normalized_session_key
        except Exception as e:
            logger.warning(
                "[DEBUG] Failed to get agent loop for {} while resolving DM session manager: {}",
                extracted_agent_id,
                e,
            )

    if raw_session_key.startswith("agent_"):
        extracted_agent_id = raw_session_key[6:]
        try:
            agent_loop = await get_agent_loop(extracted_agent_id)
            return agent_loop.sessions, normalized_session_key
        except Exception as e:
            logger.warning(
                "[DEBUG] Failed to get agent loop for {} while resolving session manager: {}",
                extracted_agent_id,
                e,
            )

    return get_session_manager(), normalized_session_key

def get_cron_service():
    """Get cron service instance."""
    global _cron_service
    if _cron_service is None:
        from horbot.utils.paths import get_cron_dir
        store_path = get_cron_dir() / "jobs.json"
        _cron_service = CronService(store_path=store_path)
    return _cron_service

def send_macos_notification(title: str, message: str) -> bool:
    """Send a MacOS notification using osascript."""
    import subprocess
    try:
        escaped_title = title.replace('"', '\\"')
        escaped_message = message.replace('"', '\\"')
        script = f'display notification "{escaped_message}" with title "{escaped_title}"'
        subprocess.run(['osascript', '-e', script], check=True, capture_output=True)
        return True
    except Exception as e:
        logger.warning("Failed to send MacOS notification: {}", e)
        return False

async def setup_cron_callback():
    """Setup cron job callback after agent loop is initialized."""
    from horbot.cron.types import CronJob

    cron_service = get_cron_service()

    # Try to initialize agent loop, but don't fail if provider is not configured
    try:
        agent_loop = await get_agent_loop()
    except HTTPException as e:
        if "Provider not configured" in str(e.detail):
            logger.warning("Provider not configured, cron jobs will not work until provider is set up")
            return
        raise

    pool = get_agent_loop_pool()
    bus = pool._bus

    async def on_cron_job(job: CronJob) -> str | None:
        """Execute a cron job through the agent."""
        logger.info("Cron: executing job '{}' ({})", job.name, job.id)

        if job.payload.notify:
            send_macos_notification(
                title=f"⏰ {job.name}",
                message=job.payload.message[:100] if len(job.payload.message) > 100 else job.payload.message
            )

        targets = job.payload.get_delivery_targets() or []

        primary_channel = targets[0].channel if targets else "web"
        primary_chat_id = targets[0].to if targets else "cron_user"

        web_targets = [t for t in targets if t.channel == "web"]
        external_targets = [t for t in targets if t.channel != "web"]

        if web_targets:
            session_key = f"web:{web_targets[0].to}"
        else:
            session_key = f"web:cron_{job.id}"

        response = await agent_loop.process_direct(
            job.payload.message,
            session_key=session_key,
            channel=primary_channel,
            chat_id=primary_chat_id,
        )

        if job.payload.deliver:
            from datetime import datetime
            from horbot.bus.events import OutboundMessage

            session_manager = get_session_manager()
            session = session_manager.get_or_create(session_key)
            session.add_message(
                role="assistant",
                content=response or "",
                timestamp=datetime.now().isoformat(),
                source="cron",
                job_name=job.name,
            )
            session_manager.save(session)
            logger.info("Cron: saved response to session {}", session_key)

            from horbot.web.websocket import broadcast_to_session
            await broadcast_to_session(session_key, {
                "type": "cron_message",
                "job_name": job.name,
                "content": response or "",
                "timestamp": datetime.now().isoformat(),
            })

            for target in external_targets:
                await bus.publish_outbound(OutboundMessage(
                    channel=target.channel,
                    chat_id=target.to,
                    content=response or ""
                ))
                logger.info("Cron: published outbound message to {}:{}", target.channel, target.to)

        return response

    cron_service.on_job = on_cron_job

async def get_agent_loop(agent_id: Optional[str] = None) -> AgentLoop:
    """Get agent loop instance by agent_id.

    If agent_id is None or invalid, returns the default AgentLoop.
    Uses AgentLoopPool for management with health checks and automatic recovery.
    """
    from horbot.agent.manager import get_agent_manager

    logger.debug(f"[get_agent_loop] Getting agent loop for agent_id={agent_id}")

    agent_manager = get_agent_manager()

    if not agent_id:
        default_agent = agent_manager.get_default_agent()
        agent_id = default_agent.id if default_agent else "default"

    pool = get_agent_loop_pool()
    logger.debug(f"[get_agent_loop] Calling pool.get_or_create for agent_id={agent_id}")
    result = await pool.get_or_create(agent_id)
    logger.debug(f"[get_agent_loop] Got agent loop for agent_id={agent_id}")
    return result


async def get_agent_loop_with_session_manager(agent_id: Optional[str], session_manager: Optional["SessionManager"]) -> AgentLoop:
    """Get agent loop instance with a specific session manager.

    If session_manager is provided, the agent will use it for team shared sessions.
    Uses AgentLoopPool for management with health checks and automatic recovery.
    """
    from horbot.agent.manager import get_agent_manager

    agent_manager = get_agent_manager()

    if not agent_id:
        default_agent = agent_manager.get_default_agent()
        agent_id = default_agent.id if default_agent else "default"

    pool = get_agent_loop_pool()
    return await pool.get_or_create(agent_id, session_manager)


async def reset_agent_loop():
    """Reset agent loop instance to reload configuration."""
    pool = get_agent_loop_pool()
    await pool.invalidate_all()


def _resolve_agent_for_request(agent_id: Optional[str] = None):
    from horbot.agent.manager import get_agent_manager

    agent_manager = get_agent_manager()
    if agent_id:
        agent = agent_manager.get_agent(agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        return agent
    return agent_manager.get_default_agent()


def _resolve_agent_workspace_for_request(agent_id: Optional[str] = None) -> tuple[Optional[Any], Path]:
    agent = _resolve_agent_for_request(agent_id)
    if agent is not None:
        return agent, agent.get_workspace()
    return None, Path(get_cached_config().workspace_path)


def _resolve_skill_dir_for_request(agent_id: Optional[str] = None) -> tuple[Optional[Any], Path, Path]:
    from horbot.agent.skills import resolve_skills_dir

    agent, workspace_path = _resolve_agent_workspace_for_request(agent_id)
    if agent is not None:
        return agent, workspace_path, agent.get_skills_dir()
    return agent, workspace_path, resolve_skills_dir(workspace_path, agent_id=agent_id)


def _describe_skill_source(
    *,
    skill: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    source = str(skill.get("source") or "user").strip()
    path = str(skill.get("path") or "")

    if source == "builtin":
        return {
            "source_group": "system",
            "source_origin_kind": "builtin",
            "source_origin_agent_id": None,
        }

    generated_by = str(metadata.get("generated_by") or "").strip()
    path_parts = Path(path).parts
    agent_from_path: str | None = None
    for index in range(len(path_parts) - 5):
        if (
            path_parts[index] == ".horbot"
            and path_parts[index + 1] == "agents"
            and path_parts[index + 3] == "workspace"
            and path_parts[index + 4] == ".horbot-agent"
            and path_parts[index + 5] == "skills"
        ):
            agent_from_path = path_parts[index + 2]
            break

    if generated_by == "skill-evolution" and agent_from_path:
        return {
            "source_group": "custom",
            "source_origin_kind": "agent",
            "source_origin_agent_id": agent_from_path,
        }

    return {
        "source_group": "custom",
        "source_origin_kind": "manual",
        "source_origin_agent_id": None,
    }


def _agent_bootstrap_file_path(agent_id: str, file_kind: str) -> tuple[Path, str]:
    _, workspace_path = _resolve_agent_workspace_for_request(agent_id)
    normalized = (file_kind or "").strip().lower()
    if normalized == "agents":
        return workspace_path / "AGENTS.md", "AGENTS.md"
    if normalized == "soul":
        return workspace_path / "SOUL.md", "SOUL.md"
    if normalized == "user":
        return workspace_path / "USER.md", "USER.md"
    raise HTTPException(status_code=400, detail="Unsupported bootstrap file. Use 'agents', 'soul', or 'user'.")


def _read_bootstrap_file(path: Path) -> dict[str, Any]:
    exists = path.exists()
    return {
        "path": str(path),
        "exists": exists,
        "content": path.read_text(encoding="utf-8") if exists else "",
    }


def _build_bootstrap_summary(agent, soul_content: str, user_content: str) -> dict[str, Any]:
    return build_bootstrap_summary(getattr(agent, "name", None), soul_content, user_content)


def _build_agent_bootstrap_payload(agent) -> dict[str, Any]:
    _ensure_agent_bootstrap_files(agent)

    agents_path, _ = _agent_bootstrap_file_path(agent.id, "agents")
    soul_path, _ = _agent_bootstrap_file_path(agent.id, "soul")
    user_path, _ = _agent_bootstrap_file_path(agent.id, "user")
    agents_file = _read_bootstrap_file(agents_path)
    soul_file = _read_bootstrap_file(soul_path)
    user_file = _read_bootstrap_file(user_path)

    return {
        "agent_id": agent.id,
        "agent_name": agent.name,
        "workspace_path": str(agent.get_workspace()),
        "summary": _build_bootstrap_summary(agent, soul_file["content"], user_file["content"]),
        "files": {
            "agents": agents_file,
            "soul": soul_file,
            "user": user_file,
        },
    }


def _maybe_materialize_bootstrap_from_session(agent, session) -> bool:
    if agent is None or session is None:
        return False
    if getattr(agent, "setup_required", False):
        return False
    if not _agent_bootstrap_setup_pending(agent):
        return False
    try:
        workspace = agent.get_workspace()
        return materialize_bootstrap_from_messages(
            workspace,
            agent_name=getattr(agent, "name", None),
            messages=list(getattr(session, "messages", []) or []),
        )
    except Exception:
        logger.exception("Failed to auto-materialize bootstrap files for agent {}", getattr(agent, "id", "<unknown>"))
        return False


def _build_system_status_payload(config: Config | None = None) -> dict[str, Any]:
    return build_system_status_payload(
        config=config or get_cached_config(),
        started_at=_api_started_at,
        cron_status_fn=lambda: get_cron_service().status(),
        agent_initialized_fn=lambda: len(get_agent_loop_pool()._pools) > 0,
    )


def _cache_remote_image_file(url: str, index: int) -> dict[str, Any] | None:
    """Compatibility patch point for tests/extensions that mock remote image caching."""
    return _upload_cache_remote_image_file(url, index)


def _normalize_saved_assistant_content_and_files(
    content: str | None,
    files: list[dict[str, Any]] | None,
) -> tuple[str, list[dict[str, Any]]]:
    """Normalize saved assistant content and promote standalone image URLs to file attachments."""
    cleaned_content = clean_message_content(content or "")
    normalized_files = list(files or [])
    remote_image_urls = upload_preview_module._extract_remote_image_urls(cleaned_content)
    if remote_image_urls:
        seen_urls = {
            str((item or {}).get("preview_url") or (item or {}).get("url") or "").strip()
            for item in normalized_files
        }
        seen_file_ids = {
            str((item or {}).get("file_id") or "").strip()
            for item in normalized_files
        }
        for index, url in enumerate(remote_image_urls, start=1):
            remote_file_id = upload_preview_module._remote_image_file_id(url)
            if url in seen_urls or remote_file_id in seen_file_ids:
                continue
            cached_file = _cache_remote_image_file(url, index)
            if cached_file:
                normalized_files.append(cached_file)
                seen_file_ids.add(remote_file_id)
                continue
            filename, original_name, mime_type = upload_preview_module._guess_remote_image_file_name(url, index)
            normalized_files.append({
                "file_id": remote_file_id,
                "filename": filename,
                "original_name": original_name,
                "mime_type": mime_type,
                "size": 0,
                "category": "image",
                "url": url,
                "preview_url": url,
            })
        cleaned_content = upload_preview_module._strip_standalone_remote_image_url_lines(cleaned_content, remote_image_urls)
    return cleaned_content, normalized_files


async def get_chat_history(
    session_key: str = "default",
    agent_id: Optional[str] = None,
):
    """Get chat history for a session."""
    normalized_session_key = session_key if session_key.startswith("web:") else f"web:{session_key}"
    resolved_agent_id = agent_id
    raw_session_key = normalized_session_key[4:] if normalized_session_key.startswith("web:") else normalized_session_key
    if not resolved_agent_id and raw_session_key.startswith("dm_"):
        resolved_agent_id = raw_session_key[3:]
    logger.info(f"[DEBUG] get_chat_history called: session_key={session_key}, normalized={normalized_session_key}, agent_id={agent_id}")

    manager, normalized_session_key = await _resolve_chat_session_manager(
        session_key,
        agent_id=resolved_agent_id,
    )
    logger.info(f"[DEBUG] Using sessions_dir={manager.sessions_dir}")

    candidate_managers = [manager]
    if raw_session_key.startswith("team_"):
        candidate_managers = _team_history_session_managers(raw_session_key[5:])
    elif resolved_agent_id:
        from horbot.agent.manager import get_agent_manager

        agent = get_agent_manager().get_agent(resolved_agent_id)
        if agent is not None:
            candidate_managers = [
                get_session_manager(),
                *_legacy_agent_session_managers(agent),
                manager,
            ]

    raw_messages = _load_merged_session_messages(normalized_session_key, candidate_managers)
    logger.info(f"[DEBUG] Merged session messages count={len(raw_messages)}")

    # Return messages in format expected by frontend
    messages = []
    for msg in raw_messages:
        # Skip metadata entries
        if msg.get("_type") == "metadata":
            continue
        content = msg.get("content")
        files = msg.get("files")
        if msg.get("role") == "assistant":
            content, files = _normalize_saved_assistant_content_and_files(content, files)
        msg_data = {
            "id": ensure_history_message_id(msg),
            "role": msg.get("role"),
            "content": content,
            "timestamp": msg.get("timestamp")
        }
        # Include execution_steps if present (saved with underscore naming)
        if "execution_steps" in msg:
            msg_data["execution_steps"] = sanitize_execution_steps(msg["execution_steps"])

        # Include files if present
        if files:
            msg_data["files"] = files

        # Include metadata if present
        if "metadata" in msg:
            msg_data["metadata"] = msg["metadata"]

        messages.append(msg_data)

    return {"messages": messages, "session_key": session_key}


@router.get("/chat/history")
async def get_chat_history_endpoint(
    response: Response,
    session_key: str = "default",
    agent_id: Optional[str] = None,
):
    """Get chat history for a session."""
    response.headers["Cache-Control"] = "no-store"
    return await get_chat_history(session_key=session_key, agent_id=agent_id)


async def create_new_session(request: Optional[CreateSessionRequest] = None):
    """Compatibility wrapper for tests importing this function from horbot.web.api."""
    return await create_new_session_payload(request, get_session_manager_fn=lambda: get_session_manager())


async def update_session_title(session_key: str, title: str):
    """Compatibility wrapper for tests importing this function from horbot.web.api."""
    return await update_session_title_payload(
        session_key,
        title,
        resolve_chat_session_manager_fn=lambda key: _resolve_chat_session_manager(key),
    )


async def delete_session(session_key: str):
    """Compatibility wrapper for tests importing this function from horbot.web.api."""
    return await delete_session_payload(
        session_key,
        resolve_chat_session_manager_fn=lambda key: _resolve_chat_session_manager(key),
    )


async def list_chat_sessions():
    """Compatibility wrapper for tests importing this function from horbot.web.api."""
    return await list_chat_sessions_payload(get_session_manager_fn=lambda: get_session_manager())


async def get_conversation_messages(
    conv_id: str,
    limit: int = DEFAULT_CONVERSATION_HISTORY_LIMIT,
    before_id: Optional[str] = None,
    after_id: Optional[str] = None,
    around_id: Optional[str] = None,
    context_before: int = DEFAULT_CONVERSATION_AROUND_CONTEXT,
    context_after: int = DEFAULT_CONVERSATION_AROUND_CONTEXT,
):
    """Compatibility wrapper for tests importing this function from horbot.web.api."""
    return await get_conversation_messages_payload(
        conv_id,
        resolve_conversation_for_history=lambda value: _resolve_conversation_for_history(value),
        load_conversation_raw_messages=lambda conv: _load_conversation_raw_messages(conv),
        limit=limit,
        before_id=before_id,
        after_id=after_id,
        around_id=around_id,
        context_before=context_before,
        context_after=context_after,
    )

@router.post("/chat")
async def send_chat_message(request: ChatRequest):
    """Send chat message and get response."""

    agent_loop = await get_agent_loop(request.agent_id)

    if not request.content:
        raise HTTPException(status_code=400, detail="Content is required")

    manager = agent_loop.sessions
    session_key = request.session_key if request.session_key.startswith("web:") else f"web:{request.session_key}"
    session = manager.get_or_create(session_key)
    session.add_message("user", request.content, dedup=True)
    manager.save(session)

    chat_id = request.session_key
    if chat_id.startswith("web:"):
        chat_id = chat_id[4:]

    msg = InboundMessage(
        channel="web",
        sender_id="web_user",
        chat_id=chat_id,
        content=request.content,
        metadata={"file_ids": request.file_ids} if request.file_ids else None,
    )

    try:
        response = await agent_loop.process_message(msg, session_key=session_key)

        if response:
            session.add_message("assistant", response.content)
            manager.save(session)
            return {"content": response.content}
        else:
            return {"content": "No response"}
    except Exception as e:
        logger.exception(f"[ChatAPI] Error in non-stream chat for session {session_key}: {e}")
        raise HTTPException(
            status_code=500,
            detail=public_error_message(e),
        )


class StreamRequest(BaseModel):
    content: str
    session_key: str = "default"
    file_ids: List[str] = []  # MiniMax file IDs for document processing
    web_search: bool = False  # Enable web search for MiniMax
    files: List[dict] = []  # Full file info for displaying attachments in history
    agent_id: Optional[str] = None  # Target agent ID for multi-agent chat
    group_chat: bool = False  # Enable group chat mode
    team_id: Optional[str] = None  # Team ID for team chat
    mentioned_agents: List[str] = []  # List of agent IDs mentioned with @
    conversation_id: Optional[str] = None  # Conversation ID (dm_xxx or team_xxx)
    conversation_type: Optional[str] = None  # Conversation type (dm or team)


def _sse_event(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _build_chat_stream_event(
    event: str,
    *,
    agent_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    turn_id: Optional[str] = None,
    message_id: Optional[str] = None,
    **payload: Any,
) -> Dict[str, Any]:
    data: Dict[str, Any] = {"event": event, **payload}
    if any(value is not None for value in (agent_id, agent_name, turn_id, message_id)):
        data.update({
            "agent_id": agent_id,
            "agent_name": agent_name,
            "turn_id": turn_id,
            "message_id": message_id,
        })
    return data


async def _queue_chat_stream_event(
    queue: asyncio.Queue,
    event: str,
    *,
    agent_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    turn_id: Optional[str] = None,
    message_id: Optional[str] = None,
    **payload: Any,
) -> None:
    await queue.put(
        _build_chat_stream_event(
            event,
            agent_id=agent_id,
            agent_name=agent_name,
            turn_id=turn_id,
            message_id=message_id,
            **payload,
        )
    )


def _create_chat_stream_callbacks(
    *,
    queue: asyncio.Queue,
    stream_manager: "StreamManager",
    request_id: str,
    agent_id: str,
    agent_name: str,
    turn_id: str,
    message_id: str,
    execution_steps: List[dict],
    content_state: Dict[str, str],
    on_message_tool_content: Optional[Callable[[str], None]] = None,
    on_message_tool_dispatch: Optional[Callable[[dict[str, Any]], None]] = None,
    on_step_start_hook: Optional[Callable[[dict], None]] = None,
    enable_synthetic_progress: bool = False,
) -> Dict[str, Callable[..., Any]]:
    has_real_progress = False
    last_synthetic_progress = ""

    async def emit(event: str, **payload: Any) -> None:
        if stream_manager.should_stop(request_id):
            raise asyncio.CancelledError()
        await _queue_chat_stream_event(
            queue,
            event,
            agent_id=agent_id,
            agent_name=agent_name,
            turn_id=turn_id,
            message_id=message_id,
            **payload,
        )

    async def on_progress(content: str, **kwargs: Any) -> None:
        nonlocal has_real_progress, last_synthetic_progress
        tool_hint = kwargs.get("tool_hint", False)
        synthetic_progress = bool(kwargs.get("synthetic_progress"))
        if not tool_hint:
            existing_content = clean_message_content(content_state.get("content") or "").strip()
            if synthetic_progress:
                if has_real_progress:
                    return
                cleaned_synthetic = clean_message_content(content or "").strip()
                if not cleaned_synthetic or cleaned_synthetic == last_synthetic_progress:
                    return
                last_synthetic_progress = cleaned_synthetic
                if not existing_content:
                    content_state["content"] = content
            else:
                has_real_progress = True
                content_state["content"] = content
        await emit("progress", content=content, tool_hint=tool_hint, synthetic_progress=synthetic_progress)

    async def emit_synthetic_progress(message: str) -> None:
        if not enable_synthetic_progress:
            return
        await on_progress(message, synthetic_progress=True)

    async def on_tool_start(tool_name: str, arguments: dict) -> None:
        if tool_name == "message" and arguments and on_message_tool_content:
            content = arguments.get("content")
            if content:
                on_message_tool_content(content)
        if tool_name == "message" and arguments and on_message_tool_dispatch:
            on_message_tool_dispatch(dict(arguments))
        label = str(tool_name or "").strip()
        if label:
            await emit_synthetic_progress(f"{agent_name} 正在调用 {label}...")
        await emit("tool_start", tool_name=tool_name, arguments=arguments)

    async def on_tool_result(tool_name: str, result: str, execution_time: float) -> None:
        label = str(tool_name or "").strip()
        if label:
            await emit_synthetic_progress(f"{agent_name} 已拿到 {label} 结果，继续整理中...")
        await emit(
            "tool_result",
            tool_name=tool_name,
            result=result,
            execution_time=execution_time,
        )

    async def on_status(message: str) -> None:
        await emit("status", message=message)

    async def on_thinking(content: str) -> None:
        await emit("thinking")

    async def on_step_start(step_id: str, step_type: str, title: str) -> None:
        new_step = {
            "id": step_id,
            "type": step_type,
            "title": title,
            "status": "running",
            "timestamp": datetime.now().isoformat(),
        }
        execution_steps.append(new_step)
        if on_step_start_hook:
            on_step_start_hook(new_step)
        if step_type == "thinking":
            await emit_synthetic_progress(f"{agent_name} 正在分析任务与约束...")
        elif step_type == "response":
            await emit_synthetic_progress(f"{agent_name} 正在整理回复...")
        await emit("step_start", step_id=step_id, step_type=step_type, title=title)

    async def on_step_complete(step_id: str, status: str, details: dict) -> None:
        safe_details = sanitize_execution_step_details(
            next((step.get("type") for step in execution_steps if step.get("id") == step_id), ""),
            details,
        )
        step_type = next((step.get("type") for step in execution_steps if step.get("id") == step_id), "")
        for step in execution_steps:
            if step["id"] == step_id:
                step["status"] = status
                step["details"] = safe_details
                break
        if step_type == "thinking" and status not in {"error", "failed"}:
            await emit_synthetic_progress(f"{agent_name} 正在收束思路，准备给出结论...")
        await emit("step_complete", step_id=step_id, status=status, details=safe_details)

    async def on_plan_created(plan: dict) -> None:
        await emit("plan_created", plan=plan)

    async def on_plan_generating() -> None:
        await emit("plan_generating")

    async def on_plan_progress(step_name: str, step_type: str, content: str | None) -> None:
        await emit("plan_progress", step_name=step_name, step_type=step_type, content=content)

    async def on_plan_skipped() -> None:
        await emit("plan_skipped")

    return {
        "on_progress": on_progress,
        "on_tool_start": on_tool_start,
        "on_tool_result": on_tool_result,
        "on_status": on_status,
        "on_thinking": on_thinking,
        "on_step_start": on_step_start,
        "on_step_complete": on_step_complete,
        "on_plan_created": on_plan_created,
        "on_plan_generating": on_plan_generating,
        "on_plan_progress": on_plan_progress,
        "on_plan_skipped": on_plan_skipped,
    }


async def _stream_generator(
    request: StreamRequest,
    request_id: str
) -> AsyncGenerator[str, None]:
    """Generate SSE stream for chat response."""
    logger.info(f"[ChatAPI][{request_id}] _stream_generator entered")
    from horbot.agent.manager import get_agent_manager
    agent_manager = get_agent_manager()
    stream_manager = get_stream_manager()

    session_key = request.session_key if request.session_key.startswith("web:") else f"web:{request.session_key}"
    default_agent = agent_manager.get_default_agent()
    agent_id = request.agent_id or (default_agent.id if default_agent else "default")
    heartbeat_interval = 10.0
    turn_id = str(uuid.uuid4())[:8]
    assistant_message_id = str(uuid.uuid4())[:8]

    logger.info(f"[ChatAPI][{request_id}] Starting single chat: session_key={session_key}, agent_id={agent_id}")

    target_kind, target_instance = _resolve_chat_target(agent_id)
    agent_instance = target_instance if target_kind == "internal" else None
    external_agent = target_instance if target_kind == "external" else None
    agent_name = _resolve_chat_target_name(agent_id)

    # Emit an initial event before heavier initialization so the client
    # receives headers promptly and can transition out of "connecting".
    logger.info(f"[ChatAPI][{request_id}] Emitting initial agent_start event")
    yield _sse_event(
        _build_chat_stream_event(
            "agent_start",
            agent_id=agent_id,
            agent_name=agent_name,
            turn_id=turn_id,
            message_id=assistant_message_id,
        )
    )

    if target_kind == "missing":
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    if target_kind == "internal":
        try:
            agent_loop = await get_agent_loop(request.agent_id)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[ChatAPI][{request_id}] Failed to get agent loop: {e}")
            raise HTTPException(status_code=500, detail="初始化对话代理失败，请稍后重试。")
        manager = agent_loop.sessions
    else:
        agent_loop = None
        manager = get_session_manager()

    session = manager.get_or_create(session_key)

    user_message_id = session.add_message(
        "user",
        request.content,
        dedup=True,
        files=request.files if request.files else None,
        file_ids=request.file_ids if request.file_ids else None,
        web_search=request.web_search,
        metadata={
            "turn_id": turn_id,
            "request_id": request_id,
            "conversation_type": "user_to_agent",
        },
    )

    msg = InboundMessage(
        channel="web",
        sender_id="web_user",
        chat_id=request.session_key[4:] if request.session_key.startswith("web:") else request.session_key,
        content=request.content,
        metadata={
            "file_ids": request.file_ids if request.file_ids else None,
            "files": request.files if request.files else None,
            "web_search": request.web_search,
            "turn_id": turn_id,
            "user_message_id": user_message_id,
            "message_id": assistant_message_id,
            "assistant_message_id": assistant_message_id,
            "request_id": request_id,
        },
    )

    if external_agent is not None:
        from horbot.external_agents.runtime import get_external_agent_runtime

        history = _build_external_agent_history(session)
        result = await get_external_agent_runtime().complete(
            external_agent,
            message=msg.content,
            session_key=session_key,
            history=history,
            conversation={
                "type": "dm",
                "target_id": agent_id,
                "target_name": agent_name,
            },
            metadata={
                "request_id": request_id,
                "turn_id": turn_id,
                "user_message_id": user_message_id,
            },
        )
        content = clean_message_content(str(result.get("content") or "").strip())
        if not result.get("ok") and not content:
            yield _sse_event(
                _build_chat_stream_event(
                    "error",
                    content=str(result.get("detail") or "External agent request failed"),
                    agent_id=agent_id,
                    agent_name=agent_name,
                    turn_id=turn_id,
                    message_id=assistant_message_id,
                )
            )
            yield _sse_event({"event": "done"})
            return

        if content:
            yield _sse_event(
                _build_chat_stream_event(
                    "agent_done",
                    content=content,
                    agent_id=agent_id,
                    agent_name=agent_name,
                    turn_id=turn_id,
                    message_id=assistant_message_id,
                )
            )
            yield _sse_event(
                _build_chat_stream_event(
                    "content",
                    content=content,
                    agent_id=agent_id,
                    agent_name=agent_name,
                    turn_id=turn_id,
                    message_id=assistant_message_id,
                )
            )
            session.add_message(
                "assistant",
                content,
                dedup=True,
                message_id=assistant_message_id,
                metadata={
                    "turn_id": turn_id,
                    "request_id": request_id,
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "agent_type": "external",
                    "_external_agent_adapter": result.get("adapter"),
                    "_external_agent_mode": result.get("mode"),
                    "_external_agent_transport": result.get("transport"),
                    "_external_agent_detail": result.get("detail"),
                },
            )
        await manager.async_save(session)
        yield _sse_event({"event": "done"})
        return

    queue: asyncio.Queue = asyncio.Queue()
    final_response = {"content": None}
    execution_steps: list[dict] = []
    content_state = {"content": ""}
    message_tool_dispatch_state: dict[str, Any] = {}
    idle_status_index = 0
    idle_status_messages = [
        f"{agent_name} 正在分析较长上下文...",
        f"{agent_name} 仍在等待模型返回首个结果...",
        f"{agent_name} 正在整理本轮回复结构...",
    ]

    def store_message_tool_content(content: str) -> None:
        content_state["content"] = content

    def store_message_tool_dispatch(arguments: dict[str, Any]) -> None:
        message_tool_dispatch_state.clear()
        message_tool_dispatch_state.update(arguments)

    callbacks = _create_chat_stream_callbacks(
        queue=queue,
        stream_manager=stream_manager,
        request_id=request_id,
        agent_id=agent_id,
        agent_name=agent_name,
        turn_id=turn_id,
        message_id=assistant_message_id,
        execution_steps=execution_steps,
        content_state=content_state,
        on_message_tool_content=store_message_tool_content,
        on_message_tool_dispatch=store_message_tool_dispatch,
        on_step_start_hook=lambda step: logger.info(
            f"[ChatAPI] Added step: id={step['id']}, type={step['type']}, title={step['title']}, total steps: {len(execution_steps)}"
        ),
        enable_synthetic_progress=True,
    )

    async def process_task():
        nonlocal execution_steps
        try:
            response = await agent_loop.process_message(
                msg,
                session_key=session_key,
                **callbacks,
            )
            if response:
                final_response["content"] = response.content
                if response.metadata:
                    final_response["metadata"] = response.metadata
                    memory_sources = response.metadata.get("_memory_sources")
                    memory_recall = response.metadata.get("_memory_recall")
                    if memory_sources:
                        await queue.put(
                            _build_chat_stream_event(
                                "memory_sources",
                                agent_id=agent_id,
                                agent_name=agent_name,
                                turn_id=turn_id,
                                message_id=assistant_message_id,
                                sources=memory_sources,
                                recall=memory_recall,
                            )
                        )
            await queue.put({"event": "done", "execution_steps": execution_steps})
        except asyncio.CancelledError:
            logger.info(f"[ChatAPI][{request_id}] Stream cancelled for session: {session_key}")
            await queue.put({"event": "stopped"})
        except Exception as e:
            logger.exception(f"[ChatAPI][{request_id}] Error processing message for session {session_key}: {e}")
            await queue.put(
                {
                    "event": "error",
                    "content": public_error_message(e),
                }
            )

    task = asyncio.create_task(process_task())
    await stream_manager.register(request_id, task)
    last_heartbeat = time.monotonic()

    try:
        while True:
            if stream_manager.should_stop(request_id):
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                yield _sse_event({"event": "stopped", "content": "Generation stopped by user"})
                break

            try:
                item = await asyncio.wait_for(queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                if task.done():
                    break
                now = time.monotonic()
                if now - last_heartbeat >= heartbeat_interval:
                    yield _sse_event({"event": "heartbeat"})
                    if not content_state["content"] and final_response["content"] is None:
                        yield _sse_event(
                            _build_chat_stream_event(
                                "status",
                                message=idle_status_messages[idle_status_index % len(idle_status_messages)],
                                agent_id=agent_id,
                                agent_name=agent_name,
                                turn_id=turn_id,
                                message_id=assistant_message_id,
                            )
                        )
                        idle_status_index += 1
                    last_heartbeat = now
                continue

            event = item.get("event")
            if event == "done":
                exec_steps = item.get("execution_steps", [])
                exec_steps_to_save = sanitize_execution_steps(exec_steps)
                existing_msg_idx = _find_session_message_index(
                    session,
                    message_id=assistant_message_id,
                    turn_id=turn_id,
                    role="assistant",
                )
                # Check if response has confirmation metadata
                if final_response.get("metadata", {}).get("_confirmation_required"):
                    metadata = final_response["metadata"]
                    # Only save if content is not empty
                    if final_response["content"]:
                        yield _sse_event(
                            _build_chat_stream_event(
                                "confirmation_required",
                                content=final_response["content"],
                                confirmation_id=metadata.get("confirmation_id"),
                                tool_name=metadata.get("tool_name"),
                                tool_arguments=metadata.get("tool_arguments"),
                                agent_id=agent_id,
                                agent_name=agent_name,
                                turn_id=turn_id,
                                message_id=assistant_message_id,
                            )
                        )
                        if existing_msg_idx >= 0:
                            session.messages[existing_msg_idx]["content"] = final_response["content"]
                            session.messages[existing_msg_idx]["execution_steps"] = exec_steps_to_save
                            session.messages[existing_msg_idx].setdefault("metadata", {}).update({
                                "turn_id": turn_id,
                                "request_id": request_id,
                                "agent_id": agent_id,
                                "agent_name": agent_name,
                                **{
                                    key: value for key, value in final_response.get("metadata", {}).items()
                                    if key != "assistant_message_id"
                                },
                            })
                        else:
                            session.add_message(
                                "assistant",
                                final_response["content"],
                                execution_steps=exec_steps_to_save,
                                dedup=True,
                                message_id=assistant_message_id,
                                metadata={
                                    "turn_id": turn_id,
                                    "request_id": request_id,
                                    "agent_id": agent_id,
                                    "agent_name": agent_name,
                                    **{
                                        key: value for key, value in final_response.get("metadata", {}).items()
                                        if key != "assistant_message_id"
                                    },
                                },
                            )
                        await manager.async_save(session)
                        _maybe_materialize_bootstrap_from_session(agent_instance, session)
                        yield _sse_event({"event": "done"})
                elif final_response["content"] or exec_steps_to_save:
                    resolved_content = _resolve_final_agent_display_content(
                        final_response["content"],
                        content_state["content"],
                    )
                    cleaned_content, outbound_files = _normalize_outbound_content_and_files(
                        resolved_content,
                        message_tool_dispatch_state.get("media"),
                    )
                    provider_error = final_response.get("metadata", {}).get("_provider_error")
                    if cleaned_content or outbound_files:
                        yield _sse_event(
                            _build_chat_stream_event(
                                "agent_done",
                                content=cleaned_content,
                                provider_error=provider_error,
                                agent_id=agent_id,
                                agent_name=agent_name,
                                turn_id=turn_id,
                                message_id=assistant_message_id,
                                files=outbound_files or None,
                            )
                        )
                        yield _sse_event(
                            _build_chat_stream_event(
                                "content",
                                content=cleaned_content,
                                provider_error=provider_error,
                                agent_id=agent_id,
                                agent_name=agent_name,
                                turn_id=turn_id,
                                message_id=assistant_message_id,
                                files=outbound_files or None,
                            )
                        )
                    content_to_save = cleaned_content

                    if existing_msg_idx >= 0:
                        if content_to_save:
                            session.messages[existing_msg_idx]["content"] = content_to_save
                        if exec_steps_to_save:
                            session.messages[existing_msg_idx]["execution_steps"] = exec_steps_to_save
                        if outbound_files:
                            session.messages[existing_msg_idx]["files"] = outbound_files
                        msg_meta = session.messages[existing_msg_idx].setdefault("metadata", {})
                        msg_meta["turn_id"] = turn_id
                        msg_meta["request_id"] = request_id
                        msg_meta["agent_id"] = agent_id
                        msg_meta["agent_name"] = agent_name
                        for key, value in final_response.get("metadata", {}).items():
                            if key == "assistant_message_id":
                                continue
                            msg_meta[key] = value
                    else:
                        session.add_message(
                            "assistant",
                            content_to_save,
                            execution_steps=exec_steps_to_save,
                            dedup=True,
                            message_id=assistant_message_id,
                            files=outbound_files or None,
                            metadata={
                                "turn_id": turn_id,
                                "request_id": request_id,
                                "agent_id": agent_id,
                                "agent_name": agent_name,
                                **{
                                    key: value for key, value in final_response.get("metadata", {}).items()
                                    if key != "assistant_message_id"
                                },
                            },
                        )

                    await manager.async_save(session)
                    _maybe_materialize_bootstrap_from_session(agent_instance, session)
                    yield _sse_event({"event": "done"})
                else:
                    await manager.async_save(session)
                    _maybe_materialize_bootstrap_from_session(agent_instance, session)
                    yield _sse_event({"event": "done"})
                break
            elif event == "stopped":
                yield _sse_event({"event": "stopped", "content": "Generation stopped by user"})
                break
            elif event == "error":
                yield _sse_event(
                    _build_chat_stream_event(
                        "error",
                        content=item.get("content", "Unknown error"),
                        agent_id=agent_id,
                        agent_name=agent_name,
                        turn_id=turn_id,
                        message_id=assistant_message_id,
                    )
                )
                break
            else:
                yield _sse_event(item)

    except asyncio.CancelledError:
        logger.info(f"[ChatAPI][{request_id}] Stream cancelled externally")
        yield _sse_event({"event": "stopped", "content": "Generation cancelled"})
    finally:
        logger.info(f"[ChatAPI][{request_id}] Stream completed, cleaning up")
        await stream_manager.cleanup_task(request_id, task)


async def _group_chat_stream_generator(
    request: StreamRequest,
    request_id: str
) -> AsyncGenerator[str, None]:
    """Generate SSE stream for group chat response with multiple agents.

    Implements agent-to-agent conversation architecture:
    - When user @mentions Agent A: Agent A speaks to "用户" (user_to_agent)
    - When Agent A @mentions Agent B: Agent B speaks to Agent A (agent_to_agent)
    - Each agent has its own conversation context and knows who it's talking to
    """
    from horbot.agent.manager import get_agent_manager
    from horbot.workspace.manager import get_workspace_manager
    from horbot.agent.conversation import ConversationContext, ConversationType, build_conversation_context

    agent_manager = get_agent_manager()
    workspace_manager = get_workspace_manager()
    stream_manager = get_stream_manager()

    session_key = request.session_key if request.session_key.startswith("web:") else f"web:{request.session_key}"
    logger.info(f"[ChatAPI][{request_id}] Starting group chat: session_key={session_key}, team_id={request.team_id}")

    team_id = request.team_id
    team_session_manager = None
    try:
        if team_id:
            team_ws = workspace_manager.get_team_workspace(team_id)
            if not team_ws:
                raise HTTPException(status_code=404, detail=f"Team '{team_id}' not found")
            team_sessions_path = Path(team_ws.workspace_path) / "sessions"
            team_sessions_path.mkdir(parents=True, exist_ok=True)
            team_session_manager = SessionManager(workspace=team_sessions_path)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ChatAPI][{request_id}] Failed to initialize team session: {e}")
        raise HTTPException(status_code=500, detail="初始化团队会话失败，请稍后重试。")

    manager = team_session_manager or get_session_manager()
    session = manager.get_or_create(session_key)
    logger.info(f"[ChatAPI][{request_id}] Created session: key={session.key}, manager_type={type(manager).__name__}")

    stream_task = asyncio.current_task()
    if stream_task is not None:
        await stream_manager.register(request_id, stream_task)
    else:
        logger.warning(f"[ChatAPI][{request_id}] No current asyncio task available for stream registration")

    session.add_message(
        "user",
        request.content,
        dedup=True,
        files=request.files if request.files else None,
        file_ids=request.file_ids if request.file_ids else None,
        web_search=request.web_search,
        metadata={
            "request_id": request_id,
            "conversation_type": "user_to_team",
            "team_id": request.team_id,
            "mentioned_agents": request.mentioned_agents,
        },
    )

    if is_stop_discussion_message(request.content):
        logger.info(f"[ChatAPI][{request_id}] User requested to stop discussion")
        yield _sse_event({"event": "discussion_stopped", "content": "讨论已停止。你可以继续发送消息开始新的对话。"})
        return

    agents_to_respond: List[str] = []

    has_mentioned_agents = hasattr(request, 'mentioned_agents') and request.mentioned_agents is not None

    logger.info(f"[ChatAPI][{request_id}] Group chat request: mentioned_agents={request.mentioned_agents}, team_id={request.team_id}")

    available_agents = _get_group_chat_available_agent_ids(request.team_id)

    parsed_mentions = parse_agent_mentions(request.content, available_agents)
    logger.info(f"[ChatAPI][{request_id}] Parsed mentions from content: {parsed_mentions}")

    if has_mentioned_agents and len(request.mentioned_agents) > 0:
        agents_to_respond = request.mentioned_agents.copy()
        for agent_id in parsed_mentions:
            if agent_id not in agents_to_respond:
                agents_to_respond.append(agent_id)
        logger.info(f"[ChatAPI][{request_id}] Using mentioned agents (combined with parsed): {agents_to_respond}")
    elif parsed_mentions:
        agents_to_respond = parsed_mentions.copy()
        logger.info(f"[ChatAPI][{request_id}] Using parsed mentions: {agents_to_respond}")
    elif request.team_id:
        team_default_agent_id = _resolve_team_default_agent_id(request.team_id)
        if team_default_agent_id:
            agents_to_respond = [team_default_agent_id]
            logger.info(f"[ChatAPI][{request_id}] Team mode without mentions, using team lead/default: {agents_to_respond}")
        elif available_agents:
            agents_to_respond = [available_agents[0]]
            logger.info(f"[ChatAPI][{request_id}] Team mode without mentions, using first agent: {agents_to_respond}")
    else:
        default_agent = agent_manager.get_default_agent()
        if default_agent:
            agents_to_respond = [default_agent.id]
            logger.info(f"[ChatAPI][{request_id}] Using default agent: {agents_to_respond}")

    if not agents_to_respond:
        if available_agents:
            agents_to_respond = [available_agents[0]]

    queue: asyncio.Queue = asyncio.Queue()
    all_responses: List[dict] = []

    originally_mentioned = set(agents_to_respond.copy())
    return_to_user_agents: set[str] = set()

    conversation_contexts: Dict[str, ConversationContext] = {}
    for agent_id in originally_mentioned:
        agent_name = _resolve_chat_target_name(agent_id)
        kickoff_trigger_message = _build_team_baton_trigger_message(
            request.content,
            mode="kickoff",
            target_name=agent_name,
        )
        conversation_contexts[agent_id] = build_conversation_context(
            conversation_type=ConversationType.USER_TO_AGENT,
            source_id="user",
            source_name="用户",
            target_id=agent_id,
            target_name=agent_name,
            trigger_message=kickoff_trigger_message,
        )
        logger.info(f"[ChatAPI][{request_id}] Created user_to_agent context for {agent_name}")

    async def process_agent_response(
        agent_id: str,
        agent_index: int,
        conversation_ctx: ConversationContext
    ):
        """Process response from a single agent with conversation context."""
        try:
            target_kind, target_instance = _resolve_chat_target(agent_id)
            agent_loop = None
            agent_name = _resolve_chat_target_name(agent_id)
            turn_id = str(uuid.uuid4())[:8]
            assistant_message_id = str(uuid.uuid4())[:8]

            execution_steps: list[dict] = []
            content_state = {"content": ""}
            message_tool_dispatch_state: dict[str, Any] = {}

            def store_message_tool_content(content: str) -> None:
                content_state["content"] = content
                logger.info(f"[ChatAPI][{request_id}] Extracted content from message tool (on_tool_start): {content[:100]}...")

            def store_message_tool_dispatch(arguments: dict[str, Any]) -> None:
                message_tool_dispatch_state.clear()
                message_tool_dispatch_state.update(arguments)
                logger.info(
                    "[ChatAPI][{}] Captured message tool dispatch for {}: channel={}, chat_id={}, team_id={}, mentioned_agents={}, trigger_group_chat={}",
                    request_id,
                    agent_id,
                    arguments.get("channel"),
                    arguments.get("chat_id"),
                    arguments.get("team_id"),
                    arguments.get("mentioned_agents"),
                    arguments.get("trigger_group_chat"),
                )

            await _queue_chat_stream_event(
                queue,
                "agent_start",
                agent_id=agent_id,
                agent_name=agent_name,
                agent_index=agent_index,
                turn_id=turn_id,
                message_id=assistant_message_id,
            )

            speaking_to = conversation_ctx.get_speaking_to()
            conv_type = conversation_ctx.conversation_type.value

            logger.info(f"[ChatAPI][{request_id}] Agent {agent_name} speaking_to={speaking_to}, conversation_type={conv_type}")

            if conversation_ctx.trigger_message:
                message_content = conversation_ctx.trigger_message.strip()
            elif conversation_ctx.conversation_type == ConversationType.AGENT_TO_AGENT:
                message_content = (conversation_ctx.trigger_message or request.content).strip()
                logger.info(
                    f"[ChatAPI][{request_id}] Agent-to-agent message for {agent_name}: "
                    f"source={conversation_ctx.source_name}, content={message_content[:100]}..."
                )
            else:
                message_content = request.content

            msg = InboundMessage(
                channel="web",
                sender_id="web_user",
                chat_id=request.session_key[4:] if request.session_key.startswith("web:") else request.session_key,
                content=message_content,
                metadata={
                    "file_ids": request.file_ids if request.file_ids else None,
                    "files": request.files if request.files else None,
                    "web_search": request.web_search,
                    "group_chat": True,
                    "mentioned_agents": request.mentioned_agents,
                    "conversation_context": conversation_ctx.to_dict(),
                    "turn_id": turn_id,
                    "assistant_message_id": assistant_message_id,
                    "request_id": request_id,
                },
            )
            if target_kind == "external":
                from horbot.external_agents.runtime import get_external_agent_runtime

                result = await get_external_agent_runtime().complete(
                    target_instance,
                    message=msg.content,
                    session_key=session_key,
                    history=_build_external_agent_history(session),
                    conversation={
                        "type": conv_type,
                        "target_id": agent_id,
                        "target_name": agent_name,
                        "source_id": conversation_ctx.source,
                        "source_name": conversation_ctx.source_name,
                    },
                    metadata={
                        "request_id": request_id,
                        "turn_id": turn_id,
                        "group_chat": True,
                    },
                )
                response = None
                response_content = str(result.get("content") or "").strip()
                final_content = clean_message_content(response_content)
            else:
                agent_loop = await get_agent_loop_with_session_manager(agent_id, team_session_manager)
                callbacks = _create_chat_stream_callbacks(
                    queue=queue,
                    stream_manager=stream_manager,
                    request_id=request_id,
                    agent_id=agent_id,
                    agent_name=agent_name,
                    turn_id=turn_id,
                    message_id=assistant_message_id,
                    execution_steps=execution_steps,
                    content_state=content_state,
                    on_message_tool_content=store_message_tool_content,
                    on_message_tool_dispatch=store_message_tool_dispatch,
                    enable_synthetic_progress=bool(request.group_chat),
                )

                response = await agent_loop.process_message(
                    msg,
                    session_key=session_key,
                    **callbacks,
                    speaking_to=speaking_to,
                    conversation_type=conv_type,
                )

                response_content = response.content if response else None
                final_content = _resolve_final_agent_display_content(
                    response_content,
                    content_state["content"],
                )

            logger.info(f"[ChatAPI][{request_id}] Agent {agent_id} response: response={response is not None}, response_content={response_content[:50] if response_content else None}, streamed_content={content_state['content'][:50] if content_state['content'] else None}, final_content={final_content[:50] if final_content else None}")

            relay_targets: list[str] = []
            if team_id and message_tool_dispatch_state:
                target_chat_id = str(message_tool_dispatch_state.get("chat_id") or "").strip()
                target_session_key = _normalize_web_session_key(target_chat_id) if target_chat_id else ""
                target_team_id = (
                    str(message_tool_dispatch_state.get("team_id") or "").strip()
                    or _extract_team_id_from_chat_id(target_session_key)
                )
                if target_session_key == session_key and target_team_id == team_id:
                    relay_targets = _resolve_team_dispatch_targets(
                        team_id=team_id,
                        source_agent_id=agent_id,
                        content=str(message_tool_dispatch_state.get("content") or final_content or ""),
                        explicit_mentions=list(message_tool_dispatch_state.get("mentioned_agents") or []),
                        trigger_group_chat=bool(message_tool_dispatch_state.get("trigger_group_chat")),
                    )
                    logger.info(
                        "[ChatAPI][{}] Resolved inline relay targets for {}: {}",
                        request_id,
                        agent_id,
                        relay_targets,
                    )

            # Only send agent_done event if there's actual content to display
            normalized_content, outbound_files = _normalize_outbound_content_and_files(
                final_content,
                message_tool_dispatch_state.get("media"),
            )

            if normalized_content or outbound_files:
                memory_sources = []
                memory_recall = {}
                if response and response.metadata:
                    memory_sources = list(response.metadata.get("_memory_sources") or [])
                    memory_recall = dict(response.metadata.get("_memory_recall") or {})
                all_responses.append({
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "content": normalized_content,
                    "files": outbound_files or None,
                    "execution_steps": sanitize_execution_steps(execution_steps),
                    "memory_sources": memory_sources,
                    "memory_recall": memory_recall,
                })

                await _queue_chat_stream_event(
                    queue,
                    "agent_done",
                    agent_id=agent_id,
                    agent_name=agent_name,
                    agent_index=agent_index,
                    content=normalized_content,
                    turn_id=turn_id,
                    message_id=assistant_message_id,
                    files=outbound_files or None,
                    execution_steps=sanitize_execution_steps(execution_steps),
                    memory_sources=memory_sources,
                    memory_recall=memory_recall,
                    relay_targets=relay_targets,
                )
            else:
                logger.info(f"[ChatAPI][{request_id}] Agent {agent_id} completed with empty content, skipping agent_done event")

        except asyncio.CancelledError:
            await _queue_chat_stream_event(
                queue,
                "agent_stopped",
                agent_id=agent_id,
                agent_name=_resolve_chat_target_name(agent_id),
                turn_id=turn_id,
                message_id=assistant_message_id,
            )
        except Exception as e:
            import traceback
            logger.error(f"[ERROR] agent_error: agent_id={agent_id}, error={str(e)}, traceback={traceback.format_exc()}")
            safe_error = public_error_message(e)
            await _queue_chat_stream_event(
                queue,
                "agent_error",
                agent_id=agent_id,
                agent_name=_resolve_chat_target_name(agent_id),
                turn_id=turn_id,
                message_id=assistant_message_id,
                error=safe_error,
                content=safe_error,
            )
    completed_agents = 0
    total_agents = len(agents_to_respond)
    processed_agents = set()
    current_idx = 0
    mention_triggered_agents = set()
    active_tasks: Dict[str, asyncio.Task] = {}

    last_speaking_agent: Dict[str, str] = {}

    try:
        while current_idx < len(agents_to_respond):
            if stream_manager.should_stop(request_id):
                yield _sse_event({"event": "stopped", "content": "Generation stopped by user"})
                break

            agent_id = agents_to_respond[current_idx]

            if agent_id in processed_agents and agent_id not in mention_triggered_agents:
                current_idx += 1
                continue

            if agent_id in mention_triggered_agents:
                mention_triggered_agents.discard(agent_id)

            processed_agents.add(agent_id)

            if agent_id in conversation_contexts:
                conv_ctx = conversation_contexts[agent_id]
            else:
                agent_name = _resolve_chat_target_name(agent_id)
                source_id = last_speaking_agent.get(agent_id, "user")
                if source_id == "user":
                    source_name = "用户"
                else:
                    source_name = _resolve_chat_target_name(source_id)

                conv_ctx = build_conversation_context(
                    conversation_type=ConversationType.AGENT_TO_AGENT,
                    source_id=source_id,
                    source_name=source_name,
                    target_id=agent_id,
                    target_name=agent_name,
                    trigger_message=_build_team_baton_trigger_message(
                        request.content,
                        mode="kickoff" if source_id == "user" else "relay",
                        source_name=None if source_id == "user" else source_name,
                        target_name=agent_name,
                    ),
                )
                conversation_contexts[agent_id] = conv_ctx
                logger.info(f"[ConversationContext] Created agent_to_agent context: {source_name} -> {agent_name}")

            task = asyncio.create_task(process_agent_response(agent_id, current_idx, conv_ctx))
            active_tasks[agent_id] = task

            done_task = None
            while not done_task:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=0.3)
                    event = item.get("event")

                    if event == "agent_done":
                        resp = {
                            "agent_id": item.get("agent_id"),
                            "agent_name": item.get("agent_name"),
                            "content": item.get("content"),
                            "files": item.get("files"),
                            "turn_id": item.get("turn_id"),
                            "message_id": item.get("message_id"),
                            "execution_steps": sanitize_execution_steps(item.get("execution_steps", [])),
                            "memory_sources": item.get("memory_sources", []),
                            "memory_recall": item.get("memory_recall", {}),
                        }
                        if resp["content"] or resp["files"]:
                            content_to_save = clean_message_content(resp["content"])
                            resp_ctx = conversation_contexts.get(resp["agent_id"])
                            metadata = {
                                "agent_id": resp["agent_id"],
                                "agent_name": resp["agent_name"]
                            }
                            if resp_ctx:
                                metadata["source"] = resp_ctx.source
                                metadata["source_name"] = resp_ctx.source_name
                                metadata["target"] = resp_ctx.target
                                metadata["target_name"] = resp_ctx.target_name
                                metadata["conversation_type"] = resp_ctx.conversation_type.value
                            if resp["turn_id"]:
                                metadata["turn_id"] = resp["turn_id"]
                            metadata["request_id"] = request_id
                            if resp["memory_sources"]:
                                metadata["_memory_sources"] = resp["memory_sources"]
                            if resp["memory_recall"]:
                                metadata["_memory_recall"] = resp["memory_recall"]

                            logger.info(f"[ChatAPI][{request_id}] Adding assistant message with metadata: {metadata}")
                            existing_msg_idx = _find_session_message_index(
                                session,
                                message_id=resp["message_id"],
                                turn_id=resp["turn_id"],
                                role="assistant",
                            )
                            if existing_msg_idx >= 0:
                                session.messages[existing_msg_idx]["content"] = content_to_save
                                if resp["execution_steps"]:
                                    session.messages[existing_msg_idx]["execution_steps"] = resp["execution_steps"]
                                if resp["files"]:
                                    session.messages[existing_msg_idx]["files"] = resp["files"]
                                session.messages[existing_msg_idx].setdefault("metadata", {}).update(metadata)
                            else:
                                session.add_message(
                                    "assistant",
                                    content_to_save,
                                    dedup=True,
                                    message_id=resp["message_id"],
                                    files=resp["files"],
                                    execution_steps=resp["execution_steps"],
                                    metadata=metadata,
                                )
                            logger.info(f"[ChatAPI][{request_id}] Message saved. Session messages count: {len(session.messages)}")
                        all_responses.append(resp)
                        sanitized_item = dict(item)
                        sanitized_item["execution_steps"] = resp["execution_steps"]
                        yield _sse_event(sanitized_item)

                        relay_targets = list(item.get("relay_targets") or [])

                        if resp["content"] or relay_targets:
                            logger.info(f"[ChatAPI][{request_id}] Checking relay targets from {resp['agent_id']}: content_preview={resp['content'][:100] if resp['content'] else None}, tool_targets={relay_targets}")
                            ordered_candidates: list[str] = []
                            allow_plaintext_mentions = resp["agent_id"] not in return_to_user_agents
                            mentioned_agents = (
                                parse_agent_mentions(resp["content"], available_agents)
                                if resp["content"] and allow_plaintext_mentions
                                else []
                            )
                            if not allow_plaintext_mentions and resp["content"]:
                                logger.info(
                                    "[ChatAPI][{}] Ignoring plain-text mentions for user-summary return turn: agent={}",
                                    request_id,
                                    resp["agent_id"],
                                )
                            logger.info(f"[ChatAPI][{request_id}] Found mentioned agents: {mentioned_agents}")
                            if resp["agent_id"] in return_to_user_agents:
                                return_to_user_agents.discard(resp["agent_id"])
                            for candidate in relay_targets + mentioned_agents:
                                if candidate not in ordered_candidates:
                                    ordered_candidates.append(candidate)
                            resp_ctx = conversation_contexts.get(resp["agent_id"])
                            originator_return_mode = _get_originator_return_mode(resp_ctx)
                            should_auto_return_to_source = (
                                not ordered_candidates
                                and resp_ctx is not None
                                and resp_ctx.conversation_type == ConversationType.AGENT_TO_AGENT
                                and resp_ctx.source != "user"
                                and resp_ctx.source in originally_mentioned
                                and resp["agent_id"] not in originally_mentioned
                                and originator_return_mode in {"summary", "continue"}
                            )
                            if should_auto_return_to_source:
                                ordered_candidates.append(resp_ctx.source)
                                logger.info(
                                    "[ChatAPI][{}] Auto-returning relay from {} back to originator {} with mode={}",
                                    request_id,
                                    resp["agent_id"],
                                    resp_ctx.source,
                                    originator_return_mode,
                                )
                            new_agents_to_respond = [a for a in ordered_candidates if a != resp['agent_id'] and a not in active_tasks]
                            logger.info(f"[ChatAPI][{request_id}] New agents to respond (after filtering): {new_agents_to_respond}")

                            if new_agents_to_respond:
                                logger.info(f"[ChatAPI][{request_id}] Agent {resp['agent_id']} mentioned agents: {new_agents_to_respond}")
                                queued_future_agents = set(agents_to_respond[current_idx + 1:])
                                handoff_event_meta: dict[str, dict[str, Any]] = {}
                                for a in new_agents_to_respond:
                                    pending_again = a in processed_agents and a not in queued_future_agents
                                    pending_unprocessed = a in queued_future_agents and a not in processed_agents

                                    if pending_unprocessed:
                                        logger.info(
                                            "[ChatAPI][{}] Preserving pending context for {} while already queued; source mention from {} is ignored",
                                            request_id,
                                            a,
                                            resp["agent_id"],
                                        )
                                        continue

                                    mention_triggered_agents.add(a)
                                    last_speaking_agent[a] = resp["agent_id"]

                                    if a not in agents_to_respond or pending_again:
                                        agents_to_respond.append(a)
                                        logger.info(
                                            f"[ChatAPI][{request_id}] Added {a} to agents_to_respond, "
                                            f"requeued={pending_again}, new total: {len(agents_to_respond)}"
                                        )

                                    target_name = _resolve_chat_target_name(a)
                                    return_to_user_summary = _should_return_to_user_summary_turn(
                                        candidate_agent_id=a,
                                        response_agent_id=resp["agent_id"],
                                        response_context=resp_ctx,
                                        originally_mentioned=originally_mentioned,
                                    )
                                    if return_to_user_summary:
                                        handoff_preview = _build_relay_handoff_preview(request.content)
                                        return_to_user_agents.add(a)
                                        new_conv_ctx = build_conversation_context(
                                            conversation_type=ConversationType.USER_TO_AGENT,
                                            source_id="user",
                                            source_name="用户",
                                            target_id=a,
                                            target_name=target_name,
                                            trigger_message=_build_user_summary_trigger_message(request.content),
                                        )
                                        logger.info(
                                            "[ChatAPI][{}] Re-entering user-summary turn for {} after relay from {}",
                                            request_id,
                                            a,
                                            resp["agent_id"],
                                        )
                                        handoff_mode = "summary"
                                    else:
                                        handoff_payload = (
                                            extract_agent_mention_payload(
                                                resp["content"],
                                                target_agent_id=a,
                                                target_agent_name=target_name,
                                            )
                                            or resp["content"]
                                        )
                                        handoff_preview = _build_relay_handoff_preview(handoff_payload)
                                        relay_trigger_message = _build_team_baton_trigger_message(
                                            handoff_payload,
                                            mode="relay",
                                            source_name=resp["agent_name"],
                                            target_name=target_name,
                                        )
                                        new_conv_ctx = build_conversation_context(
                                            conversation_type=ConversationType.AGENT_TO_AGENT,
                                            source_id=resp["agent_id"],
                                            source_name=resp["agent_name"],
                                            target_id=a,
                                            target_name=target_name,
                                            trigger_message=relay_trigger_message,
                                        )
                                        handoff_mode = (
                                            "continue"
                                            if (
                                                should_auto_return_to_source
                                                and resp_ctx is not None
                                                and a == resp_ctx.source
                                                and originator_return_mode == "continue"
                                            )
                                            else "relay"
                                        )
                                    conversation_contexts[a] = new_conv_ctx
                                    handoff_event_meta[a] = {
                                        "mentioned_by_name": resp["agent_name"],
                                        "handoff_mode": handoff_mode,
                                        "handoff_preview": handoff_preview,
                                    }
                                    logger.info(
                                        "[ChatAPI][{}] Created {} context: {} -> {}",
                                        request_id,
                                        new_conv_ctx.conversation_type.value,
                                        resp["agent_name"],
                                        target_name,
                                    )

                                total_agents = len(agents_to_respond)

                                for new_agent_id in new_agents_to_respond:
                                    yield _sse_event(
                                        _build_chat_stream_event(
                                            "agent_mentioned",
                                            agent_id=new_agent_id,
                                            agent_name=_resolve_chat_target_name(new_agent_id),
                                            mentioned_by=resp["agent_id"],
                                            **handoff_event_meta.get(new_agent_id, {}),
                                        )
                                    )

                        done_task = active_tasks.get(agent_id)
                    elif event in ("agent_stopped", "agent_error"):
                        yield _sse_event(item)
                        done_task = active_tasks.get(agent_id)
                    else:
                        yield _sse_event(item)

                except asyncio.TimeoutError:
                    if task.done():
                        done_task = task
                        break
                    continue

            if done_task:
                await done_task
                completed_agents += 1
                active_tasks.pop(agent_id, None)

            current_idx += 1  # Move to next agent

        await manager.async_save(session)
        logger.info(f"[ChatAPI][{request_id}] Session saved: key={session.key}, messages_count={len(session.messages)}")
        yield _sse_event({"event": "done", "total_agents": total_agents})

    except asyncio.CancelledError:
        logger.info(f"[ChatAPI][{request_id}] Group chat cancelled externally")
        yield _sse_event({"event": "stopped", "content": "Generation cancelled"})
    except GeneratorExit:
        pass
    finally:
        logger.info(f"[ChatAPI][{request_id}] Group chat completed, cleaning up {len(active_tasks)} active tasks")
        for agent_id, task in active_tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        await stream_manager.unregister(request_id)


def _validate_chat_request(request: StreamRequest) -> None:
    """Validate chat request parameters.

    Raises HTTPException if validation fails.
    """
    if not request.content or not request.content.strip():
        raise HTTPException(status_code=400, detail="Content is required")

    input_guard = inspect_user_input(request.content)
    if input_guard.blocked:
        raise HTTPException(
            status_code=400,
            detail=f"Unsafe user intent detected: {', '.join(input_guard.reasons[:2])}",
        )

    if request.agent_id:
        target_kind, target = _resolve_chat_target(request.agent_id)
        if target is None:
            raise HTTPException(status_code=404, detail=f"Agent '{request.agent_id}' not found")
        if target_kind == "external" and not bool(target.config.dm_enabled):
            raise HTTPException(status_code=400, detail=f"External agent '{request.agent_id}' does not allow direct chat")

    available_group_agents = _get_group_chat_available_agent_ids(request.team_id) if request.group_chat else []
    parsed_group_mentions = parse_agent_mentions(request.content, available_group_agents) if available_group_agents else []

    if request.group_chat and (request.mentioned_agents or parsed_group_mentions):
        team_members = set(_get_team_member_agent_ids(request.team_id)) if request.team_id else set()
        team_external_agents = set(_get_team_external_agent_ids(request.team_id)) if request.team_id else set()
        for agent_id in list(dict.fromkeys([*request.mentioned_agents, *parsed_group_mentions])):
            target_kind, target = _resolve_chat_target(agent_id)
            if target is None:
                raise HTTPException(status_code=404, detail=f"Mentioned agent '{agent_id}' not found")
            if request.team_id:
                if target_kind == "internal" and agent_id not in team_members:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Mentioned agent '{agent_id}' is not a member of team '{request.team_id}'",
                    )
                if target_kind == "external" and agent_id not in team_external_agents:
                    raise HTTPException(
                        status_code=400,
                        detail=f"External agent '{agent_id}' is not enabled for team '{request.team_id}'",
                    )

    requires_internal_provider = True
    if request.group_chat:
        resolved_mentions = list(dict.fromkeys([*request.mentioned_agents, *parsed_group_mentions]))
        if resolved_mentions:
            requires_internal_provider = any(_resolve_chat_target(agent_id)[0] == "internal" for agent_id in resolved_mentions)
    elif request.agent_id:
        requires_internal_provider = _resolve_chat_target(request.agent_id)[0] == "internal"

    if requires_internal_provider:
        config = get_cached_config()
        provider_config = config.get_provider() if config else None
        if not provider_config or not provider_config.api_key:
            raise HTTPException(status_code=500, detail="Provider not configured. Please set up API key in settings.")


@router.post("/chat/stream")
async def stream_chat_message(request: StreamRequest):
    """Send chat message and get streaming response via SSE."""
    _validate_chat_request(request)

    request_id = str(uuid.uuid4())
    logger.info(f"[ChatAPI] Request started: request_id={request_id}, session_key={request.session_key}, agent_id={request.agent_id}, group_chat={request.group_chat}")

    stream_manager = get_stream_manager()

    if request.group_chat:
        return StreamingResponse(
            _group_chat_stream_generator(request, request_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Request-Id": request_id,
            }
        )

    return StreamingResponse(
        _stream_generator(request, request_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Request-Id": request_id,
        }
    )


# ============ Multi-Agent API ============

def _resolve_team_default_agent_id(team_id: str | None) -> str | None:
    if not team_id:
        return None

    from horbot.team.manager import get_team_manager

    team_manager = get_team_manager()
    team = team_manager.get_team(team_id)
    if not team:
        return None

    ordered_members = team.get_ordered_member_ids()
    return ordered_members[0] if ordered_members else None
