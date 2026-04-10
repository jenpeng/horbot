import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from horbot.conversation import ConversationType
from horbot.session.manager import SessionManager
from horbot.web.api import delete_session, get_conversation_messages, get_session_manager, update_session_title


class ChatSessionRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_session_manager_refreshes_when_workspace_changes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_a = Path(tmpdir) / "workspace-a"
            workspace_b = Path(tmpdir) / "workspace-b"

            config_a = SimpleNamespace(workspace_path=str(workspace_a))
            config_b = SimpleNamespace(workspace_path=str(workspace_b))

            with (
                patch("horbot.web.api._session_manager", None),
                patch("horbot.web.api.get_cached_config", side_effect=[config_a, config_b]),
            ):
                manager_a = get_session_manager()
                manager_b = get_session_manager()

            self.assertNotEqual(manager_a.sessions_dir, manager_b.sessions_dir)
            self.assertEqual(manager_a.sessions_dir, workspace_a / "sessions")
            self.assertEqual(manager_b.sessions_dir, workspace_b / "sessions")

    async def test_delete_dm_session_uses_agent_workspace_manager(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_workspace = Path(tmpdir) / "writer-workspace"
            session_manager = SessionManager(workspace=agent_workspace / "sessions")
            session = session_manager.get_or_create("web:dm_writer")
            session.add_message("user", "hello writer")
            session_manager.save(session)

            fake_loop = SimpleNamespace(sessions=session_manager)

            with patch("horbot.web.api.get_agent_loop", new=AsyncMock(return_value=fake_loop)):
                result = await delete_session("web:dm_writer")

            self.assertEqual(result["status"], "success")
            self.assertFalse(session_manager._get_session_path("web:dm_writer").exists())

    async def test_delete_team_session_uses_team_workspace_manager(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            team_workspace = Path(tmpdir) / "team-alpha-workspace"
            session_manager = SessionManager(workspace=team_workspace / "sessions")
            session = session_manager.get_or_create("web:team_alpha")
            session.add_message("user", "hello team")
            session_manager.save(session)

            fake_team_manager = SimpleNamespace(
                get_team=lambda team_id: SimpleNamespace(id=team_id) if team_id == "alpha" else None
            )
            fake_workspace_manager = SimpleNamespace(
                get_team_workspace=lambda team_id: SimpleNamespace(workspace_path=str(team_workspace))
                if team_id == "alpha" else None
            )

            with (
                patch("horbot.team.manager.get_team_manager", return_value=fake_team_manager),
                patch("horbot.workspace.manager.get_workspace_manager", return_value=fake_workspace_manager),
            ):
                result = await delete_session("web:team_alpha")

            self.assertEqual(result["status"], "success")
            self.assertFalse(session_manager._get_session_path("web:team_alpha").exists())

    async def test_update_team_session_title_uses_team_workspace_manager(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            team_workspace = Path(tmpdir) / "team-alpha-workspace"
            session_manager = SessionManager(workspace=team_workspace / "sessions")
            session = session_manager.get_or_create("web:team_alpha")
            session.add_message("user", "hello team")
            session_manager.save(session)

            fake_team_manager = SimpleNamespace(
                get_team=lambda team_id: SimpleNamespace(id=team_id) if team_id == "alpha" else None
            )
            fake_workspace_manager = SimpleNamespace(
                get_team_workspace=lambda team_id: SimpleNamespace(workspace_path=str(team_workspace))
                if team_id == "alpha" else None
            )

            with (
                patch("horbot.team.manager.get_team_manager", return_value=fake_team_manager),
                patch("horbot.workspace.manager.get_workspace_manager", return_value=fake_workspace_manager),
            ):
                result = await update_session_title("web:team_alpha", "团队新标题")

            self.assertEqual(result["status"], "success")
            updated = SessionManager(workspace=team_workspace / "sessions").get("web:team_alpha")
            self.assertIsNotNone(updated)
            self.assertEqual(updated.metadata.get("title"), "团队新标题")

    async def test_delete_missing_team_session_returns_404(self):
        fake_team_manager = SimpleNamespace(
            get_team=lambda team_id: SimpleNamespace(id=team_id) if team_id == "alpha" else None
        )
        fake_workspace_manager = SimpleNamespace(
            get_team_workspace=lambda team_id: SimpleNamespace(workspace_path="/tmp/missing-team-workspace")
            if team_id == "alpha" else None
        )

        with (
            patch("horbot.team.manager.get_team_manager", return_value=fake_team_manager),
            patch("horbot.workspace.manager.get_workspace_manager", return_value=fake_workspace_manager),
        ):
            with self.assertRaises(HTTPException) as ctx:
                await delete_session("web:team_alpha")

        self.assertEqual(ctx.exception.status_code, 404)

    async def test_get_dm_conversation_messages_reads_agent_scoped_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_workspace = Path(tmpdir) / "writer-workspace"
            session_manager = SessionManager(workspace=agent_workspace / "sessions")
            session = session_manager.get_or_create("web:dm_writer")
            session.add_message("user", "hello writer")
            session.add_message(
                "assistant",
                "hi there",
                agent_id="writer",
                agent_name="Writer",
            )
            session_manager.save(session)

            fake_conversation = SimpleNamespace(
                id="dm_writer",
                type=ConversationType.DM,
                target_id="writer",
                to_dict=lambda: {"id": "dm_writer", "type": "dm", "target_id": "writer"},
            )
            fake_conv_manager = SimpleNamespace(
                get=lambda conv_id: fake_conversation if conv_id == "dm_writer" else None,
            )
            fake_agent = SimpleNamespace(
                get_sessions_dir=lambda: agent_workspace / "sessions",
            )
            fake_agent_manager = SimpleNamespace(
                get_agent=lambda agent_id: fake_agent if agent_id == "writer" else None,
            )

            with (
                patch("horbot.conversation.get_conversation_manager", return_value=fake_conv_manager),
                patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager),
            ):
                payload = await get_conversation_messages("dm_writer")

        self.assertEqual(payload["conversation_id"], "dm_writer")
        self.assertEqual(len(payload["messages"]), 2)
        self.assertEqual(payload["messages"][0]["content"], "hello writer")
        self.assertEqual(payload["messages"][1]["content"], "hi there")

    async def test_get_team_conversation_messages_merges_legacy_global_and_team_scoped_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            global_manager = SessionManager(workspace=root / "global-workspace" / "sessions")
            team_workspace = root / "team-alpha-workspace"
            team_manager = SessionManager(workspace=team_workspace / "sessions")

            legacy_session = global_manager.get_or_create("web:team_alpha")
            legacy_session.add_message("user", "先前的团队问题")
            global_manager.save(legacy_session)

            current_session = team_manager.get_or_create("web:team_alpha")
            current_session.add_message(
                "assistant",
                "当前团队回复",
                agent_id="writer",
                agent_name="Writer",
            )
            team_manager.save(current_session)

            fake_conversation = SimpleNamespace(
                id="team_alpha",
                type=ConversationType.TEAM,
                target_id="alpha",
                to_dict=lambda: {"id": "team_alpha", "type": "team", "target_id": "alpha"},
            )
            fake_conv_manager = SimpleNamespace(
                get=lambda conv_id: fake_conversation if conv_id == "team_alpha" else None,
            )
            fake_workspace_manager = SimpleNamespace(
                get_team_workspace=lambda team_id: SimpleNamespace(workspace_path=str(team_workspace))
                if team_id == "alpha" else None,
            )

            with (
                patch("horbot.conversation.get_conversation_manager", return_value=fake_conv_manager),
                patch("horbot.workspace.manager.get_workspace_manager", return_value=fake_workspace_manager),
                patch("horbot.web.api.get_session_manager", return_value=global_manager),
            ):
                payload = await get_conversation_messages("team_alpha")

        self.assertEqual(payload["conversation_id"], "team_alpha")
        self.assertEqual([message["content"] for message in payload["messages"]], ["先前的团队问题", "当前团队回复"])
