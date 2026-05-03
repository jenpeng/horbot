import asyncio
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from horbot.agent.tools.message import MessageTool
from horbot.bus.events import OutboundMessage
from horbot.bus.queue import MessageBus
from horbot.web.api import (
    _configure_web_agent_loop_message_routing,
    _dispatch_team_group_followups,
    _dispatch_internal_web_outbound,
    _persist_and_broadcast_subagent_event,
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


class FakeDispatchLoop:
    def __init__(self, agent_id: str, final_content: str, calls: list[dict], progress_chunks: list[str] | None = None) -> None:
        self.agent_id = agent_id
        self.final_content = final_content
        self.calls = calls
        self.progress_chunks = progress_chunks or []

    async def process_message(self, msg, **kwargs):
        self.calls.append(
            {
                "agent_id": self.agent_id,
                "content": msg.content,
                "metadata": dict(msg.metadata or {}),
                "speaking_to": kwargs.get("speaking_to"),
                "conversation_type": kwargs.get("conversation_type"),
            }
        )
        on_step_start = kwargs.get("on_step_start")
        on_step_complete = kwargs.get("on_step_complete")
        if on_step_start:
            await on_step_start(f"thinking-{self.agent_id}", "thinking", "思考中...")
        for chunk in self.progress_chunks:
            on_progress = kwargs.get("on_progress")
            if on_progress:
                await on_progress(chunk)
        if on_step_complete:
            await on_step_complete(
                f"thinking-{self.agent_id}",
                "success",
                {"thinking": f"{self.agent_id} reasoning"},
            )
            await on_step_start(f"response-{self.agent_id}", "response", "生成回复")
            await on_step_complete(
                f"response-{self.agent_id}",
                "success",
                {"content": self.final_content},
            )
        return SimpleNamespace(content=self.final_content, metadata={})


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

    async def test_message_tool_keeps_same_team_web_messages_inline(self):
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
            message_tool.set_context("web", "team_team-001")

            await message_tool.execute(
                "请 @main 看一下这个问题",
                channel="web",
                chat_id="team_team-001",
                team_id="team-001",
                trigger_group_chat=True,
                mentioned_agents=["main"],
            )

        internal_dispatch.assert_not_awaited()
        local_bus.publish_outbound.assert_not_awaited()
        external_dispatch.assert_not_awaited()

    async def test_subagent_lifecycle_event_is_persisted_and_broadcast(self):
        fake_manager = FakeSessionManager()
        fake_loop = SimpleNamespace(_agent_id="main", _agent_name="小项")
        event = {
            "task_id": "46af4371",
            "label": "生成PPT",
            "task": "做一个漂亮的 PPT",
            "status": "running",
            "session_key": "web:dm_main",
            "origin": {"channel": "web", "chat_id": "dm_main"},
            "metadata": {"request_id": "req-1", "turn_id": "turn-1"},
        }

        with patch(
            "horbot.web.api._resolve_chat_session_manager",
            new=AsyncMock(return_value=(fake_manager, "web:dm_main")),
        ), patch("horbot.web.websocket.broadcast_to_session", new=AsyncMock()) as broadcast:
            await _persist_and_broadcast_subagent_event(fake_loop, event)

        self.assertEqual(len(fake_manager.session.messages), 1)
        saved = fake_manager.session.messages[0]
        self.assertEqual(saved["message_id"], "subagent-46af4371")
        self.assertIn("后台任务", saved["content"])
        self.assertEqual(saved["execution_steps"][0]["status"], "running")
        self.assertEqual(saved["metadata"]["subagent_task_id"], "46af4371")
        fake_manager.async_save.assert_awaited_once()
        broadcast.assert_awaited_once()

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

    def test_parse_agent_mentions_preserves_text_order(self):
        fake_agent_manager = SimpleNamespace(
            get_agent=lambda agent_id: {
                "horbot-02": SimpleNamespace(id="horbot-02", name="袭人"),
                "main": SimpleNamespace(id="main", name="小项 🐎"),
            }.get(agent_id),
        )

        with patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager):
            mentioned = parse_agent_mentions(
                "@小项 🐎 你先处理，然后再请 @袭人 补充风险。",
                ["horbot-02", "main"],
            )

        self.assertEqual(mentioned, ["main", "horbot-02"])

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

    async def test_dispatch_internal_web_outbound_persists_media_as_files(self):
        fake_manager = FakeSessionManager()
        fake_loop = SimpleNamespace(_agent_id="main", _agent_name="小项 🐎")
        msg = OutboundMessage(
            channel="web",
            chat_id="team_team-001",
            content="图已发出",
            media=["/tmp/demo.png"],
            metadata={"team_id": "team-001"},
        )
        imported_files = [
            {
                "file_id": "file-1",
                "filename": "file-1.png",
                "original_name": "demo.png",
                "mime_type": "image/png",
                "size": 123,
                "category": "image",
                "url": "/api/files/file-1",
                "preview_url": "/api/files/file-1/preview",
            }
        ]

        with patch("horbot.web.api._get_team_session_manager", new=AsyncMock(return_value=fake_manager)), patch(
            "horbot.web.api._normalize_outbound_content_and_files",
            return_value=("图已发出", imported_files),
        ), patch(
            "horbot.web.api._dispatch_team_group_followups",
            new=AsyncMock(),
        ), patch(
            "horbot.web.websocket.broadcast_to_session",
            new=AsyncMock(),
        ) as broadcast:
            await _dispatch_internal_web_outbound(fake_loop, msg)

        saved = fake_manager.session.messages[0]
        self.assertEqual(saved["files"], imported_files)
        broadcast_payload = broadcast.await_args.args[1]
        self.assertEqual(broadcast_payload["files"], imported_files)

    async def test_dispatch_internal_web_outbound_converts_remote_image_links_to_files(self):
        fake_manager = FakeSessionManager()
        fake_loop = SimpleNamespace(_agent_id="main", _agent_name="小项 🐎")
        remote_url = "https://image.pollinations.ai/prompt/pony?seed=1776249001"
        msg = OutboundMessage(
            channel="web",
            chat_id="team_team-001",
            content=f"彭老师，继续用“小马主题”给你生成了1张，见下图～\n\n1. {remote_url}",
            metadata={"team_id": "team-001"},
        )

        with patch("horbot.web.api._get_team_session_manager", new=AsyncMock(return_value=fake_manager)), patch(
            "horbot.web.api._dispatch_team_group_followups",
            new=AsyncMock(),
        ), patch(
            "horbot.web.websocket.broadcast_to_session",
            new=AsyncMock(),
        ) as broadcast:
            await _dispatch_internal_web_outbound(fake_loop, msg)

        saved = fake_manager.session.messages[0]
        self.assertEqual(saved["content"], "彭老师，继续用“小马主题”给你生成了1张，见下图～")
        self.assertEqual(len(saved["files"]), 1)
        self.assertEqual(saved["files"][0]["preview_url"], remote_url)
        self.assertEqual(saved["files"][0]["category"], "image")
        broadcast_payload = broadcast.await_args.args[1]
        self.assertEqual(broadcast_payload["content"], "彭老师，继续用“小马主题”给你生成了1张，见下图～")
        self.assertEqual(broadcast_payload["files"][0]["preview_url"], remote_url)

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

    async def test_message_tool_internal_team_dispatch_survives_caller_cancellation(self):
        local_bus = MessageBus()
        local_bus.publish_outbound = AsyncMock()

        message_tool = MessageTool()
        fake_loop = SimpleNamespace(
            tools=SimpleNamespace(get=lambda name: message_tool if name == "message" else None),
        )

        dispatch_started = asyncio.Event()
        dispatch_completed = asyncio.Event()

        async def slow_internal_dispatch(agent_loop, msg):
            dispatch_started.set()
            await asyncio.sleep(0.05)
            dispatch_completed.set()

        with patch("horbot.web.api._dispatch_internal_web_outbound", side_effect=slow_internal_dispatch), patch(
            "horbot.web.api._dispatch_outbound_via_gateway",
            new=AsyncMock(),
        ):
            _configure_web_agent_loop_message_routing(fake_loop, local_bus)
            message_tool.set_context("web", "dm_main")

            dispatch_task = asyncio.create_task(
                message_tool.execute(
                    "请去团队里接力",
                    channel="web",
                    chat_id="team_team-001",
                    team_id="team-001",
                    trigger_group_chat=True,
                    mentioned_agents=["main"],
                )
            )

            await asyncio.wait_for(dispatch_started.wait(), timeout=1)
            dispatch_task.cancel()

            with self.assertRaises(asyncio.CancelledError):
                await dispatch_task

            await asyncio.wait_for(dispatch_completed.wait(), timeout=1)
            local_bus.publish_outbound.assert_not_awaited()

    async def test_dispatch_team_group_followups_streams_progress_and_returns_to_source_summary(self):
        fake_manager = FakeSessionManager()
        source_dm_manager = FakeSessionManager()
        loop_calls: list[dict] = []
        loops = {
            "horbot-02": FakeDispatchLoop(
                "horbot-02",
                "袭人给出分析结论",
                loop_calls,
                progress_chunks=["袭人正在分析", "袭人正在分析并收敛"],
            ),
            "main": FakeDispatchLoop(
                "main",
                "小项最终汇报",
                loop_calls,
                progress_chunks=["小项正在汇总团队意见"],
            ),
        }
        fake_agent_manager = SimpleNamespace(
            get_agent=lambda agent_id: {
                "main": SimpleNamespace(id="main", name="小项 🐎"),
                "horbot-02": SimpleNamespace(id="horbot-02", name="袭人"),
            }.get(agent_id),
        )
        msg = OutboundMessage(
            channel="web",
            chat_id="team_team-001",
            content="@袭人 先分析，等你回复后我再做最终整合汇报给用户。",
            metadata={
                "team_id": "team-001",
                "trigger_group_chat": True,
                "mentioned_agents": ["horbot-02"],
                "_source_channel": "web",
                "_source_chat_id": "dm_main",
            },
        )

        async def fake_get_loop(agent_id, session_manager):
            return loops[agent_id]

        with patch("horbot.web.api._resolve_team_dispatch_targets", return_value=["horbot-02"]), patch(
            "horbot.agent.manager.get_agent_manager",
            return_value=fake_agent_manager,
        ), patch(
            "horbot.web.api.get_agent_loop_with_session_manager",
            side_effect=fake_get_loop,
        ), patch(
            "horbot.web.api._resolve_chat_session_manager",
            new=AsyncMock(return_value=(source_dm_manager, "web:dm_main")),
        ), patch(
            "horbot.web.websocket.broadcast_to_session",
            new=AsyncMock(),
        ) as broadcast:
            await _dispatch_team_group_followups(
                SimpleNamespace(_agent_id="main", _agent_name="小项 🐎"),
                msg,
                team_id="team-001",
                session_key="web:team_team-001",
                session_manager=fake_manager,
                source_agent_id="main",
                source_agent_name="小项 🐎",
            )

        self.assertGreaterEqual(fake_manager.async_save.await_count, 3)
        self.assertEqual(
            [message["content"] for message in fake_manager.session.messages],
            ["袭人给出分析结论", "小项最终汇报"],
        )
        self.assertEqual(
            [message["content"] for message in source_dm_manager.session.messages],
            ["小项最终汇报"],
        )
        self.assertEqual(
            source_dm_manager.session.messages[0]["metadata"]["dispatch_origin"],
            "message_tool_summary_mirror",
        )
        event_names = [call.args[1]["event"] for call in broadcast.await_args_list]
        self.assertIn("agent_start", event_names)
        self.assertIn("progress", event_names)
        self.assertIn("step_start", event_names)
        self.assertIn("step_complete", event_names)
        self.assertIn("agent_done", event_names)
        self.assertEqual(loop_calls[-1]["agent_id"], "main")
        self.assertIn("现在直接面向用户输出最终总结", loop_calls[-1]["content"])
        self.assertTrue(isinstance(loop_calls[0]["metadata"].get("assistant_message_id"), str))
        self.assertTrue(isinstance(loop_calls[0]["metadata"].get("turn_id"), str))
        self.assertTrue(isinstance(loop_calls[-1]["metadata"].get("assistant_message_id"), str))
        self.assertTrue(isinstance(loop_calls[-1]["metadata"].get("turn_id"), str))

    async def test_dispatch_team_group_followups_emits_synthetic_progress_without_real_delta(self):
        fake_manager = FakeSessionManager()
        source_dm_manager = FakeSessionManager()
        loop_calls: list[dict] = []
        loops = {
            "horbot-02": FakeDispatchLoop(
                "horbot-02",
                "袭人给出分析结论",
                loop_calls,
                progress_chunks=[],
            ),
            "main": FakeDispatchLoop(
                "main",
                "小项最终汇报",
                loop_calls,
                progress_chunks=[],
            ),
        }
        fake_agent_manager = SimpleNamespace(
            get_agent=lambda agent_id: {
                "main": SimpleNamespace(id="main", name="小项 🐎"),
                "horbot-02": SimpleNamespace(id="horbot-02", name="袭人"),
            }.get(agent_id),
        )
        msg = OutboundMessage(
            channel="web",
            chat_id="team_team-001",
            content="@袭人 先分析，等你回复后我再做最终整合汇报给用户。",
            metadata={
                "team_id": "team-001",
                "trigger_group_chat": True,
                "mentioned_agents": ["horbot-02"],
                "_source_channel": "web",
                "_source_chat_id": "dm_main",
            },
        )

        async def fake_get_loop(agent_id, session_manager):
            return loops[agent_id]

        with patch("horbot.web.api._resolve_team_dispatch_targets", return_value=["horbot-02"]), patch(
            "horbot.agent.manager.get_agent_manager",
            return_value=fake_agent_manager,
        ), patch(
            "horbot.web.api.get_agent_loop_with_session_manager",
            side_effect=fake_get_loop,
        ), patch(
            "horbot.web.api._resolve_chat_session_manager",
            new=AsyncMock(return_value=(source_dm_manager, "web:dm_main")),
        ), patch(
            "horbot.web.websocket.broadcast_to_session",
            new=AsyncMock(),
        ) as broadcast:
            await _dispatch_team_group_followups(
                SimpleNamespace(_agent_id="main", _agent_name="小项 🐎"),
                msg,
                team_id="team-001",
                session_key="web:team_team-001",
                session_manager=fake_manager,
                source_agent_id="main",
                source_agent_name="小项 🐎",
            )

        progress_events = [
            payload
            for target_session, payload in ((call.args[0], call.args[1]) for call in broadcast.await_args_list)
            if target_session == "web:team_team-001" and payload["event"] == "progress"
        ]
        self.assertGreaterEqual(len(progress_events), 2)
        self.assertTrue(all(event.get("synthetic_progress") is True for event in progress_events))
        self.assertTrue(any("正在分析任务与约束" in str(event.get("content", "")) for event in progress_events))

        mirrored_done_events = [
            payload
            for target_session, payload in ((call.args[0], call.args[1]) for call in broadcast.await_args_list)
            if target_session == "web:dm_main" and payload["event"] == "agent_done"
        ]
        self.assertEqual(len(mirrored_done_events), 1)
        self.assertEqual(mirrored_done_events[0].get("dispatch_origin"), "message_tool_summary_mirror")
        self.assertEqual(mirrored_done_events[0].get("source_team_id"), "team-001")
        self.assertEqual(mirrored_done_events[0].get("source_session_key"), "web:team_team-001")
        self.assertTrue(isinstance(mirrored_done_events[0].get("request_id"), str))


if __name__ == "__main__":
    unittest.main()
