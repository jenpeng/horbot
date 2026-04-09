import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from horbot.agent.loop import AgentLoop
from horbot.bus.events import InboundMessage, OutboundMessage
from horbot.bus.queue import MessageBus
from horbot.channels.telemetry import clear_channel_telemetry, get_channel_events, get_channel_summary
from horbot.config.schema import Config
from horbot.gateway.http_api import build_gateway_http_app
from horbot.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from horbot.session.manager import SessionManager
from horbot.utils.paths import HORBOT_ROOT_ENV
from horbot.web.api import _configure_web_agent_loop_message_routing


class StubProvider(LLMProvider):
    def __init__(self) -> None:
        super().__init__(api_key="stub", api_base="stub://local")
        self.seen_messages = []

    async def chat(self, messages, **kwargs):
        self.seen_messages = [dict(message) for message in messages]
        if not any(message.get("role") == "tool" for message in messages):
            return LLMResponse(
                content="",
                tool_calls=[
                    ToolCallRequest(
                        id="bound_channel_dispatch_message",
                        name="message",
                        arguments={
                            "channel": "feishu",
                            "chat_id": "group-001",
                            "content": "BOUND_CHANNEL_ROUTE_MARKER_TEST",
                            "channel_instance_id": "sales-feishu",
                            "target_agent_id": "agent-01",
                        },
                    )
                ],
                finish_reason="tool_calls",
            )
        return LLMResponse(content="BOUND_CHANNEL_ROUTE_OK_TEST")

    def get_default_model(self) -> str:
        return "stub-model"


class BoundChannelDispatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_agent_loop_routes_bound_external_channel_via_gateway(self):
        config = Config()
        provider = StubProvider()
        bus = MessageBus()
        endpoint = SimpleNamespace(
            id="sales-feishu",
            type="feishu",
            name="Sales Feishu",
            agent_id="agent-01",
            enabled=True,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            session_manager = SessionManager(workspace=Path(tmpdir) / "sessions")
            loop = AgentLoop(
                bus=bus,
                provider=provider,
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
                session_manager=session_manager,
                use_hierarchical_context=False,
                enable_hot_reload=False,
                agent_id="agent-01",
                agent_name="Agent 01",
                team_ids=[],
            )
            _configure_web_agent_loop_message_routing(loop, bus)

            captured = []
            clear_channel_telemetry(endpoint.id)

            async def _send(msg: OutboundMessage) -> None:
                captured.append(msg)

            fake_channel = SimpleNamespace(
                name="feishu",
                endpoint_id="sales-feishu",
                target_agent_id="agent-01",
                send=_send,
            )

            class FakeManager:
                enabled_channels = ["sales-feishu"]

                def _resolve_outbound_channel(self, msg: OutboundMessage):
                    if msg.channel_instance_id == "sales-feishu":
                        return fake_channel
                    return None

            gateway_app = build_gateway_http_app(FakeManager())

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

            with patch("horbot.channels.endpoints.list_channel_endpoints", return_value=[endpoint]), patch(
                "horbot.web.api._dispatch_outbound_via_gateway",
                new=_dispatch_via_inprocess_gateway,
            ):
                response = await loop.process_message(
                    InboundMessage(
                        channel="web",
                        sender_id="tester",
                        chat_id="dm_agent-01",
                        content="请使用 message 工具把消息发到你绑定的外部渠道。",
                    ),
                    session_key="web:dm_agent-01",
                )

            await loop.cleanup()

        self.assertEqual(response.content, "Message sent to feishu:group-001 via sales-feishu")
        self.assertEqual(len(captured), 1)
        outbound = captured[0]
        self.assertEqual(outbound.channel, "feishu")
        self.assertEqual(outbound.chat_id, "group-001")
        self.assertEqual(outbound.channel_instance_id, "sales-feishu")
        self.assertEqual(outbound.target_agent_id, "agent-01")
        self.assertEqual(outbound.content, "BOUND_CHANNEL_ROUTE_MARKER_TEST")
        self.assertEqual(outbound.metadata["_source_channel"], "web")
        self.assertEqual(outbound.metadata["_source_chat_id"], "dm_agent-01")
        self.assertEqual(get_channel_summary("sales-feishu")["messages_sent"], 1)
        self.assertEqual(get_channel_events("sales-feishu", limit=1)[0]["event_type"], "outbound")
        runtime_hint_text = "\n".join(
            str(message.get("content") or "")
            for message in provider.seen_messages
            if message.get("role") == "user"
        )
        self.assertIn("[Bound Channel Routing]", runtime_hint_text)
        self.assertIn("sales-feishu", runtime_hint_text)

    async def test_bound_external_dispatch_persists_outbound_metadata_to_execution_and_memory(self):
        config = Config()
        provider = StubProvider()
        bus = MessageBus()
        endpoint = SimpleNamespace(
            id="sales-feishu",
            type="feishu",
            name="Sales Feishu",
            agent_id="agent-01",
            enabled=True,
        )
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ,
            {HORBOT_ROOT_ENV: str(Path(tmpdir) / ".horbot")},
            clear=False,
        ):
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            session_manager = SessionManager(workspace=Path(tmpdir) / "sessions")
            loop = AgentLoop(
                bus=bus,
                provider=provider,
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
                session_manager=session_manager,
                use_hierarchical_context=True,
                enable_hot_reload=False,
                agent_id="agent-01",
                agent_name="Agent 01",
                team_ids=[],
            )
            _configure_web_agent_loop_message_routing(loop, bus)

            captured = []
            clear_channel_telemetry(endpoint.id)

            async def _send(msg: OutboundMessage) -> None:
                captured.append(msg)

            fake_channel = SimpleNamespace(
                name="feishu",
                endpoint_id="sales-feishu",
                target_agent_id="agent-01",
                send=_send,
            )

            class FakeManager:
                enabled_channels = ["sales-feishu"]

                def _resolve_outbound_channel(self, msg: OutboundMessage):
                    if msg.channel_instance_id == "sales-feishu":
                        return fake_channel
                    return None

            gateway_app = build_gateway_http_app(FakeManager())

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

            with patch("horbot.channels.endpoints.list_channel_endpoints", return_value=[endpoint]), patch(
                "horbot.web.api._dispatch_outbound_via_gateway",
                new=_dispatch_via_inprocess_gateway,
            ):
                await loop.process_message(
                    InboundMessage(
                        channel="web",
                        sender_id="tester",
                        chat_id="dm_agent-01",
                        content="请把这条消息发到绑定的飞书群。",
                    ),
                    session_key="web:dm_agent-01",
                )

            await loop.cleanup()

            agent_memory_root = Path(tmpdir) / ".horbot" / "agents" / "agent-01" / "memory"
            execution_files = sorted(
                (
                    path for path in (agent_memory_root / "executions" / "recent").glob("*.json")
                    if path.name != "README.md"
                ),
                key=lambda path: path.stat().st_mtime,
            )
            self.assertTrue(execution_files)
            execution_log = json.loads(execution_files[-1].read_text(encoding="utf-8"))

            self.assertEqual(execution_log["source_channel_instance_id"], "web")
            self.assertEqual(execution_log["outbound_count"], 1)
            self.assertEqual(execution_log["outbound_channel_instance_id"], "sales-feishu")
            self.assertEqual(execution_log["outbound_channel_type"], "feishu")
            self.assertEqual(execution_log["outbound_chat_id"], "group-001")
            self.assertEqual(execution_log["outbound_target_agent_id"], "agent-01")
            self.assertEqual(execution_log["outbound_via"], "gateway_http")
            self.assertEqual(len(execution_log["outbound_messages"]), 1)
            self.assertEqual(
                execution_log["outbound_messages"][0]["outbound_channel_instance_id"],
                "sales-feishu",
            )

            memory_files = sorted(
                (
                    path for path in (agent_memory_root / "memories" / "L1").glob("memory_*.md")
                    if path.name != "README.md"
                ),
                key=lambda path: path.stat().st_mtime,
            )
            self.assertTrue(memory_files)
            memory_text = memory_files[-1].read_text(encoding="utf-8")
            self.assertIn("<!-- source_channel_instance_id: web -->", memory_text)
            self.assertIn("<!-- outbound_channel_instance_id: sales-feishu -->", memory_text)
            self.assertIn("<!-- outbound_channel_type: feishu -->", memory_text)
            self.assertIn("<!-- outbound_chat_id: group-001 -->", memory_text)
            self.assertIn("<!-- outbound_target_agent_id: agent-01 -->", memory_text)
            self.assertIn("<!-- outbound_via: gateway_http -->", memory_text)
            self.assertEqual(len(captured), 1)


if __name__ == "__main__":
    unittest.main()
