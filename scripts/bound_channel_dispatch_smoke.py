#!/usr/bin/env python3
"""Verify DM -> agent tool call -> bound external channel routing stays correct."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from horbot.agent.loop import AgentLoop
from horbot.agent.manager import get_agent_manager
from horbot.bus.events import InboundMessage, OutboundMessage
from horbot.bus.queue import MessageBus
from horbot.channels.endpoints import list_channel_endpoints
from horbot.channels.telemetry import clear_channel_telemetry, get_channel_events, get_channel_summary
from horbot.config.loader import get_cached_config
from horbot.gateway.http_api import build_gateway_http_app
from horbot.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from horbot.session.manager import SessionManager
from horbot.web.api import _configure_web_agent_loop_message_routing


class StubProvider(LLMProvider):
    """Provider that always issues one outbound message tool call, then confirms."""

    def __init__(
        self,
        *,
        endpoint_id: str,
        channel_type: str,
        target_agent_id: str,
        target_chat_id: str,
        outbound_content: str,
        final_reply: str,
        model: str,
    ) -> None:
        super().__init__(api_key="stub", api_base="stub://local")
        self._endpoint_id = endpoint_id
        self._channel_type = channel_type
        self._target_agent_id = target_agent_id
        self._target_chat_id = target_chat_id
        self._outbound_content = outbound_content
        self._final_reply = final_reply
        self._model = model
        self.seen_messages: list[dict[str, Any]] = []

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **_: Any,
    ) -> LLMResponse:
        self.seen_messages = [dict(message) for message in messages]
        if not any(message.get("role") == "tool" for message in messages):
            return LLMResponse(
                content="",
                tool_calls=[
                    ToolCallRequest(
                        id="bound_channel_dispatch_message",
                        name="message",
                        arguments={
                            "channel": self._channel_type,
                            "chat_id": self._target_chat_id,
                            "content": self._outbound_content,
                            "channel_instance_id": self._endpoint_id,
                            "target_agent_id": self._target_agent_id,
                        },
                    )
                ],
                finish_reason="tool_calls",
            )
        return LLMResponse(content=self._final_reply)

    def get_default_model(self) -> str:
        return self._model


def _discover_targets() -> list[tuple[str, str]]:
    config = get_cached_config()
    targets: list[tuple[str, str]] = []
    for endpoint in list_channel_endpoints(config):
        if not getattr(endpoint, "enabled", False):
            continue
        agent_id = str(getattr(endpoint, "agent_id", "") or "").strip()
        if not agent_id:
            continue
        targets.append((agent_id, endpoint.id))
    return targets


def _build_default_external_chat_id(channel_type: str) -> str:
    stamp = int(time.time())
    if channel_type == "sharecrm":
        return f"0:fs:horbot-bound-dispatch-{stamp}:"
    if channel_type == "feishu":
        return f"group_horbot_bound_dispatch_{stamp}"
    return f"group-horbot-bound-dispatch-{stamp}"


async def run_smoke(agent_id: str, endpoint_id: str, chat_id: str | None = None) -> dict[str, Any]:
    config = get_cached_config()
    agent = get_agent_manager().get_agent(agent_id)
    if agent is None:
        raise RuntimeError(f"Agent not found: {agent_id}")

    endpoint = next((item for item in list_channel_endpoints(config) if item.id == endpoint_id), None)
    if endpoint is None:
        raise RuntimeError(f"Channel endpoint not found: {endpoint_id}")
    if endpoint.agent_id != agent_id:
        raise RuntimeError(
            f"Endpoint {endpoint_id} is bound to agent {endpoint.agent_id}, not {agent_id}"
        )

    dm_chat_id = f"dm_bound_channel_dispatch_{agent.id}_{int(time.time())}"
    target_chat_id = chat_id or _build_default_external_chat_id(endpoint.type)
    outbound_content = f"BOUND_CHANNEL_ROUTE_MARKER_{int(time.time())}"
    final_reply = f"BOUND_CHANNEL_ROUTE_OK_{int(time.time())}"
    provider = StubProvider(
        endpoint_id=endpoint.id,
        channel_type=endpoint.type,
        target_agent_id=agent.id,
        target_chat_id=target_chat_id,
        outbound_content=outbound_content,
        final_reply=final_reply,
        model=agent.model or "stub-model",
    )

    bus = MessageBus()
    session_manager = SessionManager(workspace=agent.get_sessions_dir())
    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=agent.get_workspace(),
        model=agent.model or "stub-model",
        max_iterations=config.agents.defaults.max_tool_iterations,
        temperature=config.agents.defaults.temperature,
        max_tokens=config.agents.defaults.max_tokens,
        memory_window=config.agents.defaults.memory_window,
        brave_api_key=config.tools.web.search.api_key,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        mcp_servers={},
        channels_config=config.channels,
        exec_config=config.tools.exec,
        session_manager=session_manager,
        use_hierarchical_context=False,
        enable_hot_reload=False,
        agent_id=agent.id,
        agent_name=agent.name,
        team_ids=agent.teams,
    )
    _configure_web_agent_loop_message_routing(loop, bus)

    captured: list[OutboundMessage] = []
    clear_channel_telemetry(endpoint.id)

    async def _send(msg: OutboundMessage) -> None:
        captured.append(msg)

    fake_channel = SimpleNamespace(
        name=endpoint.type,
        endpoint_id=endpoint.id,
        target_agent_id=agent.id,
        send=_send,
    )

    class FakeManager:
        enabled_channels = [endpoint.id]

        def _resolve_outbound_channel(self, msg: OutboundMessage):
            if msg.channel_instance_id == endpoint.id:
                return fake_channel
            return None

    fake_manager = FakeManager()
    gateway_app = build_gateway_http_app(fake_manager)

    async def _dispatch_via_inprocess_gateway(msg: OutboundMessage) -> None:
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
        transport = httpx.ASGITransport(app=gateway_app, client=("127.0.0.1", 43123))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post("/api/gateway/outbound", json=payload)
        response.raise_for_status()

    try:
        with patch("horbot.web.api._dispatch_outbound_via_gateway", new=_dispatch_via_inprocess_gateway):
            response = await loop.process_message(
                InboundMessage(
                    channel="web",
                    sender_id="bound-channel-dispatch-smoke",
                    chat_id=dm_chat_id,
                    content=(
                        "请使用 message 工具把一条消息发到你绑定的外部渠道群里，"
                        "必须使用绑定 endpoint，不要直接回复文本。"
                    ),
                    metadata={"smoke_test": "bound_channel_dispatch"},
                ),
                session_key=f"web:{dm_chat_id}",
            )
    finally:
        await loop.cleanup()

    if len(captured) != 1:
        raise RuntimeError(f"Expected exactly one outbound gateway dispatch, got {len(captured)}")

    outbound = captured[0]
    telemetry_summary = get_channel_summary(endpoint.id)
    telemetry_events = get_channel_events(endpoint.id, limit=5)
    runtime_hint_text = "\n".join(
        str(message.get("content") or "")
        for message in provider.seen_messages
        if message.get("role") == "user"
    )

    expected_metadata = {
        "_source_channel": "web",
        "_source_chat_id": dm_chat_id,
        "channel_instance_id": endpoint.id,
        "target_agent_id": agent.id,
    }
    for key, value in expected_metadata.items():
        actual = outbound.metadata.get(key) if outbound.metadata else None
        if actual != value:
            raise RuntimeError(
                f"Outbound metadata mismatch for {key}: expected={value!r} actual={actual!r}"
            )

    if outbound.channel != endpoint.type:
        raise RuntimeError(
            f"Outbound channel mismatch: expected={endpoint.type!r} actual={outbound.channel!r}"
        )
    if outbound.channel_instance_id != endpoint.id:
        raise RuntimeError(
            f"Outbound channel_instance_id mismatch: expected={endpoint.id!r} actual={outbound.channel_instance_id!r}"
        )
    if outbound.target_agent_id != agent.id:
        raise RuntimeError(
            f"Outbound target_agent_id mismatch: expected={agent.id!r} actual={outbound.target_agent_id!r}"
        )
    if outbound.chat_id != target_chat_id:
        raise RuntimeError(
            f"Outbound chat_id mismatch: expected={target_chat_id!r} actual={outbound.chat_id!r}"
        )
    if outbound.content != outbound_content:
        raise RuntimeError(
            f"Outbound content mismatch: expected={outbound_content!r} actual={outbound.content!r}"
        )
    if "[Bound Channel Routing]" not in runtime_hint_text or endpoint.id not in runtime_hint_text:
        raise RuntimeError("Runtime bound-channel hints were not injected into the DM prompt")
    if int(telemetry_summary.get("messages_sent", 0)) < 1:
        raise RuntimeError(f"Gateway telemetry did not record outbound send for {endpoint.id}")
    if not telemetry_events or telemetry_events[0].get("event_type") != "outbound":
        raise RuntimeError(f"Gateway telemetry did not expose outbound event for {endpoint.id}")

    return {
        "ok": True,
        "agent_id": agent.id,
        "agent_name": agent.name,
        "endpoint_id": endpoint.id,
        "channel_type": endpoint.type,
        "target_chat_id": target_chat_id,
        "outbound_content": outbound.content,
        "final_reply": getattr(response, "content", None),
        "runtime_hint_contains_endpoint": endpoint.id in runtime_hint_text,
        "telemetry_summary": telemetry_summary,
        "telemetry_events": telemetry_events,
        "outbound_metadata": {
            key: outbound.metadata.get(key) if outbound.metadata else None
            for key in sorted(expected_metadata)
        },
    }


async def run_many(targets: list[tuple[str, str]]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for agent_id, endpoint_id in targets:
        try:
            result = await run_smoke(agent_id, endpoint_id)
        except Exception as exc:
            result = {
                "ok": False,
                "agent_id": agent_id,
                "endpoint_id": endpoint_id,
                "error": str(exc),
            }
        results.append(result)
    return {
        "ok": all(bool(item.get("ok")) for item in results),
        "count": len(results),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent-id", help="Bound agent id")
    parser.add_argument("--endpoint-id", help="Bound channel endpoint id")
    parser.add_argument("--chat-id", help="Optional outbound chat id override")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run against all enabled endpoints bound to agents. Default when agent/endpoint are omitted.",
    )
    args = parser.parse_args()

    run_all = args.all or (not args.agent_id and not args.endpoint_id)
    if run_all:
        targets = _discover_targets()
        if not targets:
            raise SystemExit("No enabled channel endpoints with bound agents found.")
        result = asyncio.run(run_many(targets))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1

    if not args.agent_id or not args.endpoint_id:
        raise SystemExit("--agent-id and --endpoint-id must be provided together, or omit both to auto-discover.")

    result = asyncio.run(run_smoke(args.agent_id, args.endpoint_id, args.chat_id))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
