import unittest

import httpx
from fastapi import FastAPI
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
