"""API routes."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse
from typing import List, Dict, Any, AsyncGenerator, Optional, Callable
from datetime import datetime
import asyncio
import hashlib
import json
import uuid
import os
import mimetypes
import shutil
import threading
import time
from loguru import logger

from horbot.config.loader import get_cached_config, save_config
from horbot.config.normalizer import (
    remove_agent_references,
    remove_team_references,
    set_agent_team_memberships,
    set_team_members,
)
from horbot.config.schema import ChannelEndpointConfig, Config, ModelsConfig
from horbot.config.validator import validate_config
from horbot.agent.loop import AgentLoop
from horbot.bus.queue import MessageBus
from horbot.bus.events import InboundMessage, OutboundMessage
from horbot.agent.tools.permission import PermissionManager, PermissionLevel, PROFILES, TOOL_GROUPS
from horbot.agent.tools.message import MessageTool
from horbot.providers.base import LLMProvider
from horbot.providers.registry import create_provider
from horbot.cron.service import CronService
from horbot.cron.types import CronSchedule
from horbot.session.manager import SessionManager
from horbot.web.security import (
    mask_secret,
    redact_sensitive_data,
    sanitize_config_for_client,
    sanitize_execution_step_details,
    sanitize_execution_steps,
    sanitize_mcp_server_for_client,
)
from horbot.utils.error_messages import public_error_message
from horbot.channels.endpoints import (
    CHANNEL_TYPE_MODELS,
    build_legacy_endpoint,
    build_custom_endpoint,
    build_runtime_channel_config,
    find_channel_endpoint,
    get_channel_catalog,
    legacy_endpoint_id,
    list_channel_endpoints,
)
from horbot.channels.diagnostics import test_channel_connection
from horbot.channels.telemetry import get_channel_events, get_channel_summary, record_channel_event
from horbot.utils.bootstrap import (
    bootstrap_file_needs_setup,
    bootstrap_content_needs_setup,
    build_bootstrap_summary,
    clean_summary_items,
    materialize_bootstrap_from_messages,
    normalize_bootstrap_file_content,
    parse_markdown_sections,
    normalize_markdown_items,
    reconcile_bootstrap_files,
    remove_setup_pending_marker,
    truncate_summary_items,
    upsert_markdown_section,
)
from pydantic import BaseModel, Field
from pathlib import Path

router = APIRouter()

_hot_reload_test_counter = 0

_cron_service = None
_session_manager = None
_api_started_at = time.time()


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
    session = session_manager.get_or_create(session_key)
    source_name = source_agent_name or source_agent_id or "Agent"

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
        conversation_ctx = build_conversation_context(
            conversation_type=ConversationType.AGENT_TO_AGENT,
            source_id=source_agent_id or "agent_dispatch",
            source_name=source_name,
            target_id=target_agent_id,
            target_name=target_agent.name,
            trigger_message=trigger_message,
        )
        target_loop = await get_agent_loop_with_session_manager(target_agent_id, session_manager)
        response = await target_loop.process_message(
            InboundMessage(
                channel="web",
                sender_id="web_user",
                chat_id=session_key[4:] if session_key.startswith("web:") else session_key,
                content=trigger_message,
                metadata={
                    "group_chat": True,
                    "team_id": team_id,
                    "conversation_context": conversation_ctx.to_dict(),
                    "mentioned_agents": target_agent_ids,
                    "request_id": str(uuid.uuid4()),
                    "triggered_via": "message_tool_dispatch",
                },
            ),
            session_key=session_key,
            speaking_to=source_name,
            conversation_type=conversation_ctx.conversation_type.value,
        )
        final_content = clean_message_content(response.content if response else "")
        if not final_content:
            logger.info(
                "[TeamDispatch] followup produced no direct assistant content: team={}, source={}, target={}",
                team_id,
                source_agent_id,
                target_agent_id,
            )
            continue

        assistant_message_id = str(uuid.uuid4())[:8]
        memory_sources = list((response.metadata or {}).get("_memory_sources") or []) if response else []
        memory_recall = dict((response.metadata or {}).get("_memory_recall") or {}) if response else {}
        session.add_message(
            "assistant",
            final_content,
            dedup=True,
            message_id=assistant_message_id,
            metadata={
                "agent_id": target_agent_id,
                "agent_name": target_agent.name,
                "team_id": team_id,
                "source": source_agent_id or "agent_dispatch",
                "source_name": source_name,
                "target": target_agent_id,
                "target_name": target_agent.name,
                "conversation_type": conversation_ctx.conversation_type.value,
                "dispatch_origin": "message_tool_followup",
                **({"_memory_sources": memory_sources} if memory_sources else {}),
                **({"_memory_recall": memory_recall} if memory_recall else {}),
            },
        )
        await session_manager.async_save(session)
        await broadcast_to_session(
            session_key,
            _build_chat_stream_event(
                "agent_done",
                agent_id=target_agent_id,
                agent_name=target_agent.name,
                content=final_content,
                message_id=assistant_message_id,
                memory_sources=memory_sources,
                memory_recall=memory_recall,
            ),
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
    message_id = session.add_message(
        "assistant",
        clean_message_content(msg.content),
        dedup=True,
        message_id=str(uuid.uuid4())[:8],
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
            content=clean_message_content(msg.content),
            message_id=message_id,
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
            if target_team_id or target_session_key != current_session_key:
                msg.metadata.setdefault("outbound_via", "internal_web_dispatch")
                await _dispatch_internal_web_outbound(agent_loop, msg)
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


def parse_agent_mentions(content: str, available_agents: List[str]) -> List[str]:
    """Parse @mentions from content and return list of mentioned agent IDs.
    
    Supports agent names with spaces (e.g., "@小项 🐎" matches agent named "小项 🐎").
    Priority: exact name match > exact ID match > partial name match
    """
    import re
    from horbot.agent.manager import get_agent_manager
    
    agent_manager = get_agent_manager()
    mentioned = []
    
    # Build a list of agent identities used for mention matching.
    agents_info = []
    for agent_id in available_agents:
        agent = agent_manager.get_agent(agent_id)
        if agent:
            agents_info.append(
                {
                    "id": agent_id,
                    "name": agent.name,
                    "normalized_id": _normalize_agent_mention_token(agent_id),
                    "normalized_name": _normalize_agent_mention_token(agent.name),
                }
            )
    
    # Sort by name length (longest first) to match longer names first
    # This ensures "@小项 🐎" matches "小项 🐎" not just "小项"
    agents_info.sort(key=lambda x: len(x["name"]), reverse=True)
    
    # Track which positions in content have been matched
    matched_positions = set()
    
    # First pass: try to match full agent names (including spaces)
    for agent_info in agents_info:
        agent_id = agent_info["id"]
        agent_name = agent_info["name"]
        # Create pattern to match @agent_name
        # The name can be followed by space, punctuation, or end of string
        pattern = re.escape(f"@{agent_name}")
        for match in re.finditer(pattern, content):
            start, end = match.start(), match.end()
            # Check if this position hasn't been matched yet
            # and the character after match is space, punctuation, or end of string
            if start not in matched_positions:
                # Verify it's a valid mention (not part of a longer word)
                if end >= len(content) or content[end] in ' \t\n\r.,!?;:，。！？；：':
                    if agent_id not in mentioned:
                        mentioned.append(agent_id)
                    # Mark all positions of this match as used
                    for i in range(start, end):
                        matched_positions.add(i)
    
    # Second pass: try to match agent IDs (for cases like @main, @horbot-02)
    mention_pattern = r'@(\S+)'
    for match in re.finditer(mention_pattern, content):
        start = match.start()
        # Skip if this position was already matched by name matching
        if start in matched_positions:
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
                break
    
    return mentioned


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


def clean_message_content(content: str) -> str:
    """Clean message content by removing tool call wrappers and think tags.
    
    Handles formats like:
    - message('...') -> ...
    - message("...") -> ...
    - <think>...</think> -> (removed)
    - <message from="...">...</message> -> ... (LLM history format)
    - "Message sent to..." -> (removed, system message)
    """
    import re
    
    if not content:
        return content
    
    # Remove <think> tags
    content = re.sub(r'<think[\s\S]*?</think\s*>', '', content).strip()
    
    # Remove one or more outer <message ...>...</message> wrappers.
    # Agent-to-agent history can include attributes like `from` / `to`, and
    # wrappers may be nested if a response was re-persisted through another hop.
    message_wrapper_pattern = re.compile(
        r'^\s*<message\b[^>]*>\s*([\s\S]*?)\s*</message>\s*$',
        re.IGNORECASE,
    )
    while True:
        match = message_wrapper_pattern.match(content)
        if not match:
            break
        content = match.group(1).strip()
    
    # Extract content from message(...) wrapper
    # Match message('...') or message("...") with proper handling of escaped quotes
    message_pattern = r"^message\((['\"])(.*?)\1\)$"
    match = re.match(message_pattern, content, re.DOTALL)
    if match:
        # Return the content inside the quotes, unescaping escaped quotes
        inner_content = match.group(2)
        # Unescape quotes (\' -> ', \" -> ")
        inner_content = inner_content.replace("\\'", "'").replace('\\"', '"')
        return inner_content.strip()
    
    # Filter out system/tool messages that shouldn't be displayed
    # These are typically tool execution results like "Message sent to..."
    system_patterns = [
        r'^Message sent to\s+\S+.*$',  # "Message sent to channel:chat_id"
        r'^Error\s*:.*$',  # Error messages
        r'^Error sending message.*$',  # Message sending errors
    ]
    for pattern in system_patterns:
        if re.match(pattern, content, re.IGNORECASE):
            return ""  # Return empty string for system messages
    
    return content.strip()


def ensure_history_message_id(message: dict[str, Any]) -> str:
    """Return a stable message id for legacy history entries missing `id`.

    Older persisted assistant messages may not have message ids. The frontend
    reloads history multiple times, so random fallback ids cause duplicates to
    be appended and later grouped into one oversized bubble. Use a stable
    fingerprint instead.
    """
    existing_id = message.get("id")
    if isinstance(existing_id, str) and existing_id.strip():
        return existing_id

    metadata = message.get("metadata") or {}
    fingerprint_source = {
        "role": message.get("role") or "",
        "timestamp": message.get("timestamp") or "",
        "content": clean_message_content(str(message.get("content") or "")),
        "agent_id": metadata.get("agent_id") or "",
        "agent_name": metadata.get("agent_name") or "",
        "turn_id": metadata.get("turn_id") or "",
        "request_id": metadata.get("request_id") or "",
    }
    payload = json.dumps(fingerprint_source, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
    return f"legacy-{digest}"


def _history_message_fingerprint(message: dict[str, Any]) -> str:
    metadata = message.get("metadata") or {}
    fingerprint_source = {
        "role": message.get("role") or "",
        "timestamp": message.get("timestamp") or "",
        "content": clean_message_content(str(message.get("content") or "")),
        "agent_id": metadata.get("agent_id") or "",
        "agent_name": metadata.get("agent_name") or "",
        "turn_id": metadata.get("turn_id") or "",
        "request_id": metadata.get("request_id") or "",
    }
    payload = json.dumps(fingerprint_source, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _history_sort_key(message: dict[str, Any]) -> tuple[int, datetime]:
    timestamp = message.get("timestamp")
    if not isinstance(timestamp, str) or not timestamp.strip():
        return (1, datetime.min)
    try:
        return (0, datetime.fromisoformat(timestamp))
    except ValueError:
        return (1, datetime.min)


def _merge_history_messages(message_groups: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    index_by_id: dict[str, int] = {}
    index_by_fingerprint: dict[str, int] = {}

    for group in message_groups:
        for raw_message in group:
            message = dict(raw_message)
            message["id"] = ensure_history_message_id(message)
            fingerprint = _history_message_fingerprint(message)
            existing_index = index_by_id.get(message["id"])
            if existing_index is None:
                existing_index = index_by_fingerprint.get(fingerprint)

            if existing_index is None:
                next_index = len(merged)
                merged.append(message)
                index_by_id[message["id"]] = next_index
                index_by_fingerprint[fingerprint] = next_index
                continue

            existing_message = merged[existing_index]
            merged_message = {
                **existing_message,
                **message,
                "content": message.get("content") or existing_message.get("content") or "",
                "files": message.get("files") or existing_message.get("files"),
                "execution_steps": message.get("execution_steps") or existing_message.get("execution_steps"),
                "metadata": {
                    **(existing_message.get("metadata") or {}),
                    **(message.get("metadata") or {}),
                },
            }
            merged[existing_index] = merged_message
            index_by_id[merged_message["id"]] = existing_index
            index_by_fingerprint[fingerprint] = existing_index

    return [
        item["message"]
        for item in sorted(
            (
                {"message": message, "index": index}
                for index, message in enumerate(merged)
            ),
            key=lambda item: (_history_sort_key(item["message"]), item["index"]),
        )
    ]


def _unique_session_managers(managers: list[SessionManager]) -> list[SessionManager]:
    unique: list[SessionManager] = []
    seen_dirs: set[str] = set()
    for manager in managers:
        sessions_dir = str(Path(manager.sessions_dir).resolve())
        if sessions_dir in seen_dirs:
            continue
        seen_dirs.add(sessions_dir)
        unique.append(manager)
    return unique


def _legacy_agent_session_managers(agent) -> list[SessionManager]:
    candidates: list[SessionManager] = []
    try:
        primary_sessions_dir = Path(agent.get_sessions_dir()).resolve()
        workspace_sessions_dir = (Path(agent.get_workspace()) / "sessions").resolve()
        if workspace_sessions_dir != primary_sessions_dir and workspace_sessions_dir.exists():
            candidates.append(SessionManager(workspace=workspace_sessions_dir))
    except Exception as exc:
        logger.warning("Failed to resolve legacy session path for agent {}: {}", getattr(agent, "id", "unknown"), exc)
    return candidates


def _load_merged_session_messages(session_key: str, managers: list[SessionManager]) -> list[dict[str, Any]]:
    message_groups: list[list[dict[str, Any]]] = []
    for manager in _unique_session_managers(managers):
        session = manager.get(session_key)
        if session and session.messages:
            message_groups.append(list(session.messages))
    if not message_groups:
        return []
    return _merge_history_messages(message_groups)


def _find_session_message_index(
    session,
    *,
    message_id: str | None = None,
    turn_id: str | None = None,
    role: str | None = None,
) -> int:
    for idx in range(len(session.messages) - 1, -1, -1):
        msg = session.messages[idx]
        if role and msg.get("role") != role:
            continue
        if message_id and msg.get("id") == message_id:
            return idx
        metadata = msg.get("metadata", {})
        if turn_id and metadata.get("turn_id") == turn_id:
            return idx
    return -1


class ChatRequest(BaseModel):
    content: str
    session_key: str = "default"
    file_ids: List[str] = []  # MiniMax file IDs for document processing
    web_search: bool = False  # Enable web search for MiniMax
    agent_id: Optional[str] = None  # Target agent ID for multi-agent chat


class CreateSessionRequest(BaseModel):
    title: Optional[str] = None


class ConfirmRequest(BaseModel):
    confirmation_id: str
    action: str  # "confirm" or "cancel"
    session_key: str = "default"


def get_session_manager():
    """Get session manager instance."""
    global _session_manager
    config = get_cached_config()
    expected_sessions_dir = SessionManager(workspace=Path(config.workspace_path)).sessions_dir

    if _session_manager is None or Path(_session_manager.sessions_dir) != Path(expected_sessions_dir):
        _session_manager = SessionManager(workspace=Path(config.workspace_path))
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
        agent_loop = await get_agent_loop(agent_id)
        return agent_loop.sessions, normalized_session_key

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


@router.get("/config")
async def get_config():
    """Get current configuration."""
    config = get_cached_config()
    raw_data = config.model_dump(by_alias=True)
    data = sanitize_config_for_client(raw_data)
    
    # Predefined providers (always show in UI)
    PREDEFINED_PROVIDERS = {
        'custom', 'anthropic', 'openai', 'openrouter', 'deepseek', 'groq',
        'zhipu', 'dashscope', 'vllm', 'gemini', 'moonshot', 'minimax',
        'aihubmix', 'siliconflow', 'volcengine', 'openaiCodex', 'githubCopilot'
    }
    
    # Filter providers: keep predefined ones and custom ones with apiKey
    if "providers" in data:
        providers = raw_data.get("providers", {})
        sanitized_providers = data["providers"]
        data["providers"] = {
            name: sanitized_providers.get(name, {}) for name, settings in providers.items()
            if name in PREDEFINED_PROVIDERS or (settings and (settings.get("apiKey") or settings.get("api_key")))
        }
    
    return data


@router.get("/config/validate")
async def validate_config_endpoint():
    """Validate current configuration and return structured result."""
    config = get_cached_config()
    result = validate_config(config)
    
    return {
        "valid": result.valid,
        "errors": [
            {
                "code": msg.code,
                "message": msg.message,
                "field_path": msg.field_path,
                "suggestion": msg.suggestion,
            }
            for msg in result.errors
        ],
        "warnings": [
            {
                "code": msg.code,
                "message": msg.message,
                "field_path": msg.field_path,
                "suggestion": msg.suggestion,
            }
            for msg in result.warnings
        ],
        "infos": [
            {
                "code": msg.code,
                "message": msg.message,
                "field_path": msg.field_path,
                "suggestion": msg.suggestion,
            }
            for msg in result.infos
        ],
    }


@router.get("/soul")
async def get_soul(agent_id: Optional[str] = None):
    """Get SOUL.md content for persona display."""
    agent, workspace_path = _resolve_agent_workspace_for_request(agent_id)
    resolved_agent_id = agent.id if agent is not None else (agent_id or "main")
    soul_path = workspace_path / "SOUL.md"
    
    if not soul_path.exists():
        return {"name": "horbot", "content": "", "agent_id": resolved_agent_id}
    
    try:
        content = soul_path.read_text(encoding="utf-8")
        import re
        name_match = re.search(r'^# (.+)$', content, re.MULTILINE)
        name = name_match.group(1) if name_match else "horbot"
        
        name_match2 = re.search(r'我是([^，。\n]+)', content)
        if name_match2:
            name = name_match2.group(1).strip()
        
        return {"name": name, "content": content, "agent_id": resolved_agent_id}
    except Exception as e:
        return {"name": "horbot", "content": "", "error": str(e), "agent_id": resolved_agent_id}

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


def _build_memory_store(agent_id: Optional[str] = None):
    from horbot.agent.memory import MemoryStore

    agent, workspace_path = _resolve_agent_workspace_for_request(agent_id)
    if agent is not None:
        return agent, workspace_path, MemoryStore(
            workspace=workspace_path,
            agent_id=agent.id,
            team_ids=agent.teams,
        )
    return agent, workspace_path, MemoryStore(workspace=workspace_path)


def _get_memory_roots(memory_store) -> tuple[Path, Path]:
    context_manager = getattr(memory_store, "_context_manager", None)
    if context_manager is not None:
        return (
            Path(context_manager.context_dir) / context_manager.MEMORIES_DIR,
            Path(context_manager.context_dir) / context_manager.EXECUTIONS_DIR,
        )
    base = Path(memory_store.memory_dir)
    return base, base.parent / "executions"


def _agent_bootstrap_file_path(agent_id: str, file_kind: str) -> tuple[Path, str]:
    _, workspace_path = _resolve_agent_workspace_for_request(agent_id)
    normalized = (file_kind or "").strip().lower()
    if normalized == "soul":
        return workspace_path / "SOUL.md", "SOUL.md"
    if normalized == "user":
        return workspace_path / "USER.md", "USER.md"
    raise HTTPException(status_code=400, detail="Unsupported bootstrap file. Use 'soul' or 'user'.")


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

    soul_path, _ = _agent_bootstrap_file_path(agent.id, "soul")
    user_path, _ = _agent_bootstrap_file_path(agent.id, "user")
    soul_file = _read_bootstrap_file(soul_path)
    user_file = _read_bootstrap_file(user_path)

    return {
        "agent_id": agent.id,
        "agent_name": agent.name,
        "workspace_path": str(agent.get_workspace()),
        "summary": _build_bootstrap_summary(agent, soul_file["content"], user_file["content"]),
        "files": {
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


def _resolve_app_version() -> str:
    try:
        import importlib.metadata
        return importlib.metadata.version("horbot")
    except Exception:
        return "0.1.4.post2"


def _format_uptime(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds_remaining = total_seconds % 60
    return f"{hours}h {minutes}m {seconds_remaining}s"


def _build_system_status_payload(config: Config | None = None) -> dict[str, Any]:
    import psutil

    config = config or get_cached_config()

    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
    except Exception:
        cpu_percent = 0

    try:
        memory = psutil.virtual_memory()
        memory_info = {
            "total": memory.total,
            "available": memory.available,
            "used": memory.used,
            "percent": memory.percent,
        }
    except Exception:
        memory_info = {
            "total": 0,
            "available": 0,
            "used": 0,
            "percent": 0,
        }

    try:
        disk = psutil.disk_usage('/')
        disk_info = {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent,
        }
    except Exception:
        disk_info = {
            "total": 0,
            "used": 0,
            "free": 0,
            "percent": 0,
        }

    try:
        uptime_seconds = time.time() - _api_started_at
        uptime_str = _format_uptime(uptime_seconds)
    except Exception:
        uptime_seconds = 0
        uptime_str = "Unknown"

    try:
        cron_status = get_cron_service().status()
    except Exception:
        cron_status = {"enabled": False, "jobs": 0}

    return {
        "status": "running",
        "version": _resolve_app_version(),
        "uptime": uptime_str,
        "uptime_seconds": uptime_seconds,
        "system": {
            "cpu_percent": cpu_percent,
            "memory": memory_info,
            "disk": disk_info,
        },
        "services": {
            "cron": {
                "enabled": cron_status.get("enabled", False),
                "jobs_count": cron_status.get("jobs", 0),
                "next_wake_at_ms": cron_status.get("next_wake_at_ms"),
            },
            "agent": {
                "initialized": len(get_agent_loop_pool()._pools) > 0,
            },
        },
        "config": {
            "workspace": str(config.workspace_path),
            "model": config.agents.defaults.model if config.agents else None,
            "provider": config.get_provider_name() if config else None,
        },
    }


_DASHBOARD_CHANNEL_REQUIRED_FIELDS: dict[str, list[str]] = {
    "whatsapp": ["bridge_url"],
    "telegram": ["token"],
    "discord": ["token"],
    "feishu": ["app_id", "app_secret"],
    "dingtalk": ["client_id", "client_secret"],
    "email": [
        "consent_granted",
        "imap_host",
        "imap_username",
        "imap_password",
        "smtp_host",
        "smtp_username",
        "smtp_password",
        "from_address",
    ],
    "slack": ["bot_token", "app_token"],
    "qq": ["app_id", "secret"],
    "matrix": ["homeserver", "access_token", "user_id"],
    "mochat": ["claw_token", "agent_user_id"],
    "sharecrm": ["app_id", "app_secret"],
}

_DASHBOARD_CHANNEL_DISPLAY_NAMES: dict[str, str] = {
    "qq": "QQ",
    "mochat": "Mochat",
    "sharecrm": "ShareCRM",
    "dingtalk": "DingTalk",
    "feishu": "Feishu",
}


def _is_channel_configured(channel_name: str, channel_config: dict[str, Any]) -> tuple[bool, list[str]]:
    required_fields = _DASHBOARD_CHANNEL_REQUIRED_FIELDS.get(channel_name, [])
    missing_fields: list[str] = []

    for field in required_fields:
        value = channel_config.get(field)
        if isinstance(value, bool):
            if not value:
                missing_fields.append(field)
        elif value in (None, "", []):
            missing_fields.append(field)

    return len(missing_fields) == 0, missing_fields


def _build_dashboard_channel_summary(config: Config) -> dict[str, Any]:
    raw_channels = config.channels.model_dump(by_alias=True)
    items: list[dict[str, Any]] = []
    counts = {
        "total": 0,
        "enabled": 0,
        "online": 0,
        "disabled": 0,
        "misconfigured": 0,
    }

    for channel_name, channel_config in raw_channels.items():
        if not isinstance(channel_config, dict) or "enabled" not in channel_config:
            continue

        enabled = bool(channel_config.get("enabled"))
        configured, missing_fields = _is_channel_configured(channel_name, channel_config)

        if not enabled:
            status = "disabled"
            status_label = "已禁用"
            reason = "当前通道未启用"
            counts["disabled"] += 1
        elif configured:
            status = "online"
            status_label = "就绪"
            reason = None
            counts["online"] += 1
        else:
            status = "error"
            status_label = "配置缺失"
            reason = f"缺少配置: {', '.join(missing_fields)}"
            counts["misconfigured"] += 1

        if enabled:
            counts["enabled"] += 1
        counts["total"] += 1

        items.append({
            "name": channel_name,
            "display_name": _DASHBOARD_CHANNEL_DISPLAY_NAMES.get(channel_name, channel_name.capitalize()),
            "enabled": enabled,
            "configured": configured,
            "status": status,
            "status_label": status_label,
            "reason": reason,
            "missing_fields": missing_fields,
        })

    items.sort(key=lambda item: (0 if item["status"] == "online" else 1 if item["status"] == "error" else 2, item["display_name"]))

    return {
        "items": items,
        "counts": counts,
    }


def _build_dashboard_alerts(config: Config, system_status: dict[str, Any], channel_summary: dict[str, Any]) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []

    provider_name = config.get_provider_name()
    provider_configured = False
    if provider_name:
        try:
            provider = config.get_provider()
            provider_configured = bool(provider and getattr(provider, "api_key", None))
        except Exception:
            provider_configured = False

    if not provider_name:
        alerts.append({
            "id": "provider-missing",
            "level": "warning",
            "title": "未配置模型提供商",
            "message": "当前还没有可用的 AI provider，聊天和诊断能力会受限。",
        })
    elif not provider_configured:
        alerts.append({
            "id": "provider-key-missing",
            "level": "warning",
            "title": "Provider 缺少 API Key",
            "message": f"已选择 {provider_name}，但认证信息不完整。",
        })

    if channel_summary["counts"]["misconfigured"] > 0:
        alerts.append({
            "id": "channel-misconfigured",
            "level": "warning",
            "title": "存在配置不完整的通道",
            "message": f"{channel_summary['counts']['misconfigured']} 个已启用通道缺少必要配置。",
        })

    if not system_status["services"]["agent"]["initialized"]:
        alerts.append({
            "id": "agent-not-ready",
            "level": "warning",
            "title": "Agent Loop 尚未初始化",
            "message": "当前尚未检测到可用的 agent loop，首次请求前部分能力可能未完全预热。",
        })

    if system_status["system"]["memory"]["percent"] >= 85:
        alerts.append({
            "id": "memory-high",
            "level": "error",
            "title": "内存占用较高",
            "message": f"当前内存占用 {round(system_status['system']['memory']['percent'])}%，建议关注长时间运行任务。",
        })

    if system_status["system"]["disk"]["percent"] >= 90:
        alerts.append({
            "id": "disk-high",
            "level": "error",
            "title": "磁盘空间不足",
            "message": f"当前磁盘占用 {round(system_status['system']['disk']['percent'])}%，可能影响日志和会话写入。",
        })

    return alerts


def _build_dashboard_activities(
    system_status: dict[str, Any],
    channel_summary: dict[str, Any],
    alerts: list[dict[str, str]],
) -> list[dict[str, str]]:
    activities: list[dict[str, str]] = []

    if system_status["status"] == "running":
        activities.append({
            "id": "system-running",
            "type": "system",
            "message": "控制面板摘要已成功加载",
            "time": "刚刚",
            "status": "success",
        })

    if system_status["services"]["agent"]["initialized"]:
        activities.append({
            "id": "agent-ready",
            "type": "agent",
            "message": "Agent loop 已初始化",
            "time": "当前",
            "status": "success",
        })

    if system_status["services"]["cron"]["enabled"]:
        activities.append({
            "id": "cron-running",
            "type": "task",
            "message": f"{system_status['services']['cron']['jobs_count']} 个定时任务处于启用状态",
            "time": "持续中",
            "status": "info",
        })

    if channel_summary["counts"]["enabled"] > 0:
        activities.append({
            "id": "channels-enabled",
            "type": "channel",
            "message": (
                f"{channel_summary['counts']['enabled']} 个通道已启用，"
                f"{channel_summary['counts']['online']} 个配置完整"
            ),
            "time": "当前",
            "status": "success" if channel_summary["counts"]["misconfigured"] == 0 else "warning",
        })

    if alerts:
        first_alert = alerts[0]
        activities.append({
            "id": f"alert-{first_alert['id']}",
            "type": "system",
            "message": first_alert["title"],
            "time": "当前",
            "status": first_alert["level"],
        })

    return activities[:6]


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


@router.get("/channels/catalog")
async def get_channels_catalog():
    """Return channel catalog metadata and agent choices for the channels UI."""
    config = get_cached_config()
    return {
        "catalog": get_channel_catalog(),
        "agents": _channel_agents_payload(config),
    }


@router.get("/channels/endpoints")
async def get_channel_endpoints():
    """Return channel endpoints, including legacy global configs projected as endpoints."""
    config = get_cached_config()
    return _channel_endpoints_payload(config)


@router.get("/channels/endpoints/{endpoint_id}/events")
async def get_channel_endpoint_events(endpoint_id: str, limit: int = 20):
    """Return recent runtime events for one channel endpoint."""
    config = get_cached_config()
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
    config = get_cached_config()
    endpoint = find_channel_endpoint(config, endpoint_id)
    if endpoint is None:
        raise HTTPException(status_code=404, detail=f"Endpoint not found: {endpoint_id}")

    runtime_config = build_runtime_channel_config(config.channels, endpoint)
    result = await test_channel_connection(endpoint.type, runtime_config)
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
    config = get_cached_config()
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
        config=request.config,
    )
    resolved = build_custom_endpoint(config, draft_endpoint)
    runtime_config = build_runtime_channel_config(config.channels, resolved)
    result = await test_channel_connection(request.type, runtime_config)

    return {
        "endpoint": _serialize_channel_endpoint(resolved),
        "tested_at": datetime.now().isoformat(),
        "result": result,
    }


@router.post("/channels/endpoints")
async def create_channel_endpoint(request: ChannelEndpointUpsertRequest):
    """Create a custom channel endpoint bound to a specific agent."""
    config = get_cached_config()
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
        save_config(config)
        await reset_agent_loop()
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
    config = get_cached_config()
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
            save_config(config)
            await reset_agent_loop()
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
    target.config = request.config
    _apply_endpoint_binding(config, endpoint_id, request.agent_id)

    try:
        save_config(config)
        await reset_agent_loop()
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

    config = get_cached_config()
    before_count = len(config.channels.endpoints)
    config.channels.endpoints = [
        endpoint for endpoint in config.channels.endpoints
        if endpoint.id != endpoint_id
    ]
    if len(config.channels.endpoints) == before_count:
        raise HTTPException(status_code=404, detail=f"Endpoint not found: {endpoint_id}")

    _apply_endpoint_binding(config, endpoint_id, "")

    try:
        save_config(config)
        await reset_agent_loop()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete channel endpoint: {str(e)}")

    return {"status": "deleted", "endpoint_id": endpoint_id}


@router.patch("/channels/{channel_name}")
async def update_channel(channel_name: str, channel_data: ChannelUpdateRequest):
    """Update a single channel's lightweight dashboard fields."""
    config = get_cached_config()
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
        save_config(config)
        await reset_agent_loop()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update channel: {str(e)}")

    return channel.model_dump(by_alias=True)


