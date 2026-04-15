import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from horbot.config.normalizer import normalize_config
from horbot.config.schema import Config, ExternalAgentConfig, TeamConfig
from horbot.external_agents.manager import get_external_agent_manager
from horbot.session.manager import SessionManager
from horbot.web.main import app


def _decode_sse_events(lines: list[str]) -> list[dict]:
    return [json.loads(line[6:]) for line in lines if line.startswith("data: ")]


class ExternalAgentChatStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_chat_stream_supports_external_agent_without_provider(self):
        config = self._build_config(
            external_agents={
                "partner-agent": ExternalAgentConfig(
                    id="partner-agent",
                    name="Partner Agent",
                    endpoint="https://example.com/agent",
                    transport="http",
                    dm_enabled=True,
                ),
            }
        )

        manager = get_external_agent_manager()
        runtime_complete = AsyncMock(
            return_value={
                "ok": True,
                "content": "External agent reply",
                "detail": "ok",
                "mode": "http_chat",
                "transport": "http",
            }
        )

        with (
            patch("horbot.web.security.get_cached_config", return_value=config),
            patch("horbot.web.api.get_cached_config", return_value=config),
            patch("horbot.config.loader.get_cached_config", return_value=config),
            patch("horbot.external_agents.manager.get_cached_config", return_value=config),
            patch("horbot.external_agents.runtime.get_external_agent_runtime") as runtime_factory,
        ):
            manager.reload(config)
            runtime_factory.return_value.complete = runtime_complete
            transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                async with client.stream(
                    "POST",
                    "/api/chat/stream",
                    json={
                        "content": "hello external",
                        "session_key": "web:dm_partner-agent",
                        "agent_id": "partner-agent",
                    },
                ) as response:
                    self.assertEqual(response.status_code, 200)
                    lines = [line async for line in response.aiter_lines() if line]

        events = _decode_sse_events(lines)
        self.assertEqual([event["event"] for event in events if event["event"] in {"agent_start", "agent_done", "done"}], ["agent_start", "agent_done", "done"])
        agent_done = next(event for event in events if event["event"] == "agent_done")
        self.assertEqual(agent_done["agent_id"], "partner-agent")
        self.assertEqual(agent_done["content"], "External agent reply")
        runtime_complete.assert_awaited_once()

    async def test_group_chat_stream_supports_explicit_external_mentions_without_provider(self):
        config = self._build_config(
            external_agents={
                "partner-agent": ExternalAgentConfig(
                    id="partner-agent",
                    name="Partner Agent",
                    endpoint="https://example.com/agent",
                    transport="http",
                    team_enabled=True,
                ),
            }
        )

        manager = get_external_agent_manager()
        runtime_complete = AsyncMock(
            return_value={
                "ok": True,
                "content": "External relay reply",
                "detail": "ok",
                "mode": "http_chat",
                "transport": "http",
            }
        )

        fake_agent_manager = SimpleNamespace(
            get_all_agents=lambda: [],
            get_default_agent=lambda: None,
            get_agent=lambda agent_id: None,
        )
        fake_workspace_manager = SimpleNamespace(
            get_team_workspace=lambda team_id: SimpleNamespace(workspace_path=f"/tmp/{team_id}"),
        )

        with (
            patch("horbot.web.security.get_cached_config", return_value=config),
            patch("horbot.web.api.get_cached_config", return_value=config),
            patch("horbot.config.loader.get_cached_config", return_value=config),
            patch("horbot.team.manager.get_cached_config", return_value=config),
            patch("horbot.external_agents.manager.get_cached_config", return_value=config),
            patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager),
            patch("horbot.team.manager.get_workspace_manager", return_value=fake_workspace_manager),
            patch("horbot.workspace.manager.get_workspace_manager", return_value=fake_workspace_manager),
            patch("horbot.external_agents.runtime.get_external_agent_runtime") as runtime_factory,
        ):
            from horbot.team.manager import get_team_manager

            manager.reload(config)
            get_team_manager().reload(config)
            runtime_factory.return_value.complete = runtime_complete
            transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                async with client.stream(
                    "POST",
                    "/api/chat/stream",
                    json={
                        "content": "please respond",
                        "session_key": "web:test_external_group",
                        "group_chat": True,
                        "mentioned_agents": ["partner-agent"],
                    },
                ) as response:
                    self.assertEqual(response.status_code, 200)
                    lines = [line async for line in response.aiter_lines() if line]

        events = _decode_sse_events(lines)
        self.assertEqual([event["event"] for event in events if event["event"] in {"agent_start", "agent_done", "done"}], ["agent_start", "agent_done", "done"])
        agent_done = next(event for event in events if event["event"] == "agent_done")
        self.assertEqual(agent_done["agent_id"], "partner-agent")
        self.assertEqual(agent_done["content"], "External relay reply")
        runtime_complete.assert_awaited_once()

    async def test_group_chat_stream_supports_parsed_external_mentions_without_provider(self):
        config = self._build_config(
            external_agents={
                "partner-agent": ExternalAgentConfig(
                    id="partner-agent",
                    name="Partner Agent",
                    endpoint="https://example.com/agent",
                    transport="http",
                    team_enabled=True,
                ),
            }
        )

        manager = get_external_agent_manager()
        runtime_complete = AsyncMock(
            return_value={
                "ok": True,
                "content": "External parsed mention reply",
                "detail": "ok",
                "mode": "http_chat",
                "transport": "http",
            }
        )

        fake_agent_manager = SimpleNamespace(
            get_all_agents=lambda: [],
            get_default_agent=lambda: None,
            get_agent=lambda agent_id: None,
        )
        fake_workspace_manager = SimpleNamespace(get_team_workspace=lambda team_id: None)

        with (
            patch("horbot.web.security.get_cached_config", return_value=config),
            patch("horbot.web.api.get_cached_config", return_value=config),
            patch("horbot.config.loader.get_cached_config", return_value=config),
            patch("horbot.team.manager.get_cached_config", return_value=config),
            patch("horbot.external_agents.manager.get_cached_config", return_value=config),
            patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager),
            patch("horbot.workspace.manager.get_workspace_manager", return_value=fake_workspace_manager),
            patch("horbot.external_agents.runtime.get_external_agent_runtime") as runtime_factory,
        ):
            from horbot.team.manager import get_team_manager

            manager.reload(config)
            get_team_manager().reload(config)
            runtime_factory.return_value.complete = runtime_complete
            transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                async with client.stream(
                    "POST",
                    "/api/chat/stream",
                    json={
                        "content": "@Partner Agent please respond",
                        "session_key": "web:test_external_group_parsed",
                        "group_chat": True,
                    },
                ) as response:
                    self.assertEqual(response.status_code, 200)
                    lines = [line async for line in response.aiter_lines() if line]

        events = _decode_sse_events(lines)
        self.assertEqual([event["event"] for event in events if event["event"] in {"agent_start", "agent_done", "done"}], ["agent_start", "agent_done", "done"])
        agent_done = next(event for event in events if event["event"] == "agent_done")
        self.assertEqual(agent_done["agent_id"], "partner-agent")
        self.assertEqual(agent_done["content"], "External parsed mention reply")
        runtime_complete.assert_awaited_once()

    async def test_group_chat_stream_supports_external_team_members_in_specific_team(self):
        config = self._build_config(
            external_agents={
                "partner-agent": ExternalAgentConfig(
                    id="partner-agent",
                    name="Partner Agent",
                    endpoint="https://example.com/agent",
                    transport="http",
                    team_enabled=True,
                ),
            }
        )
        config.teams.instances["team-a"] = TeamConfig(
            id="team-a",
            name="Team A",
            members=["partner-agent"],
        )
        config = normalize_config(config)

        manager = get_external_agent_manager()
        runtime_complete = AsyncMock(
            return_value={
                "ok": True,
                "content": "External team member reply",
                "detail": "ok",
                "mode": "http_chat",
                "transport": "http",
            }
        )

        fake_agent_manager = SimpleNamespace(
            get_all_agents=lambda: [],
            get_default_agent=lambda: None,
            get_agent=lambda agent_id: None,
        )
        fake_workspace_manager = SimpleNamespace(
            get_team_workspace=lambda team_id: SimpleNamespace(workspace_path=f"/tmp/{team_id}"),
        )

        with (
            patch("horbot.web.security.get_cached_config", return_value=config),
            patch("horbot.web.api.get_cached_config", return_value=config),
            patch("horbot.config.loader.get_cached_config", return_value=config),
            patch("horbot.team.manager.get_cached_config", return_value=config),
            patch("horbot.external_agents.manager.get_cached_config", return_value=config),
            patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager),
            patch("horbot.team.manager.get_workspace_manager", return_value=fake_workspace_manager),
            patch("horbot.workspace.manager.get_workspace_manager", return_value=fake_workspace_manager),
            patch("horbot.external_agents.runtime.get_external_agent_runtime") as runtime_factory,
        ):
            from horbot.team.manager import get_team_manager

            manager.reload(config)
            get_team_manager().reload(config)
            runtime_factory.return_value.complete = runtime_complete
            transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                async with client.stream(
                    "POST",
                    "/api/chat/stream",
                    json={
                        "content": "@Partner Agent please respond",
                        "session_key": "web:team_team-a",
                        "team_id": "team-a",
                        "group_chat": True,
                    },
                ) as response:
                    self.assertEqual(response.status_code, 200)
                    lines = [line async for line in response.aiter_lines() if line]

        events = _decode_sse_events(lines)
        agent_done = next(event for event in events if event["event"] == "agent_done")
        self.assertEqual(agent_done["agent_id"], "partner-agent")
        self.assertEqual(agent_done["content"], "External team member reply")
        runtime_complete.assert_awaited_once()

    async def test_group_chat_stream_rejects_external_mentions_outside_team_scope(self):
        config = self._build_config(
            external_agents={
                "partner-agent": ExternalAgentConfig(
                    id="partner-agent",
                    name="Partner Agent",
                    endpoint="https://example.com/agent",
                    transport="http",
                    team_enabled=True,
                ),
            }
        )
        config.teams.instances["team-a"] = TeamConfig(
            id="team-a",
            name="Team A",
            members=[],
        )
        config = normalize_config(config)

        manager = get_external_agent_manager()
        fake_agent_manager = SimpleNamespace(
            get_all_agents=lambda: [],
            get_default_agent=lambda: None,
            get_agent=lambda agent_id: None,
        )
        fake_workspace_manager = SimpleNamespace(
            get_team_workspace=lambda team_id: SimpleNamespace(workspace_path=f"/tmp/{team_id}"),
        )

        with (
            patch("horbot.web.security.get_cached_config", return_value=config),
            patch("horbot.web.api.get_cached_config", return_value=config),
            patch("horbot.config.loader.get_cached_config", return_value=config),
            patch("horbot.team.manager.get_cached_config", return_value=config),
            patch("horbot.external_agents.manager.get_cached_config", return_value=config),
            patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager),
            patch("horbot.team.manager.get_workspace_manager", return_value=fake_workspace_manager),
            patch("horbot.workspace.manager.get_workspace_manager", return_value=fake_workspace_manager),
        ):
            from horbot.team.manager import get_team_manager

            manager.reload(config)
            get_team_manager().reload(config)
            transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post(
                    "/api/chat/stream",
                    json={
                        "content": "please ask partner",
                        "session_key": "web:team_team-a",
                        "team_id": "team-a",
                        "group_chat": True,
                        "mentioned_agents": ["partner-agent"],
                    },
                )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "External agent 'partner-agent' is not enabled for team 'team-a'",
        )

    async def test_group_chat_stream_rejects_disabled_external_team_member_mentions(self):
        config = self._build_config(
            external_agents={
                "partner-agent": ExternalAgentConfig(
                    id="partner-agent",
                    name="Partner Agent",
                    endpoint="https://example.com/agent",
                    transport="http",
                    team_enabled=False,
                ),
            }
        )
        config.teams.instances["team-a"] = TeamConfig(
            id="team-a",
            name="Team A",
            members=["partner-agent"],
        )
        config = normalize_config(config)

        manager = get_external_agent_manager()
        fake_agent_manager = SimpleNamespace(
            get_all_agents=lambda: [],
            get_default_agent=lambda: None,
            get_agent=lambda agent_id: None,
        )
        fake_workspace_manager = SimpleNamespace(
            get_team_workspace=lambda team_id: SimpleNamespace(workspace_path=f"/tmp/{team_id}"),
        )

        with (
            patch("horbot.web.security.get_cached_config", return_value=config),
            patch("horbot.web.api.get_cached_config", return_value=config),
            patch("horbot.config.loader.get_cached_config", return_value=config),
            patch("horbot.team.manager.get_cached_config", return_value=config),
            patch("horbot.external_agents.manager.get_cached_config", return_value=config),
            patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager),
            patch("horbot.team.manager.get_workspace_manager", return_value=fake_workspace_manager),
            patch("horbot.workspace.manager.get_workspace_manager", return_value=fake_workspace_manager),
        ):
            from horbot.team.manager import get_team_manager

            manager.reload(config)
            get_team_manager().reload(config)
            transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post(
                    "/api/chat/stream",
                    json={
                        "content": "please ask partner",
                        "session_key": "web:team_team-a",
                        "team_id": "team-a",
                        "group_chat": True,
                        "mentioned_agents": ["partner-agent"],
                    },
                )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "External agent 'partner-agent' is not enabled for team 'team-a'",
        )

    async def test_group_chat_stream_rejects_unknown_external_mentions_in_team_chat(self):
        config = self._build_config(external_agents={})
        config.teams.instances["team-a"] = TeamConfig(
            id="team-a",
            name="Team A",
            members=[],
        )
        config = normalize_config(config)

        manager = get_external_agent_manager()
        fake_agent_manager = SimpleNamespace(
            get_all_agents=lambda: [],
            get_default_agent=lambda: None,
            get_agent=lambda agent_id: None,
        )
        fake_workspace_manager = SimpleNamespace(
            get_team_workspace=lambda team_id: SimpleNamespace(workspace_path=f"/tmp/{team_id}"),
        )

        with (
            patch("horbot.web.security.get_cached_config", return_value=config),
            patch("horbot.web.api.get_cached_config", return_value=config),
            patch("horbot.config.loader.get_cached_config", return_value=config),
            patch("horbot.team.manager.get_cached_config", return_value=config),
            patch("horbot.external_agents.manager.get_cached_config", return_value=config),
            patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager),
            patch("horbot.team.manager.get_workspace_manager", return_value=fake_workspace_manager),
            patch("horbot.workspace.manager.get_workspace_manager", return_value=fake_workspace_manager),
        ):
            from horbot.team.manager import get_team_manager

            manager.reload(config)
            get_team_manager().reload(config)
            transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post(
                    "/api/chat/stream",
                    json={
                        "content": "please ask missing agent",
                        "session_key": "web:team_team-a",
                        "team_id": "team-a",
                        "group_chat": True,
                        "mentioned_agents": ["missing-agent"],
                    },
                )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Mentioned agent 'missing-agent' not found")

    async def test_conversation_messages_support_external_dm_history(self):
        config = self._build_config(
            external_agents={
                "partner-agent": ExternalAgentConfig(
                    id="partner-agent",
                    name="Partner Agent",
                    endpoint="https://example.com/agent",
                    transport="http",
                    dm_enabled=True,
                ),
            }
        )

        manager = get_external_agent_manager()

        with tempfile.TemporaryDirectory() as tempdir:
            session_dir = Path(tempdir)
            session_manager = SessionManager(workspace=session_dir)
            session = session_manager.get_or_create("web:dm_partner-agent")
            session.add_message("user", "hello external", dedup=True)
            session.add_message(
                "assistant",
                "external history reply",
                dedup=True,
                metadata={"agent_id": "partner-agent", "agent_name": "Partner Agent"},
            )
            await session_manager.async_save(session)

            with (
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
                patch("horbot.external_agents.manager.get_cached_config", return_value=config),
                patch("horbot.web.api.get_session_manager", return_value=session_manager),
            ):
                manager.reload(config)
                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.get("/api/conversations/dm_partner-agent/messages")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["conversation"]["id"], "dm_partner-agent")
        self.assertEqual(payload["conversation"]["name"], "Partner Agent")
        self.assertTrue(any(message.get("content") == "external history reply" for message in payload["messages"]))

    def _build_config(self, *, external_agents: dict[str, ExternalAgentConfig]) -> Config:
        with tempfile.TemporaryDirectory() as tempdir:
            workspace_root = Path(tempdir) / "workspace"
            config = Config()
            config.agents.defaults.workspace = str(workspace_root)
            config.external_agents.instances = external_agents
            return normalize_config(config)


if __name__ == "__main__":
    unittest.main()
