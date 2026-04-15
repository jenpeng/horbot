import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import httpx

from horbot.agent.loop import AgentLoop
from horbot.agent.manager import get_agent_manager
from horbot.bus.events import InboundMessage
from horbot.bus.queue import MessageBus
from horbot.config.normalizer import normalize_config
from horbot.config.schema import AgentConfig, Config
from horbot.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from horbot.session.manager import SessionManager
from horbot.utils.paths import HORBOT_ROOT_ENV
from horbot.web.api import _build_memory_store
from horbot.web.main import app


class ToolAuditApiProvider(LLMProvider):
    def __init__(self, target_path: Path) -> None:
        super().__init__(api_key="stub", api_base="stub://local")
        self._target_path = target_path

    async def chat(self, messages, **kwargs):
        if not any(message.get("role") == "tool" for message in messages):
            return LLMResponse(
                content="",
                tool_calls=[
                    ToolCallRequest(
                        id="tool_audit_api_read_file",
                        name="read_file",
                        arguments={"path": str(self._target_path)},
                    )
                ],
                finish_reason="tool_calls",
            )
        return LLMResponse(content="读取完成")

    def get_default_model(self) -> str:
        return "stub-model"


class ToolAuditApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_memory_tool_audits_endpoint_returns_recent_audit_events(self):
        with tempfile.TemporaryDirectory() as tempdir:
            horbot_root = Path(tempdir) / ".horbot"
            workspace_root = Path(tempdir) / "workspace"
            workspace = workspace_root / "agent-01"
            workspace.mkdir(parents=True, exist_ok=True)
            target_file = workspace / "notes.txt"
            target_file.write_text("audit api test\n", encoding="utf-8")

            config = Config()
            config.agents.defaults.workspace = str(workspace_root)
            config.agents.instances = {
                "agent-01": AgentConfig(
                    id="agent-01",
                    name="Agent 01",
                    workspace=str(workspace),
                    is_main=True,
                ),
            }
            config = normalize_config(config)

            manager = get_agent_manager()
            with (
                patch.dict(os.environ, {HORBOT_ROOT_ENV: str(horbot_root)}, clear=False),
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.agent.manager.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
            ):
                manager.reload(config)

                loop = AgentLoop(
                    bus=MessageBus(),
                    provider=ToolAuditApiProvider(target_file),
                    workspace=workspace,
                    model="stub-model",
                    max_iterations=config.agents.defaults.max_tool_iterations,
                    temperature=config.agents.defaults.temperature,
                    max_tokens=config.agents.defaults.max_tokens,
                    memory_window=config.agents.defaults.memory_window,
                    brave_api_key=config.tools.web.search.api_key,
                    restrict_to_workspace=config.tools.restrict_to_workspace,
                    mcp_servers={},
                    channels_config=config.channels,
                    exec_config=config.tools.exec,
                    session_manager=SessionManager(workspace=Path(tempdir) / "sessions"),
                    use_hierarchical_context=True,
                    enable_hot_reload=False,
                    agent_id="agent-01",
                    agent_name="Agent 01",
                    team_ids=[],
                )

                response = await loop.process_message(
                    InboundMessage(
                        channel="web",
                        sender_id="tester",
                        chat_id="dm_agent-01",
                        content="请读取 notes.txt",
                    ),
                    session_key="web:dm_agent-01",
                )
                self.assertEqual(response.content, "读取完成")
                await loop.cleanup()

                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    api_response = await client.get(
                        "/api/memory/tool-audits",
                        params={
                            "agent_id": "agent-01",
                            "session_key": "web:dm_agent-01",
                            "limit": 10,
                        },
                    )

            self.assertEqual(api_response.status_code, 200)
            payload = api_response.json()
            self.assertEqual(payload["agent_id"], "agent-01")
            self.assertEqual(payload["session_key"], "web:dm_agent-01")
            self.assertEqual(payload["window_hours"], 24)
            self.assertEqual(payload["total_returned"], 1)
            self.assertEqual(payload["total_matches"], 1)
            self.assertEqual(payload["blocked_count"], 0)
            self.assertEqual(payload["error_count"], 0)
            self.assertEqual(payload["summary"]["window_hours"], 24)
            self.assertEqual(payload["summary"]["total_count"], 1)
            self.assertEqual(payload["summary"]["blocked_count"], 0)
            self.assertEqual(payload["summary"]["exec_count"], 0)
            self.assertEqual(payload["summary"]["outbound_count"], 0)
            self.assertEqual(len(payload["items"]), 1)
            item = payload["items"][0]
            self.assertEqual(item["type"], "tool_audit")
            self.assertEqual(item["tool_name"], "read_file")
            self.assertEqual(item["audit_event"]["event_type"], "tool_result")
            self.assertEqual(item["audit_event"]["session_key"], "web:dm_agent-01")
            self.assertEqual(item["audit_event"]["origin"], "process_message")

    async def test_memory_tool_audits_endpoint_returns_24h_risk_summary(self):
        with tempfile.TemporaryDirectory() as tempdir:
            horbot_root = Path(tempdir) / ".horbot"
            workspace_root = Path(tempdir) / "workspace"
            workspace = workspace_root / "agent-01"
            workspace.mkdir(parents=True, exist_ok=True)

            config = Config()
            config.agents.defaults.workspace = str(workspace_root)
            config.agents.instances = {
                "agent-01": AgentConfig(
                    id="agent-01",
                    name="Agent 01",
                    workspace=str(workspace),
                    is_main=True,
                ),
            }
            config = normalize_config(config)

            manager = get_agent_manager()
            with (
                patch.dict(os.environ, {HORBOT_ROOT_ENV: str(horbot_root)}, clear=False),
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.agent.manager.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
            ):
                manager.reload(config)
                _, _, memory_store = _build_memory_store("agent-01")
                session_key = "web:dm_agent-01"
                now = datetime.now()

                for execution_log in [
                    {
                        "type": "tool_audit",
                        "task": "tool:exec",
                        "result": "denied",
                        "tool_name": "exec",
                        "tools_used": ["exec"],
                        "timestamp": (now - timedelta(hours=1)).isoformat(),
                        "message_count": 1,
                        "audit_event": {"event_type": "tool_denied"},
                        "guard_blocked": False,
                        "guard_reasons": [],
                        "permission_level": "deny",
                        "duration_ms": 5,
                        "error": "denied",
                    },
                    {
                        "type": "tool_audit",
                        "task": "tool:web_fetch",
                        "result": "[Security notice]",
                        "tool_name": "web_fetch",
                        "tools_used": ["web_fetch"],
                        "timestamp": (now - timedelta(hours=2)).isoformat(),
                        "message_count": 1,
                        "audit_event": {"event_type": "tool_result"},
                        "guard_blocked": True,
                        "guard_reasons": ["instruction override content"],
                        "permission_level": "allow",
                        "duration_ms": 7,
                        "error": None,
                    },
                    {
                        "type": "tool_audit",
                        "task": "tool:message",
                        "result": "sent",
                        "tool_name": "message",
                        "tools_used": ["message"],
                        "timestamp": (now - timedelta(hours=3)).isoformat(),
                        "message_count": 1,
                        "audit_event": {"event_type": "tool_result"},
                        "guard_blocked": False,
                        "guard_reasons": [],
                        "permission_level": "allow",
                        "duration_ms": 9,
                        "error": None,
                    },
                    {
                        "type": "tool_audit",
                        "task": "tool:web_search",
                        "result": "ok",
                        "tool_name": "web_search",
                        "tools_used": ["web_search"],
                        "timestamp": (now - timedelta(hours=30)).isoformat(),
                        "message_count": 1,
                        "audit_event": {"event_type": "tool_result"},
                        "guard_blocked": False,
                        "guard_reasons": [],
                        "permission_level": "allow",
                        "duration_ms": 11,
                        "error": None,
                    },
                ]:
                    memory_store.add_execution_memory(
                        execution_log,
                        session_key,
                        index_as_memory=False,
                    )

                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43124))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    api_response = await client.get(
                        "/api/memory/tool-audits",
                        params={
                            "agent_id": "agent-01",
                            "session_key": session_key,
                            "limit": 10,
                            "summary_window_hours": 24,
                        },
                    )
                    exec_only_response = await client.get(
                        "/api/memory/tool-audits",
                        params={
                            "agent_id": "agent-01",
                            "session_key": session_key,
                            "limit": 10,
                            "risk_kind": "exec",
                        },
                    )
                    short_window_response = await client.get(
                        "/api/memory/tool-audits",
                        params={
                            "agent_id": "agent-01",
                            "session_key": session_key,
                            "limit": 10,
                            "window_hours": 4,
                        },
                    )

            self.assertEqual(api_response.status_code, 200)
            payload = api_response.json()
            self.assertEqual(payload["summary"]["window_hours"], 24)
            self.assertEqual(payload["summary"]["total_count"], 3)
            self.assertEqual(payload["summary"]["blocked_count"], 2)
            self.assertEqual(payload["summary"]["error_count"], 1)
            self.assertEqual(payload["summary"]["exec_count"], 1)
            self.assertEqual(payload["summary"]["outbound_count"], 2)

            self.assertEqual(exec_only_response.status_code, 200)
            exec_payload = exec_only_response.json()
            self.assertEqual(exec_payload["risk_kind"], "exec")
            self.assertEqual(exec_payload["window_hours"], 24)
            self.assertEqual(exec_payload["total_returned"], 1)
            self.assertEqual(exec_payload["total_matches"], 1)
            self.assertEqual(len(exec_payload["items"]), 1)
            self.assertEqual(exec_payload["items"][0]["tool_name"], "exec")

            self.assertEqual(short_window_response.status_code, 200)
            short_window_payload = short_window_response.json()
            self.assertEqual(short_window_payload["window_hours"], 4)
            self.assertEqual(short_window_payload["total_matches"], 3)
            self.assertEqual(short_window_payload["total_returned"], 3)


if __name__ == "__main__":
    unittest.main()