@router.get("/dashboard/summary")
async def get_dashboard_summary():
    """Return a lightweight dashboard summary optimized for the home page."""
    config = get_cached_config()
    system_status = _build_system_status_payload(config)
    channel_summary = _build_dashboard_channel_summary(config)
    alerts = _build_dashboard_alerts(config, system_status, channel_summary)

    provider_name = config.get_provider_name()
    provider_configured = False
    if provider_name:
        try:
            provider = config.get_provider()
            provider_configured = bool(provider and getattr(provider, "api_key", None))
        except Exception:
            provider_configured = False

    return {
        "generated_at": datetime.now().isoformat(),
        "system_status": system_status,
        "provider": {
            "name": provider_name,
            "configured": provider_configured,
        },
        "channels": channel_summary,
        "recent_activities": _build_dashboard_activities(system_status, channel_summary, alerts),
        "alerts": alerts,
    }

@router.put("/config")
async def update_config(config_data: Dict[str, Any]):
    """Update configuration."""
    try:
        from loguru import logger
        logger.info(f"[Config Update] Received config data keys: {list(config_data.keys())}")
        logger.debug("[Config Update] Config data: {}", redact_sensitive_data(config_data))
        
        config = Config.model_validate(config_data)
        saved_path = save_config(config)
        
        await reset_agent_loop()
        
        return {
            "status": "success", 
            "message": "Configuration updated and agent reloaded",
            "path": str(saved_path)
        }
    except PermissionError as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Permission denied: {str(e)}. The application may be running in a sandbox environment. Please run outside of sandbox or check file permissions."
        )
    except ValueError as e:
        from loguru import logger
        logger.error(f"[Config Update] Validation error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
    except Exception as e:
        from loguru import logger
        logger.error(f"[Config Update] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save configuration: {str(e)}")


class ModelConfigUpdate(BaseModel):
    """Model configuration update request."""
    provider: str
    model: str
    description: str = ""
    capabilities: List[str] = []


class AgentDefaultsUpdateRequest(BaseModel):
    """Partial update request for agent defaults."""
    workspace: Optional[str] = None
    maxTokens: Optional[int] = None
    temperature: Optional[float] = None
    models: Optional[Dict[str, Any]] = None


class WebSearchConfigUpdateRequest(BaseModel):
    """Partial update request for web search config."""
    provider: Optional[str] = None
    apiKey: Optional[str] = None
    maxResults: Optional[int] = None


@router.put("/config/models/{scenario}")
async def update_model_config(scenario: str, model_data: ModelConfigUpdate):
    """Update a single model configuration."""
    valid_scenarios = ["main", "planning", "file", "image", "webSearch", "audio", "video"]
    if scenario not in valid_scenarios:
        raise HTTPException(status_code=400, detail=f"Invalid scenario: {scenario}. Valid scenarios are: {valid_scenarios}")
    
    try:
        config = get_cached_config()
        
        models = config.agents.defaults.models
        if not hasattr(models, scenario):
            raise HTTPException(status_code=400, detail=f"Model scenario not found: {scenario}")
        
        model_config = getattr(models, scenario)
        model_config.provider = model_data.provider
        model_config.model = model_data.model
        model_config.description = model_data.description
        model_config.capabilities = model_data.capabilities
        
        saved_path = save_config(config)
        
        return {
            "status": "success",
            "message": f"Model '{scenario}' updated successfully",
            "scenario": scenario,
            "path": str(saved_path)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update model configuration: {str(e)}")


@router.patch("/config/agent-defaults")
async def update_agent_defaults(request: AgentDefaultsUpdateRequest):
    """Patch agent default settings without replacing the full config."""
    try:
        config = get_cached_config()
        defaults = config.agents.defaults

        if request.workspace is not None:
            defaults.workspace = request.workspace
        if request.maxTokens is not None:
            defaults.max_tokens = request.maxTokens
        if request.temperature is not None:
            defaults.temperature = request.temperature
        if request.models is not None:
            defaults.models = ModelsConfig.model_validate(request.models)

        saved_path = save_config(config)
        await reset_agent_loop()

        return {
            "status": "success",
            "message": "Agent defaults updated successfully",
            "path": str(saved_path),
        }
    except PermissionError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Permission denied: {str(e)}. The application may be running in a sandbox environment."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update agent defaults: {str(e)}")


@router.patch("/config/web-search")
async def update_web_search_config(request: WebSearchConfigUpdateRequest):
    """Patch web search config without replacing the full config."""
    try:
        config = get_cached_config()
        search_config = config.tools.web.search

        if request.provider is not None:
            search_config.provider = request.provider
        if request.apiKey is not None:
            search_config.api_key = request.apiKey
        if request.maxResults is not None:
            search_config.max_results = request.maxResults

        saved_path = save_config(config)
        await reset_agent_loop()

        return {
            "status": "success",
            "message": "Web search config updated successfully",
            "path": str(saved_path),
        }
    except PermissionError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Permission denied: {str(e)}. The application may be running in a sandbox environment."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update web search config: {str(e)}")


@router.get("/hot-reload-test")
async def hot_reload_test():
    """Test endpoint to verify hot reload is working."""
    global _hot_reload_test_counter
    _hot_reload_test_counter += 1
    return {
        "status": "hot_reload_working",
        "counter": _hot_reload_test_counter,
        "message": "HOT RELOAD SUCCESS! This message was updated after code modification.",
        "version": "v2"
    }


@router.post("/test-task-analysis")
async def test_task_analysis(request: dict):
    """Test task complexity analysis."""
    from horbot.agent.planner.analyzer import TaskAnalyzer
    
    task = request.get("task", "")
    analyzer = TaskAnalyzer()
    analysis = analyzer.analyze(task)
    
    return {
        "task": task,
        "level": analysis.level.value,
        "score": analysis.score,
        "reasons": analysis.reasons,
        "needs_planning": analysis.needs_planning,
        "estimated_steps": analysis.estimated_steps,
        "suggested_mode": analysis.suggested_mode,
    }


@router.post("/test-plan-generation")
async def test_plan_generation(request: dict):
    """Test plan generation."""
    from horbot.agent.planner.generator import PlanGenerator
    
    task = request.get("task", "")
    agent_loop = await get_agent_loop()
    
    generator = PlanGenerator(provider=agent_loop.provider, model=agent_loop.model)
    
    try:
        result = await generator.generate(
            task=task,
            available_tools=agent_loop.tools.tool_names,
        )
        
        if result.success and result.plan:
            return {
                "success": True,
                "plan": {
                    "id": result.plan.id,
                    "title": result.plan.title,
                    "description": result.plan.description,
                    "steps": [
                        {
                            "id": step.id,
                            "title": step.description[:100] if step.description else f"步骤 {i+1}",
                            "description": step.description or "",
                            "tool_name": step.tool_name,
                        }
                        for i, step in enumerate(result.plan.steps)
                    ]
                },
                "raw_response": result.raw_response[:500] if result.raw_response else None,
            }
        else:
            return {
                "success": False,
                "error": result.error,
                "raw_response": result.raw_response[:500] if result.raw_response else None,
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


# File upload configuration
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo"}
ALLOWED_AUDIO_TYPES = {"audio/mpeg", "audio/wav", "audio/mp4", "audio/x-m4a"}
ALLOWED_DOC_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
    "text/markdown",
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def _get_upload_dir() -> Path:
    """Get upload directory, create if not exists."""
    from horbot.utils.paths import get_uploads_dir
    return get_uploads_dir()


def _get_file_category(mime_type: str) -> str:
    """Get file category from mime type."""
    if mime_type in ALLOWED_IMAGE_TYPES:
        return "image"
    elif mime_type in ALLOWED_VIDEO_TYPES:
        return "video"
    elif mime_type in ALLOWED_AUDIO_TYPES:
        return "audio"
    elif mime_type in ALLOWED_DOC_TYPES:
        return "document"
    else:
        return "other"


class UploadResponse(BaseModel):
    """Response model for file upload."""
    file_id: str
    filename: str
    original_name: str
    mime_type: str
    size: int
    category: str
    url: str
    preview_url: Optional[str] = None
    minimax_file_id: Optional[str] = None  # MiniMax file ID for document processing
    extracted_text: Optional[str] = None  # Extracted text content from documents


def _extract_text_from_pdf(file_path: Path) -> Optional[str]:
    """Extract text content from PDF file."""
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        return "\n\n".join(text_parts) if text_parts else None
    except ImportError:
        logger.warning("pdfplumber not installed, falling back to PyMuPDF for PDF text extraction")
    except Exception as e:
        logger.error(f"PDF text extraction error with pdfplumber: {e}")

    try:
        import fitz

        text_parts = []
        with fitz.open(file_path) as pdf:
            for page in pdf:
                text = page.get_text("text")
                if text:
                    text_parts.append(text)
        return "\n\n".join(text_parts) if text_parts else None
    except Exception as e:
        logger.error(f"PDF text extraction error with PyMuPDF: {e}")
        return None


def _extract_text_from_docx(file_path: Path) -> Optional[str]:
    """Extract text content from DOCX file."""
    try:
        from docx import Document
        doc = Document(file_path)
        text_parts = []
        for para in doc.paragraphs:
            if para.text:
                text_parts.append(para.text)
        return "\n\n".join(text_parts) if text_parts else None
    except ImportError:
        logger.warning("python-docx not installed, skipping DOCX text extraction")
        return None
    except Exception as e:
        logger.error(f"DOCX text extraction error: {e}")
        return None


def _office_archive_sort_key(name: str) -> tuple[int, str]:
    stem = Path(name).stem
    digits = "".join(ch for ch in stem if ch.isdigit())
    return (int(digits) if digits else 0, name)


def _extract_text_from_pptx(file_path: Path) -> Optional[str]:
    """Extract text content from PPTX file using XML parsing."""
    try:
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile

        with ZipFile(file_path) as archive:
            slide_paths = sorted(
                (
                    name
                    for name in archive.namelist()
                    if name.startswith("ppt/slides/slide") and name.endswith(".xml")
                ),
                key=_office_archive_sort_key,
            )

            text_parts: list[str] = []
            for index, slide_path in enumerate(slide_paths, start=1):
                root = ET.fromstring(archive.read(slide_path))
                slide_texts = [
                    node.text.strip()
                    for node in root.iter()
                    if node.tag.rsplit("}", 1)[-1] == "t" and node.text and node.text.strip()
                ]
                if slide_texts:
                    text_parts.append(f"[Slide {index}]")
                    text_parts.append("\n".join(slide_texts))

        return "\n\n".join(text_parts) if text_parts else None
    except Exception as e:
        logger.error(f"PPTX text extraction error: {e}")
        return None


def _extract_text_from_xlsx(file_path: Path) -> Optional[str]:
    """Extract text content from XLSX file using XML parsing."""
    try:
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile

        with ZipFile(file_path) as archive:
            shared_strings: list[str] = []
            if "xl/sharedStrings.xml" in archive.namelist():
                shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                for node in shared_root.iter():
                    if node.tag.rsplit("}", 1)[-1] == "t" and node.text and node.text.strip():
                        shared_strings.append(node.text.strip())

            sheet_names: list[str] = []
            if "xl/workbook.xml" in archive.namelist():
                workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
                for node in workbook_root.iter():
                    if node.tag.rsplit("}", 1)[-1] == "sheet":
                        name = (node.attrib.get("name") or "").strip()
                        if name:
                            sheet_names.append(name)

            worksheet_paths = sorted(
                (
                    name
                    for name in archive.namelist()
                    if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
                ),
                key=_office_archive_sort_key,
            )

            text_parts: list[str] = []
            for index, sheet_path in enumerate(worksheet_paths):
                root = ET.fromstring(archive.read(sheet_path))
                rows: list[str] = []
                for row in root.iter():
                    if row.tag.rsplit("}", 1)[-1] != "row":
                        continue
                    cell_values: list[str] = []
                    for cell in row:
                        if cell.tag.rsplit("}", 1)[-1] != "c":
                            continue
                        cell_type = (cell.attrib.get("t") or "").strip()
                        value = ""
                        if cell_type == "inlineStr":
                            inline_parts = [
                                node.text.strip()
                                for node in cell.iter()
                                if node.tag.rsplit("}", 1)[-1] == "t" and node.text and node.text.strip()
                            ]
                            value = "".join(inline_parts)
                        else:
                            raw = next(
                                (
                                    node.text.strip()
                                    for node in cell
                                    if node.tag.rsplit("}", 1)[-1] == "v" and node.text and node.text.strip()
                                ),
                                "",
                            )
                            if cell_type == "s" and raw.isdigit():
                                shared_index = int(raw)
                                if 0 <= shared_index < len(shared_strings):
                                    value = shared_strings[shared_index]
                            else:
                                value = raw
                        if value:
                            cell_values.append(value)
                    if cell_values:
                        rows.append("\t".join(cell_values))

                if rows:
                    sheet_label = sheet_names[index] if index < len(sheet_names) else Path(sheet_path).stem
                    text_parts.append(f"[{sheet_label}]")
                    text_parts.append("\n".join(rows))

        return "\n\n".join(text_parts) if text_parts else None
    except Exception as e:
        logger.error(f"XLSX text extraction error: {e}")
        return None


def _extract_text_from_txt(file_path: Path) -> Optional[str]:
    """Extract text content from TXT file."""
    try:
        return file_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"TXT text extraction error: {e}")
        return None


