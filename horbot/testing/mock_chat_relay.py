"""Mock SSE regression for local multi-agent relay flows."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import httpx
from fastapi import FastAPI

from horbot.session.manager import SessionManager
from horbot.web.api import router as api_router


class FakeAgent:
    def __init__(self, agent_id: str, name: str, is_main: bool = False):
        self.id = agent_id
        self.name = name
        self.is_main = is_main


class FakeAgentManager:
    def __init__(self):
        self.agents = {
            "alpha": FakeAgent("alpha", "Alpha", is_main=True),
            "beta": FakeAgent("beta", "Beta"),
        }

    def get_agent(self, agent_id: str):
        return self.agents.get(agent_id)

    def get_all_agents(self):
        return list(self.agents.values())

    def get_main_agent(self):
        return self.agents["alpha"]


class FakeWorkspaceManager:
    def get_team_workspace(self, team_id: str):
        return None


class FakeResponse:
    def __init__(self, content: str):
        self.content = content
        self.metadata = {}


class FakeAgentLoop:
    def __init__(self, agent_id: str, outputs: dict[str, Any], calls: list[dict[str, Any]]):
        self.agent_id = agent_id
        self.outputs = outputs
        self.calls = calls

    async def process_message(self, msg, **kwargs):
        self.calls.append(
            {
                "agent_id": self.agent_id,
                "content": msg.content,
                "speaking_to": kwargs.get("speaking_to"),
                "conversation_type": kwargs.get("conversation_type"),
            }
        )

        output = self.outputs[self.agent_id]
        if isinstance(output, list):
            if not output:
                raise AssertionError(f"No remaining outputs configured for {self.agent_id}")
            content = output.pop(0)
        else:
            content = output

        await kwargs["on_step_start"]("thinking_1", "thinking", "思考中...")
        await kwargs["on_status"]("正在思考...")
        await kwargs["on_step_complete"]("thinking_1", "success", {"thinking": f"{self.agent_id} thinking"})
        await kwargs["on_step_start"]("response_1", "response", "生成回复")
        await kwargs["on_progress"](content)
        await kwargs["on_step_complete"]("response_1", "success", {"content": content})
        return FakeResponse(content)


def _decode_sse_lines(lines: list[str]) -> list[dict[str, Any]]:
    return [json.loads(line[6:]) for line in lines if line.startswith("data: ")]


async def run_mock_relay_stream_test() -> dict[str, Any]:
    """Run a real SSE request against /api/chat/stream using fully local fake agents."""
    fake_agent_manager = FakeAgentManager()
    fake_workspace_manager = FakeWorkspaceManager()
    loop_calls: list[dict[str, Any]] = []
    outputs = {
        "alpha": ["@Beta 接力第一跳", "接力完成2"],
        "beta": "@Alpha 接力回给你",
    }
    loops = {
        agent_id: FakeAgentLoop(agent_id, outputs, loop_calls)
        for agent_id in outputs
    }

    async def fake_get_agent_loop_with_session_manager(agent_id, session_manager):
        return loops[agent_id]

    fake_config = SimpleNamespace(
        get_provider=lambda: SimpleNamespace(api_key="mock-key", api_base=None),
    )

    payload = {
        "content": "请开始接力",
        "session_key": "web:test_mock_relay_e2e",
        "group_chat": True,
        "mentioned_agents": ["alpha"],
        "conversation_id": "test_mock_relay_e2e",
        "conversation_type": "team",
    }

    result: dict[str, Any] = {
        "ok": False,
        "status_code": None,
        "events": [],
        "agent_start_sequence": [],
        "agent_done_sequence": [],
        "mention_sequence": [],
        "loop_calls": loop_calls,
        "errors": [],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        session_manager = SessionManager(workspace=Path(tmpdir))
        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        with (
            patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager),
            patch("horbot.workspace.manager.get_workspace_manager", return_value=fake_workspace_manager),
            patch("horbot.web.api.get_session_manager", return_value=session_manager),
            patch("horbot.web.api.get_cached_config", return_value=fake_config),
            patch(
                "horbot.web.api.get_agent_loop_with_session_manager",
                side_effect=fake_get_agent_loop_with_session_manager,
            ),
        ):
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://mock-horbot.local",
            ) as client:
                async with client.stream("POST", "/api/chat/stream", json=payload) as response:
                    result["status_code"] = response.status_code
                    lines = [line async for line in response.aiter_lines() if line]

    events = _decode_sse_lines(lines)
    result["events"] = [
        {
            "event": event.get("event"),
            "agent_id": event.get("agent_id"),
            "mentioned_by": event.get("mentioned_by"),
            "content": event.get("content"),
            "total_agents": event.get("total_agents"),
        }
        for event in events
        if event.get("event") in {"agent_start", "agent_done", "agent_mentioned", "done", "agent_error"}
    ]
    result["agent_start_sequence"] = [
        event["agent_id"] for event in events if event.get("event") == "agent_start"
    ]
    result["agent_done_sequence"] = [
        [event.get("agent_id"), event.get("content")]
        for event in events
        if event.get("event") == "agent_done"
    ]
    result["mention_sequence"] = [
        [event.get("mentioned_by"), event.get("agent_id")]
        for event in events
        if event.get("event") == "agent_mentioned"
    ]

    if result["status_code"] != 200:
        result["errors"].append(f"unexpected_status={result['status_code']}")
    if result["agent_start_sequence"] != ["alpha", "beta", "alpha"]:
        result["errors"].append(
            f"unexpected_agent_start_sequence={result['agent_start_sequence']}"
        )
    if result["agent_done_sequence"] != [
        ["alpha", "@Beta 接力第一跳"],
        ["beta", "@Alpha 接力回给你"],
        ["alpha", "接力完成2"],
    ]:
        result["errors"].append(
            f"unexpected_agent_done_sequence={result['agent_done_sequence']}"
        )
    if result["mention_sequence"] != [["alpha", "beta"], ["beta", "alpha"]]:
        result["errors"].append(
            f"unexpected_mention_sequence={result['mention_sequence']}"
        )
    if not events or events[-1].get("event") != "done" or events[-1].get("total_agents") != 3:
        result["errors"].append("missing_final_done_event")
    if [call["agent_id"] for call in loop_calls] != ["alpha", "beta", "alpha"]:
        result["errors"].append(f"unexpected_loop_call_order={loop_calls}")

    result["ok"] = not result["errors"]
    return result
