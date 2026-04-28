import json
import unittest

from websockets.asyncio.server import serve

from horbot.config.schema import ExternalAgentConfig
from horbot.external_agents.models import ExternalAgentInstance
from horbot.external_agents.registry import get_external_agent_adapter_registry
from horbot.external_agents.runtime import ExternalAgentRuntime


class ExternalAgentRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def test_registry_resolves_adapter_and_legacy_transport_aliases(self):
        registry = get_external_agent_adapter_registry()

        self.assertEqual(registry.get("generic-agent-api").adapter_id, "generic-agent-api")
        self.assertEqual(registry.get("http_sse").adapter_id, "generic-agent-api")
        self.assertEqual(registry.get("websocket-chat").adapter_id, "generic-agent-api")
        self.assertEqual(registry.get("openai-compatible").adapter_id, "openai-compatible")
        self.assertEqual(registry.get("inbound-bot").adapter_id, "inbound-bot")
        self.assertEqual(registry.get("channel-backed-agent").adapter_id, "inbound-bot")

    async def test_runtime_reports_unsupported_adapter(self):
        runtime = ExternalAgentRuntime()
        agent = ExternalAgentInstance(
            ExternalAgentConfig(
                id="future-agent",
                name="Future Agent",
                adapter="dify",
                endpoint="https://example.com/agent",
            )
        )

        result = await runtime.complete(
            agent,
            message="hello",
            session_key="web:future-agent",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["adapter"], "dify")
        self.assertIn("Unsupported external agent adapter", result["detail"])

    async def test_inbound_bot_probe_reports_credentials_ready(self):
        runtime = ExternalAgentRuntime()
        agent = ExternalAgentInstance(
            ExternalAgentConfig(
                id="workbuddy-agent",
                name="WorkBuddy Agent",
                adapter="inbound-bot",
                adapter_config={
                    "bot_app_id": "hbot_workbuddy",
                    "bot_token": "secret-token",
                },
            )
        )

        result = await runtime.probe(agent)

        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "inbound_bot_probe")
        self.assertEqual(result["inbound"]["app_id"], "hbot_workbuddy")

    async def test_complete_websocket_supports_single_json_reply(self):
        runtime = ExternalAgentRuntime()
        received_payloads: list[dict[str, object]] = []

        async def handler(connection):
            payload = json.loads(await connection.recv())
            received_payloads.append(payload)
            await connection.send(json.dumps({"content": "websocket reply"}))

        async with serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            agent = self._build_agent(f"ws://127.0.0.1:{port}/agent")
            result = await runtime.complete(
                agent,
                message="hello websocket",
                session_key="web:test_websocket_dm",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "websocket_chat")
        self.assertEqual(result["content"], "websocket reply")
        self.assertEqual(received_payloads[0]["message"], "hello websocket")
        self.assertEqual(received_payloads[0]["session_key"], "web:test_websocket_dm")
        self.assertEqual(received_payloads[0]["agent"]["id"], "partner-agent")

    async def test_complete_websocket_supports_delta_streams(self):
        runtime = ExternalAgentRuntime()

        async def handler(connection):
            await connection.recv()
            await connection.send(json.dumps({"delta": {"content": "hello"}}))
            await connection.send(json.dumps({"delta": {"content": "world"}}))
            await connection.send(json.dumps({"event": "done"}))

        async with serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            agent = self._build_agent(f"ws://127.0.0.1:{port}/agent")
            result = await runtime.complete(
                agent,
                message="stream please",
                session_key="web:test_websocket_stream",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "websocket_chat")
        self.assertEqual(result["content"], "helloworld")

    async def test_probe_websocket_reports_success(self):
        runtime = ExternalAgentRuntime()

        async def handler(connection):
            await connection.wait_closed()

        async with serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            agent = self._build_agent(f"ws://127.0.0.1:{port}/probe")
            result = await runtime.probe(agent)

        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "websocket_probe")
        self.assertEqual(result["detail"], "Endpoint accepted websocket connection")

    def _build_agent(self, endpoint: str) -> ExternalAgentInstance:
        return ExternalAgentInstance(
            ExternalAgentConfig(
                id="partner-agent",
                name="Partner Agent",
                endpoint=endpoint,
                transport="websocket",
                timeout_s=5,
            )
        )


if __name__ == "__main__":
    unittest.main()