def _extract_document_content(file_path: Path, mime_type: str) -> Optional[str]:
    """Extract text content from document based on mime type."""
    if mime_type == "application/pdf":
        return _extract_text_from_pdf(file_path)
    elif mime_type in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/docx"):
        return _extract_text_from_docx(file_path)
    elif mime_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
        return _extract_text_from_pptx(file_path)
    elif mime_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        return _extract_text_from_xlsx(file_path)
    elif mime_type in ("text/plain", "text/markdown"):
        return _extract_text_from_txt(file_path)
    return None


async def _upload_to_minimax(file_path: Path, api_key: str, base_url: str = "https://api.minimax.chat") -> Optional[str]:
    """Upload file to MiniMax file management API.
    
    API Reference: https://platform.minimaxi.com/document/guides/chat-conversation
    Endpoint: POST /v1/files/upload
    """
    import httpx
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, "application/octet-stream")}
                headers = {"Authorization": f"Bearer {api_key}"}
                response = await client.post(
                    f"{base_url}/v1/files/upload",
                    files=files,
                    headers=headers,
                )
            
            if response.status_code == 200:
                data = response.json()
                file_id = data.get("file", {}).get("file_id")
                if file_id:
                    logger.info(f"Uploaded to MiniMax: {file_path.name} -> {file_id}")
                    return file_id
            else:
                logger.warning(f"MiniMax upload failed: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"MiniMax upload error: {e}")
    
    return None


@router.post("/upload", response_model=List[UploadResponse])
async def upload_files(files: List[UploadFile] = File(...)):
    """Upload multiple files."""
    upload_dir = _get_upload_dir()
    config = get_cached_config()
    results = []
    
    # Get MiniMax API key if available
    minimax_api_key = None
    minimax_base_url = "https://api.minimax.chat"
    providers = config.providers or {}
    if "minimax" in providers:
        minimax_config = providers["minimax"] or {}
        minimax_api_key = minimax_config.get("apiKey") or minimax_config.get("api_key")
        minimax_base_url = minimax_config.get("baseUrl", "https://api.minimax.chat")
    
    for file in files:
        # Validate file size
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File {file.filename} exceeds maximum size of 50MB"
            )
        
        # Generate file ID and determine mime type
        file_id = str(uuid.uuid4())
        mime_type = file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
        category = _get_file_category(mime_type)
        
        # Generate unique filename
        ext = Path(file.filename).suffix if file.filename else ""
        safe_filename = f"{file_id}{ext}"
        file_path = upload_dir / safe_filename
        
        # Save file
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Upload to MiniMax for document files
        minimax_file_id = None
        extracted_text = None
        if category == "document":
            # Extract text content from document
            extracted_text = _extract_document_content(file_path, mime_type)
            if extracted_text:
                logger.info(f"Extracted {len(extracted_text)} characters from {file.filename}")
            
            # Upload to MiniMax if API key available
            if minimax_api_key:
                minimax_file_id = await _upload_to_minimax(file_path, minimax_api_key, minimax_base_url)
        
        # Create response
        result = UploadResponse(
            file_id=file_id,
            filename=safe_filename,
            original_name=file.filename or "unknown",
            mime_type=mime_type,
            size=len(content),
            category=category,
            url=f"/api/files/{file_id}",
            preview_url=f"/api/files/{file_id}/preview" if category == "image" else None,
            minimax_file_id=minimax_file_id,
            extracted_text=extracted_text,
        )
        results.append(result)
        logger.info(f"Uploaded file: {file.filename} -> {safe_filename} ({category})")
    
    return results


@router.get("/files/{file_id}")
async def get_file(file_id: str):
    """Get uploaded file by ID."""
    upload_dir = _get_upload_dir()
    
    # Find file by ID (may have extension)
    matching_files = list(upload_dir.glob(f"{file_id}.*"))
    if not matching_files:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_path = matching_files[0]
    mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    
    return FileResponse(
        path=file_path,
        media_type=mime_type,
        filename=file_path.name,
        content_disposition_type="inline",
    )


@router.get("/files/{file_id}/preview")
async def get_file_preview(file_id: str):
    """Get file preview (for images)."""
    upload_dir = _get_upload_dir()
    
    matching_files = list(upload_dir.glob(f"{file_id}.*"))
    if not matching_files:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_path = matching_files[0]
    mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    
    if not mime_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Preview only available for images")
    
    return FileResponse(
        path=file_path,
        media_type=mime_type
    )


@router.delete("/files/{file_id}")
async def delete_file(file_id: str):
    """Delete uploaded file by ID."""
    upload_dir = _get_upload_dir()
    
    matching_files = list(upload_dir.glob(f"{file_id}.*"))
    if not matching_files:
        raise HTTPException(status_code=404, detail="File not found")
    
    for file_path in matching_files:
        file_path.unlink()
        logger.info(f"Deleted file: {file_path}")
    
    return {"status": "success", "message": f"File {file_id} deleted"}


@router.get("/chat/history")
async def get_chat_history(session_key: str = "default", agent_id: Optional[str] = None):
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
    if resolved_agent_id:
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
        msg_data = {
            "id": ensure_history_message_id(msg),
            "role": msg.get("role"),
            "content": msg.get("content"),
            "timestamp": msg.get("timestamp")
        }
        # Include execution_steps if present (saved with underscore naming)
        if "execution_steps" in msg:
            msg_data["execution_steps"] = sanitize_execution_steps(msg["execution_steps"])
        
        # Include files if present
        if "files" in msg:
            msg_data["files"] = msg["files"]
        
        # Include metadata if present
        if "metadata" in msg:
            msg_data["metadata"] = msg["metadata"]
        
        messages.append(msg_data)
    
    return {"messages": messages, "session_key": session_key}


@router.post("/chat/sessions")
async def create_new_session(request: Optional[CreateSessionRequest] = None):
    """Create a new chat session."""
    manager = get_session_manager()

    session_key = f"session_{uuid.uuid4().hex}"

    # Full session key includes channel prefix
    full_session_key = f"web:{session_key}"

    session = manager.get_or_create(full_session_key)
    title = ((request.title if request else None) or "").strip() or "新对话"
    session.title = title
    session.metadata["title"] = title
    session.metadata["created_at"] = session.created_at.isoformat()

    manager.save(session)

    return {"session_key": session_key, "title": title}


@router.put("/chat/sessions/{session_key}")
async def update_session_title(session_key: str, title: str):
    """Update session title."""
    manager, normalized_session_key = await _resolve_chat_session_manager(session_key)
    session = manager.get(normalized_session_key)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    resolved_title = title.strip() or "新对话"
    session.title = resolved_title
    session.metadata["title"] = resolved_title
    manager.save(session)

    return {"status": "success", "title": resolved_title}


@router.delete("/chat/sessions/{session_key}")
async def delete_session(session_key: str):
    """Delete a session."""
    manager, normalized_session_key = await _resolve_chat_session_manager(session_key)
    session_path = manager._get_session_path(normalized_session_key)

    if session_path.exists():
        import os
        os.remove(session_path)
        manager.invalidate(normalized_session_key)
        return {"status": "success"}
    else:
        raise HTTPException(status_code=404, detail="Session not found")


