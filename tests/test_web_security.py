import unittest
from unittest.mock import patch

import httpx

from horbot.config.schema import Config
from horbot.web.main import app
from horbot.web.security import sanitize_execution_step_details


def _make_config(admin_token: str = "", allow_remote_without_token: bool = False) -> Config:
    config = Config()
    config.gateway.admin_token = admin_token
    config.gateway.allow_remote_without_token = allow_remote_without_token
    config.providers.openrouter.api_key = "sk-test-secret"
    config.providers.openrouter.api_base = "https://openrouter.example/v1"
    return config


class WebSecurityTests(unittest.IsolatedAsyncioTestCase):
    async def test_remote_api_access_is_blocked_without_token(self):
        transport = httpx.ASGITransport(app=app, client=("203.0.113.10", 43123))
        config = _make_config()

        with (
            patch("horbot.web.security.get_cached_config", return_value=config),
            patch("horbot.web.api.get_cached_config", return_value=config),
        ):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.get("/api/status")

        self.assertEqual(response.status_code, 403)
        self.assertIn("Remote API access is disabled", response.text)

    async def test_remote_api_access_requires_matching_token(self):
        transport = httpx.ASGITransport(app=app, client=("203.0.113.10", 43123))
        config = _make_config(admin_token="secret-token")

        with (
            patch("horbot.web.security.get_cached_config", return_value=config),
            patch("horbot.web.api.get_cached_config", return_value=config),
        ):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                denied = await client.get("/api/status")
                allowed = await client.get(
                    "/api/status",
                    headers={"X-Horbot-Admin-Token": "secret-token"},
                )

        self.assertEqual(denied.status_code, 401)
        self.assertEqual(allowed.status_code, 200)

    async def test_loopback_requests_still_work_without_token(self):
        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
        config = _make_config()

        with (
            patch("horbot.web.security.get_cached_config", return_value=config),
            patch("horbot.web.api.get_cached_config", return_value=config),
        ):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.get("/api/status")

        self.assertEqual(response.status_code, 200)

    async def test_config_response_redacts_provider_secrets(self):
        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
        config = _make_config()

        with (
            patch("horbot.web.security.get_cached_config", return_value=config),
            patch("horbot.web.api.get_cached_config", return_value=config),
        ):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.get("/api/config")

        self.assertEqual(response.status_code, 200)
        provider = response.json()["providers"]["openrouter"]
        self.assertEqual(provider["apiKey"], "")
        self.assertTrue(provider["hasApiKey"])
        self.assertEqual(provider["apiKeyMasked"], "sk-t...cret")


    async def test_chat_stop_returns_success_for_inactive_request(self):
        class FakeStreamManager:
            def exists(self, request_id: str) -> bool:
                return False

        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
        config = _make_config()

        with (
            patch("horbot.web.security.get_cached_config", return_value=config),
            patch("horbot.web.api.get_cached_config", return_value=config),
            patch("horbot.web.api.get_stream_manager", return_value=FakeStreamManager()),
        ):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post("/api/chat/stop", json={"request_id": "req-missing"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

    async def test_chat_stop_returns_success_when_stream_finishes_before_cancel(self):
        class FakeStreamManager:
            def exists(self, request_id: str) -> bool:
                return True

            async def cancel(self, request_id: str) -> bool:
                return False

        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
        config = _make_config()

        with (
            patch("horbot.web.security.get_cached_config", return_value=config),
            patch("horbot.web.api.get_cached_config", return_value=config),
            patch("horbot.web.api.get_stream_manager", return_value=FakeStreamManager()),
        ):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post("/api/chat/stop", json={"request_id": "req-race"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

    async def test_execution_details_keep_thinking_but_redact_secrets(self):
        details = sanitize_execution_step_details(
            "thinking",
            {
                "thinking": "先检查 provider 配置，再决定是否热加载。",
                "apiKey": "sk-test-secret",
                "nested": {"token": "abc123"},
            },
        )

        self.assertEqual(details["thinking"], "先检查 provider 配置，再决定是否热加载。")
        self.assertNotEqual(details["apiKey"], "sk-test-secret")
        self.assertNotEqual(details["nested"]["token"], "abc123")


if __name__ == "__main__":
    unittest.main()
