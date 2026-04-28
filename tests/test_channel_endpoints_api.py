import unittest

import httpx
from fastapi import FastAPI
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from horbot.channels.telemetry import clear_channel_telemetry, record_channel_event
from horbot.config.normalizer import normalize_config
from horbot.config.schema import AgentConfig, ChannelEndpointConfig, Config
from horbot.web.api import router as api_router


class ChannelEndpointsApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        clear_channel_telemetry()

    async def asyncTearDown(self) -> None:
        clear_channel_telemetry()

    async def test_endpoints_list_includes_runtime_summary_and_events_endpoint(self):
        config = Config()
        config.agents.instances = {
            "alpha": AgentConfig(id="alpha", name="Alpha", channel_bindings=["sales-feishu"]),
        }
        config.channels.endpoints = [
            ChannelEndpointConfig(
                id="sales-feishu",
                type="feishu",
                name="Sales Feishu",
                agent_id="alpha",
                enabled=True,
                config={"app_id": "cli_xxx", "app_secret": "secret"},
            ),
        ]
        config = normalize_config(config)

        record_channel_event(
            "sales-feishu",
            channel_type="feishu",
            event_type="inbound",
            status="ok",
            message="Received message from u_1",
        )

        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        with patch("horbot.web.api.get_cached_config", return_value=config):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                list_response = await client.get("/api/channels/endpoints")
                events_response = await client.get("/api/channels/endpoints/sales-feishu/events")

        self.assertEqual(list_response.status_code, 200)
        payload = list_response.json()
        self.assertEqual(payload["counts"]["total"], 1)
        self.assertEqual(payload["endpoints"][0]["runtime"]["messages_received"], 1)

        self.assertEqual(events_response.status_code, 200)
        events_payload = events_response.json()
        self.assertEqual(events_payload["summary"]["messages_received"], 1)
        self.assertEqual(events_payload["events"][0]["event_type"], "inbound")

    async def test_catalog_includes_wecom_channel_type(self):
        config = normalize_config(Config())

        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        with patch("horbot.web.api.get_cached_config", return_value=config):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.get("/api/channels/catalog")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        wecom_entry = next(item for item in payload["catalog"] if item["type"] == "wecom")
        self.assertEqual(wecom_entry["label"], "WeCom")
        self.assertIn("bot_id", wecom_entry["required_fields"])
        inbound_entry = next(item for item in payload["catalog"] if item["type"] == "horbot-inbound-bot")
        self.assertEqual(inbound_entry["label"], "Horbot 入站机器人")
        self.assertEqual(inbound_entry["required_fields"], [])

    async def test_create_horbot_inbound_bot_channel_generates_credentials(self):
        config = Config()
        config.agents.instances = {
            "alpha": AgentConfig(id="alpha", name="Alpha"),
        }
        config = normalize_config(config)

        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        with (
            patch("horbot.web.api.get_cached_config", return_value=config),
            patch("horbot.web.api.save_config"),
            patch("horbot.web.api.reset_agent_loop", new=AsyncMock()),
        ):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post("/api/channels/endpoints", json={
                    "id": "workbuddy-inbound",
                    "type": "horbot-inbound-bot",
                    "name": "WorkBuddy Inbound",
                    "agent_id": "alpha",
                    "enabled": True,
                    "allow_from": [],
                    "config": {},
                })

        self.assertEqual(response.status_code, 200)
        endpoint = response.json()["endpoint"]
        self.assertEqual(endpoint["type"], "horbot-inbound-bot")
        self.assertIn("bot_app_id", endpoint["config"])
        self.assertIn("bot_token", endpoint["config"])
        self.assertEqual(
            endpoint["config"]["inbound_url_path"],
            f"/api/channels/inbound/{endpoint['config']['bot_app_id']}/messages",
        )

    async def test_horbot_inbound_bot_message_routes_to_bound_agent(self):
        config = Config()
        config.agents.instances = {
            "alpha": AgentConfig(id="alpha", name="Alpha"),
        }
        config.channels.endpoints = [
            ChannelEndpointConfig(
                id="workbuddy-inbound",
                type="horbot-inbound-bot",
                name="WorkBuddy Inbound",
                agent_id="alpha",
                enabled=True,
                config={
                    "bot_app_id": "hbot_ch_workbuddy",
                    "bot_token": "secret-token",
                    "inbound_url_path": "/api/channels/inbound/hbot_ch_workbuddy/messages",
                },
            ),
        ]
        config = normalize_config(config)
        agent_loop = SimpleNamespace(process_message=AsyncMock(return_value=SimpleNamespace(content="agent reply")))

        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        with (
            patch("horbot.web.api.get_cached_config", return_value=config),
            patch("horbot.web.api.get_agent_loop", new=AsyncMock(return_value=agent_loop)),
        ):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post(
                    "/api/channels/inbound/hbot_ch_workbuddy/messages",
                    headers={"Authorization": "Bearer secret-token"},
                    json={
                        "content": "hello from WorkBuddy",
                        "chat_id": "room-1",
                        "sender_id": "workbuddy",
                        "message_id": "msg-1",
                    },
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["endpoint_id"], "workbuddy-inbound")
        self.assertEqual(payload["agent_id"], "alpha")
        self.assertEqual(payload["session_key"], "workbuddy-inbound:room-1")
        self.assertEqual(payload["content"], "agent reply")
        agent_loop.process_message.assert_awaited_once()

    async def test_horbot_inbound_bot_message_can_route_to_request_agent_when_unbound(self):
        config = Config()
        config.agents.instances = {
            "alpha": AgentConfig(id="alpha", name="Alpha"),
            "beta": AgentConfig(id="beta", name="Beta"),
        }
        config.channels.endpoints = [
            ChannelEndpointConfig(
                id="workbuddy-inbound",
                type="horbot-inbound-bot",
                name="WorkBuddy Inbound",
                agent_id="",
                enabled=True,
                config={
                    "bot_app_id": "hbot_ch_workbuddy",
                    "bot_token": "secret-token",
                    "inbound_url_path": "/api/channels/inbound/hbot_ch_workbuddy/messages",
                },
            ),
        ]
        config = normalize_config(config)
        agent_loop = SimpleNamespace(process_message=AsyncMock(return_value=SimpleNamespace(content="beta reply")))

        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        with (
            patch("horbot.web.api.get_cached_config", return_value=config),
            patch("horbot.web.api.get_agent_loop", new=AsyncMock(return_value=agent_loop)) as get_agent_loop_mock,
        ):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post(
                    "/api/channels/inbound/hbot_ch_workbuddy/messages",
                    headers={"Authorization": "Bearer secret-token"},
                    json={
                        "content": "hello beta",
                        "chat_id": "room-1",
                        "sender_id": "workbuddy",
                        "target_agent_id": "beta",
                    },
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["agent_id"], "beta")
        self.assertEqual(payload["content"], "beta reply")
        get_agent_loop_mock.assert_awaited_once_with("beta")
        agent_loop.process_message.assert_awaited_once()

    async def test_horbot_inbound_bot_rejects_unknown_request_agent_when_unbound(self):
        config = Config()
        config.agents.instances = {
            "alpha": AgentConfig(id="alpha", name="Alpha"),
        }
        config.channels.endpoints = [
            ChannelEndpointConfig(
                id="workbuddy-inbound",
                type="horbot-inbound-bot",
                name="WorkBuddy Inbound",
                agent_id="",
                enabled=True,
                config={
                    "bot_app_id": "hbot_ch_workbuddy",
                    "bot_token": "secret-token",
                    "inbound_url_path": "/api/channels/inbound/hbot_ch_workbuddy/messages",
                },
            ),
        ]
        config = normalize_config(config)

        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        with patch("horbot.web.api.get_cached_config", return_value=config):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post(
                    "/api/channels/inbound/hbot_ch_workbuddy/messages",
                    headers={"Authorization": "Bearer secret-token"},
                    json={
                        "content": "hello nobody",
                        "target_agent_id": "missing-agent",
                    },
                )

        self.assertEqual(response.status_code, 400)
        self.assertIn("not bound to a valid agent", response.json()["detail"])

    async def test_endpoint_test_api_returns_result_and_records_healthcheck_event(self):
        config = Config()
        config.agents.instances = {
            "alpha": AgentConfig(id="alpha", name="Alpha", channel_bindings=["sales-feishu"]),
        }
        config.channels.endpoints = [
            ChannelEndpointConfig(
                id="sales-feishu",
                type="feishu",
                name="Sales Feishu",
                agent_id="alpha",
                enabled=True,
                config={"app_id": "cli_xxx", "app_secret": "secret"},
            ),
        ]
        config = normalize_config(config)

        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        with (
            patch("horbot.web.api.get_cached_config", return_value=config),
            patch(
                "horbot.web.api.test_channel_connection",
                new=AsyncMock(return_value={
                    "name": "feishu",
                    "enabled": True,
                    "status": "ok",
                    "latency_ms": 123,
                    "error": None,
                    "error_code": None,
                    "error_kind": None,
                    "remediation": [],
                }),
            ),
        ):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post("/api/channels/endpoints/sales-feishu/test")
                events_response = await client.get("/api/channels/endpoints/sales-feishu/events")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["result"]["status"], "ok")
        self.assertEqual(payload["result"]["latency_ms"], 123)

        self.assertEqual(events_response.status_code, 200)
        events_payload = events_response.json()
        self.assertEqual(events_payload["events"][0]["event_type"], "healthcheck")
        self.assertEqual(events_payload["events"][0]["status"], "ok")

    async def test_draft_endpoint_test_api_supports_unsaved_payload(self):
        config = Config()
        config.agents.instances = {
            "alpha": AgentConfig(id="alpha", name="Alpha"),
        }
        config = normalize_config(config)

        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        with (
            patch("horbot.web.api.get_cached_config", return_value=config),
            patch(
                "horbot.web.api.test_channel_connection",
                new=AsyncMock(return_value={
                    "name": "feishu",
                    "enabled": True,
                    "status": "ok",
                    "latency_ms": 88,
                    "error": None,
                    "error_code": None,
                    "error_kind": None,
                    "remediation": [],
                }),
            ),
        ):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post("/api/channels/draft-test", json={
                    "type": "feishu",
                    "name": "Draft Feishu",
                    "agent_id": "alpha",
                    "enabled": True,
                    "allow_from": [],
                    "config": {
                        "app_id": "cli_xxx",
                        "app_secret": "secret",
                    },
                })

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["result"]["status"], "ok")
        self.assertEqual(payload["result"]["latency_ms"], 88)
        self.assertEqual(payload["endpoint"]["agent_id"], "alpha")
        self.assertEqual(payload["endpoint"]["source"], "custom")

    async def test_endpoint_test_api_returns_structured_diagnostics_fields(self):
        config = Config()
        config.agents.instances = {
            "alpha": AgentConfig(id="alpha", name="Alpha", channel_bindings=["sales-feishu"]),
        }
        config.channels.endpoints = [
            ChannelEndpointConfig(
                id="sales-feishu",
                type="feishu",
                name="Sales Feishu",
                agent_id="alpha",
                enabled=True,
                config={"app_id": "cli_xxx", "app_secret": "secret"},
            ),
        ]
        config = normalize_config(config)

        app = FastAPI()
        app.include_router(api_router, prefix="/api")
        transport = httpx.ASGITransport(app=app)

        with (
            patch("horbot.web.api.get_cached_config", return_value=config),
            patch(
                "horbot.web.api.test_channel_connection",
                new=AsyncMock(return_value={
                    "name": "feishu",
                    "enabled": True,
                    "status": "error",
                    "latency_ms": 45,
                    "error": "missing_scope",
                    "error_code": "INSUFFICIENT_PERMISSIONS",
                    "error_kind": "permission",
                    "remediation": [
                        "去飞书开放平台检查应用权限、机器人能力和事件订阅是否已开启。",
                    ],
                }),
            ),
        ):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post("/api/channels/endpoints/sales-feishu/test")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["result"]["error_code"], "INSUFFICIENT_PERMISSIONS")
        self.assertEqual(payload["result"]["error_kind"], "permission")
        self.assertIn("飞书开放平台", payload["result"]["remediation"][0])


if __name__ == "__main__":
    unittest.main()