@router.get("/chat/sessions")
async def list_chat_sessions():
    """List all chat sessions with metadata."""
    manager = get_session_manager()
    session_infos = manager.list_sessions(key_prefix="web:")
    
    # Enrich with metadata, only show web sessions
    enriched_sessions = []
    for session_info in session_infos:
        session_key = session_info.get("key")
        if not session_key:
            continue
        
        title = session_info.get("title", "未命名对话")
        message_count = int(session_info.get("message_count", 0) or 0)
        created_at = session_info.get("created_at", "")

        if title == "未命名对话":
            session = manager.get(session_key)
            if session:
                title = session.metadata.get("title", "未命名对话")
                if title == "未命名对话" and session.messages:
                    for msg in session.messages:
                        if msg.get("role") == "user":
                            content = msg.get("content", "")
                            if len(content) > 50:
                                title = content[:50] + "..."
                            else:
                                title = content or "未命名对话"
                            break
                created_at = session.metadata.get("created_at", created_at)
                message_count = len(session.messages)

        enriched_sessions.append({
            "key": session_key,
            "title": title,
            "created_at": created_at,
            "message_count": message_count,
        })
    
    # Sort by creation time (newest first)
    enriched_sessions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    return {"sessions": enriched_sessions}

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
    on_step_start_hook: Optional[Callable[[dict], None]] = None,
) -> Dict[str, Callable[..., Any]]:
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
        tool_hint = kwargs.get("tool_hint", False)
        if not tool_hint:
            content_state["content"] = content
        await emit("progress", content=content, tool_hint=tool_hint)

    async def on_tool_start(tool_name: str, arguments: dict) -> None:
        if tool_name == "message" and arguments and on_message_tool_content:
            content = arguments.get("content")
            if content:
                on_message_tool_content(content)
        await emit("tool_start", tool_name=tool_name, arguments=arguments)

    async def on_tool_result(tool_name: str, result: str, execution_time: float) -> None:
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
        await emit("step_start", step_id=step_id, step_type=step_type, title=title)

    async def on_step_complete(step_id: str, status: str, details: dict) -> None:
        safe_details = sanitize_execution_step_details(
            next((step.get("type") for step in execution_steps if step.get("id") == step_id), ""),
            details,
        )
        for step in execution_steps:
            if step["id"] == step_id:
                step["status"] = status
                step["details"] = safe_details
                break
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

    agent_instance = agent_manager.get_agent(agent_id)
    agent_name = agent_instance.name if agent_instance else "助手"

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
    
    try:
        agent_loop = await get_agent_loop(request.agent_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ChatAPI][{request_id}] Failed to get agent loop: {e}")
        raise HTTPException(status_code=500, detail="初始化对话代理失败，请稍后重试。")
    
    manager = agent_loop.sessions
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
            "assistant_message_id": assistant_message_id,
            "request_id": request_id,
        },
    )

    queue: asyncio.Queue = asyncio.Queue()
    final_response = {"content": None}
    execution_steps: list[dict] = []
    content_state = {"content": ""}

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
        on_step_start_hook=lambda step: logger.info(
            f"[ChatAPI] Added step: id={step['id']}, type={step['type']}, title={step['title']}, total steps: {len(execution_steps)}"
        ),
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
                    cleaned_content = clean_message_content(final_response["content"] or "")
                    provider_error = final_response.get("metadata", {}).get("_provider_error")
                    if cleaned_content:
                        yield _sse_event(
                            _build_chat_stream_event(
                                "agent_done",
                                content=cleaned_content,
                                provider_error=provider_error,
                                agent_id=agent_id,
                                agent_name=agent_name,
                                turn_id=turn_id,
                                message_id=assistant_message_id,
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
                            )
                        )
                    content_to_save = cleaned_content

                    if existing_msg_idx >= 0:
                        if content_to_save:
                            session.messages[existing_msg_idx]["content"] = content_to_save
                        if exec_steps_to_save:
                            session.messages[existing_msg_idx]["execution_steps"] = exec_steps_to_save
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
    
    all_agents = [a.id for a in agent_manager.get_all_agents()]
    
    parsed_mentions = parse_agent_mentions(request.content, all_agents)
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
        elif all_agents:
            agents_to_respond = [all_agents[0]]
            logger.info(f"[ChatAPI][{request_id}] Team mode without mentions, using first agent: {agents_to_respond}")
    else:
        default_agent = agent_manager.get_default_agent()
        if default_agent:
            agents_to_respond = [default_agent.id]
            logger.info(f"[ChatAPI][{request_id}] Using default agent: {agents_to_respond}")
    
    if not agents_to_respond:
        if all_agents:
            agents_to_respond = [all_agents[0]]

    queue: asyncio.Queue = asyncio.Queue()
    all_responses: List[dict] = []
    
    originally_mentioned = set(agents_to_respond.copy())
    
    conversation_contexts: Dict[str, ConversationContext] = {}
    for agent_id in originally_mentioned:
        agent_instance = agent_manager.get_agent(agent_id)
        agent_name = agent_instance.name if agent_instance else agent_id
        conversation_contexts[agent_id] = build_conversation_context(
            conversation_type=ConversationType.USER_TO_AGENT,
            source_id="user",
            source_name="用户",
            target_id=agent_id,
            target_name=agent_name,
            trigger_message=request.content,
        )
        logger.info(f"[ChatAPI][{request_id}] Created user_to_agent context for {agent_name}")

    async def process_agent_response(
        agent_id: str, 
        agent_index: int, 
        conversation_ctx: ConversationContext
    ):
        """Process response from a single agent with conversation context."""
        try:
            agent_loop = await get_agent_loop_with_session_manager(agent_id, team_session_manager)
            agent_instance = agent_manager.get_agent(agent_id)
            agent_name = agent_instance.name if agent_instance else agent_id
            turn_id = str(uuid.uuid4())[:8]
            assistant_message_id = str(uuid.uuid4())[:8]
            
            execution_steps: list[dict] = []
            content_state = {"content": ""}

            def store_message_tool_content(content: str) -> None:
                content_state["content"] = content
                logger.info(f"[ChatAPI][{request_id}] Extracted content from message tool (on_tool_start): {content[:100]}...")

            await _queue_chat_stream_event(
                queue,
                "agent_start",
                agent_id=agent_id,
                agent_name=agent_name,
                agent_index=agent_index,
                turn_id=turn_id,
                message_id=assistant_message_id,
            )

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
            )

            speaking_to = conversation_ctx.get_speaking_to()
            conv_type = conversation_ctx.conversation_type.value
            
            logger.info(f"[ChatAPI][{request_id}] Agent {agent_name} speaking_to={speaking_to}, conversation_type={conv_type}")
            
            if conversation_ctx.conversation_type == ConversationType.AGENT_TO_AGENT:
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

            response = await agent_loop.process_message(
                msg,
                session_key=session_key,
                **callbacks,
                speaking_to=speaking_to,
                conversation_type=conv_type,
            )
            
            response_content = response.content if response else None
            # Use the latest streamed content if response.content is empty.
            # This handles cases where the agent uses tools like 'message' to send content
            final_content = response_content if response_content else content_state["content"]
            # Clean the content before sending to frontend
            final_content = clean_message_content(final_content)
            
            logger.info(f"[ChatAPI][{request_id}] Agent {agent_id} response: response={response is not None}, response_content={response_content[:50] if response_content else None}, streamed_content={content_state['content'][:50] if content_state['content'] else None}, final_content={final_content[:50] if final_content else None}")
            
            # Only send agent_done event if there's actual content to display
            if final_content:
                memory_sources = []
                memory_recall = {}
                if response and response.metadata:
                    memory_sources = list(response.metadata.get("_memory_sources") or [])
                    memory_recall = dict(response.metadata.get("_memory_recall") or {})
                all_responses.append({
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "content": final_content,
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
                    content=final_content,
                    turn_id=turn_id,
                    message_id=assistant_message_id,
                    execution_steps=sanitize_execution_steps(execution_steps),
                    memory_sources=memory_sources,
                    memory_recall=memory_recall,
                )
            else:
                logger.info(f"[ChatAPI][{request_id}] Agent {agent_id} completed with empty content, skipping agent_done event")
            
        except asyncio.CancelledError:
            await _queue_chat_stream_event(
                queue,
                "agent_stopped",
                agent_id=agent_id,
                agent_name=agent_manager.get_agent(agent_id).name if agent_manager.get_agent(agent_id) else agent_id,
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
                agent_name=agent_manager.get_agent(agent_id).name if agent_manager.get_agent(agent_id) else agent_id,
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
                agent_instance = agent_manager.get_agent(agent_id)
                agent_name = agent_instance.name if agent_instance else agent_id
                source_id = last_speaking_agent.get(agent_id, "user")
                if source_id == "user":
                    source_name = "用户"
                else:
                    source_agent = agent_manager.get_agent(source_id)
                    source_name = source_agent.name if source_agent else source_id
                
                conv_ctx = build_conversation_context(
                    conversation_type=ConversationType.AGENT_TO_AGENT,
                    source_id=source_id,
                    source_name=source_name,
                    target_id=agent_id,
                    target_name=agent_name,
                    trigger_message=request.content,
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
                            "turn_id": item.get("turn_id"),
                            "message_id": item.get("message_id"),
                            "execution_steps": sanitize_execution_steps(item.get("execution_steps", [])),
                            "memory_sources": item.get("memory_sources", []),
                            "memory_recall": item.get("memory_recall", {}),
                        }
                        if resp["content"]:
                            content_to_save = clean_message_content(resp["content"])
                            if content_to_save:
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
                                    session.messages[existing_msg_idx].setdefault("metadata", {}).update(metadata)
                                else:
                                    session.add_message(
                                        "assistant",
                                        content_to_save,
                                        dedup=True,
                                        message_id=resp["message_id"],
                                        execution_steps=resp["execution_steps"],
                                        metadata=metadata,
                                    )
                                logger.info(f"[ChatAPI][{request_id}] Message saved. Session messages count: {len(session.messages)}")
                        all_responses.append(resp)
                        sanitized_item = dict(item)
                        sanitized_item["execution_steps"] = resp["execution_steps"]
                        yield _sse_event(sanitized_item)
                        
                        if resp["content"]:
                            logger.info(f"[ChatAPI][{request_id}] Checking for @mentions in content from {resp['agent_id']}: {resp['content'][:100]}...")
                            mentioned_agents = parse_agent_mentions(resp["content"], all_agents)
                            logger.info(f"[ChatAPI][{request_id}] Found mentioned agents: {mentioned_agents}")
                            new_agents_to_respond = [a for a in mentioned_agents if a != resp['agent_id'] and a not in active_tasks]
                            logger.info(f"[ChatAPI][{request_id}] New agents to respond (after filtering): {new_agents_to_respond}")
                            
                            if new_agents_to_respond:
                                logger.info(f"[ChatAPI][{request_id}] Agent {resp['agent_id']} mentioned agents: {new_agents_to_respond}")
                                for a in new_agents_to_respond:
                                    mention_triggered_agents.add(a)
                                    last_speaking_agent[a] = resp["agent_id"]
                                    
                                    pending_again = a in processed_agents and a not in agents_to_respond[current_idx + 1:]
                                    if a not in agents_to_respond or pending_again:
                                        agents_to_respond.append(a)
                                        logger.info(
                                            f"[ChatAPI][{request_id}] Added {a} to agents_to_respond, "
                                            f"requeued={pending_again}, new total: {len(agents_to_respond)}"
                                        )
                                    
                                    target_agent = agent_manager.get_agent(a)
                                    target_name = target_agent.name if target_agent else a
                                    new_conv_ctx = build_conversation_context(
                                        conversation_type=ConversationType.AGENT_TO_AGENT,
                                        source_id=resp["agent_id"],
                                        source_name=resp["agent_name"],
                                        target_id=a,
                                        target_name=target_name,
                                        trigger_message=(
                                            extract_agent_mention_payload(
                                                resp["content"],
                                                target_agent_id=a,
                                                target_agent_name=target_name,
                                            )
                                            or resp["content"]
                                        ),
                                    )
                                    conversation_contexts[a] = new_conv_ctx
                                    logger.info(f"[ChatAPI][{request_id}] Created agent_to_agent context: {resp['agent_name']} -> {target_name}")
                                
                                total_agents = len(agents_to_respond)
                                
                                for new_agent_id in new_agents_to_respond:
                                    new_agent = agent_manager.get_agent(new_agent_id)
                                    if new_agent:
                                        yield _sse_event(
                                            _build_chat_stream_event(
                                                "agent_mentioned",
                                                agent_id=new_agent_id,
                                                agent_name=new_agent.name,
                                                mentioned_by=resp["agent_id"],
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


@router.get("/chat/health")
async def chat_health_check():
    """Health check endpoint for chat service."""
    config = get_cached_config()
    provider_config = config.get_provider() if config else None
    
    return {
        "status": "healthy",
        "provider_configured": provider_config is not None and provider_config.api_key is not None,
        "active_streams": len(get_stream_manager()._streams),
        "timestamp": datetime.now().isoformat()
    }


def _validate_chat_request(request: StreamRequest) -> None:
    """Validate chat request parameters.
    
    Raises HTTPException if validation fails.
    """
    if not request.content or not request.content.strip():
        raise HTTPException(status_code=400, detail="Content is required")
    
    from horbot.agent.manager import get_agent_manager
    
    agent_manager = get_agent_manager()
    
    if request.agent_id:
        agent = agent_manager.get_agent(request.agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{request.agent_id}' not found")
    
    if request.group_chat and request.mentioned_agents:
        for agent_id in request.mentioned_agents:
            if not agent_manager.get_agent(agent_id):
                raise HTTPException(status_code=404, detail=f"Mentioned agent '{agent_id}' not found")
    
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


class StopRequest(BaseModel):
    request_id: str


@router.post("/chat/stop")
async def stop_chat_generation(request: StopRequest):
    """Stop an ongoing chat generation."""
    request_id = request.request_id
    stream_manager = get_stream_manager()

    if not stream_manager.exists(request_id):
        logger.info(f"[ChatAPI][{request_id}] Stop requested for inactive stream")
        return {"status": "success", "message": "Request already completed"}

    success = await stream_manager.cancel(request_id)
    if success:
        return {"status": "success", "message": "Stop signal sent"}

    logger.info(f"[ChatAPI][{request_id}] Stop requested after stream completed")
    return {"status": "success", "message": "Request already completed"}


@router.post("/chat/confirm")
async def confirm_tool_execution(request: ConfirmRequest):
    """Confirm or cancel a pending tool execution."""
    session_manager = get_session_manager()
    session = session_manager.get_or_create(request.session_key)
    
    # Get pending confirmations from session
    pending_confirmations = getattr(session, '_pending_confirmations', {})
    
    if request.confirmation_id not in pending_confirmations:
        raise HTTPException(status_code=404, detail="Confirmation not found or expired")
    
    conf = pending_confirmations.pop(request.confirmation_id)
    
    if request.action == "cancel":
        # Save session and return cancellation message
        session_manager.save(session)
        return {
            "status": "cancelled",
            "message": f"Tool `{conf['tool_name']}` execution cancelled.",
            "tool_name": conf["tool_name"]
        }
    
    if request.action == "confirm":
        # Get agent loop to execute the tool
        agent_loop = await get_agent_loop()
        
        # Execute the tool (using execute_confirmed to bypass permission check)
        try:
            result = await agent_loop.tools.execute_confirmed(conf["tool_name"], conf["arguments"])
            
            # Add tool result to messages
            messages = conf["messages"]
            from horbot.agent.context import ContextBuilder
            context = ContextBuilder(Path(session_manager.workspace))
            messages = context.add_tool_result(
                messages, conf["tool_call_id"], conf["tool_name"], result
            )
            
            # Continue the conversation
            final_content, _, all_msgs, new_confirmations = await agent_loop._run_agent_loop(
                messages, pending_confirmations=pending_confirmations
            )
            
            # Update session with new confirmations
            if new_confirmations:
                session._pending_confirmations = new_confirmations
            
            # Save messages to session
            for msg in all_msgs[len(messages):]:
                if msg.get("role") == "assistant":
                    session.add_message("assistant", msg.get("content", ""), dedup=True)
            
            session_manager.save(session)
            
            return {
                "status": "confirmed",
                "result": result,
                "final_content": final_content,
                "tool_name": conf["tool_name"]
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Tool execution failed: {str(e)}")
    
    raise HTTPException(status_code=400, detail="Invalid action. Use 'confirm' or 'cancel'.")


class PlanConfirmRequest(BaseModel):
    plan_id: str
    session_key: str = "default"


@router.post("/plan/{plan_id}/confirm")
async def confirm_plan(plan_id: str, request: PlanConfirmRequest):
    """Confirm an execution plan and start execution."""
    from horbot.agent.planner import get_plan_storage
    from fastapi.responses import StreamingResponse
    import json
    import logging
    
    logger = logging.getLogger("horbot.api")
    logger.info("confirm_plan called: plan_id={}, session_key={}", plan_id, request.session_key)
    
    storage = get_plan_storage()
    
    agent_loop = await get_agent_loop()
    
    # Get active plan from agent loop
    plan_dict = agent_loop.get_active_plan(request.session_key)
    if not plan_dict or plan_dict["id"] != plan_id:
        logger.warning("Plan not found or not active: plan_id={}, session_key={}", plan_id, request.session_key)
        raise HTTPException(status_code=404, detail="Plan not found or not active")
    
    storage.update_plan_status(plan_id, "confirmed")
    
    # Create a queue for SSE events
    queue = asyncio.Queue()
    
    # Execute plan and stream progress
    async def execute_and_stream():
        async def on_subtask_start(plan_id: str, subtask_id: str, title: str):
            await queue.put({
                "event": "subtask_start",
                "plan_id": plan_id,
                "subtask_id": subtask_id,
                "title": title
            })
        
        async def on_subtask_complete(plan_id: str, subtask_id: str, status: str, result: str, execution_time: float = 0, logs: list = None, input_tokens: int = 0, output_tokens: int = 0):
            await queue.put({
                "event": "subtask_complete",
                "plan_id": plan_id,
                "subtask_id": subtask_id,
                "status": status,
                "result": result,
                "execution_time": execution_time,
                "logs": logs or [],
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            })
        
        try:
            logger.info("Calling execute_plan_by_id: plan_id={}, session_key={}", plan_id, request.session_key)
            result = await agent_loop.execute_plan_by_id(
                plan_id=plan_id,
                session_key=request.session_key,
                on_subtask_start=on_subtask_start,
                on_subtask_complete=on_subtask_complete,
            )
            
            logger.info("execute_plan_by_id completed: plan_id={}, result={}", plan_id, result is not None)
            
            # Send final result
            if result:
                await queue.put({
                    "event": "plan_complete",
                    "content": result.content
                })
            
            await queue.put({"event": "done"})
        except Exception as e:
            logger.error("Error in execute_and_stream: plan_id={}, error={}", plan_id, str(e))
            await queue.put({
                "event": "error",
                "content": str(e)
            })
    
    # Start execution in background
    asyncio.create_task(execute_and_stream())
    
    # Return SSE stream
    async def event_generator():
        try:
            event_count = 0
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=30.0)
                    event = item.get("event")
                    event_count += 1
                    
                    logger.info("SSE event #{}: {}", event_count, event)
                    
                    if event == "done":
                        yield f"data: {json.dumps({'event': 'done'}, ensure_ascii=False)}\n\n"
                        break
                    elif event == "error":
                        yield f"data: {json.dumps({'event': 'error', 'content': item.get('content')}, ensure_ascii=False)}\n\n"
                        break
                    elif event == "subtask_start":
                        yield f"data: {json.dumps({'event': 'subtask_start', 'plan_id': item.get('plan_id'), 'subtask_id': item.get('subtask_id'), 'title': item.get('title')}, ensure_ascii=False)}\n\n"
                    elif event == 'subtask_complete':
                        yield f"data: {json.dumps({'event': 'subtask_complete', 'plan_id': item.get('plan_id'), 'subtask_id': item.get('subtask_id'), 'status': item.get('status'), 'result': item.get('result'), 'execution_time': item.get('execution_time'), 'logs': item.get('logs'), 'input_tokens': item.get('input_tokens', 0), 'output_tokens': item.get('output_tokens', 0)}, ensure_ascii=False)}\n\n"
                    elif event == "plan_complete":
                        yield f"data: {json.dumps({'event': 'plan_complete', 'content': item.get('content')}, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    # Send keep-alive
                    logger.debug("SSE keep-alive")
                    yield f": keep-alive\n\n"
        except asyncio.CancelledError:
            logger.info("SSE stream cancelled")
            yield f"data: {json.dumps({'event': 'stopped', 'content': 'Generation cancelled'}, ensure_ascii=False)}\n\n"
        
        logger.info("SSE stream finished, total events: {}", event_count)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/plan/{plan_id}/cancel")
async def cancel_plan(plan_id: str, request: PlanConfirmRequest):
    """Cancel an execution plan."""
    from horbot.agent.planner import get_plan_storage
    
    storage = get_plan_storage()
    
    # Try to load from storage first
    plan = storage.load_plan(plan_id)
    
    # If not in storage, check active plans in agent loop
    if not plan:
        agent_loop = await get_agent_loop()
        plan_dict = agent_loop.get_active_plan(request.session_key)
        if plan_dict and plan_dict["id"] == plan_id:
            # Create a minimal plan object for status update
            plan = type('obj', (object,), {'status': plan_dict['status']})()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    if plan.status not in ("pending", "confirmed"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel plan in {plan.status} status")
    
    storage.update_plan_status(plan_id, "cancelled")
    
    # Cancel all running subagents for this session
    agent_loop = await get_agent_loop()
    cancelled_subagents = await agent_loop.subagents.cancel_by_session(request.session_key)
    
    return {
        "status": "cancelled",
        "message": f"计划已取消，已停止 {cancelled_subagents} 个子代理" if cancelled_subagents > 0 else "计划已取消",
        "plan_id": plan_id,
        "cancelled_subagents": cancelled_subagents
    }


@router.post("/plan/{plan_id}/stop")
async def stop_plan_execution(plan_id: str, request: PlanConfirmRequest):
    """Stop the execution of a running plan."""
    agent_loop = await get_agent_loop()
    
    # Log the stop request
    import logging
    logger = logging.getLogger("horbot.api")
    logger.info("Stop plan execution request: plan_id={}, session_key={}", plan_id, request.session_key)
    
    # Stop the plan execution
    success = agent_loop.stop_plan_execution(request.session_key)
    
    logger.info("Stop plan execution result: success={}", success)
    
    if success:
        from horbot.agent.planner import get_plan_storage
        storage = get_plan_storage()
        storage.update_plan_status(plan_id, "stopped")
        
        return {
            "status": "stopped",
            "message": "计划执行已停止",
            "plan_id": plan_id,
        }
    else:
        logger.error("Failed to stop plan execution: plan_id={}, session_key={}", plan_id, request.session_key)
        raise HTTPException(status_code=400, detail="Failed to stop plan execution")


@router.get("/plan/{plan_id}/logs")
async def get_plan_execution_logs(plan_id: str):
    """Get execution logs for a plan."""
    from horbot.agent.planner import get_plan_storage
    
    storage = get_plan_storage()
    all_logs = storage.load_all_execution_logs(plan_id)
    
    return {
        "plan_id": plan_id,
        "logs": all_logs,
    }


@router.get("/plan/{plan_id}")
async def get_plan(plan_id: str):
    """Get plan details."""
    from horbot.agent.planner import get_plan_storage
    
    storage = get_plan_storage()
    plan = storage.load_plan(plan_id)
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    return {
        "id": plan.id,
        "title": plan.title,
        "description": plan.description,
        "status": plan.status,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
        "session_key": plan.session_key,
        "plan_type": plan.plan_type,
        "content": plan.content,
        "spec_content": plan.spec_content,
        "tasks_content": plan.tasks_content,
        "checklist_content": plan.checklist_content,
        "subtasks": [
            {
                "id": st.id,
                "title": st.title,
                "description": st.description,
                "status": st.status,
                "tools": st.tools,
            }
            for st in plan.subtasks
        ],
        "spec": {
            "why": plan.spec.why if plan.spec else "",
            "what_changes": plan.spec.what_changes if plan.spec else [],
            "impact": plan.spec.impact if plan.spec else {},
        },
        "checklist": {
            "items": plan.checklist.items if plan.checklist else [],
        },
    }


@router.get("/plans")
async def list_plans(session_key: str = None):
    """List all plans."""
    from horbot.agent.planner import get_plan_storage
    
    storage = get_plan_storage()
    plans = storage.list_plans(session_key)
    
    return {"plans": plans}


@router.get("/status")
async def get_system_status():
    """Get system status."""
    return _build_system_status_payload()


@router.get("/environment")
async def get_environment_info():
    """Get runtime environment information."""
    import platform
    import sys
    import psutil
    
    config = get_cached_config()
    
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    os_info = {
        "name": platform.system(),
        "version": platform.version(),
        "platform": platform.platform(),
    }
    
    dependencies = []
    package_names = ["litellm", "fastapi", "pydantic", "loguru", "psutil", "httpx", "aiofiles"]
    
    for pkg_name in package_names:
        try:
            import importlib.metadata
            version = importlib.metadata.version(pkg_name)
            dependencies.append({"name": pkg_name, "version": version})
        except Exception:
            dependencies.append({"name": pkg_name, "version": "not installed"})
    
    try:
        disk = psutil.disk_usage('/')
        disk_info = {
            "total_gb": round(disk.total / (1024 ** 3), 2),
            "used_gb": round(disk.used / (1024 ** 3), 2),
            "free_gb": round(disk.free / (1024 ** 3), 2),
            "usage_percent": disk.percent,
        }
    except Exception:
        disk_info = {
            "total_gb": 0,
            "used_gb": 0,
            "free_gb": 0,
            "usage_percent": 0,
        }
    
    try:
        memory = psutil.virtual_memory()
        memory_info = {
            "total_gb": round(memory.total / (1024 ** 3), 2),
            "used_gb": round(memory.used / (1024 ** 3), 2),
            "available_gb": round(memory.available / (1024 ** 3), 2),
            "usage_percent": memory.percent,
        }
    except Exception:
        memory_info = {
            "total_gb": 0,
            "used_gb": 0,
            "available_gb": 0,
            "usage_percent": 0,
        }
    
    try:
        cpu_info = {
            "count": psutil.cpu_count(logical=True),
            "percent": psutil.cpu_percent(interval=0.1),
        }
    except Exception:
        cpu_info = {
            "count": 0,
            "percent": 0,
        }
    
    workspace_path = Path(config.workspace_path)
    workspace_info = {
        "path": str(workspace_path),
        "exists": workspace_path.exists(),
        "files_count": 0,
    }
    
    if workspace_path.exists():
        try:
            files_count = sum(1 for _ in workspace_path.rglob("*") if _.is_file())
            workspace_info["files_count"] = files_count
        except Exception:
            pass
    
    return {
        "python_version": python_version,
        "os_info": os_info,
        "dependencies": dependencies,
        "disk": disk_info,
        "memory": memory_info,
        "cpu": cpu_info,
        "workspace": workspace_info,
    }

@router.get("/api-metrics")
async def get_api_metrics(lines: int = 100):
    """Get API request metrics from api_requests.log."""
    from pathlib import Path
    import json
    
    config = get_cached_config()
    log_dir = Path(config.workspace_path) / "logs"
    log_file = log_dir / "api_requests.log"
    
    metrics = {
        "recent_requests": [],
        "total_count": 0,
        "avg_process_time_ms": 0,
        "error_count": 0,
    }
    
    if not log_file.exists():
        return metrics
        
    try:
        content = log_file.read_text(encoding="utf-8")
        log_lines = [line for line in content.strip().split("\n") if line.strip()]
        
        # We only take the last `lines` entries
        recent_lines = log_lines[-lines:]
        total_time = 0
        
        import re
        # Example format: 2026-03-27 12:34:56.789 | INFO     | API Request: GET http://localhost:8000/api/status - 200 (15.23ms) - Client: 127.0.0.1
        # It's better to parse the structured log if possible, but loguru outputs plain text with our format.
        # Format we used: "API Request: {method} {url} - {status_code} ({process_time_ms}ms) - Client: {client_ip}"
        
        pattern = re.compile(r"API Request:\s+(?P<method>[A-Z]+)\s+(?P<url>\S+)\s+-\s+(?P<status_code>\d+|None)\s+\((?P<time_ms>[\d.]+)ms\)\s+-\s+Client:\s+(?P<client_ip>\S+)")
        timestamp_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})")
        
        for line in recent_lines:
            ts_match = timestamp_pattern.match(line)
            req_match = pattern.search(line)
            
            if req_match:
                ts = ts_match.group(1) if ts_match else ""
                status_code_str = req_match.group("status_code")
                status_code = int(status_code_str) if status_code_str != "None" else 500
                time_ms = float(req_match.group("time_ms"))
                
                if status_code >= 400:
                    metrics["error_count"] += 1
                    
                total_time += time_ms
                metrics["recent_requests"].append({
                    "timestamp": ts,
                    "method": req_match.group("method"),
                    "url": req_match.group("url"),
                    "status_code": status_code,
                    "process_time_ms": time_ms,
                    "client_ip": req_match.group("client_ip")
                })
                
        metrics["total_count"] = len(metrics["recent_requests"])
        if metrics["total_count"] > 0:
            metrics["avg_process_time_ms"] = round(total_time / metrics["total_count"], 2)
            
        # Reverse to show newest first
        metrics["recent_requests"].reverse()
        
    except Exception as e:
        logger.error(f"Failed to read api_requests.log: {e}")
        
    return metrics

@router.get("/logs")
async def get_logs(lines: int = 100, level: str = None):
    """Get recent logs."""
    from pathlib import Path
    import re
    from horbot.utils.paths import get_logs_dir
    
    log_dir = get_logs_dir()
    
    logs = []
    if log_dir.exists():
        log_files = sorted(log_dir.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
        if log_files:
            try:
                content = log_files[0].read_text(encoding="utf-8")
                log_lines = content.strip().split("\n")[-lines:]
                
                for line in log_lines:
                    if not line.strip():
                        continue
                    
                    log_entry = {"raw": line}
                    
                    timestamp_match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
                    if timestamp_match:
                        log_entry["timestamp"] = timestamp_match.group(1)
                    
                    level_match = re.search(r"\| (DEBUG|INFO|WARNING|ERROR|CRITICAL) \|", line)
                    if level_match:
                        log_entry["level"] = level_match.group(1)
                    else:
                        log_entry["level"] = "INFO"
                    
                    if level and log_entry.get("level") != level:
                        continue
                    
                    logs.append(log_entry)
            except Exception as e:
                logs.append({"raw": f"Error reading log file: {e}", "level": "ERROR"})
    
    return {"logs": logs, "total": len(logs)}

@router.get("/channels")
async def get_channels():
    """Get all channels status."""
    config = get_cached_config()
    data = config.channels.model_dump(by_alias=True)
    data.pop("endpoints", None)
    return data


@router.get("/gateway/diagnostics")
async def get_gateway_diagnostics():
    """Diagnose connection status for all channel gateways."""
    import httpx
    import time
    
    config = get_cached_config()
    channels_config = config.channels
    results = []
    
    async def test_telegram() -> dict:
        """Test Telegram bot connection."""
        tg_config = channels_config.telegram
        if not tg_config.enabled:
            return {"name": "telegram", "enabled": False, "status": "disabled", "latency_ms": 0, "error": None}
        
        if not tg_config.token:
            return {"name": "telegram", "enabled": True, "status": "error", "latency_ms": 0, "error": "Token not configured"}
        
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"https://api.telegram.org/bot{tg_config.token}/getMe",
                    proxy=tg_config.proxy
                )
                latency = int((time.time() - start) * 1000)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        return {"name": "telegram", "enabled": True, "status": "ok", "latency_ms": latency, "error": None}
                    else:
                        return {"name": "telegram", "enabled": True, "status": "error", "latency_ms": latency, "error": data.get("description", "Unknown error")}
                else:
                    return {"name": "telegram", "enabled": True, "status": "error", "latency_ms": latency, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"name": "telegram", "enabled": True, "status": "error", "latency_ms": 0, "error": str(e)}
    
    async def test_discord() -> dict:
        """Test Discord bot connection."""
        dc_config = channels_config.discord
        if not dc_config.enabled:
            return {"name": "discord", "enabled": False, "status": "disabled", "latency_ms": 0, "error": None}
        
        if not dc_config.token:
            return {"name": "discord", "enabled": True, "status": "error", "latency_ms": 0, "error": "Token not configured"}
        
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://discord.com/api/v10/users/@me",
                    headers={"Authorization": f"Bot {dc_config.token}"}
                )
                latency = int((time.time() - start) * 1000)
                
                if response.status_code == 200:
                    return {"name": "discord", "enabled": True, "status": "ok", "latency_ms": latency, "error": None}
                elif response.status_code == 401:
                    return {"name": "discord", "enabled": True, "status": "error", "latency_ms": latency, "error": "Invalid token"}
                else:
                    return {"name": "discord", "enabled": True, "status": "error", "latency_ms": latency, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"name": "discord", "enabled": True, "status": "error", "latency_ms": 0, "error": str(e)}
    
    async def test_whatsapp() -> dict:
        """Test WhatsApp bridge connection."""
        wa_config = channels_config.whatsapp
        if not wa_config.enabled:
            return {"name": "whatsapp", "enabled": False, "status": "disabled", "latency_ms": 0, "error": None}
        
        start = time.time()
        try:
            bridge_url = wa_config.bridge_url.replace("ws://", "http://").replace("wss://", "https://")
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {}
                if wa_config.bridge_token:
                    headers["Authorization"] = f"Bearer {wa_config.bridge_token}"
                
                response = await client.get(f"{bridge_url}/health", headers=headers)
                latency = int((time.time() - start) * 1000)
                
                if response.status_code == 200:
                    return {"name": "whatsapp", "enabled": True, "status": "ok", "latency_ms": latency, "error": None}
                else:
                    return {"name": "whatsapp", "enabled": True, "status": "error", "latency_ms": latency, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"name": "whatsapp", "enabled": True, "status": "error", "latency_ms": 0, "error": str(e)}
    
    async def test_feishu() -> dict:
        """Test Feishu API connection."""
        fs_config = channels_config.feishu
        if not fs_config.enabled:
            return {"name": "feishu", "enabled": False, "status": "disabled", "latency_ms": 0, "error": None}
        
        if not fs_config.app_id or not fs_config.app_secret:
            return {"name": "feishu", "enabled": True, "status": "error", "latency_ms": 0, "error": "App ID or Secret not configured"}
        
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0, verify=not fs_config.skip_ssl_verify) as client:
                response = await client.post(
                    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                    json={"app_id": fs_config.app_id, "app_secret": fs_config.app_secret}
                )
                latency = int((time.time() - start) * 1000)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 0:
                        return {"name": "feishu", "enabled": True, "status": "ok", "latency_ms": latency, "error": None}
                    else:
                        return {"name": "feishu", "enabled": True, "status": "error", "latency_ms": latency, "error": data.get("msg", "Unknown error")}
                else:
                    return {"name": "feishu", "enabled": True, "status": "error", "latency_ms": latency, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"name": "feishu", "enabled": True, "status": "error", "latency_ms": 0, "error": str(e)}
    
    async def test_dingtalk() -> dict:
        """Test DingTalk API connection."""
        dt_config = channels_config.dingtalk
        if not dt_config.enabled:
            return {"name": "dingtalk", "enabled": False, "status": "disabled", "latency_ms": 0, "error": None}
        
        if not dt_config.client_id or not dt_config.client_secret:
            return {"name": "dingtalk", "enabled": True, "status": "error", "latency_ms": 0, "error": "Client ID or Secret not configured"}
        
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://api.dingtalk.com/v1.0/oauth2/accessToken",
                    json={"appKey": dt_config.client_id, "appSecret": dt_config.client_secret}
                )
                latency = int((time.time() - start) * 1000)
                
                if response.status_code == 200:
                    data = response.json()
                    if "accessToken" in data:
                        return {"name": "dingtalk", "enabled": True, "status": "ok", "latency_ms": latency, "error": None}
                    else:
                        return {"name": "dingtalk", "enabled": True, "status": "error", "latency_ms": latency, "error": data.get("message", "Unknown error")}
                else:
                    return {"name": "dingtalk", "enabled": True, "status": "error", "latency_ms": latency, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"name": "dingtalk", "enabled": True, "status": "error", "latency_ms": 0, "error": str(e)}
    
    async def test_slack() -> dict:
        """Test Slack API connection."""
        slack_config = channels_config.slack
        if not slack_config.enabled:
            return {"name": "slack", "enabled": False, "status": "disabled", "latency_ms": 0, "error": None}
        
        if not slack_config.bot_token:
            return {"name": "slack", "enabled": True, "status": "error", "latency_ms": 0, "error": "Bot token not configured"}
        
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://slack.com/api/auth.test",
                    headers={"Authorization": f"Bearer {slack_config.bot_token}"}
                )
                latency = int((time.time() - start) * 1000)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        return {"name": "slack", "enabled": True, "status": "ok", "latency_ms": latency, "error": None}
                    else:
                        return {"name": "slack", "enabled": True, "status": "error", "latency_ms": latency, "error": data.get("error", "Unknown error")}
                else:
                    return {"name": "slack", "enabled": True, "status": "error", "latency_ms": latency, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"name": "slack", "enabled": True, "status": "error", "latency_ms": 0, "error": str(e)}
    
    async def test_email() -> dict:
        """Test Email IMAP connection."""
        email_config = channels_config.email
        if not email_config.enabled:
            return {"name": "email", "enabled": False, "status": "disabled", "latency_ms": 0, "error": None}
        
        if not email_config.imap_host or not email_config.imap_username:
            return {"name": "email", "enabled": True, "status": "error", "latency_ms": 0, "error": "IMAP host or username not configured"}
        
        start = time.time()
        try:
            import imaplib
            import socket
            
            if email_config.imap_use_ssl:
                imap = imaplib.IMAP4_SSL(email_config.imap_host, email_config.imap_port, timeout=10)
            else:
                imap = imaplib.IMAP4(email_config.imap_host, email_config.imap_port)
                imap.starttls()
            
            imap.login(email_config.imap_username, email_config.imap_password)
            latency = int((time.time() - start) * 1000)
            imap.logout()
            
            return {"name": "email", "enabled": True, "status": "ok", "latency_ms": latency, "error": None}
        except Exception as e:
            return {"name": "email", "enabled": True, "status": "error", "latency_ms": 0, "error": str(e)}
    
    async def test_matrix() -> dict:
        """Test Matrix connection."""
        mx_config = channels_config.matrix
        if not mx_config.enabled:
            return {"name": "matrix", "enabled": False, "status": "disabled", "latency_ms": 0, "error": None}
        
        if not mx_config.access_token or not mx_config.homeserver:
            return {"name": "matrix", "enabled": True, "status": "error", "latency_ms": 0, "error": "Access token or homeserver not configured"}
        
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{mx_config.homeserver}/_matrix/client/v3/account/whoami",
                    headers={"Authorization": f"Bearer {mx_config.access_token}"}
                )
                latency = int((time.time() - start) * 1000)
                
                if response.status_code == 200:
                    data = response.json()
                    if "user_id" in data:
                        return {"name": "matrix", "enabled": True, "status": "ok", "latency_ms": latency, "error": None}
                    else:
                        return {"name": "matrix", "enabled": True, "status": "error", "latency_ms": latency, "error": "Invalid response"}
                elif response.status_code == 401:
                    return {"name": "matrix", "enabled": True, "status": "error", "latency_ms": latency, "error": "Invalid access token"}
                else:
                    return {"name": "matrix", "enabled": True, "status": "error", "latency_ms": latency, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"name": "matrix", "enabled": True, "status": "error", "latency_ms": 0, "error": str(e)}
    
    async def test_mochat() -> dict:
        """Test Mochat connection."""
        mc_config = channels_config.mochat
        if not mc_config.enabled:
            return {"name": "mochat", "enabled": False, "status": "disabled", "latency_ms": 0, "error": None}
        
        if not mc_config.claw_token:
            return {"name": "mochat", "enabled": True, "status": "error", "latency_ms": 0, "error": "Claw token not configured"}
        
        start = time.time()
        try:
            base_url = mc_config.base_url or "https://mochat.io"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{base_url}/api/health",
                    headers={"Authorization": f"Bearer {mc_config.claw_token}"}
                )
                latency = int((time.time() - start) * 1000)
                
                if response.status_code == 200:
                    return {"name": "mochat", "enabled": True, "status": "ok", "latency_ms": latency, "error": None}
                elif response.status_code == 401:
                    return {"name": "mochat", "enabled": True, "status": "error", "latency_ms": latency, "error": "Invalid claw token"}
                else:
                    return {"name": "mochat", "enabled": True, "status": "error", "latency_ms": latency, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"name": "mochat", "enabled": True, "status": "error", "latency_ms": 0, "error": str(e)}
    
    async def test_qq() -> dict:
        """Test QQ bot connection."""
        qq_config = channels_config.qq
        if not qq_config.enabled:
            return {"name": "qq", "enabled": False, "status": "disabled", "latency_ms": 0, "error": None}
        
        if not qq_config.app_id or not qq_config.secret:
            return {"name": "qq", "enabled": True, "status": "error", "latency_ms": 0, "error": "App ID or Secret not configured"}
        
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://bots.qq.com/app/getAppAccessToken",
                    json={"appId": qq_config.app_id, "clientSecret": qq_config.secret}
                )
                latency = int((time.time() - start) * 1000)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 0:
                        return {"name": "qq", "enabled": True, "status": "ok", "latency_ms": latency, "error": None}
                    else:
                        return {"name": "qq", "enabled": True, "status": "error", "latency_ms": latency, "error": data.get("message", "Unknown error")}
                else:
                    return {"name": "qq", "enabled": True, "status": "error", "latency_ms": latency, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"name": "qq", "enabled": True, "status": "error", "latency_ms": 0, "error": str(e)}
    
    async def test_sharecrm() -> dict:
        """Test ShareCRM connection."""
        crm_config = channels_config.sharecrm
        if not crm_config.enabled:
            return {"name": "sharecrm", "enabled": False, "status": "disabled", "latency_ms": 0, "error": None}
        
        if not crm_config.app_id or not crm_config.app_secret:
            return {"name": "sharecrm", "enabled": True, "status": "error", "latency_ms": 0, "error": "App ID or Secret not configured"}
        
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{crm_config.gateway_base_url}/im-gateway/auth/token",
                    json={"appId": crm_config.app_id, "appSecret": crm_config.app_secret},
                    headers={"Content-Type": "application/json"},
                )
                latency = int((time.time() - start) * 1000)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 0 and data.get("data", {}).get("accessToken"):
                        return {"name": "sharecrm", "enabled": True, "status": "ok", "latency_ms": latency, "error": None}
                    else:
                        return {"name": "sharecrm", "enabled": True, "status": "error", "latency_ms": latency, "error": data.get("msg", "Unknown error")}
                else:
                    return {"name": "sharecrm", "enabled": True, "status": "error", "latency_ms": latency, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"name": "sharecrm", "enabled": True, "status": "error", "latency_ms": 0, "error": str(e)}
    
    results = await asyncio.gather(
        test_telegram(),
        test_discord(),
        test_whatsapp(),
        test_feishu(),
        test_dingtalk(),
        test_slack(),
        test_email(),
        test_matrix(),
        test_mochat(),
        test_qq(),
        test_sharecrm(),
    )
    
    # Calculate overall status
    enabled_channels = [r for r in results if r.get("enabled", False)]
    ok_count = sum(1 for r in enabled_channels if r.get("status") == "ok")
    error_count = sum(1 for r in enabled_channels if r.get("status") == "error")
    
    if not enabled_channels:
        overall_status = "healthy"  # No enabled channels is considered healthy
    elif error_count == 0:
        overall_status = "healthy"
    elif ok_count > 0:
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"
    
    return {
        "channels": list(results),
        "overall_status": overall_status,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

@router.get("/tasks")
async def get_tasks(cron_service: CronService = Depends(get_cron_service)):
    """Get all cron tasks."""
    jobs = cron_service.list_jobs(include_disabled=True)
    return {
        "tasks": [
            {
                "id": job.id,
                "name": job.name,
                "enabled": job.enabled,
                "schedule": {
                    "kind": job.schedule.kind,
                    "at_ms": job.schedule.at_ms,
                    "every_ms": job.schedule.every_ms,
                    "expr": job.schedule.expr,
                    "tz": job.schedule.tz
                },
                "payload": {
                    "kind": job.payload.kind,
                    "message": job.payload.message,
                    "deliver": job.payload.deliver,
                    "channel": job.payload.channel,
                    "to": job.payload.to,
                    "channels": [{"channel": c.channel, "to": c.to} for c in job.payload.channels] if job.payload.channels else None,
                    "notify": job.payload.notify,
                },
                "state": {
                    "next_run_at_ms": job.state.next_run_at_ms,
                    "last_run_at_ms": job.state.last_run_at_ms,
                    "last_status": job.state.last_status,
                    "last_error": job.state.last_error
                },
                "created_at_ms": job.created_at_ms,
                "updated_at_ms": job.updated_at_ms,
                "delete_after_run": job.delete_after_run
            }
            for job in jobs
        ]
    }

@router.post("/tasks")
async def add_task(
    request_data: Dict[str, Any],
    cron_service: CronService = Depends(get_cron_service)
):
    """Add a new task."""
    try:
        name = request_data.get("name")
        schedule_data = request_data.get("schedule")
        message = request_data.get("message")
        deliver = request_data.get("deliver", False)
        channel = request_data.get("channel")
        to = request_data.get("to")
        delete_after_run = request_data.get("delete_after_run", False)
        
        if not name or not schedule_data or not message:
            raise HTTPException(status_code=400, detail="Name, schedule, and message are required")
        
        schedule = CronSchedule(
            kind=schedule_data.get("kind"),
            at_ms=schedule_data.get("at_ms"),
            every_ms=schedule_data.get("every_ms"),
            expr=schedule_data.get("expr"),
            tz=schedule_data.get("tz")
        )
        
        job = cron_service.add_job(
            name=name,
            schedule=schedule,
            message=message,
            deliver=deliver,
            channel=channel,
            to=to,
            delete_after_run=delete_after_run
        )
        
        return {
            "id": job.id,
            "name": job.name,
            "enabled": job.enabled,
            "schedule": {
                "kind": job.schedule.kind,
                "at_ms": job.schedule.at_ms,
                "every_ms": job.schedule.every_ms,
                "expr": job.schedule.expr,
                "tz": job.schedule.tz
            },
            "payload": {
                "kind": job.payload.kind,
                "message": job.payload.message,
                "deliver": job.payload.deliver,
                "channel": job.payload.channel,
                "to": job.payload.to
            },
            "state": {
                "next_run_at_ms": job.state.next_run_at_ms,
                "last_run_at_ms": job.state.last_run_at_ms,
                "last_status": job.state.last_status,
                "last_error": job.state.last_error
            },
            "created_at_ms": job.created_at_ms,
            "updated_at_ms": job.updated_at_ms,
            "delete_after_run": job.delete_after_run
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    cron_service: CronService = Depends(get_cron_service)
):
    """Delete a task."""
    removed = cron_service.remove_job(task_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "success", "message": "Task deleted"}

@router.put("/tasks/{task_id}/enable")
async def enable_task(
    task_id: str,
    request_data: Dict[str, bool],
    cron_service: CronService = Depends(get_cron_service)
):
    """Enable or disable a task."""
    enabled = request_data.get("enabled", True)
    job = cron_service.enable_job(task_id, enabled)
    if not job:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "id": job.id,
        "name": job.name,
        "enabled": job.enabled
    }

