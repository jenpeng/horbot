import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from horbot.agent.manager import get_agent_manager
from horbot.config.normalizer import normalize_config
from horbot.config.schema import AgentConfig, Config, TeamConfig, TeamMemberProfile
from horbot.utils.paths import HORBOT_ROOT_ENV
from horbot.web.main import app


class AgentDeleteApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_delete_agent_removes_default_workspace_and_team_profiles(self):
        with tempfile.TemporaryDirectory() as tempdir:
            horbot_root = Path(tempdir) / ".horbot"
            config = Config()
            config.agents.instances = {
                "writer": AgentConfig(id="writer", name="Writer"),
            }
            config.teams.instances = {
                "delivery": TeamConfig(
                    id="delivery",
                    name="Delivery",
                    members=["writer"],
                    member_profiles={
                        "writer": TeamMemberProfile(role="builder", responsibility="负责实现", priority=10, is_lead=True),
                    },
                ),
            }
            config = normalize_config(config)
            reset_mock = AsyncMock()
            manager = get_agent_manager()

            with (
                patch.dict(os.environ, {HORBOT_ROOT_ENV: str(horbot_root)}),
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.agent.manager.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
                patch("horbot.config.loader.load_config", return_value=config),
                patch("horbot.config.loader.save_config") as save_config_mock,
                patch("horbot.web.api.reset_agent_loop", reset_mock),
            ):
                manager.reload(config)
                writer = manager.get_agent("writer")
                self.assertIsNotNone(writer)
                workspace = writer.get_workspace()
                memory_dir = writer.get_memory_dir()
                sessions_dir = writer.get_sessions_dir()
                skills_dir = writer.get_skills_dir()
                (workspace / "SOUL.md").write_text("# Writer\n", encoding="utf-8")
                (memory_dir / "facts.json").write_text("{}", encoding="utf-8")
                (sessions_dir / "chat.jsonl").write_text("", encoding="utf-8")
                (skills_dir / "tool.py").write_text("print('ok')\n", encoding="utf-8")
                agent_root = workspace.parent
                self.assertTrue(agent_root.exists())

                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.delete("/api/agents/writer")

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["status"], "deleted")
                save_config_mock.assert_called_once()
                reset_mock.assert_awaited_once()
                self.assertNotIn("writer", config.agents.instances)
                self.assertEqual(config.teams.instances["delivery"].members, [])
                self.assertEqual(config.teams.instances["delivery"].member_profiles, {})
                self.assertFalse(agent_root.exists())
                self.assertIsNone(manager.get_agent("writer"))

    async def test_delete_agent_only_removes_horbot_files_from_custom_workspace(self):
        with tempfile.TemporaryDirectory() as tempdir:
            horbot_root = Path(tempdir) / ".horbot"
            custom_workspace = Path(tempdir) / "custom-writer"
            config = Config()
            config.agents.instances = {
                "writer": AgentConfig(id="writer", name="Writer", workspace=str(custom_workspace)),
            }
            config = normalize_config(config)
            reset_mock = AsyncMock()
            manager = get_agent_manager()

            with (
                patch.dict(os.environ, {HORBOT_ROOT_ENV: str(horbot_root)}),
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.agent.manager.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
                patch("horbot.config.loader.load_config", return_value=config),
                patch("horbot.config.loader.save_config") as save_config_mock,
                patch("horbot.web.api.reset_agent_loop", reset_mock),
            ):
                manager.reload(config)
                writer = manager.get_agent("writer")
                self.assertIsNotNone(writer)
                workspace = writer.get_workspace()
                metadata_dir = workspace / ".horbot-agent"
                memory_dir = writer.get_memory_dir()
                metadata_dir.mkdir(parents=True, exist_ok=True)
                memory_dir.mkdir(parents=True, exist_ok=True)
                (metadata_dir / "memory.json").write_text("{}", encoding="utf-8")
                (memory_dir / "facts.json").write_text("{}", encoding="utf-8")
                (workspace / "SOUL.md").write_text("# Writer Soul\n", encoding="utf-8")
                (workspace / "USER.md").write_text("# User Profile\n", encoding="utf-8")
                user_file = workspace / "notes.txt"
                user_file.write_text("keep me\n", encoding="utf-8")
                self.assertTrue(str(memory_dir).startswith(str(horbot_root / "agents" / "writer")))

                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.delete("/api/agents/writer")

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["status"], "deleted")
                save_config_mock.assert_called_once()
                reset_mock.assert_awaited_once()
                self.assertFalse((workspace / ".horbot-agent").exists())
                self.assertFalse((workspace / "SOUL.md").exists())
                self.assertFalse((workspace / "USER.md").exists())
                self.assertFalse(memory_dir.exists())
                self.assertTrue(user_file.exists())
                self.assertTrue(workspace.exists())
                self.assertNotIn("writer", config.agents.instances)
                self.assertIsNone(manager.get_agent("writer"))


if __name__ == "__main__":
    unittest.main()
