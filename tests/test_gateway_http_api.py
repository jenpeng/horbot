import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from horbot.agent.tools.message import MessageTool
from horbot.bus.events import OutboundMessage
from horbot.bus.queue import MessageBus
from horbot.config.schema import Config
from horbot.gateway.http_api import build_gateway_http_app
from horbot.web.api import _configure_web_agent_loop_message_routing


def _make_config(admin_token: str = "") -> Config:
    config = Config()
    config.gateway.admin_token = admin_token
    config.gateway.host = "127.0.0.1"
    config.gateway.port = 18790
    return config


class GatewayHttpApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_gateway_outbound_dispatch_sends_to_resolved_channel(self):
        send = AsyncMock()
        fake_channel = SimpleNamespace(
            name="feishu",
            endpoint_id="sales-feishu",
            send=send,
        )

        class FakeManager:
            enabled_channels = ["sales-feishu"]

            def _resolve_outbound_channel(self, msg: OutboundMessage):
                if msg.channel_instance_id == "sales-feishu":
                    return fake_channel
                return None

        app = build_gateway_http_app(FakeManager())
        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))

        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/gateway/outbound",
                json={
                    "channel": "feishu",
                    "chat_id": "group-001",
                    "content": "hello",
                    "channel_instance_id": "sales-feishu",
                    "target_agent_id": "agent-01",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["endpoint_id"], "sales-feishu")
        send.assert_awaited_once()
        sent_msg = send.await_args.args[0]
        self.assertEqual(sent_msg.channel_instance_id, "sales-feishu")
        self.assertEqual(sent_msg.target_agent_id, "agent-01")

    async def test_web_message_routing_uses_gateway_for_external_channels(self):
        local_bus = MessageBus()
        publish_local = AsyncMock()
        local_bus.publish_outbound = publish_local

        message_tool = MessageTool()
        fake_loop = SimpleNamespace(
            tools=SimpleNamespace(get=lambda name: message_tool if name == "message" else None),
        )

        with patch("horbot.web.api._dispatch_outbound_via_gateway", new=AsyncMock()) as dispatch_external:
            _configure_web_agent_loop_message_routing(fake_loop, local_bus)

            message_tool.set_context("web", "dm_agent")
            await message_tool.execute("本地回复")
            await message_tool.execute(
                "外发消息",
                channel="feishu",
                chat_id="group-001",
                channel_instance_id="sales-feishu",
                target_agent_id="agent-01",
            )

        publish_local.assert_awaited_once()
        local_msg = publish_local.await_args.args[0]
        self.assertEqual(local_msg.channel, "web")
        self.assertEqual(local_msg.chat_id, "dm_agent")

        dispatch_external.assert_awaited_once()
        external_msg = dispatch_external.await_args.args[0]
        self.assertEqual(external_msg.channel, "feishu")
        self.assertEqual(external_msg.channel_instance_id, "sales-feishu")
        self.assertEqual(external_msg.target_agent_id, "agent-01")


if __name__ == "__main__":
    unittest.main()