@router.post("/tasks/{task_id}/run")
async def run_task(
    task_id: str,
    cron_service: CronService = Depends(get_cron_service)
):
    """Run a task manually."""
    result = await cron_service.run_job(task_id, force=True)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "success", "message": "Task run started"}

@router.get("/skills")
async def get_skills(agent_id: Optional[str] = None):
    """Get all skills."""
    from horbot.agent.skills import SkillsLoader
    
    _, workspace_path = _resolve_agent_workspace_for_request(agent_id)
    loader = SkillsLoader(workspace=workspace_path)
    
    skills = loader.list_skills(filter_unavailable=False, include_disabled=True)
    
    result = []
    for skill in skills:
        metadata = loader.get_skill_metadata(skill["name"]) or {}
        meta = loader._get_skill_meta(skill["name"])
        
        compat = meta.get("_compat", {}) if isinstance(meta, dict) else {}

        result.append({
            "name": skill["name"],
            "source": skill["source"],
            "path": skill["path"],
            "description": metadata.get("description", skill["name"]),
            "available": loader._check_requirements(meta),
            "enabled": skill.get("enabled", True),
            "always": meta.get("always", False) or metadata.get("always", False),
            "requires": meta.get("requires", {}),
            "schema": compat.get("canonical_schema", "horbot"),
            "schema_version": compat.get("canonical_schema_version", 1),
            "source_schema": compat.get("source_schema", "horbot"),
            "source_schema_version": compat.get("source_schema_version", 1),
            "normalized_from_legacy": bool(compat.get("normalized_from_legacy", False)),
            "install": meta.get("install", []) if isinstance(meta.get("install"), list) else [],
            "missing_requirements": loader._get_missing_requirements(meta) if not loader._check_requirements(meta) else None
        })
    
    return {"skills": result}

@router.get("/skills/{skill_name}")
async def get_skill_detail(skill_name: str, agent_id: Optional[str] = None):
    """Get skill detail."""
    from horbot.agent.skills import SkillsLoader
    
    _, workspace_path = _resolve_agent_workspace_for_request(agent_id)
    loader = SkillsLoader(workspace=workspace_path)
    
    content = loader.load_skill(skill_name)
    if not content:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    metadata = loader.get_skill_metadata(skill_name) or {}
    meta = loader._get_skill_meta(skill_name)
    
    compat = meta.get("_compat", {}) if isinstance(meta, dict) else {}

    return {
        "name": skill_name,
        "content": content,
        "metadata": metadata,
        "available": loader._check_requirements(meta),
        "always": meta.get("always", False) or metadata.get("always", False),
        "schema": compat.get("canonical_schema", "horbot"),
        "schema_version": compat.get("canonical_schema_version", 1),
        "source_schema": compat.get("source_schema", "horbot"),
        "source_schema_version": compat.get("source_schema_version", 1),
        "normalized_from_legacy": bool(compat.get("normalized_from_legacy", False))
    }

class SkillCreateRequest(BaseModel):
    name: str
    content: str

class SkillUpdateRequest(BaseModel):
    content: str

@router.post("/skills")
async def create_skill(request: SkillCreateRequest, agent_id: Optional[str] = None):
    """Create a new skill."""
    from horbot.agent.skills import SkillsLoader

    _, workspace_path = _resolve_agent_workspace_for_request(agent_id)
    loader = SkillsLoader(workspace=workspace_path)

    skills_dir = workspace_path / "skills"
    skill_dir = skills_dir / request.name
    skill_file = skill_dir / "SKILL.md"
    
    if skill_file.exists():
        raise HTTPException(status_code=409, detail=f"Skill '{request.name}' already exists")
    
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file.write_text(request.content)
    
    return {
        "name": request.name,
        "path": str(skill_file),
        "source": "user",
        "message": f"Skill '{request.name}' created successfully"
    }

