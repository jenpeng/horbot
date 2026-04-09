#!/usr/bin/env python3
"""Replay one external-style inbound turn and verify source metadata persistence."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from horbot.agent.loop import AgentLoop
from horbot.agent.manager import get_agent_manager
from horbot.bus.events import InboundMessage
from horbot.bus.queue import MessageBus
from horbot.channels.endpoints import list_channel_endpoints
from horbot.config.loader import get_cached_config
from horbot.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from horbot.session.manager import SessionManager
from horbot.utils.paths import get_agent_memory_dir


class StubProvider(LLMProvider):
    """Minimal provider used to validate persistence without external network calls."""

    def __init__(self, reply: str, model: str, tool_path: str) -> None:
        super().__init__(api_key="stub", api_base="stub://local")
        self._reply = reply
        self._model = model
        self._tool_path = tool_path

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **_: Any,
    ) -> LLMResponse:
        if not any(message.get("role") == "tool" for message in messages):
            return LLMResponse(
                content="",
                tool_calls=[
                    ToolCallRequest(
                        id="external_inbound_memory_smoke_list_dir",
                        name="list_dir",
                        arguments={"path": self._tool_path},
                    )
                ],
                finish_reason="tool_calls",
            )
        return LLMResponse(content=self._reply)

    def get_default_model(self) -> str:
        return self._model


def _parse_memory_source_metadata(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    matches = re.findall(r"<!--\s*([^:]+):\s*(.*?)\s*-->", text)
    return {key.strip(): value.strip() for key, value in matches}


def _find_newest_file(directory: Path, suffix: str, started_at: float) -> Path | None:
    if not directory.exists():
        return None

    candidates = [
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix == suffix and path.stat().st_mtime >= started_at
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def _build_default_chat_id(channel_type: str) -> str:
    stamp = int(time.time())
    if channel_type == "sharecrm":
        return f"0:fs:horbot-extmem-smoke-{stamp}:"
    if channel_type == "feishu":
        return f"ou_horbot_extmem_smoke_{stamp}"
    return f"external-smoke-{stamp}"


def _discover_targets() -> list[tuple[str, str]]:
    config = get_cached_config()
    endpoints = list_channel_endpoints(config)
    targets: list[tuple[str, str]] = []
    for endpoint in endpoints:
        if not getattr(endpoint, "enabled", False):
            continue
        agent_id = str(getattr(endpoint, "agent_id", "") or "").strip()
        if not agent_id:
            continue
        targets.append((agent_id, endpoint.id))
    return targets


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

    target_chat_id = chat_id or _build_default_chat_id(endpoint.type)
    session_key = f"{endpoint.id}:{target_chat_id}"
    expected_reply = f"EXTERNAL_INBOUND_MEMORY_OK_{int(time.time())}"

    bus = MessageBus()
    session_manager = SessionManager(workspace=agent.get_sessions_dir())
    loop = AgentLoop(
        bus=bus,
        provider=StubProvider(
            expected_reply,
            agent.model or "stub-model",
            str(agent.get_workspace()),
        ),
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
        use_hierarchical_context=True,
        enable_hot_reload=False,
        agent_id=agent.id,
        agent_name=agent.name,
        team_ids=agent.teams,
    )

    agent_memory_dir = get_agent_memory_dir(agent.id)
    execution_dir = agent_memory_dir / "executions" / "recent"
    memory_dir = agent_memory_dir / "memories" / "L1"
    started_at = time.time()

    msg = InboundMessage(
        channel=endpoint.type,
        sender_id="external-smoke",
        chat_id=target_chat_id,
        content="请仅回复我给你的固定确认串，不要额外解释。",
        channel_instance_id=endpoint.id,
        target_agent_id=agent.id,
        metadata={
            "channel_instance_id": endpoint.id,
            "target_agent_id": agent.id,
            "channel_type": endpoint.type,
            "channel_endpoint_name": endpoint.name or endpoint.id,
            "smoke_test": "external_inbound_memory",
        },
        session_key_override=session_key,
    )

    try:
        response = await loop.process_message(msg)
    finally:
        await loop.cleanup()

    execution_file = _find_newest_file(execution_dir, ".json", started_at)
    memory_file = _find_newest_file(memory_dir, ".md", started_at)
    if execution_file is None:
        raise RuntimeError(f"No execution log created under {execution_dir}")
    if memory_file is None:
        raise RuntimeError(f"No memory file created under {memory_dir}")

    execution_payload = json.loads(execution_file.read_text(encoding="utf-8"))
    memory_metadata = _parse_memory_source_metadata(memory_file)

    expected_source = {
        "source_session_key": session_key,
        "source_channel_instance_id": endpoint.id,
        "source_chat_id": target_chat_id,
        "source_channel_type": endpoint.type,
    }

    for key, value in expected_source.items():
        actual = execution_payload.get(key)
        if actual != value:
            raise RuntimeError(
                f"Execution metadata mismatch for {key}: expected={value!r} actual={actual!r}"
            )
        mem_actual = memory_metadata.get(key)
        if mem_actual != value:
            raise RuntimeError(
                f"Memory metadata mismatch for {key}: expected={value!r} actual={mem_actual!r}"
            )

    return {
        "ok": True,
        "agent_id": agent.id,
        "agent_name": agent.name,
        "endpoint_id": endpoint.id,
        "channel_type": endpoint.type,
        "chat_id": target_chat_id,
        "session_key": session_key,
        "response_content": getattr(response, "content", None),
        "execution_file": str(execution_file),
        "memory_file": str(memory_file),
        "execution_source": {key: execution_payload.get(key) for key in expected_source},
        "memory_source": {key: memory_metadata.get(key) for key in expected_source},
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
    parser.add_argument("--endpoint-id", help="Channel endpoint id, e.g. legacy:feishu")
    parser.add_argument("--chat-id", help="Optional chat id override")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
