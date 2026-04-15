import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from horbot.config.normalizer import normalize_config
from horbot.config.schema import AgentConfig, Config, ExternalAgentConfig, TeamConfig
from horbot.agent.manager import get_agent_manager
from horbot.external_agents.manager import get_external_agent_manager
from horbot.team.manager import get_team_manager
from horbot.web.main import app


class TeamCreateApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_team_rejects_exact_duplicate_id(self):
        response, save_config_mock, reset_mock = await self._post_create_request(
            existing_team_id="delivery",
            request_id="delivery",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Team ID 'delivery' already exists")
        save_config_mock.assert_not_called()
        reset_mock.assert_not_awaited()

    async def test_create_team_rejects_duplicate_id_after_normalization(self):
        response, save_config_mock, reset_mock = await self._post_create_request(
            existing_team_id="Delivery",
            request_id=" delivery ",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Team ID 'delivery' already exists")
        save_config_mock.assert_not_called()
        reset_mock.assert_not_awaited()

    async def test_create_team_accepts_team_enabled_external_agent_members(self):
        with tempfile.TemporaryDirectory() as tempdir:
            workspace_root = Path(tempdir) / "workspace"
            config = Config()
            config.external_agents.instances = {
                "partner-agent": ExternalAgentConfig(
                    id="partner-agent",
                    name="Partner Agent",
                    endpoint="https://example.com/agent",
                    team_enabled=True,
                ),
            }
            config = normalize_config(config)
            reset_mock = AsyncMock()

            with (
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.team.manager.get_cached_config", return_value=config),
                patch("horbot.external_agents.manager.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
                patch("horbot.config.loader.load_config", return_value=config),
                patch("horbot.config.loader.save_config") as save_config_mock,
                patch("horbot.web.api.reset_agent_loop", reset_mock),
            ):
                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.post(
                        "/api/teams",
                        json={
                            "id": "delivery",
                            "name": "Delivery",
                            "description": "team with external member",
                            "members": ["partner-agent"],
                            "member_profiles": {
                                "partner-agent": {
                                    "role": "researcher",
                                    "priority": 50,
                                },
                            },
                            "workspace": str(workspace_root / "delivery"),
                        },
                    )

            self.assertEqual(response.status_code, 200)
            save_config_mock.assert_called_once()
            saved_team = save_config_mock.call_args.args[0].teams.instances["delivery"]
            self.assertEqual(saved_team.members, ["partner-agent"])
            self.assertIn("partner-agent", saved_team.member_profiles)
            reset_mock.assert_awaited_once()

    async def test_create_team_rejects_non_team_enabled_external_agent_members(self):
        with tempfile.TemporaryDirectory() as tempdir:
            config = Config()
            config.external_agents.instances = {
                "partner-agent": ExternalAgentConfig(
                    id="partner-agent",
                    name="Partner Agent",
                    endpoint="https://example.com/agent",
                    team_enabled=False,
                ),
            }
            config = normalize_config(config)
            reset_mock = AsyncMock()

            with (
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.team.manager.get_cached_config", return_value=config),
                patch("horbot.external_agents.manager.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
                patch("horbot.config.loader.load_config", return_value=config),
                patch("horbot.config.loader.save_config") as save_config_mock,
                patch("horbot.web.api.reset_agent_loop", reset_mock),
            ):
                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.post(
                        "/api/teams",
                        json={
                            "id": "delivery",
                            "name": "Delivery",
                            "description": "team with disabled external member",
                            "members": ["partner-agent"],
                            "member_profiles": {},
                            "workspace": "",
                        },
                    )

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()["detail"], "External agents are not team-enabled: partner-agent")
            save_config_mock.assert_not_called()
            reset_mock.assert_not_awaited()

    async def test_get_team_members_returns_explicit_internal_and_external_groups(self):
        with tempfile.TemporaryDirectory() as tempdir:
            workspace_root = Path(tempdir) / "workspace"
            config = Config()
            config.agents.defaults.workspace = str(workspace_root)
            config.agents.instances = {
                "agent-a": AgentConfig(
                    id="agent-a",
                    name="Agent A",
                    provider="openai",
                    model="gpt-test",
                ),
            }
            config.external_agents.instances = {
                "partner-agent": ExternalAgentConfig(
                    id="partner-agent",
                    name="Partner Agent",
                    endpoint="https://example.com/agent",
                    team_enabled=True,
                ),
            }
            config.teams.instances = {
                "delivery": TeamConfig(
                    id="delivery",
                    name="Delivery",
                    members=["agent-a", "partner-agent"],
                    member_profiles={
                        "agent-a": {"role": "lead", "priority": 10},
                        "partner-agent": {"role": "researcher", "priority": 50},
                    },
                ),
            }
            config = normalize_config(config)

            with (
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.team.manager.get_cached_config", return_value=config),
                patch("horbot.agent.manager.get_cached_config", return_value=config),
                patch("horbot.external_agents.manager.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
            ):
                get_team_manager().reload(config)
                get_agent_manager().reload(config)
                get_external_agent_manager().reload(config)
                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.get("/api/teams/delivery/members")

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["team_id"], "delivery")
            self.assertEqual(payload["count"], 2)
            self.assertEqual(payload["counts"], {"total": 2, "internal": 1, "external": 1})
            self.assertEqual(
                payload["member_order"],
                [
                    {"id": "agent-a", "kind": "internal"},
                    {"id": "partner-agent", "kind": "external"},
                ],
            )
            self.assertEqual([member["id"] for member in payload["internal_members"]], ["agent-a"])
            self.assertEqual([member["id"] for member in payload["external_members"]], ["partner-agent"])
            self.assertEqual([member["kind"] for member in payload["members"]], ["internal", "external"])
            self.assertEqual(
                payload["internal_members"][0]["profile"],
                {"role": "lead", "responsibility": "", "priority": 10, "isLead": False},
            )
            self.assertEqual(payload["internal_members"][0]["agent"]["id"], "agent-a")
            self.assertNotIn("external_agent", payload["internal_members"][0])
            self.assertEqual(
                payload["external_members"][0]["profile"],
                {"role": "researcher", "responsibility": "", "priority": 50, "isLead": False},
            )
            self.assertEqual(payload["external_members"][0]["external_agent"]["id"], "partner-agent")
            self.assertNotIn("agent", payload["external_members"][0])

    async def _post_create_request(self, existing_team_id: str, request_id: str):
        with tempfile.TemporaryDirectory() as tempdir:
            workspace_root = Path(tempdir) / "workspace"
            config = Config()
            config.teams.instances = {
                existing_team_id: TeamConfig(
                    id=existing_team_id,
                    name="Existing Team",
                    workspace=str(workspace_root / existing_team_id),
                ),
            }
            config = normalize_config(config)
            reset_mock = AsyncMock()

            with (
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.team.manager.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
                patch("horbot.config.loader.load_config", return_value=config),
                patch("horbot.config.loader.save_config") as save_config_mock,
                patch("horbot.web.api.reset_agent_loop", reset_mock),
            ):
                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.post(
                        "/api/teams",
                        json={
                            "id": request_id,
                            "name": "Delivery Clone",
                            "description": "duplicate id test",
                            "members": [],
                            "member_profiles": {},
                            "workspace": "",
                        },
                    )

        return response, save_config_mock, reset_mock


if __name__ == "__main__":
    unittest.main()