@router.put("/skills/{skill_name}")
async def update_skill(skill_name: str, request: SkillUpdateRequest, agent_id: Optional[str] = None):
    """Update an existing skill."""
    from horbot.agent.skills import SkillsLoader
    
    _, workspace_path = _resolve_agent_workspace_for_request(agent_id)
    loader = SkillsLoader(workspace=workspace_path)
    
    skills = loader.list_skills(filter_unavailable=False)
    skill_info = next((s for s in skills if s["name"] == skill_name), None)
    
    if not skill_info:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
    
    if skill_info["source"] == "builtin":
        raise HTTPException(status_code=403, detail="Cannot modify builtin skills")
    
    skill_path = Path(skill_info["path"])
    skill_path.write_text(request.content)
    
    return {
        "name": skill_name,
        "path": str(skill_path),
        "message": f"Skill '{skill_name}' updated successfully"
    }

@router.delete("/skills/{skill_name}")
async def delete_skill(skill_name: str, agent_id: Optional[str] = None):
    """Delete a skill."""
    import shutil
    from horbot.agent.skills import SkillsLoader
    
    _, workspace_path = _resolve_agent_workspace_for_request(agent_id)
    loader = SkillsLoader(workspace=workspace_path)
    
    skills = loader.list_skills(filter_unavailable=False)
    skill_info = next((s for s in skills if s["name"] == skill_name), None)
    
    if not skill_info:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
    
    if skill_info["source"] == "builtin":
        raise HTTPException(status_code=403, detail="Cannot delete builtin skills")
    
    skill_path = Path(skill_info["path"])
    
    # If it's a directory structure, remove the whole directory
    if skill_path.name == "SKILL.md":
        skill_dir = skill_path.parent
        shutil.rmtree(skill_dir)
    else:
        # Legacy file structure
        skill_path.unlink()
    
    return {
        "name": skill_name,
        "message": f"Skill '{skill_name}' deleted successfully"
    }

@router.patch("/skills/{skill_name}/toggle")
async def toggle_skill(skill_name: str, agent_id: Optional[str] = None):
    """Toggle skill enabled status."""
    import re
    from horbot.agent.skills import SkillsLoader
    
    _, workspace_path = _resolve_agent_workspace_for_request(agent_id)
    loader = SkillsLoader(workspace=workspace_path)
    
    content = loader.load_skill(skill_name)
    if not content:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
    
    # Get current enabled status
    current_enabled = loader._get_skill_enabled(skill_name)
    new_enabled = not current_enabled
    
    # Update frontmatter
    if content.startswith("---"):
        # Has frontmatter - update enabled field
        match = re.match(r"^(---\n)(.*?)(\n---\n)(.*)", content, re.DOTALL)
        if match:
            frontmatter = match.group(2)
            body = match.group(4)
            
            # Update or add enabled field
            if "enabled:" in frontmatter:
                frontmatter = re.sub(r"enabled:\s*\S+", f"enabled: {str(new_enabled).lower()}", frontmatter)
            else:
                frontmatter += f"\nenabled: {str(new_enabled).lower()}"
            
            new_content = f"---\n{frontmatter}\n---\n{body}"
        else:
            raise HTTPException(status_code=500, detail="Failed to parse skill frontmatter")
    else:
        # No frontmatter - add one
        new_content = f"---\nname: {skill_name}\nenabled: {str(new_enabled).lower()}\n---\n\n{content}"
    
    # Write updated content
    skills = loader.list_skills(filter_unavailable=False, include_disabled=True)
    skill_info = next((s for s in skills if s["name"] == skill_name), None)
    if skill_info:
        skill_path = Path(skill_info["path"])
        skill_path.write_text(new_content)
    
    return {
        "name": skill_name,
        "enabled": new_enabled,
        "message": f"Skill '{skill_name}' {'enabled' if new_enabled else 'disabled'} successfully"
    }


# ============ Subagent Management API ============

@router.get("/subagents")
async def list_subagents(
    session_key: str | None = None,
    agent_loop = Depends(get_agent_loop)
):
    """List all running subagents."""
    subagents = agent_loop.subagents.list_subagents(session_key=session_key)
    return {
        "subagents": [info.to_dict() for info in subagents],
        "count": len(subagents)
    }

@router.post("/subagents/{task_id}/cancel")
async def cancel_subagent(
    task_id: str,
    agent_loop = Depends(get_agent_loop)
):
    """Cancel a specific subagent by task_id."""
    # First check if subagent exists
    info = agent_loop.subagents.get_subagent_info(task_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"Subagent '{task_id}' not found")
    
    # Cancel the subagent
    cancelled = await agent_loop.subagents.cancel(task_id)
    
    if cancelled:
        return {
            "status": "cancelled",
            "task_id": task_id,
            "message": f"Subagent [{info.label}] cancelled successfully"
        }
    else:
        return {
            "status": "already_completed",
            "task_id": task_id,
            "message": f"Subagent [{info.label}] was already completed"
        }

@router.post("/subagents/cancel-all")
async def cancel_all_subagents(
    session_key: str | None = None,
    agent_loop = Depends(get_agent_loop)
):
    """Cancel all running subagents, optionally filtered by session."""
    if session_key:
        cancelled = await agent_loop.subagents.cancel_by_session(session_key)
    else:
        cancelled = await agent_loop.subagents.cancel_all()
    
    return {
        "status": "success",
        "cancelled_count": cancelled,
        "message": f"Cancelled {cancelled} subagent(s)"
    }

@router.get("/subagents/{task_id}")
async def get_subagent_info(
    task_id: str,
    agent_loop = Depends(get_agent_loop)
):
    """Get information about a specific subagent."""
    info = agent_loop.subagents.get_subagent_info(task_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"Subagent '{task_id}' not found")
    
    return info.to_dict()


@router.get("/mcp-servers")
async def get_mcp_servers():
    """Get MCP servers configuration."""
    config = get_cached_config()
    
    servers = []
    if config.tools and config.tools.mcp_servers:
        for name, cfg in config.tools.mcp_servers.items():
            servers.append(sanitize_mcp_server_for_client(name, cfg))
    
    return {"servers": servers}


@router.get("/web-search-providers")
async def get_web_search_providers():
    """Get supported web search providers."""
    providers = [
        {
            "id": "duckduckgo",
            "name": "DuckDuckGo",
            "description": "免费搜索，无需 API key",
            "requires_api_key": False
        },
        {
            "id": "brave",
            "name": "Brave Search",
            "description": "Brave 搜索 API，需要 API key",
            "requires_api_key": True,
            "api_key_url": "https://brave.com/search/api/"
        },
        {
            "id": "tavily",
            "name": "Tavily",
            "description": "AI 优化的搜索 API，需要 API key",
            "requires_api_key": True,
            "api_key_url": "https://tavily.com/"
        }
    ]
    
    return {"providers": providers}


class MCPServerCreateRequest(BaseModel):
    name: str
    command: str = ""
    args: List[str] = []
    env: Dict[str, str] = {}
    url: str = ""
    tool_timeout: int = 30
    headers: Dict[str, str] = {}


@router.post("/mcp-servers")
async def add_mcp_server(request: MCPServerCreateRequest):
    """Add a new MCP server."""
    try:
        config = get_cached_config()
        
        if not config.tools:
            from horbot.config.schema import ToolsConfig
            config.tools = ToolsConfig()
        
        if not config.tools.mcp_servers:
            config.tools.mcp_servers = {}
        
        if request.name in config.tools.mcp_servers:
            raise HTTPException(status_code=400, detail=f"MCP server '{request.name}' already exists")
        
        from horbot.config.schema import MCPServerConfig
        server_config = MCPServerConfig(
            command=request.command,
            args=request.args,
            env=request.env,
            url=request.url,
            tool_timeout=request.tool_timeout,
            headers=request.headers
        )
        
        config.tools.mcp_servers[request.name] = server_config
        saved_path = save_config(config)
        
        await reset_agent_loop()
        
        return {
            "status": "success",
            "message": f"MCP server '{request.name}' added successfully",
            "path": str(saved_path),
            "server": sanitize_mcp_server_for_client(request.name, server_config)
        }
    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Permission denied: {str(e)}. The application may be running in a sandbox environment."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add MCP server: {str(e)}")


@router.put("/mcp-servers/{name}")
async def update_mcp_server(name: str, request: Dict[str, Any]):
    """Update an existing MCP server."""
    try:
        config = get_cached_config()

        if not config.tools or not config.tools.mcp_servers or name not in config.tools.mcp_servers:
            raise HTTPException(status_code=404, detail=f"MCP server '{name}' not found")

        from horbot.config.schema import MCPServerConfig

        existing = config.tools.mcp_servers[name]
        incoming_env = request.get("env", existing.env)
        if isinstance(incoming_env, dict):
            incoming_env = {
                key: (existing.env or {}).get(key, value) if value == "********" else value
                for key, value in incoming_env.items()
            }

        incoming_headers = request.get("headers", existing.headers)
        if isinstance(incoming_headers, dict):
            incoming_headers = {
                key: (existing.headers or {}).get(key, value) if value == "********" else value
                for key, value in incoming_headers.items()
            }

        server_config = MCPServerConfig(
            command=request.get("command", existing.command),
            args=request.get("args", existing.args),
            env=incoming_env,
            url=request.get("url", existing.url),
            tool_timeout=request.get("tool_timeout", existing.tool_timeout),
            headers=incoming_headers,
        )

        config.tools.mcp_servers[name] = server_config
        saved_path = save_config(config)

        await reset_agent_loop()

        return {
            "status": "success",
            "message": f"MCP server '{name}' updated successfully",
            "path": str(saved_path),
            "server": sanitize_mcp_server_for_client(name, server_config),
        }
    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Permission denied: {str(e)}. The application may be running in a sandbox environment."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update MCP server: {str(e)}")


@router.delete("/mcp-servers/{name}")
async def delete_mcp_server(name: str):
    """Delete an MCP server."""
    try:
        config = get_cached_config()
        
        if not config.tools or not config.tools.mcp_servers:
            raise HTTPException(status_code=404, detail=f"MCP server '{name}' not found")
        
        if name not in config.tools.mcp_servers:
            raise HTTPException(status_code=404, detail=f"MCP server '{name}' not found")
        
        del config.tools.mcp_servers[name]
        saved_path = save_config(config)
        
        await reset_agent_loop()
        
        return {
            "status": "success",
            "message": f"MCP server '{name}' deleted successfully",
            "path": str(saved_path)
        }
    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Permission denied: {str(e)}. The application may be running in a sandbox environment."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete MCP server: {str(e)}")

@router.get("/token-usage/stats")
async def get_token_usage_stats(
    start_date: str = None,
    end_date: str = None,
):
    """Get token usage statistics."""
    from datetime import datetime
    from horbot.agent.token_tracker import get_token_tracker
    
    tracker = get_token_tracker()
    
    start_time = None
    end_time = None
    
    if start_date:
        try:
            start_time = datetime.fromisoformat(start_date)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_time = datetime.fromisoformat(end_date)
        except ValueError:
            pass
    
    stats = tracker.get_stats(start_time=start_time, end_time=end_time)
    
    # Transform to frontend expected format
    result = {
        "total_input_tokens": stats["total"]["prompt_tokens"],
        "total_output_tokens": stats["total"]["completion_tokens"],
        "total_tokens": stats["total"]["total_tokens"],
        "total_requests": stats["total"]["requests"],
        "total_cost": stats["total"]["estimated_cost"],
        "by_provider": {
            provider: {
                "input": data["prompt_tokens"],
                "output": data["completion_tokens"],
                "total": data["total_tokens"],
                "cost": round(data.get("cost", 0), 4),
            }
            for provider, data in stats["by_provider"].items()
        },
        "by_model": {
            model: {
                "input": data["prompt_tokens"],
                "output": data["completion_tokens"],
                "total": data["total_tokens"],
                "cost": round(data.get("cost", 0), 4),
            }
            for model, data in stats["by_model"].items()
        },
        "by_day": [
            {
                "date": date,
                "input": data["prompt_tokens"],
                "output": data["completion_tokens"],
                "total": data["total_tokens"],
                "cost": round(data.get("cost", 0), 4),
            }
            for date, data in stats["by_date"].items()
        ],
    }
    
    return result

@router.get("/token-usage/records")
async def get_token_usage_records(
    provider: str = None,
    model: str = None,
    session_id: str = None,
    start_date: str = None,
    end_date: str = None,
    limit: int = 100,
):
    """Get token usage records."""
    from datetime import datetime
    from horbot.agent.token_tracker import get_token_tracker
    
    tracker = get_token_tracker()
    
    start_time = None
    end_time = None
    
    if start_date:
        try:
            start_time = datetime.fromisoformat(start_date)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_time = datetime.fromisoformat(end_date)
        except ValueError:
            pass
    
    records = tracker.query(
        provider=provider,
        model=model,
        session_id=session_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
    
    return {
        "records": [r.to_dict() for r in records],
        "total": len(records),
    }

@router.post("/restart")
async def restart_service():
    """Restart the horbot service."""
    import os
    import signal
    import sys
    
    def do_restart():
        """Perform the actual restart."""
        import time
        time.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)
    
    import threading
    restart_thread = threading.Thread(target=do_restart, daemon=True)
    restart_thread.start()
    
    return {"status": "success", "message": "Service restart initiated"}

@router.get("/config/providers/{provider_name}")
async def get_provider_config(provider_name: str):
    """Get configuration for a specific provider."""
    config = get_cached_config()
    
    provider_config = getattr(config.providers, provider_name, None)
    if not provider_config:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found")
    
    return {
        "name": provider_name,
        "apiKey": "",
        "hasApiKey": bool(provider_config.api_key),
        "apiKeyMasked": mask_secret(provider_config.api_key),
        "apiBase": provider_config.api_base,
        "extraHeaders": {key: "********" for key in (provider_config.extra_headers or {}).keys()},
        "hasExtraHeaders": bool(provider_config.extra_headers),
    }

@router.put("/config/providers/{provider_name}")
async def update_provider_config(provider_name: str, provider_data: Dict[str, Any]):
    """Update configuration for a specific provider."""
    try:
        config = get_cached_config()
        
        existing_provider = getattr(config.providers, provider_name, None)
        if not existing_provider:
            raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found")
        
        from horbot.config.schema import ProviderConfig
        api_key = provider_data.get("apiKey")
        clear_api_key = bool(provider_data.get("clearApiKey"))
        provider_config = ProviderConfig(
            api_key="" if clear_api_key else (existing_provider.api_key if api_key in (None, "") else api_key),
            api_base=provider_data.get("apiBase", existing_provider.api_base),
            extra_headers=provider_data.get("extraHeaders", existing_provider.extra_headers),
        )
        
        setattr(config.providers, provider_name, provider_config)
        saved_path = save_config(config)
        
        return {
            "status": "success",
            "message": f"Provider '{provider_name}' configuration updated",
            "path": str(saved_path)
        }
    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Permission denied: {str(e)}. The application may be running in a sandbox environment."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update provider configuration: {str(e)}")

@router.post("/config/providers")
async def add_provider(provider_data: Dict[str, Any]):
    """Add a new custom provider."""
    from loguru import logger
    try:
        logger.info("[Add Provider] Received provider data: {}", redact_sensitive_data(provider_data))
        
        provider_name = provider_data.get("name")
        if not provider_name:
            raise HTTPException(status_code=400, detail="Provider name is required")
        
        config = get_cached_config()
        
        existing_provider = getattr(config.providers, provider_name, None)
        if existing_provider:
            logger.warning(f"[Add Provider] Provider '{provider_name}' already exists")
            raise HTTPException(status_code=400, detail=f"Provider '{provider_name}' already exists")
        
        from horbot.config.schema import ProviderConfig, ProvidersConfig
        
        provider_config = ProviderConfig(
            api_key=provider_data.get("apiKey") or "",
            api_base=provider_data.get("apiBase"),
            extra_headers=provider_data.get("extraHeaders")
        )
        
        logger.info(f"[Add Provider] Created provider config for '{provider_name}'")
        
        current_providers = config.providers.model_dump()
        current_providers[provider_name] = provider_config.model_dump()
        config.providers = ProvidersConfig(**current_providers)
        
        logger.info(f"[Add Provider] Updated providers config, saving...")
        saved_path = save_config(config)
        logger.info(f"[Add Provider] Config saved to {saved_path}")
        
        return {
            "status": "success",
            "message": f"Provider '{provider_name}' added successfully",
            "path": str(saved_path)
        }
    except HTTPException:
        raise
    except PermissionError as e:
        logger.error(f"[Add Provider] Permission error: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Permission denied: {str(e)}. The application may be running in a sandbox environment."
        )
    except ValueError as e:
        logger.error(f"[Add Provider] Validation error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
    except Exception as e:
        logger.error(f"[Add Provider] Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to add provider: {str(e)}")

@router.delete("/config/providers/{provider_name}")
async def delete_provider(provider_name: str):
    """Delete a custom provider."""
    try:
        config = get_cached_config()
        
        # Predefined providers (cannot be deleted)
        PREDEFINED_PROVIDERS = {
            'custom', 'anthropic', 'openai', 'openrouter', 'deepseek', 'groq',
            'zhipu', 'dashscope', 'vllm', 'gemini', 'moonshot', 'minimax',
            'aihubmix', 'siliconflow', 'volcengine', 'openaiCodex', 'githubCopilot',
            'openai_codex', 'github_copilot'  # Also include snake_case versions
        }
        
        # Check if it's a predefined provider (cannot be deleted)
        if provider_name in PREDEFINED_PROVIDERS:
            raise HTTPException(
                status_code=403, 
                detail=f"Cannot delete predefined provider '{provider_name}'"
            )
        
        # First try the original name (for dynamic providers like "Test")
        existing_provider = getattr(config.providers, provider_name, None)
        actual_name = provider_name
        
        # If not found, try snake_case (for predefined providers like "openaiCodex" -> "openai_codex")
        if not existing_provider:
            import re
            snake_name = re.sub(r'(?<!^)(?=[A-Z])', '_', provider_name).lower()
            existing_provider = getattr(config.providers, snake_name, None)
            actual_name = snake_name
            
            # Check snake_case version too
            if snake_name in PREDEFINED_PROVIDERS:
                raise HTTPException(
                    status_code=403, 
                    detail=f"Cannot delete predefined provider '{provider_name}'"
                )
        
        if not existing_provider:
            raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found")
        
        # Pydantic models don't support dynamic attribute deletion
        # Instead, reset the provider to empty ProviderConfig
        from horbot.config.schema import ProviderConfig
        setattr(config.providers, actual_name, ProviderConfig())
        saved_path = save_config(config)
        
        return {
            "status": "success",
            "message": f"Provider '{provider_name}' deleted successfully",
            "path": str(saved_path)
        }
    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Permission denied: {str(e)}. The application may be running in a sandbox environment."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete provider: {str(e)}")


