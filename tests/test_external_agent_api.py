import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from horbot.config.normalizer import normalize_config
from horbot.config.schema import Config, ExternalAgentConfig, TeamConfig
from horbot.external_agents.manager import get_external_agent_manager
from horbot.session.manager import SessionManager
from horbot.web.main import app


class ExternalAgentApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_external_agent_rejects_duplicate_id_after_normalization(self):
        response, save_config_mock = await self._post_create_request(
            existing_agent_id="Partner-Agent",
            request_id=" partner-agent ",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "External agent ID 'partner-agent' already exists")
        save_config_mock.assert_not_called()

    async def test_get_external_agent_masks_auth_secret(self):
        with tempfile.TemporaryDirectory() as tempdir:
            config = self._build_config(
                workspace_root=Path(tempdir) / "workspace",
                external_agents={
                    "partner-agent": ExternalAgentConfig(
                        id="partner-agent",
                        name="Partner Agent",
                        endpoint="https://example.com/agent",
                        transport="http_sse",
                        auth_type="bearer",
                        auth_secret="super-secret",
                    ),
                },
            )

            manager = get_external_agent_manager()
            with (
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
                patch("horbot.external_agents.manager.get_cached_config", return_value=config),
            ):
                manager.reload(config)
                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.get("/api/external-agents/partner-agent")

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload["auth_secret_configured"])
            self.assertNotIn("auth_secret", payload)

    async def test_create_external_agent_accepts_future_adapter_slug(self):
        with tempfile.TemporaryDirectory() as tempdir:
            config = self._build_config(
                workspace_root=Path(tempdir) / "workspace",
                external_agents={},
            )

            with (
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
                patch("horbot.config.loader.load_config", return_value=config),
                patch("horbot.external_agents.manager.get_cached_config", return_value=config),
                patch("horbot.config.loader.save_config") as save_config_mock,
            ):
                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.post(
                        "/api/external-agents",
                        json={
                            "id": "dify-agent",
                            "name": "Dify Agent",
                            "description": "future adapter test",
                            "avatar": "",
                            "adapter": "dify",
                            "transport": "http",
                            "endpoint": "https://example.com/agent",
                            "auth_type": "none",
                            "auth_secret": "",
                            "auth_header": "Authorization",
                            "capabilities": [],
                            "dm_enabled": True,
                            "team_enabled": False,
                            "mention_required": True,
                            "timeout_s": 90,
                            "max_turn_chars": 12000,
                            "context_scope": "recent_turns",
                            "memory_access": "none",
                            "file_access": "none",
                            "adapter_config": {"app_id": "demo"},
                            "metadata": {},
                        },
                    )

            self.assertEqual(response.status_code, 200)
            saved_config = save_config_mock.call_args.args[0]
            saved_agent = saved_config.external_agents.instances["dify-agent"]
            self.assertEqual(saved_agent.adapter, "dify")
            self.assertEqual(saved_agent.adapter_config, {"app_id": "demo"})

    async def test_create_external_agent_allows_future_adapter_without_endpoint(self):
        with tempfile.TemporaryDirectory() as tempdir:
            config = self._build_config(
                workspace_root=Path(tempdir) / "workspace",
                external_agents={},
            )

            with (
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
                patch("horbot.config.loader.load_config", return_value=config),
                patch("horbot.external_agents.manager.get_cached_config", return_value=config),
                patch("horbot.config.loader.save_config") as save_config_mock,
            ):
                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.post(
                        "/api/external-agents",
                        json={
                            "id": "channel-agent",
                            "name": "Channel Agent",
                            "description": "future channel-backed adapter test",
                            "avatar": "",
                            "adapter": "inbound-bot",
                            "transport": "http",
                            "endpoint": "",
                            "auth_type": "none",
                            "auth_secret": "",
                            "auth_header": "Authorization",
                            "capabilities": [],
                            "dm_enabled": True,
                            "team_enabled": True,
                            "mention_required": True,
                            "timeout_s": 90,
                            "max_turn_chars": 12000,
                            "context_scope": "recent_turns",
                            "memory_access": "none",
                            "file_access": "none",
                            "adapter_config": {"channel_endpoint_id": "legacy:feishu"},
                            "metadata": {},
                        },
                    )

            self.assertEqual(response.status_code, 200)
            saved_config = save_config_mock.call_args.args[0]
            saved_agent = saved_config.external_agents.instances["channel-agent"]
            self.assertEqual(saved_agent.adapter, "inbound-bot")
            self.assertEqual(saved_agent.endpoint, "")
            self.assertIn("bot_app_id", saved_agent.adapter_config)
            self.assertIn("bot_token", saved_agent.adapter_config)

    async def test_inbound_external_agent_bot_message_is_saved_to_session(self):
        with tempfile.TemporaryDirectory() as tempdir:
            config = self._build_config(
                workspace_root=Path(tempdir) / "workspace",
                external_agents={
                    "workbuddy-agent": ExternalAgentConfig(
                        id="workbuddy-agent",
                        name="WorkBuddy Agent",
                        adapter="inbound-bot",
                        endpoint="",
                        adapter_config={
                            "bot_app_id": "hbot_workbuddy",
                            "bot_token": "secret-token",
                        },
                    ),
                },
            )
            session_manager = SessionManager(workspace=Path(tempdir) / "sessions")

            with (
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
                patch("horbot.external_agents.manager.get_cached_config", return_value=config),
                patch("horbot.web.api.get_session_manager", return_value=session_manager),
            ):
                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.post(
                        "/api/external-agents/inbound/hbot_workbuddy/messages",
                        headers={"Authorization": "Bearer secret-token"},
                        json={
                            "content": "WorkBuddy pushed a result",
                            "chat_id": "dm_workbuddy-agent",
                            "sender_id": "workbuddy",
                            "message_id": "msg-001",
                        },
                    )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["external_agent_id"], "workbuddy-agent")
            self.assertEqual(payload["session_key"], "web:dm_workbuddy-agent")
            session = session_manager.get_or_create("web:dm_workbuddy-agent")
            self.assertEqual(session.messages[-1]["role"], "assistant")
            self.assertEqual(session.messages[-1]["content"], "WorkBuddy pushed a result")
            self.assertEqual(session.messages[-1]["metadata"]["source"], "external_agent_inbound")

    async def test_inbound_external_agent_bot_rejects_bad_token(self):
        with tempfile.TemporaryDirectory() as tempdir:
            config = self._build_config(
                workspace_root=Path(tempdir) / "workspace",
                external_agents={
                    "workbuddy-agent": ExternalAgentConfig(
                        id="workbuddy-agent",
                        name="WorkBuddy Agent",
                        adapter="inbound-bot",
                        endpoint="",
                        adapter_config={
                            "bot_app_id": "hbot_workbuddy",
                            "bot_token": "secret-token",
                        },
                    ),
                },
            )

            with (
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
            ):
                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.post(
                        "/api/external-agents/inbound/hbot_workbuddy/messages",
                        json={"content": "bad token", "token": "wrong"},
                    )

            self.assertEqual(response.status_code, 401)

    async def test_create_external_agent_rejects_invalid_adapter_slug(self):
        response, save_config_mock = await self._post_create_request(
            existing_agent_id="existing-agent",
            request_id="future-agent",
            adapter="bad adapter!",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid external agent adapter", response.json()["detail"])
        save_config_mock.assert_not_called()

    async def test_update_external_agent_preserves_existing_secret_when_blank(self):
        with tempfile.TemporaryDirectory() as tempdir:
            config = self._build_config(
                workspace_root=Path(tempdir) / "workspace",
                external_agents={
                    "partner-agent": ExternalAgentConfig(
                        id="partner-agent",
                        name="Partner Agent",
                        endpoint="https://example.com/agent",
                        transport="http_sse",
                        auth_type="bearer",
                        auth_secret="stored-secret",
                    ),
                },
            )

            save_config_mock = AsyncMock()

            def _save_side_effect(updated_config):
                manager = get_external_agent_manager()
                manager.reload(updated_config)
                return Path(tempdir) / "config.json"

            with (
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
                patch("horbot.config.loader.load_config", return_value=config),
                patch("horbot.external_agents.manager.get_cached_config", return_value=config),
                patch("horbot.config.loader.save_config", side_effect=_save_side_effect) as save_config_mock,
            ):
                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.put(
                        "/api/external-agents/partner-agent",
                        json={
                            "id": "partner-agent",
                            "name": "Partner Agent Updated",
                            "description": "updated",
                            "avatar": "",
                            "transport": "http_sse",
                            "endpoint": "https://example.com/agent/v2",
                            "auth_type": "bearer",
                            "auth_secret": "",
                            "auth_header": "Authorization",
                            "capabilities": ["planning", "planning"],
                            "dm_enabled": True,
                            "team_enabled": False,
                            "mention_required": True,
                            "timeout_s": 120,
                            "max_turn_chars": 16000,
                            "context_scope": "recent_turns",
                            "memory_access": "summary_only",
                            "file_access": "referenced_only",
                            "metadata": {"region": "cn"},
                        },
                    )

            self.assertEqual(response.status_code, 200)
            save_config_mock.assert_called_once()
            saved_config = save_config_mock.call_args.args[0]
            saved_agent = saved_config.external_agents.instances["partner-agent"]
            self.assertEqual(saved_agent.auth_secret, "stored-secret")
            self.assertEqual(saved_agent.capabilities, ["planning"])
            self.assertEqual(saved_agent.memory_access, "summary_only")

    async def test_test_external_agent_returns_probe_result(self):
        with tempfile.TemporaryDirectory() as tempdir:
            config = self._build_config(
                workspace_root=Path(tempdir) / "workspace",
                external_agents={
                    "partner-agent": ExternalAgentConfig(
                        id="partner-agent",
                        name="Partner Agent",
                        endpoint="https://example.com/agent",
                    ),
                },
            )

            manager = get_external_agent_manager()
            probe_mock = AsyncMock(return_value={
                "ok": True,
                "detail": "Endpoint responded successfully",
                "mode": "http_probe",
                "transport": "http_sse",
                "endpoint": "https://example.com/agent",
                "status_code": 200,
            })

            with (
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
                patch("horbot.external_agents.manager.get_cached_config", return_value=config),
                patch("horbot.external_agents.runtime.get_external_agent_runtime") as runtime_factory,
            ):
                manager.reload(config)
                runtime_factory.return_value.probe = probe_mock
                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.post("/api/external-agents/partner-agent/test")

            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["ok"])
            probe_mock.assert_awaited_once()

    async def test_update_external_agent_disabling_team_access_removes_team_memberships(self):
        with tempfile.TemporaryDirectory() as tempdir:
            config = self._build_config(
                workspace_root=Path(tempdir) / "workspace",
                external_agents={
                    "partner-agent": ExternalAgentConfig(
                        id="partner-agent",
                        name="Partner Agent",
                        endpoint="https://example.com/agent",
                        transport="http_sse",
                        team_enabled=True,
                    ),
                },
            )
            config.teams.instances["team-a"] = TeamConfig(
                id="team-a",
                name="Team A",
                members=["partner-agent"],
                member_profiles={"partner-agent": {"role": "researcher"}},
            )
            config = normalize_config(config)

            def _save_side_effect(updated_config):
                manager = get_external_agent_manager()
                manager.reload(updated_config)
                return Path(tempdir) / "config.json"

            with (
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
                patch("horbot.config.loader.load_config", return_value=config),
                patch("horbot.external_agents.manager.get_cached_config", return_value=config),
                patch("horbot.config.loader.save_config", side_effect=_save_side_effect) as save_config_mock,
            ):
                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.put(
                        "/api/external-agents/partner-agent",
                        json={
                            "id": "partner-agent",
                            "name": "Partner Agent",
                            "description": "updated",
                            "avatar": "",
                            "transport": "http_sse",
                            "endpoint": "https://example.com/agent",
                            "auth_type": "none",
                            "auth_secret": "",
                            "auth_header": "Authorization",
                            "capabilities": [],
                            "dm_enabled": True,
                            "team_enabled": False,
                            "mention_required": True,
                            "timeout_s": 90,
                            "max_turn_chars": 12000,
                            "context_scope": "recent_turns",
                            "memory_access": "none",
                            "file_access": "none",
                            "metadata": {},
                        },
                    )

            self.assertEqual(response.status_code, 200)
            saved_config = save_config_mock.call_args.args[0]
            saved_team = saved_config.teams.instances["team-a"]
            self.assertEqual(saved_team.members, [])
            self.assertEqual(saved_team.member_profiles, {})

    async def test_delete_external_agent_removes_team_memberships(self):
        with tempfile.TemporaryDirectory() as tempdir:
            config = self._build_config(
                workspace_root=Path(tempdir) / "workspace",
                external_agents={
                    "partner-agent": ExternalAgentConfig(
                        id="partner-agent",
                        name="Partner Agent",
                        endpoint="https://example.com/agent",
                        team_enabled=True,
                    ),
                },
            )
            config.teams.instances["team-a"] = TeamConfig(
                id="team-a",
                name="Team A",
                members=["partner-agent"],
                member_profiles={"partner-agent": {"role": "researcher"}},
            )
            config = normalize_config(config)

            with (
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
                patch("horbot.config.loader.load_config", return_value=config),
                patch("horbot.external_agents.manager.get_cached_config", return_value=config),
                patch("horbot.config.loader.save_config") as save_config_mock,
            ):
                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.delete("/api/external-agents/partner-agent")

            self.assertEqual(response.status_code, 200)
            saved_config = save_config_mock.call_args.args[0]
            self.assertNotIn("partner-agent", saved_config.external_agents.instances)
            self.assertEqual(saved_config.teams.instances["team-a"].members, [])

    async def _post_create_request(
        self,
        existing_agent_id: str,
        request_id: str,
        adapter: str = "generic-agent-api",
    ):
        with tempfile.TemporaryDirectory() as tempdir:
            config = self._build_config(
                workspace_root=Path(tempdir) / "workspace",
                external_agents={
                    existing_agent_id: ExternalAgentConfig(
                        id=existing_agent_id,
                        name="Existing External Agent",
                        endpoint="https://example.com/existing",
                    ),
                },
            )

            with (
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
                patch("horbot.config.loader.load_config", return_value=config),
                patch("horbot.external_agents.manager.get_cached_config", return_value=config),
                patch("horbot.config.loader.save_config") as save_config_mock,
            ):
                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.post(
                        "/api/external-agents",
                        json={
                            "id": request_id,
                            "name": "Partner Agent",
                            "description": "duplicate id test",
                            "avatar": "",
                            "adapter": adapter,
                            "transport": "http_sse",
                            "endpoint": "https://example.com/agent",
                            "auth_type": "none",
                            "auth_secret": "",
                            "auth_header": "Authorization",
                            "capabilities": [],
                            "dm_enabled": True,
                            "team_enabled": False,
                            "mention_required": True,
                            "timeout_s": 90,
                            "max_turn_chars": 12000,
                            "context_scope": "recent_turns",
                            "memory_access": "none",
                            "file_access": "none",
                            "metadata": {},
                        },
                    )

        return response, save_config_mock

    def _build_config(self, *, workspace_root: Path, external_agents: dict[str, ExternalAgentConfig]) -> Config:
        config = Config()
        config.agents.defaults.workspace = str(workspace_root)
        config.external_agents.instances = external_agents
        return normalize_config(config)


if __name__ == "__main__":
    unittest.main()
