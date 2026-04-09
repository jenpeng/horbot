from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from horbot.agent.tools.message import MessageTool
from horbot.bus.events import OutboundMessage
from horbot.bus.queue import MessageBus
from horbot.web.api import (
    _configure_web_agent_loop_message_routing,
    _dispatch_internal_web_outbound,
    _resolve_internal_web_session_manager,
    _resolve_team_dispatch_targets,
    parse_agent_mentions,
)


class FakeSession:
    def __init__(self) -> None:
        self.messages = []

    def add_message(self, role, content, **kwargs):
        self.messages.append({
            "role": role,
            "content": content,
            **kwargs,
        })
        return kwargs.get("message_id", "msg-1")


class FakeSessionManager:
    def __init__(self, sessions_dir: str = "/tmp/fake-sessions") -> None:
        self.session = FakeSession()
        self.async_save = AsyncMock()
        self.sessions_dir = sessions_dir

    def get_or_create(self, key):
        self.session.key = key
        return self.session


class WebTeamDispatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_message_tool_routes_team_web_messages_to_internal_dispatch(self):
        local_bus = MessageBus()
        local_bus.publish_outbound = AsyncMock()

        message_tool = MessageTool()
        fake_loop = SimpleNamespace(
            tools=SimpleNamespace(get=lambda name: message_tool if name == "message" else None),
        )

        with patch("horbot.web.api._dispatch_internal_web_outbound", new=AsyncMock()) as internal_dispatch, patch(
            "horbot.web.api._dispatch_outbound_via_gateway",
            new=AsyncMock(),
        ) as external_dispatch:
            _configure_web_agent_loop_message_routing(fake_loop, local_bus)
            message_tool.set_context("web", "dm_horbot-02")

            await message_tool.execute(
                "请 @main 看一下这个问题",
                channel="web",
                chat_id="team_team-001",
                team_id="team-001",
                trigger_group_chat=True,
                mentioned_agents=["main"],
            )

        internal_dispatch.assert_awaited_once()
        local_bus.publish_outbound.assert_not_awaited()
        external_dispatch.assert_not_awaited()

    def test_resolve_team_dispatch_targets_prefers_mentions_then_default_non_source_member(self):
        fake_team = SimpleNamespace(get_ordered_member_ids=lambda: ["horbot-02", "main"])
        fake_manager = SimpleNamespace(get_team=lambda team_id: fake_team if team_id == "team-001" else None)

        with patch("horbot.team.manager.get_team_manager", return_value=fake_manager), patch(
            "horbot.web.api.parse_agent_mentions",
            return_value=["main"],
        ):
            mentioned = _resolve_team_dispatch_targets(
                team_id="team-001",
                source_agent_id="horbot-02",
                content="@main 请接力",
                explicit_mentions=[],
                trigger_group_chat=False,
            )
            fallback = _resolve_team_dispatch_targets(
                team_id="team-001",
                source_agent_id="horbot-02",
                content="请帮我继续处理",
                explicit_mentions=[],
                trigger_group_chat=True,
            )

        self.assertEqual(mentioned, ["main"])
        self.assertEqual(fallback, ["main"])

    def test_parse_agent_mentions_supports_agent_name_with_emoji_suffix(self):
        fake_agent_manager = SimpleNamespace(
            get_agent=lambda agent_id: {
                "horbot-02": SimpleNamespace(id="horbot-02", name="袭人"),
                "main": SimpleNamespace(id="main", name="小项 🐎"),
            }.get(agent_id),
        )

        with patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager):
            mentioned = parse_agent_mentions(
                "@小项 🐎 请你接手，要求你在团队群里最终只回复这个字符串：OK",
                ["horbot-02", "main"],
            )

        self.assertEqual(mentioned, ["main"])

    async def test_resolve_internal_web_session_manager_reuses_matching_team_sessions(self):
        team_sessions_dir = Path("/tmp/team-001-sessions")
        current_session_manager = FakeSessionManager(str(team_sessions_dir))
        source_loop = SimpleNamespace(sessions=current_session_manager)

        with patch("horbot.web.api._get_team_sessions_dir", return_value=team_sessions_dir), patch(
            "horbot.web.api._get_team_session_manager",
            new=AsyncMock(side_effect=AssertionError("should not build a new team session manager")),
        ):
            resolved = await _resolve_internal_web_session_manager(
                source_loop,
                team_id="team-001",
                session_key="web:team_team-001",
            )

        self.assertIs(resolved, current_session_manager)

    async def test_dispatch_internal_web_outbound_saves_team_message_and_runs_followup(self):
        fake_manager = FakeSessionManager()
        fake_loop = SimpleNamespace(_agent_id="horbot-02", _agent_name="袭人")
        msg = OutboundMessage(
            channel="web",
            chat_id="team_team-001",
            content="@main 请继续排查这个问题",
            metadata={
                "team_id": "team-001",
                "trigger_group_chat": True,
                "mentioned_agents": ["main"],
                "_source_chat_id": "dm_horbot-02",
            },
        )

        with patch("horbot.web.api._get_team_session_manager", new=AsyncMock(return_value=fake_manager)), patch(
            "horbot.web.api._dispatch_team_group_followups",
            new=AsyncMock(),
        ) as followups, patch(
            "horbot.web.websocket.broadcast_to_session",
            new=AsyncMock(),
        ) as broadcast:
            await _dispatch_internal_web_outbound(fake_loop, msg)

        self.assertEqual(fake_manager.session.key, "web:team_team-001")
        self.assertEqual(len(fake_manager.session.messages), 1)
        saved = fake_manager.session.messages[0]
        self.assertEqual(saved["role"], "assistant")
        self.assertEqual(saved["content"], "@main 请继续排查这个问题")
        self.assertEqual(saved["metadata"]["team_id"], "team-001")
        self.assertEqual(saved["metadata"]["agent_id"], "horbot-02")
        fake_manager.async_save.assert_awaited()
        broadcast.assert_awaited_once()
        followups.assert_awaited_once()

    async def test_dispatch_internal_web_outbound_prefers_existing_team_session_manager(self):
        fake_manager = FakeSessionManager("/tmp/team-001-sessions")
        fake_loop = SimpleNamespace(
            _agent_id="main",
            _agent_name="小项 🐎",
            sessions=fake_manager,
        )
        msg = OutboundMessage(
            channel="web",
            chat_id="team_team-001",
            content="DM_TEAM_DISPATCH_OK_test",
            metadata={
                "team_id": "team-001",
            },
        )

        with patch("horbot.web.api._get_team_sessions_dir", return_value=Path("/tmp/team-001-sessions")), patch(
            "horbot.web.api._get_team_session_manager",
            new=AsyncMock(side_effect=AssertionError("should reuse existing manager")),
        ), patch(
            "horbot.web.api._dispatch_team_group_followups",
            new=AsyncMock(),
        ), patch(
            "horbot.web.websocket.broadcast_to_session",
            new=AsyncMock(),
        ):
            await _dispatch_internal_web_outbound(fake_loop, msg)

        self.assertEqual(fake_manager.session.key, "web:team_team-001")
        self.assertEqual(fake_manager.session.messages[-1]["content"], "DM_TEAM_DISPATCH_OK_test")


if __name__ == "__main__":
    unittest.main()