@router.post("/system/fix")
async def fix_system(agent_id: Optional[str] = None):
    """One-click fix for common configuration issues."""
    config = get_cached_config()
    agent, workspace_path, memory_store = _build_memory_store(agent_id)
    fixed = []
    failed = []
    suggestions = []
    
    try:
        if not config.get_provider_name():
            suggestions.append({
                "issue": "provider_not_configured",
                "message": "未配置 AI 提供商，请在设置中配置 API Key",
                "action": "configure_provider"
            })
        else:
            provider_config = config.get_provider()
            if not provider_config or not provider_config.api_key:
                suggestions.append({
                    "issue": "api_key_missing",
                    "message": f"提供商 {config.get_provider_name()} 的 API Key 未配置",
                    "action": "configure_api_key"
                })
    except Exception as e:
        failed.append({
            "issue": "provider_check",
            "error": str(e)
        })
    
    try:
        if not workspace_path.exists():
            workspace_path.mkdir(parents=True, exist_ok=True)
            fixed.append({
                "issue": "workspace_missing",
                "message": f"已创建工作目录: {workspace_path}"
            })
    except Exception as e:
        failed.append({
            "issue": "workspace_creation",
            "error": str(e)
        })
    
    try:
        memory_dir, _ = _get_memory_roots(memory_store)
        for level in ["L0", "L1", "L2"]:
            level_dir = memory_dir / level
            if not level_dir.exists():
                level_dir.mkdir(parents=True, exist_ok=True)
                fixed.append({
                    "issue": f"memory_dir_{level.lower()}_missing",
                    "message": f"已创建记忆目录: {level}"
                })
    except Exception as e:
        failed.append({
            "issue": "memory_dir_creation",
            "error": str(e)
        })
    
    try:
        from horbot.utils.paths import get_logs_dir
        logs_dir = get_logs_dir()
        if not logs_dir.exists():
            logs_dir.mkdir(parents=True, exist_ok=True)
            fixed.append({
                "issue": "logs_dir_missing",
                "message": "已创建日志目录"
            })
    except Exception as e:
        failed.append({
            "issue": "logs_dir_creation",
            "error": str(e)
        })
    
    try:
        skills_dir = (agent.get_skills_dir() if agent is not None else workspace_path / "skills")
        if not skills_dir.exists():
            skills_dir.mkdir(parents=True, exist_ok=True)
            fixed.append({
                "issue": "skills_dir_missing",
                "message": "已创建技能目录"
            })
    except Exception as e:
        failed.append({
            "issue": "skills_dir_creation",
            "error": str(e)
        })
    
    try:
        soul_file = workspace_path / "SOUL.md"
        if not soul_file.exists():
            soul_content = "# Workhorse\n\n我是你的 AI 助手，随时准备帮助你完成任务。\n"
            soul_file.write_text(soul_content, encoding="utf-8")
            fixed.append({
                "issue": "soul_file_missing",
                "message": "已创建默认角色文件 SOUL.md"
            })
    except Exception as e:
        failed.append({
            "issue": "soul_file_creation",
            "error": str(e)
        })
    
    try:
        from horbot.utils.paths import get_cron_dir
        cron_dir = get_cron_dir()
        cron_store = cron_dir / "jobs.json"
        if not cron_store.exists():
            cron_store.write_text("{}", encoding="utf-8")
            fixed.append({
                "issue": "cron_store_missing",
                "message": "已创建定时任务存储文件"
            })
    except Exception as e:
        failed.append({
            "issue": "cron_store_creation",
            "error": str(e)
        })
    
    if not config.get_provider_name() or not config.get_provider().api_key:
        suggestions.append({
            "issue": "agent_not_ready",
            "message": "AI 代理未就绪，请先配置提供商和 API Key",
            "action": "configure_provider"
        })
    
    return {
        "fixed": fixed,
        "failed": failed,
        "suggestions": suggestions
    }


@router.get("/memory")
async def get_memory_stats(agent_id: Optional[str] = None):
    """Get AI memory storage usage statistics."""
    try:
        agent, _, memory_store = _build_memory_store(agent_id)
        stats = memory_store.get_memory_stats()
        
        total_entries = 0
        total_size_bytes = 0
        oldest_entry = None
        newest_entry = None
        
        if stats.get("hierarchical"):
            hierarchical_stats = stats["hierarchical"]
            memories = hierarchical_stats.get("memories", {})
            
            for level, level_stats in memories.items():
                total_entries += level_stats.get("count", 0)
                total_size_bytes += level_stats.get("total_size", 0)
            
            memory_dir, _ = _get_memory_roots(memory_store)
            
            all_files = []
            for level in ["L0", "L1", "L2"]:
                level_dir = memory_dir / level
                if level_dir.exists():
                    for f in level_dir.glob("*.md"):
                        if f.name != "README.md":
                            all_files.append((f, f.stat().st_mtime))
            
            if all_files:
                all_files.sort(key=lambda x: x[1])
                oldest_file = all_files[0][0]
                newest_file = all_files[-1][0]
                
                oldest_entry = datetime.fromtimestamp(all_files[0][1]).isoformat()
                newest_entry = datetime.fromtimestamp(all_files[-1][1]).isoformat()
        
        total_size_kb = total_size_bytes / 1024
        
        return {
            "agent_id": agent.id if agent is not None else None,
            "total_entries": total_entries,
            "total_size_kb": round(total_size_kb, 2),
            "oldest_entry": oldest_entry,
            "newest_entry": newest_entry,
            "details": stats
        }
    except Exception as e:
        logger.error("Failed to get memory stats: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to get memory stats: {str(e)}")


@router.delete("/memory")
async def clear_memory(days: int = 30, agent_id: Optional[str] = None):
    """Clear expired memory data.
    
    Args:
        days: Delete memories older than this many days (default: 30)
    """
    from datetime import timedelta

    try:
        agent, _, memory_store = _build_memory_store(agent_id)
        memory_dir, executions_dir = _get_memory_roots(memory_store)
        
        deleted_count = 0
        freed_bytes = 0
        cutoff_time = datetime.now() - timedelta(days=days)
        
        for level in ["L0", "L1"]:
            level_dir = memory_dir / level
            if not level_dir.exists():
                continue
            
            for file_path in level_dir.glob("*.md"):
                if file_path.name == "README.md":
                    continue
                
                try:
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime < cutoff_time:
                        freed_bytes += file_path.stat().st_size
                        file_path.unlink()
                        deleted_count += 1
                        logger.info("Deleted expired memory: {}", file_path.name)
                except Exception as e:
                    logger.warning("Failed to delete memory {}: {}", file_path.name, e)
        
        archived_dir = executions_dir / "archived"
        if archived_dir.exists():
            for file_path in archived_dir.glob("*.json"):
                try:
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime < cutoff_time:
                        freed_bytes += file_path.stat().st_size
                        file_path.unlink()
                        deleted_count += 1
                        logger.info("Deleted archived execution: {}", file_path.name)
                except Exception as e:
                    logger.warning("Failed to delete execution {}: {}", file_path.name, e)
        
        freed_kb = freed_bytes / 1024
        
        return {
            "agent_id": agent.id if agent is not None else None,
            "deleted_count": deleted_count,
            "freed_kb": round(freed_kb, 2),
            "cutoff_days": days
        }
    except Exception as e:
        logger.error("Failed to clear memory: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to clear memory: {str(e)}")


# ============ Multi-Agent API ============

def _extract_soul_name_from_workspace(workspace_path) -> str | None:
    """Extract the AI name from SOUL.md file in the given workspace."""
    from pathlib import Path
    import re
    
    soul_path = Path(workspace_path) / "SOUL.md"
    if not soul_path.exists():
        return None
    
    try:
        content = soul_path.read_text(encoding="utf-8")
        
        name_match = re.search(r'我是([^，。\n]+)', content)
        if name_match:
            return name_match.group(1).strip()
        
        name_match2 = re.search(r'^# (.+)$', content, re.MULTILINE)
        if name_match2:
            title = name_match2.group(1).strip()
            if title not in ["灵魂", "Soul", "SOUL"]:
                return title
    except Exception:
        pass
    
    return None


@router.get("/agents")
async def list_agents():
    """List all available agents."""
    from horbot.agent.manager import get_agent_manager
    
    agent_manager = get_agent_manager()
    agents = agent_manager.get_all_agents()
    
    agent_list = []
    for agent in agents:
        agent_dict = agent.to_dict()
        workspace = agent.get_workspace()
        soul_name = _extract_soul_name_from_workspace(workspace)
        if soul_name:
            agent_dict["name"] = soul_name
        agent_dict.update(_build_agent_runtime_capabilities(agent))
        agent_list.append(agent_dict)
    
    return {
        "agents": agent_list,
        "count": len(agents)
    }


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get details of a specific agent."""
    from horbot.agent.manager import get_agent_manager
    
    agent_manager = get_agent_manager()
    agent = agent_manager.get_agent(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    
    agent_dict = agent.to_dict()
    agent_dict.update(_build_agent_runtime_capabilities(agent))
    return agent_dict


@router.get("/agents/{agent_id}/bootstrap-files")
async def get_agent_bootstrap_files(agent_id: str):
    """Get editable bootstrap files for a specific agent."""
    agent, workspace_path = _resolve_agent_workspace_for_request(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    payload = _build_agent_bootstrap_payload(agent)
    payload["workspace_path"] = str(workspace_path)
    return payload


class AgentBootstrapFileUpdateRequest(BaseModel):
    content: str = ""


class AgentBootstrapSummaryUpdateRequest(BaseModel):
    identity: list[str] = Field(default_factory=list)
    role_focus: list[str] = Field(default_factory=list)
    communication_style: list[str] = Field(default_factory=list)
    boundaries: list[str] = Field(default_factory=list)
    user_preferences: list[str] = Field(default_factory=list)


@router.put("/agents/{agent_id}/bootstrap-files/{file_kind}")
async def update_agent_bootstrap_file(
    agent_id: str,
    file_kind: str,
    request: AgentBootstrapFileUpdateRequest,
):
    """Create or update an agent bootstrap file."""
    agent, _ = _resolve_agent_workspace_for_request(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    file_path, file_name = _agent_bootstrap_file_path(agent_id, file_kind)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_kind = (file_kind or "").strip().lower()
    normalized_content = normalize_bootstrap_file_content(request.content or "", normalized_kind)
    file_path.write_text(normalized_content, encoding="utf-8")
    if normalized_kind in {"soul", "user"}:
        reconcile_bootstrap_files(
            file_path.parent,
            agent_name=agent.name,
            updated_file=file_name,
        )

    return {
        "status": "updated",
        "agent_id": agent.id,
        "agent_name": agent.name,
        "file": file_name,
        "path": str(file_path),
        "content": normalized_content,
    }


@router.put("/agents/{agent_id}/bootstrap-summary")
async def update_agent_bootstrap_summary(
    agent_id: str,
    request: AgentBootstrapSummaryUpdateRequest,
):
    """Update structured bootstrap summary and write back to markdown files."""
    agent, _ = _resolve_agent_workspace_for_request(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    soul_path, _ = _agent_bootstrap_file_path(agent_id, "soul")
    user_path, _ = _agent_bootstrap_file_path(agent_id, "user")

    existing_soul = _read_bootstrap_file(soul_path)["content"]
    existing_user = _read_bootstrap_file(user_path)["content"]

    next_soul = remove_setup_pending_marker(existing_soul)
    next_user = remove_setup_pending_marker(existing_user)

    next_soul = upsert_markdown_section(next_soul, "身份定位", request.identity)
    next_soul = upsert_markdown_section(next_soul, "职责重点", request.role_focus)
    next_soul = upsert_markdown_section(next_soul, "沟通风格", request.communication_style)
    next_soul = upsert_markdown_section(next_soul, "边界约束", request.boundaries)
    next_user = upsert_markdown_section(next_user, "用户偏好", request.user_preferences)

    soul_path.parent.mkdir(parents=True, exist_ok=True)
    user_path.parent.mkdir(parents=True, exist_ok=True)
    soul_path.write_text(next_soul, encoding="utf-8")
    user_path.write_text(next_user, encoding="utf-8")

    payload = _build_agent_bootstrap_payload(agent)
    return {
        "status": "updated",
        **payload,
    }


@router.get("/conversations")
async def list_conversations():
    """List all conversations."""
    from horbot.conversation import get_conversation_manager, ConversationType
    
    conv_manager = get_conversation_manager()
    
    dm_convs = conv_manager.get_dm_list()
    team_convs = conv_manager.get_team_list()
    
    return {
        "conversations": [c.to_dict() for c in conv_manager.get_all()],
        "dm": [c.to_dict() for c in dm_convs],
        "team": [c.to_dict() for c in team_convs],
    }


@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    """Get details of a specific conversation."""
    from horbot.conversation import get_conversation_manager
    
    conv_manager = get_conversation_manager()
    conv = conv_manager.get(conv_id)
    
    if not conv:
        raise HTTPException(status_code=404, detail=f"Conversation '{conv_id}' not found")
    
    return conv.to_dict()


@router.get("/conversations/{conv_id}/messages")
async def get_conversation_messages(conv_id: str):
    """Get messages for a specific conversation."""
    from horbot.conversation import get_conversation_manager, ConversationType
    from horbot.session.manager import SessionManager
    from horbot.workspace.manager import get_workspace_manager
    
    conv_manager = get_conversation_manager()
    conv = conv_manager.get(conv_id)
    
    if not conv:
        conv_type, target_id = conv_manager.parse_id(conv_id)
        if conv_type == ConversationType.DM:
            from horbot.agent.manager import get_agent_manager
            agent_manager = get_agent_manager()
            agent = agent_manager.get_agent(target_id)
            if agent:
                conv = conv_manager.get_or_create_dm(target_id, agent.name)
        elif conv_type == ConversationType.TEAM:
            from horbot.team.manager import get_team_manager
            team_manager = get_team_manager()
            team = team_manager.get_team(target_id)
            if team:
                conv = conv_manager.get_or_create_team(target_id, team.name, team.members)
    
    if not conv:
        raise HTTPException(status_code=404, detail=f"Conversation '{conv_id}' not found")
    
    session_key = f"web:{conv_id}"
    
    candidate_managers: list[SessionManager] = []
    if conv.type == ConversationType.TEAM:
        workspace_manager = get_workspace_manager()
        team_ws = workspace_manager.get_team_workspace(conv.target_id)
        sessions_path = Path(team_ws.workspace_path) / "sessions"
        session_manager = SessionManager(workspace=sessions_path)
        candidate_managers = [session_manager]
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
            session_manager = get_session_manager()
            candidate_managers = [session_manager]
    else:
        session_manager = get_session_manager()
        candidate_managers = [session_manager]

    raw_messages = _load_merged_session_messages(session_key, candidate_managers)
    
    # Clean message content to remove XML wrapper from LLM history format
    cleaned_messages = []
    for msg in raw_messages:
        cleaned_msg = dict(msg)  # Create a copy
        cleaned_msg["id"] = ensure_history_message_id(cleaned_msg)
        if "content" in cleaned_msg and isinstance(cleaned_msg["content"], str):
            cleaned_msg["content"] = clean_message_content(cleaned_msg["content"])
        cleaned_messages.append(cleaned_msg)
    
    return {
        "conversation_id": conv_id,
        "conversation": conv.to_dict(),
        "messages": cleaned_messages,
    }


@router.get("/providers")
async def list_providers():
    """List all available LLM providers and their models."""
    from horbot.config.loader import load_config
    from horbot.providers.registry import PROVIDERS
    
    config = load_config()
    
    providers = []
    
    provider_names = [
        ("openai", "OpenAI"),
        ("anthropic", "Anthropic"),
        ("openrouter", "OpenRouter"),
        ("deepseek", "DeepSeek"),
        ("groq", "Groq"),
        ("zhipu", "智谱 AI"),
        ("dashscope", "阿里云通义"),
        ("vllm", "vLLM"),
        ("gemini", "Google Gemini"),
        ("moonshot", "Moonshot"),
        ("minimax", "MiniMax"),
        ("aihubmix", "AiHubMix"),
        ("siliconflow", "硅基流动"),
        ("volcengine", "火山引擎"),
        ("custom", "自定义"),
    ]

    known_provider_ids = {provider_id for provider_id, _ in provider_names}
    extra_provider_map = getattr(config.providers, "model_extra", {}) or {}
    for provider_id in sorted(extra_provider_map):
        provider_config = getattr(config.providers, provider_id, None)
        if provider_id in known_provider_ids:
            continue
        if provider_config and (provider_config.api_key or provider_config.api_base):
            provider_names.append((provider_id, provider_id))

    oauth_provider_ids = {spec.name for spec in PROVIDERS if spec.is_oauth}
    
    for provider_id, provider_name in provider_names:
        provider_config = getattr(config.providers, provider_id, None)
        has_key = False
        if provider_config:
            has_key = bool(provider_config.api_key) or provider_id in oauth_provider_ids
        
        models = _get_provider_models(provider_id)
        
        providers.append({
            "id": provider_id,
            "name": provider_name,
            "configured": has_key,
            "models": models,
        })
    
    return {
        "providers": providers,
        "default_provider": config.agents.defaults.provider,
        "default_model": config.agents.defaults.model,
    }


def _get_provider_models(provider_id: str) -> list[dict]:
    """Get available models for a provider."""
    models_map = {
        "openai": [
            {"id": "gpt-4o", "name": "GPT-4o", "description": "最新多模态模型"},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "description": "轻量多模态模型"},
            {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "description": "GPT-4 增强版"},
            {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "description": "快速经济模型"},
        ],
        "anthropic": [
            {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "description": "最新 Claude 模型"},
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "description": "平衡性能与成本"},
            {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku", "description": "快速响应模型"},
            {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus", "description": "最强能力模型"},
        ],
        "openrouter": [
            {"id": "anthropic/claude-sonnet-4", "name": "Claude Sonnet 4", "description": "通过 OpenRouter"},
            {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "description": "通过 OpenRouter"},
            {"id": "openai/gpt-4o", "name": "GPT-4o", "description": "通过 OpenRouter"},
            {"id": "google/gemini-pro-1.5", "name": "Gemini Pro 1.5", "description": "通过 OpenRouter"},
            {"id": "deepseek/deepseek-chat", "name": "DeepSeek Chat", "description": "通过 OpenRouter"},
        ],
        "deepseek": [
            {"id": "deepseek-chat", "name": "DeepSeek Chat", "description": "对话模型"},
            {"id": "deepseek-coder", "name": "DeepSeek Coder", "description": "代码专用模型"},
        ],
        "groq": [
            {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B", "description": "Meta 开源模型"},
            {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B", "description": "轻量快速模型"},
            {"id": "mixtral-8x7b-32768", "name": "Mixtral 8x7B", "description": "MoE 架构模型"},
        ],
        "zhipu": [
            {"id": "glm-4-plus", "name": "GLM-4 Plus", "description": "智谱最强模型"},
            {"id": "glm-4-0520", "name": "GLM-4", "description": "智谱旗舰模型"},
            {"id": "glm-4-flash", "name": "GLM-4 Flash", "description": "快速模型"},
        ],
        "dashscope": [
            {"id": "qwen-max", "name": "通义千问 Max", "description": "阿里最强模型"},
            {"id": "qwen-plus", "name": "通义千问 Plus", "description": "平衡模型"},
            {"id": "qwen-turbo", "name": "通义千问 Turbo", "description": "快速模型"},
        ],
        "gemini": [
            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "description": "Google 最新模型"},
            {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "description": "快速响应模型"},
            {"id": "gemini-pro", "name": "Gemini Pro", "description": "标准模型"},
        ],
        "minimax": [
            {"id": "MiniMax-Text-01", "name": "MiniMax Text 01", "description": "MiniMax 文本模型"},
            {"id": "abab6.5-chat", "name": "ABAB 6.5 Chat", "description": "MiniMax 对话模型"},
        ],
        "moonshot": [
            {"id": "moonshot-v1-8k", "name": "Moonshot V1 8K", "description": "8K 上下文"},
            {"id": "moonshot-v1-32k", "name": "Moonshot V1 32K", "description": "32K 上下文"},
            {"id": "moonshot-v1-128k", "name": "Moonshot V1 128K", "description": "128K 上下文"},
        ],
        "siliconflow": [
            {"id": "Qwen/Qwen2.5-72B-Instruct", "name": "Qwen 2.5 72B", "description": "通义千问开源版"},
            {"id": "deepseek-ai/DeepSeek-V2.5", "name": "DeepSeek V2.5", "description": "DeepSeek 最新版"},
        ],
        "volcengine": [
            {"id": "doubao-pro-32k", "name": "豆包 Pro 32K", "description": "字节豆包模型"},
            {"id": "doubao-lite-32k", "name": "豆包 Lite 32K", "description": "轻量版模型"},
        ],
        "aihubmix": [
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "description": "通过 AiHubMix"},
            {"id": "gpt-4o", "name": "GPT-4o", "description": "通过 AiHubMix"},
        ],
        "vllm": [
            {"id": "custom", "name": "自定义模型", "description": "使用 vLLM 部署的模型"},
        ],
        "custom": [
            {"id": "custom", "name": "自定义模型", "description": "自定义 OpenAI 兼容端点"},
        ],
    }
    
    if provider_id in models_map:
        return models_map[provider_id]
    return [
        {"id": "gpt-5.4", "name": "gpt-5.4", "description": "自定义 Provider 默认模型"},
        {"id": "custom", "name": "自定义模型", "description": "手动输入模型名称"},
    ]


@router.get("/agents/{agent_id}/workspace")
async def get_agent_workspace(agent_id: str):
    """Get workspace information for a specific agent."""
    from horbot.agent.manager import get_agent_manager
    from pathlib import Path
    
    agent_manager = get_agent_manager()
    agent = agent_manager.get_agent(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    
    workspace_path = agent.get_workspace()
    memory_path = agent.get_memory_dir()
    sessions_path = agent.get_sessions_dir()
    skills_path = agent.get_skills_dir()
    
    workspace_info = {
        "agent_id": agent_id,
        "workspace_path": str(workspace_path),
        "memory_path": str(memory_path),
        "sessions_path": str(sessions_path),
        "skills_path": str(skills_path),
        "exists": workspace_path.exists(),
    }
    
    if workspace_path.exists():
        try:
            files_count = sum(1 for _ in workspace_path.rglob("*") if _.is_file())
            workspace_info["files_count"] = files_count
        except Exception:
            workspace_info["files_count"] = 0
    
    return workspace_info


class CreateAgentRequest(BaseModel):
    id: str
    name: str
    description: str = ""
    profile: str = ""
    permission_profile: str = ""
    model: str = ""
    provider: str = "auto"
    system_prompt: str = ""
    capabilities: List[str] = []
    tools: List[str] = []
    skills: List[str] = []
    workspace: str = ""
    teams: List[str] = []
    personality: str = ""
    avatar: str = ""
    evolution_enabled: bool = True
    learning_enabled: bool = True
    memory_bank_profile: Dict[str, Any] = Field(default_factory=dict)


def _normalize_string_list(values: List[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _normalize_agent_id(value: str) -> str:
    return value.strip().lower()


def _normalize_team_id(value: str) -> str:
    return value.strip().lower()


def _normalize_memory_bank_profile(payload: Dict[str, Any] | None) -> Dict[str, Any]:
    raw = payload or {}
    directives = raw.get("directives", [])
    if isinstance(directives, str):
        directives = directives.splitlines()
    normalized_directives = _normalize_string_list([
        str(value).strip()
        for value in directives
        if str(value).strip()
    ])
    reasoning_style = str(raw.get("reasoning_style") or raw.get("reasoningStyle") or "").strip()
    allowed_styles = {"balanced", "structured", "exploratory", "strict"}
    return {
        "mission": str(raw.get("mission") or "").strip(),
        "directives": normalized_directives,
        "reasoning_style": reasoning_style if reasoning_style in allowed_styles else "",
    }


def _validate_team_ids_exist(config: Config, team_ids: List[str]) -> List[str]:
    normalized = _normalize_string_list(team_ids)
    missing = [team_id for team_id in normalized if team_id not in config.teams.instances]
    if missing:
        raise HTTPException(status_code=400, detail=f"Unknown teams: {', '.join(missing)}")
    return normalized


def _validate_agent_ids_exist(config: Config, agent_ids: List[str]) -> List[str]:
    normalized = _normalize_string_list(agent_ids)
    missing = [agent_id for agent_id in normalized if agent_id not in config.agents.instances]
    if missing:
        raise HTTPException(status_code=400, detail=f"Unknown agents: {', '.join(missing)}")
    return normalized


def _normalize_team_member_profiles(config: Config, member_ids: List[str], profiles: Dict[str, Any] | None) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    raw_profiles = profiles or {}

    for agent_id in member_ids:
        profile_data = raw_profiles.get(agent_id) or {}
        normalized[agent_id] = {
            "role": str(profile_data.get("role") or "member").strip() or "member",
            "responsibility": str(profile_data.get("responsibility") or "").strip(),
            "priority": int(profile_data.get("priority", 100) or 100),
            "is_lead": bool(profile_data.get("isLead", profile_data.get("is_lead", False))),
        }

    for agent_id in raw_profiles:
        if agent_id not in config.agents.instances:
            raise HTTPException(status_code=400, detail=f"Unknown agent in member profiles: {agent_id}")
        if agent_id not in member_ids:
            raise HTTPException(status_code=400, detail=f"Member profile provided for non-member agent: {agent_id}")

    lead_ids = [agent_id for agent_id, profile in normalized.items() if profile["is_lead"]]
    if len(lead_ids) > 1:
        raise HTTPException(status_code=400, detail="A team can only have one lead agent")

    return normalized


def _cleanup_agent_storage(agent_id: str, workspace_override: str = "") -> None:
    from horbot.workspace.manager import get_workspace_manager

    workspace_manager = get_workspace_manager()
    if workspace_override.strip():
        workspace_manager.delete_agent_override_artifacts(workspace_override)
    workspace_manager.delete_agent_workspace(agent_id)


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


@router.post("/agents")
async def create_agent(request: CreateAgentRequest):
    """Create a new agent."""
    from horbot.config.schema import AgentConfig
    from horbot.config.loader import load_config, save_config
    from horbot.agent.manager import get_agent_manager
    
    config = load_config()
    
    request_id = request.id.strip()
    request_name = request.name.strip()
    normalized_request_id = _normalize_agent_id(request_id)

    if not request_id:
        raise HTTPException(status_code=400, detail="Agent ID is required")

    if not request_name:
        raise HTTPException(status_code=400, detail="Agent name is required")

    existing_agent_id = next(
        (
            existing_id
            for existing_id in config.agents.instances
            if _normalize_agent_id(existing_id) == normalized_request_id
        ),
        None,
    )
    if existing_agent_id is not None:
        raise HTTPException(status_code=400, detail=f"Agent ID '{request_id}' already exists")

    team_ids = _validate_team_ids_exist(config, request.teams)
    
    agent_config = AgentConfig(
        id=request_id,
        name=request_name,
        description=request.description,
        profile=request.profile.strip(),
        permission_profile=request.permission_profile.strip(),
        model=request.model,
        provider=request.provider,
        system_prompt=request.system_prompt,
        capabilities=_normalize_string_list(request.capabilities),
        tools=_normalize_string_list(request.tools),
        skills=_normalize_string_list(request.skills),
        workspace=request.workspace.strip(),
        teams=team_ids,
        personality=request.personality,
        avatar=request.avatar,
        evolution_enabled=request.evolution_enabled,
        learning_enabled=request.learning_enabled,
        memory_bank_profile=_normalize_memory_bank_profile(request.memory_bank_profile),
    )

    config.agents.instances[request_id] = agent_config
    set_agent_team_memberships(config, request_id, team_ids)
    
    try:
        save_config(config)
        
        agent_manager = get_agent_manager()
        agent_manager.reload()
        created_agent = agent_manager.get_agent(request_id)
        _ensure_agent_bootstrap_files(created_agent)
        await reset_agent_loop()
        
        return {
            "status": "created",
            "agent_id": request_id,
            "message": f"Agent '{request_name}' created successfully"
        }
    except Exception as e:
        logger.error("Failed to create agent: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to create agent: {str(e)}")


@router.put("/agents/{agent_id}")
async def update_agent(agent_id: str, request: CreateAgentRequest):
    """Update an existing agent."""
    from horbot.config.schema import AgentConfig
    from horbot.config.loader import load_config, save_config
    from horbot.agent.manager import get_agent_manager
    
    config = load_config()
    
    if agent_id not in config.agents.instances:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    request_name = request.name.strip()
    if not request_name:
        raise HTTPException(status_code=400, detail="Agent name is required")

    team_ids = _validate_team_ids_exist(config, request.teams)
    
    agent_config = AgentConfig(
        id=agent_id,
        name=request_name,
        description=request.description,
        profile=request.profile.strip(),
        permission_profile=request.permission_profile.strip(),
        model=request.model,
        provider=request.provider,
        system_prompt=request.system_prompt,
        capabilities=_normalize_string_list(request.capabilities),
        tools=_normalize_string_list(request.tools),
        skills=_normalize_string_list(request.skills),
        workspace=request.workspace.strip(),
        teams=team_ids,
        personality=request.personality,
        avatar=request.avatar,
        evolution_enabled=request.evolution_enabled,
        learning_enabled=request.learning_enabled,
        memory_bank_profile=_normalize_memory_bank_profile(request.memory_bank_profile),
    )
    
    config.agents.instances[agent_id] = agent_config
    set_agent_team_memberships(config, agent_id, team_ids)
    
    try:
        save_config(config)
        
        agent_manager = get_agent_manager()
        agent_manager.reload()
        updated_agent = agent_manager.get_agent(agent_id)
        _ensure_agent_bootstrap_files(updated_agent)
        await reset_agent_loop()
        
        return {
            "status": "updated",
            "agent_id": agent_id,
            "message": f"Agent '{request_name}' updated successfully"
        }
    except Exception as e:
        logger.error("Failed to update agent: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to update agent: {str(e)}")


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str):
    """Delete an agent."""
    from horbot.config.loader import load_config, save_config
    from horbot.agent.manager import get_agent_manager
    
    config = load_config()
    
    if agent_id not in config.agents.instances:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    agent_config = config.agents.instances[agent_id]
    
    try:
        _cleanup_agent_storage(agent_id, str(agent_config.workspace or ""))
        remove_agent_references(config, agent_id)
        del config.agents.instances[agent_id]
        save_config(config)
        
        agent_manager = get_agent_manager()
        agent_manager.reload()
        await reset_agent_loop()
        
        return {
            "status": "deleted",
            "agent_id": agent_id,
            "message": f"Agent '{agent_id}' deleted successfully"
        }
    except Exception as e:
        logger.error("Failed to delete agent: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to delete agent: {str(e)}")


@router.get("/teams")
async def list_teams():
    """List all available teams."""
    from horbot.team.manager import get_team_manager
    
    team_manager = get_team_manager()
    teams = team_manager.get_all_teams()
    
    return {
        "teams": [team.to_dict() for team in teams],
        "count": len(teams)
    }


@router.get("/teams/{team_id}")
async def get_team(team_id: str):
    """Get details of a specific team."""
    from horbot.team.manager import get_team_manager
    
    team_manager = get_team_manager()
    team = team_manager.get_team(team_id)
    
    if not team:
        raise HTTPException(status_code=404, detail=f"Team '{team_id}' not found")
    
    return team.to_dict()


@router.get("/teams/{team_id}/members")
async def get_team_members(team_id: str):
    """Get members of a specific team."""
    from horbot.team.manager import get_team_manager
    from horbot.agent.manager import get_agent_manager
    
    team_manager = get_team_manager()
    agent_manager = get_agent_manager()
    
    team = team_manager.get_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail=f"Team '{team_id}' not found")
    
    members = []
    for agent_id in team.members:
        agent = agent_manager.get_agent(agent_id)
        if agent:
            members.append(agent.to_dict())
    
    return {
        "team_id": team_id,
        "members": members,
        "count": len(members)
    }


@router.get("/teams/{team_id}/workspace")
async def get_team_workspace(team_id: str):
    """Get workspace information for a specific team."""
    from horbot.team.manager import get_team_manager
    
    team_manager = get_team_manager()
    team = team_manager.get_team(team_id)
    
    if not team:
        raise HTTPException(status_code=404, detail=f"Team '{team_id}' not found")
    
    workspace_path = team.get_workspace()
    
    workspace_info = {
        "team_id": team_id,
        "workspace_path": str(workspace_path),
        "exists": workspace_path.exists(),
    }
    
    if workspace_path.exists():
        try:
            files_count = sum(1 for _ in workspace_path.rglob("*") if _.is_file())
            workspace_info["files_count"] = files_count
        except Exception:
            workspace_info["files_count"] = 0
    
    return workspace_info


@router.get("/teams/{team_id}/shared-memory")
async def get_team_shared_memory(team_id: str):
    """Get shared memory for a specific team."""
    from horbot.team.manager import get_team_manager
    
    team_manager = get_team_manager()
    team = team_manager.get_team(team_id)
    
    if not team:
        raise HTTPException(status_code=404, detail=f"Team '{team_id}' not found")
    
    shared_memory = team.get_shared_memory()
    context = shared_memory.get_all_context()
    
    return {
        "team_id": team_id,
        "context": context
    }


class CreateTeamRequest(BaseModel):
    id: str
    name: str
    description: str = ""
    members: List[str] = []
    member_profiles: Dict[str, Any] = {}
    workspace: str = ""


@router.post("/teams")
async def create_team(request: CreateTeamRequest):
    """Create a new team."""
    from horbot.config.schema import TeamConfig
    from horbot.config.loader import load_config, save_config
    from horbot.team.manager import get_team_manager
    
    config = load_config()
    
    request_id = request.id.strip()
    request_name = request.name.strip()
    normalized_request_id = _normalize_team_id(request_id)

    if not request_id:
        raise HTTPException(status_code=400, detail="Team ID is required")

    if not request_name:
        raise HTTPException(status_code=400, detail="Team name is required")

    existing_team_id = next(
        (
            existing_id
            for existing_id in config.teams.instances
            if _normalize_team_id(existing_id) == normalized_request_id
        ),
        None,
    )
    if existing_team_id is not None:
        raise HTTPException(status_code=400, detail=f"Team ID '{request_id}' already exists")

    member_ids = _validate_agent_ids_exist(config, request.members)
    member_profiles = _normalize_team_member_profiles(config, member_ids, request.member_profiles)
    
    team_config = TeamConfig(
        id=request_id,
        name=request_name,
        description=request.description,
        members=member_ids,
        member_profiles=member_profiles,
        workspace=request.workspace.strip(),
    )
    
    config.teams.instances[request_id] = team_config
    set_team_members(config, request_id, member_ids)
    
    try:
        save_config(config)
        
        team_manager = get_team_manager()
        team_manager.reload()
        await reset_agent_loop()
        
        return {
            "status": "created",
            "team_id": request_id,
            "message": f"Team '{request_name}' created successfully"
        }
    except Exception as e:
        logger.error("Failed to create team: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to create team: {str(e)}")


@router.put("/teams/{team_id}")
async def update_team(team_id: str, request: CreateTeamRequest):
    """Update an existing team."""
    from horbot.config.schema import TeamConfig
    from horbot.config.loader import load_config, save_config
    from horbot.team.manager import get_team_manager
    
    config = load_config()
    
    if team_id not in config.teams.instances:
        raise HTTPException(status_code=404, detail=f"Team '{team_id}' not found")

    request_name = request.name.strip()
    if not request_name:
        raise HTTPException(status_code=400, detail="Team name is required")

    member_ids = _validate_agent_ids_exist(config, request.members)
    member_profiles = _normalize_team_member_profiles(config, member_ids, request.member_profiles)
    
    team_config = TeamConfig(
        id=team_id,
        name=request_name,
        description=request.description,
        members=member_ids,
        member_profiles=member_profiles,
        workspace=request.workspace.strip(),
    )
    
    config.teams.instances[team_id] = team_config
    set_team_members(config, team_id, member_ids)
    
    try:
        save_config(config)
        
        team_manager = get_team_manager()
        team_manager.reload()
        await reset_agent_loop()
        
        return {
            "status": "updated",
            "team_id": team_id,
            "message": f"Team '{request_name}' updated successfully"
        }
    except Exception as e:
        logger.error("Failed to update team: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to update team: {str(e)}")


@router.delete("/teams/{team_id}")
async def delete_team(team_id: str):
    """Delete a team."""
    from horbot.config.loader import load_config, save_config
    from horbot.team.manager import get_team_manager
    
    config = load_config()
    
    if team_id not in config.teams.instances:
        raise HTTPException(status_code=404, detail=f"Team '{team_id}' not found")

    remove_team_references(config, team_id)
    del config.teams.instances[team_id]
    
    try:
        save_config(config)
        
        team_manager = get_team_manager()
        team_manager.reload()
        await reset_agent_loop()
        
        return {
            "status": "deleted",
            "team_id": team_id,
            "message": f"Team '{team_id}' deleted successfully"
        }
    except Exception as e:
        logger.error("Failed to delete team: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to delete team: {str(e)}")


# ============ Task Delegation API ============

@router.get("/delegated-tasks")
async def list_delegated_tasks(
    status: str = None,
    agent_id: str = None,
):
    """List all delegated tasks."""
    from horbot.agent.task_delegation import get_task_delegator
    
    delegator = get_task_delegator()
    
    if status == "pending":
        tasks = delegator.get_pending_tasks()
    elif status == "completed":
        tasks = delegator.get_completed_tasks()
    elif status == "failed":
        tasks = delegator.get_failed_tasks()
    else:
        tasks = list(delegator._delegated_tasks.values())
    
    if agent_id:
        tasks = [t for t in tasks if t.target_agent_id == agent_id or t.source_agent_id == agent_id]
    
    return {
        "tasks": [
            {
                "id": task.id,
                "description": task.description,
                "target_agent_id": task.target_agent_id,
                "source_agent_id": task.source_agent_id,
                "status": task.status,
                "result": task.result,
                "error": task.error,
                "created_at": task.created_at.isoformat(),
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "priority": task.priority,
            }
            for task in tasks
        ],
        "summary": delegator.get_status_summary()
    }


@router.get("/delegated-tasks/{task_id}")
async def get_delegated_task(task_id: str):
    """Get a specific delegated task."""
    from horbot.agent.task_delegation import get_task_delegator
    
    delegator = get_task_delegator()
    task = delegator.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    
    return {
        "id": task.id,
        "description": task.description,
        "target_agent_id": task.target_agent_id,
        "source_agent_id": task.source_agent_id,
        "status": task.status,
        "result": task.result,
        "error": task.error,
        "created_at": task.created_at.isoformat(),
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "priority": task.priority,
        "context": task.context,
    }


class DelegateTaskRequest(BaseModel):
    description: str
    target_agent_id: str
    source_agent_id: str
    context: Dict[str, Any] = {}
    priority: str = "normal"


@router.post("/delegated-tasks")
async def create_delegated_task(request: DelegateTaskRequest):
    """Create a new delegated task."""
    from horbot.agent.task_delegation import get_task_delegator
    
    delegator = get_task_delegator()
    
    task_id = await delegator.delegate_task(
        description=request.description,
        target_agent_id=request.target_agent_id,
        source_agent_id=request.source_agent_id,
        context=request.context,
        priority=request.priority,
    )
    
    return {
        "task_id": task_id,
        "status": "created",
        "message": f"Task delegated to {request.target_agent_id}"
    }


@router.post("/delegated-tasks/{task_id}/complete")
async def complete_delegated_task(task_id: str, result: Dict[str, Any]):
    """Mark a delegated task as completed."""
    from horbot.agent.task_delegation import get_task_delegator
    
    delegator = get_task_delegator()
    success = delegator.complete_task(task_id, result)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    
    return {"status": "completed", "task_id": task_id}


@router.post("/delegated-tasks/{task_id}/fail")
async def fail_delegated_task(task_id: str, error: str):
    """Mark a delegated task as failed."""
    from horbot.agent.task_delegation import get_task_delegator
    
    delegator = get_task_delegator()
    success = delegator.fail_task(task_id, error)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    
    return {"status": "failed", "task_id": task_id, "error": error}


@router.delete("/delegated-tasks/clear")
async def clear_completed_tasks():
    """Clear completed and failed tasks."""
    from horbot.agent.task_delegation import get_task_delegator
    
    delegator = get_task_delegator()
    cleared_count = delegator.clear_completed()
    
    return {
        "status": "success",
        "cleared_count": cleared_count
    }


# ============ Smart Task Router API ============

class AnalyzeTaskRequest(BaseModel):
    description: str
    context: Optional[Dict[str, Any]] = None


@router.post("/tasks/analyze")
async def analyze_task(request: AnalyzeTaskRequest):
    """Analyze a task to determine requirements and best agent."""
    from horbot.agent.task_delegation import get_smart_router
    from horbot.agent.manager import get_agent_manager
    
    router = get_smart_router()
    agent_manager = get_agent_manager()
    
    analysis = router.analyze_task(request.description, request.context)
    
    agents = agent_manager.get_all_agents()
    agents_data = [
        {
            "id": a.id,
            "capabilities": a.config.capabilities if hasattr(a, 'config') and hasattr(a.config, 'capabilities') else [],
            "is_main": a.is_main if hasattr(a, 'is_main') else False,
        }
        for a in agents
    ]
    
    best_agent_id = router.find_best_agent(analysis, agents_data)
    
    return {
        "analysis": analysis,
        "suggested_agent_id": best_agent_id,
    }


@router.post("/tasks/decompose")
async def decompose_task(request: AnalyzeTaskRequest):
    """Decompose a complex task into subtasks."""
    from horbot.agent.task_delegation import get_smart_router
    from horbot.agent.manager import get_agent_manager
    
    router = get_smart_router()
    agent_manager = get_agent_manager()
    
    analysis = router.analyze_task(request.description, request.context)
    
    agents = agent_manager.get_all_agents()
    agents_data = [
        {
            "id": a.id,
            "capabilities": a.config.capabilities if hasattr(a, 'config') and hasattr(a.config, 'capabilities') else [],
            "is_main": a.is_main if hasattr(a, 'is_main') else False,
        }
        for a in agents
    ]
    
    subtasks = router.decompose_task(request.description, analysis, agents_data)
    
    return {
        "original_task": request.description,
        "analysis": analysis,
        "subtasks": subtasks,
    }


@router.get("/agents/{agent_id}/metrics")
async def get_agent_performance_metrics(agent_id: str):
    """Get performance metrics for a specific agent."""
    from horbot.agent.task_delegation import get_smart_router
    from horbot.agent.manager import get_agent_manager
    
    router = get_smart_router()
    agent_manager = get_agent_manager()
    
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    
    metrics = router.get_agent_metrics(agent_id)
    
    return {
        "agent_id": agent_id,
        "metrics": metrics,
    }


@router.get("/agents/metrics/all")
async def get_all_agents_metrics():
    """Get performance metrics for all agents."""
    from horbot.agent.task_delegation import get_smart_router
    
    router = get_smart_router()
    
    return {
        "metrics": router.get_all_metrics()
    }
