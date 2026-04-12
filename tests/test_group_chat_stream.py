import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from horbot.session.manager import SessionManager
from horbot.agent.conversation import (
    ConversationType,
    build_conversation_context,
    format_history_for_agent,
)
from horbot.web.api import (
    StreamRequest,
    _build_user_summary_trigger_message,
    _validate_chat_request,
    _group_chat_stream_generator,
    extract_agent_mention_payload,
    parse_agent_mentions,
)


class FakeAgent:
    def __init__(self, agent_id: str, name: str, is_main: bool = False):
        self.id = agent_id
        self.name = name
        self.is_main = is_main


class FakeAgentManager:
    def __init__(self):
        self.agents = {
            "alpha": FakeAgent("alpha", "Alpha", is_main=True),
            "beta": FakeAgent("beta", "Beta"),
        }

    def get_agent(self, agent_id: str):
        return self.agents.get(agent_id)

    def get_all_agents(self):
        return list(self.agents.values())

    def get_main_agent(self):
        return self.agents["alpha"]


class FlexibleFakeAgentManager:
    def __init__(self, agents: dict[str, FakeAgent], main_agent_id: str):
        self.agents = agents
        self.main_agent_id = main_agent_id

    def get_agent(self, agent_id: str):
        return self.agents.get(agent_id)

    def get_all_agents(self):
        return list(self.agents.values())

    def get_main_agent(self):
        return self.agents[self.main_agent_id]


class FakeWorkspaceManager:
    def get_team_workspace(self, team_id: str):
        return SimpleNamespace(workspace_path=f"/tmp/{team_id}")


class FakeTeam:
    def __init__(self, team_id: str, members: list[str]):
        self.id = team_id
        self.members = members

    def get_ordered_member_ids(self) -> list[str]:
        return list(self.members)


class FakeTeamManager:
    def __init__(self, teams: dict[str, FakeTeam]):
        self.teams = teams

    def get_team(self, team_id: str):
        return self.teams.get(team_id)


class FakeResponse:
    def __init__(self, content: str):
        self.content = content
        self.metadata = {}


class FakeStreamManager:
    def __init__(self, stop_after_register: bool = False):
        self.stop_after_register = stop_after_register
        self.registered_request_ids: list[str] = []
        self.unregistered_request_ids: list[str] = []
        self.should_stop_request_ids: set[str] = set()

    async def register(self, request_id: str, task) -> None:
        self.registered_request_ids.append(request_id)
        if self.stop_after_register:
            self.should_stop_request_ids.add(request_id)

    async def unregister(self, request_id: str) -> None:
        self.unregistered_request_ids.append(request_id)

    def should_stop(self, request_id: str) -> bool:
        return request_id in self.should_stop_request_ids


class FakeAgentLoop:
    def __init__(self, agent_id: str, outputs: dict[str, str], calls: list[dict]):
        self.agent_id = agent_id
        self.outputs = outputs
        self.calls = calls

    async def process_message(self, msg, **kwargs):
        self.calls.append(
            {
                "agent_id": self.agent_id,
                "content": msg.content,
                "speaking_to": kwargs.get("speaking_to"),
                "conversation_type": kwargs.get("conversation_type"),
            }
        )

        output = self.outputs[self.agent_id]
        if isinstance(output, list):
            if not output:
                raise AssertionError(f"No remaining outputs configured for {self.agent_id}")
            content = output.pop(0)
        else:
            content = output
        await kwargs["on_step_start"]("thinking_1", "thinking", "思考中...")
        await kwargs["on_status"]("正在思考...")
        await kwargs["on_step_complete"]("thinking_1", "success", {"thinking": f"{self.agent_id} thinking"})
        await kwargs["on_step_start"]("response_1", "response", "生成回复")
        await kwargs["on_progress"](content)
        await kwargs["on_step_complete"]("response_1", "success", {"content": content})
        return FakeResponse(content)


class FakeMessageToolRelayLoop:
    def __init__(
        self,
        agent_id: str,
        tool_content: str,
        mentioned_agents: list[str],
        calls: list[dict],
    ):
        self.agent_id = agent_id
        self.tool_content = tool_content
        self.mentioned_agents = mentioned_agents
        self.calls = calls

    async def process_message(self, msg, **kwargs):
        self.calls.append(
            {
                "agent_id": self.agent_id,
                "content": msg.content,
                "speaking_to": kwargs.get("speaking_to"),
                "conversation_type": kwargs.get("conversation_type"),
            }
        )

        await kwargs["on_step_start"]("thinking_1", "thinking", "思考中...")
        await kwargs["on_status"]("正在思考...")
        await kwargs["on_step_complete"]("thinking_1", "success", {"thinking": f"{self.agent_id} thinking"})
        await kwargs["on_step_start"]("tool_1", "tool_call", "执行 message")
        await kwargs["on_tool_start"](
            "message",
            {
                "content": self.tool_content,
                "channel": "web",
                "chat_id": "team_team-001",
                "team_id": "team-001",
                "mentioned_agents": self.mentioned_agents,
                "trigger_group_chat": True,
            },
        )
        await kwargs["on_tool_result"]("message", "Message sent to web:team_team-001", 0.01)
        await kwargs["on_step_complete"]("tool_1", "success", {"tool_name": "message"})
        return FakeResponse("Message sent to web:team_team-001")


class FailingAgentLoop:
    def __init__(self, error: Exception):
        self.error = error

    async def process_message(self, msg, **kwargs):
        raise self.error


def _decode_sse(events: list[str]) -> list[dict]:
    decoded = []
    for item in events:
        assert item.startswith("data: "), item
        decoded.append(json.loads(item[6:]))
    return decoded


class GroupChatStreamTests(unittest.IsolatedAsyncioTestCase):
    def test_parse_agent_mentions_supports_normalized_short_name(self):
        fake_agent_manager = SimpleNamespace(
            agents={"main": FakeAgent("main", "小项 🐎", is_main=True)},
            get_agent=lambda agent_id: {"main": FakeAgent("main", "小项 🐎", is_main=True)}.get(agent_id),
            get_all_agents=lambda: [FakeAgent("main", "小项 🐎", is_main=True)],
            get_main_agent=lambda: FakeAgent("main", "小项 🐎", is_main=True),
        )
        with patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager):
            mentioned = parse_agent_mentions("@小项 接力完成1", ["main"])
        self.assertEqual(mentioned, ["main"])

    def test_extract_agent_mention_payload_returns_target_suffix(self):
        payload = extract_agent_mention_payload(
            "@Beta 请只回复自己的名字，不要添加任何其他内容",
            target_agent_id="beta",
            target_agent_name="Beta",
        )
        self.assertEqual(payload, "请只回复自己的名字，不要添加任何其他内容")

    def test_agent_to_agent_history_excludes_raw_user_turns(self):
        conversation_ctx = build_conversation_context(
            conversation_type=ConversationType.AGENT_TO_AGENT,
            source_id="alpha",
            source_name="Alpha",
            target_id="beta",
            target_name="Beta",
            trigger_message="请只回复自己的名字",
        )
        history = format_history_for_agent(
            [
                {"role": "user", "content": "@Beta 请只回复自己的名字"},
                {
                    "role": "assistant",
                    "content": "@Beta 请只回复自己的名字",
                    "metadata": {
                        "agent_id": "alpha",
                        "agent_name": "Alpha",
                        "source": "user",
                        "target": "alpha",
                    },
                },
            ],
            target_agent_id="beta",
            target_agent_name="Beta",
            conversation_ctx=conversation_ctx,
            is_group_chat=True,
        )
        self.assertEqual(history, [])

    def test_user_summary_turn_history_strips_raw_mentions_and_handoffs(self):
        conversation_ctx = build_conversation_context(
            conversation_type=ConversationType.USER_TO_AGENT,
            source_id="user",
            source_name="用户",
            target_id="alpha",
            target_name="小项 🐎",
            trigger_message=_build_user_summary_trigger_message(
                "@小项 你和 @袭人 还有 @小布 接力讨论后给我总结"
            ),
        )
        history = format_history_for_agent(
            [
                {
                    "role": "user",
                    "content": "@小项 你和 @袭人 还有 @小布 接力讨论后给我总结",
                },
                {
                    "role": "assistant",
                    "content": "@袭人 请从风险角度补两条，@小布 请从交付角度补两条，等你们回完我再给用户最终总结。",
                    "metadata": {
                        "agent_id": "alpha",
                        "agent_name": "小项 🐎",
                        "source": "user",
                        "target": "alpha",
                        "target_name": "小项 🐎",
                    },
                },
                {
                    "role": "assistant",
                    "content": "风险上主要是需求不稳定和回款周期。@小项 你来给用户总结。",
                    "metadata": {
                        "agent_id": "beta",
                        "agent_name": "袭人",
                        "source": "alpha",
                        "source_name": "小项 🐎",
                        "target": "alpha",
                        "target_name": "小项 🐎",
                    },
                },
                {
                    "role": "assistant",
                    "content": "交付上建议先做模板化服务，@小项 最后收口。",
                    "metadata": {
                        "agent_id": "gamma",
                        "agent_name": "小布",
                        "source": "alpha",
                        "source_name": "小项 🐎",
                        "target": "alpha",
                        "target_name": "小项 🐎",
                    },
                },
            ],
            target_agent_id="alpha",
            target_agent_name="小项 🐎",
            conversation_ctx=conversation_ctx,
            is_group_chat=True,
        )

        self.assertEqual([item["role"] for item in history], ["assistant", "assistant"])
        combined = "\n".join(item["content"] for item in history)
        self.assertNotIn("@小项", combined)
        self.assertNotIn("@袭人", combined)
        self.assertNotIn("@小布", combined)
        self.assertNotIn("给用户总结", combined)
        self.assertNotIn("最终总结", combined)
        self.assertIn("风险上主要是需求不稳定和回款周期。", combined)
        self.assertIn("交付上建议先做模板化服务，", combined)

    async def test_group_chat_agent_mention_is_processed_once(self):
        fake_agent_manager = FakeAgentManager()
        fake_workspace_manager = FakeWorkspaceManager()
        loop_calls: list[dict] = []
        outputs = {
            "alpha": "Alpha 响应并提到 @Beta",
            "beta": "Beta 已收到 Alpha 的消息",
        }

        loops = {
            agent_id: FakeAgentLoop(agent_id, outputs, loop_calls)
            for agent_id in outputs
        }

        async def fake_get_agent_loop_with_session_manager(agent_id, session_manager):
            return loops[agent_id]

        with tempfile.TemporaryDirectory() as tmpdir:
            session_manager = SessionManager(workspace=Path(tmpdir))
            request = StreamRequest(
                content="@Alpha 请开始讨论",
                session_key="web:test_group_chat_once",
                group_chat=True,
                mentioned_agents=["alpha"],
                conversation_id="test_group_chat_once",
                conversation_type="team",
            )

            with (
                patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager),
                patch("horbot.workspace.manager.get_workspace_manager", return_value=fake_workspace_manager),
                patch("horbot.web.api.get_session_manager", return_value=session_manager),
                patch(
                    "horbot.web.api.get_agent_loop_with_session_manager",
                    side_effect=fake_get_agent_loop_with_session_manager,
                ),
            ):
                raw_events = [
                    item
                    async for item in _group_chat_stream_generator(request, "req-group-chat-once")
                ]

            events = _decode_sse(raw_events)

            agent_start_events = [e for e in events if e["event"] == "agent_start"]
            self.assertEqual([e["agent_id"] for e in agent_start_events], ["alpha", "beta"])

            mentioned_events = [e for e in events if e["event"] == "agent_mentioned"]
            self.assertEqual(len(mentioned_events), 1)
            self.assertEqual(mentioned_events[0]["agent_id"], "beta")
            self.assertEqual(mentioned_events[0]["mentioned_by"], "alpha")

            agent_done_events = [e for e in events if e["event"] == "agent_done"]
            self.assertEqual([e["agent_id"] for e in agent_done_events], ["alpha", "beta"])
            for event in agent_done_events:
                self.assertTrue(event["turn_id"])
                self.assertTrue(event["message_id"])

            done_event = events[-1]
            self.assertEqual(done_event["event"], "done")
            self.assertEqual(done_event["total_agents"], 2)

            self.assertEqual(
                loop_calls,
                [
                    {
                        "agent_id": "alpha",
                        "content": "@Alpha 请开始讨论",
                        "speaking_to": "用户",
                        "conversation_type": "user_to_agent",
                    },
                    {
                        "agent_id": "beta",
                        "content": "Alpha 响应并提到 @Beta",
                        "speaking_to": "Alpha",
                        "conversation_type": "agent_to_agent",
                    },
                ],
            )

            session = session_manager.get_or_create("web:test_group_chat_once")
            assistant_messages = [msg for msg in session.messages if msg.get("role") == "assistant"]
            self.assertEqual(len(assistant_messages), 2)
            self.assertEqual(
                [msg["metadata"]["agent_id"] for msg in assistant_messages],
                ["alpha", "beta"],
            )

    async def test_group_chat_passes_extracted_payload_to_mentioned_agent(self):
        fake_agent_manager = FakeAgentManager()
        fake_workspace_manager = FakeWorkspaceManager()
        loop_calls: list[dict] = []
        outputs = {
            "alpha": "@Beta 请只回复自己的名字，不要添加任何其他内容",
            "beta": "Beta",
        }

        loops = {
            agent_id: FakeAgentLoop(agent_id, outputs, loop_calls)
            for agent_id in outputs
        }

        async def fake_get_agent_loop_with_session_manager(agent_id, session_manager):
            return loops[agent_id]

        with tempfile.TemporaryDirectory() as tmpdir:
            session_manager = SessionManager(workspace=Path(tmpdir))
            request = StreamRequest(
                content="请先联系 Beta",
                session_key="web:test_group_chat_payload",
                group_chat=True,
                mentioned_agents=["alpha"],
                conversation_id="test_group_chat_payload",
                conversation_type="team",
            )

            with (
                patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager),
                patch("horbot.workspace.manager.get_workspace_manager", return_value=fake_workspace_manager),
                patch("horbot.web.api.get_session_manager", return_value=session_manager),
                patch(
                    "horbot.web.api.get_agent_loop_with_session_manager",
                    side_effect=fake_get_agent_loop_with_session_manager,
                ),
            ):
                raw_events = [
                    item
                    async for item in _group_chat_stream_generator(request, "req-group-chat-payload")
                ]

            events = _decode_sse(raw_events)
            agent_done_events = [e for e in events if e["event"] == "agent_done"]
            self.assertEqual([e["content"] for e in agent_done_events], [outputs["alpha"], outputs["beta"]])
            self.assertEqual(loop_calls[1]["agent_id"], "beta")
            self.assertEqual(loop_calls[1]["content"], "请只回复自己的名字，不要添加任何其他内容")

    async def test_group_chat_requeues_previously_processed_agent(self):
        fake_agent_manager = FakeAgentManager()
        fake_workspace_manager = FakeWorkspaceManager()
        loop_calls: list[dict] = []
        outputs = {
            "alpha": ["@Beta 接力第一跳", "接力第二跳"],
            "beta": "@Alpha 接力回给你",
        }

        loops = {
            agent_id: FakeAgentLoop(agent_id, outputs, loop_calls)
            for agent_id in outputs
        }

        async def fake_get_agent_loop_with_session_manager(agent_id, session_manager):
            return loops[agent_id]

        with tempfile.TemporaryDirectory() as tmpdir:
            session_manager = SessionManager(workspace=Path(tmpdir))
            request = StreamRequest(
                content="请开始接力",
                session_key="web:test_group_chat_requeue",
                group_chat=True,
                mentioned_agents=["alpha"],
                conversation_id="test_group_chat_requeue",
                conversation_type="team",
            )

            with (
                patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager),
                patch("horbot.workspace.manager.get_workspace_manager", return_value=fake_workspace_manager),
                patch("horbot.web.api.get_session_manager", return_value=session_manager),
                patch(
                    "horbot.web.api.get_agent_loop_with_session_manager",
                    side_effect=fake_get_agent_loop_with_session_manager,
                ),
            ):
                raw_events = [
                    item
                    async for item in _group_chat_stream_generator(request, "req-group-chat-requeue")
                ]

            events = _decode_sse(raw_events)
            agent_start_events = [e for e in events if e["event"] == "agent_start"]
            self.assertEqual([e["agent_id"] for e in agent_start_events], ["alpha", "beta", "alpha"])

            agent_done_events = [e for e in events if e["event"] == "agent_done"]
            self.assertEqual(
                [(e["agent_id"], e["content"]) for e in agent_done_events],
                [
                    ("alpha", "@Beta 接力第一跳"),
                    ("beta", "@Alpha 接力回给你"),
                    ("alpha", "接力第二跳"),
                ],
            )
            self.assertEqual(
                [call["agent_id"] for call in loop_calls],
                ["alpha", "beta", "alpha"],
            )

    async def test_group_chat_continues_inline_relay_from_message_tool_targets(self):
        fake_agent_manager = FakeAgentManager()
        fake_workspace_manager = FakeWorkspaceManager()
        loop_calls: list[dict] = []

        loops = {
            "alpha": FakeMessageToolRelayLoop(
                "alpha",
                "我先把这个问题交给下一位继续拆解。",
                ["beta"],
                loop_calls,
            ),
            "beta": FakeAgentLoop("beta", {"beta": "Beta 已接棒并给出结论"}, loop_calls),
        }

        async def fake_get_agent_loop_with_session_manager(agent_id, session_manager):
            return loops[agent_id]

        with tempfile.TemporaryDirectory() as tmpdir:
            session_manager = SessionManager(workspace=Path(tmpdir))
            request = StreamRequest(
                content="请开始接力",
                session_key="web:team_team-001",
                group_chat=True,
                team_id="team-001",
                mentioned_agents=["alpha"],
                conversation_id="team_team-001",
                conversation_type="team",
            )

            fake_team_manager = FakeTeamManager({
                "team-001": FakeTeam("team-001", ["alpha", "beta"]),
            })

            with (
                patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager),
                patch("horbot.workspace.manager.get_workspace_manager", return_value=fake_workspace_manager),
                patch("horbot.team.manager.get_team_manager", return_value=fake_team_manager),
                patch("horbot.web.api.get_session_manager", return_value=session_manager),
                patch(
                    "horbot.web.api.get_agent_loop_with_session_manager",
                    side_effect=fake_get_agent_loop_with_session_manager,
                ),
            ):
                raw_events = [
                    item
                    async for item in _group_chat_stream_generator(request, "req-group-chat-message-tool-relay")
                ]

        events = _decode_sse(raw_events)
        agent_done_events = [event for event in events if event["event"] == "agent_done"]
        self.assertEqual(
            [(event["agent_id"], event["content"]) for event in agent_done_events],
            [
                ("alpha", "我先把这个问题交给下一位继续拆解。"),
                ("beta", "Beta 已接棒并给出结论"),
            ],
        )
        self.assertEqual([call["agent_id"] for call in loop_calls], ["alpha", "beta"])

    async def test_group_chat_auto_returns_to_originator_after_agent_reply(self):
        fake_agent_manager = FakeAgentManager()
        fake_workspace_manager = FakeWorkspaceManager()
        loop_calls: list[dict] = []
        outputs = {
            "alpha": ["@Beta 请你先从风险角度拆一下，等你拆完我来总结。", "我结合 Beta 的意见，给出最终总结。"],
            "beta": "我认为最大风险在于非标交付和回款周期。",
        }

        loops = {
            agent_id: FakeAgentLoop(agent_id, outputs, loop_calls)
            for agent_id in outputs
        }

        async def fake_get_agent_loop_with_session_manager(agent_id, session_manager):
            return loops[agent_id]

        with tempfile.TemporaryDirectory() as tmpdir:
            session_manager = SessionManager(workspace=Path(tmpdir))
            request = StreamRequest(
                content="请开始讨论并最后总结",
                session_key="web:team_team-001",
                group_chat=True,
                team_id="team-001",
                mentioned_agents=["alpha"],
                conversation_id="team_team-001",
                conversation_type="team",
            )

            fake_team_manager = FakeTeamManager({
                "team-001": FakeTeam("team-001", ["alpha", "beta"]),
            })

            with (
                patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager),
                patch("horbot.workspace.manager.get_workspace_manager", return_value=fake_workspace_manager),
                patch("horbot.team.manager.get_team_manager", return_value=fake_team_manager),
                patch("horbot.web.api.get_session_manager", return_value=session_manager),
                patch(
                    "horbot.web.api.get_agent_loop_with_session_manager",
                    side_effect=fake_get_agent_loop_with_session_manager,
                ),
            ):
                raw_events = [
                    item
                    async for item in _group_chat_stream_generator(request, "req-group-chat-auto-return")
                ]

        events = _decode_sse(raw_events)
        agent_done_events = [event for event in events if event["event"] == "agent_done"]
        self.assertEqual(
            [(event["agent_id"], event["content"]) for event in agent_done_events],
            [
                ("alpha", "@Beta 请你先从风险角度拆一下，等你拆完我来总结。"),
                ("beta", "我认为最大风险在于非标交付和回款周期。"),
                ("alpha", "我结合 Beta 的意见，给出最终总结。"),
            ],
        )
        self.assertEqual([call["agent_id"] for call in loop_calls], ["alpha", "beta", "alpha"])
        self.assertIn("请基于当前团队对话历史", loop_calls[2]["content"])
        self.assertIn("原始用户问题：请开始讨论并最后总结", loop_calls[2]["content"])
        self.assertEqual(loop_calls[2]["speaking_to"], "用户")
        self.assertEqual(loop_calls[2]["conversation_type"], "user_to_agent")

    async def test_group_chat_preserves_pending_context_for_parallel_handoffs(self):
        fake_agent_manager = FlexibleFakeAgentManager(
            {
                "alpha": FakeAgent("alpha", "Alpha", is_main=True),
                "beta": FakeAgent("beta", "Beta"),
                "gamma": FakeAgent("gamma", "Gamma"),
            },
            main_agent_id="alpha",
        )
        fake_workspace_manager = FakeWorkspaceManager()
        loop_calls: list[dict] = []
        alpha_first = "@Beta 请你从市场角度补两条，@Gamma 请你从技术落地角度补两条，等你们都补完我再给用户最终总结。"
        alpha_final = "最终总结给用户：先服务切入验证需求，再把高频稳定环节产品化。"
        beta_reply = "@Gamma 你继续补技术落地细节。@Alpha 等 Gamma 回完你再给用户总结。"
        gamma_reply = "@Alpha 我补完技术落地建议了，你现在可以给用户最终总结。"
        outputs = {
            "alpha": [
                alpha_first,
                alpha_final,
            ],
            "beta": beta_reply,
            "gamma": gamma_reply,
        }

        loops = {
            agent_id: FakeAgentLoop(agent_id, outputs, loop_calls)
            for agent_id in outputs
        }

        async def fake_get_agent_loop_with_session_manager(agent_id, session_manager):
            return loops[agent_id]

        with tempfile.TemporaryDirectory() as tmpdir:
            session_manager = SessionManager(workspace=Path(tmpdir))
            request = StreamRequest(
                content="请三人接力后再总结",
                session_key="web:team_team-001",
                group_chat=True,
                team_id="team-001",
                mentioned_agents=["alpha"],
                conversation_id="team_team-001",
                conversation_type="team",
            )

            fake_team_manager = FakeTeamManager({
                "team-001": FakeTeam("team-001", ["alpha", "beta", "gamma"]),
            })

            with (
                patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager),
                patch("horbot.workspace.manager.get_workspace_manager", return_value=fake_workspace_manager),
                patch("horbot.team.manager.get_team_manager", return_value=fake_team_manager),
                patch("horbot.web.api.get_session_manager", return_value=session_manager),
                patch(
                    "horbot.web.api.get_agent_loop_with_session_manager",
                    side_effect=fake_get_agent_loop_with_session_manager,
                ),
            ):
                raw_events = [
                    item
                    async for item in _group_chat_stream_generator(request, "req-group-chat-preserve-pending-context")
                ]

        events = _decode_sse(raw_events)
        agent_done_events = [event for event in events if event["event"] == "agent_done"]
        self.assertEqual(
            [(event["agent_id"], event["content"]) for event in agent_done_events],
            [
                ("alpha", alpha_first),
                ("beta", beta_reply),
                ("gamma", gamma_reply),
                ("alpha", alpha_final),
            ],
        )
        self.assertEqual([call["agent_id"] for call in loop_calls], ["alpha", "beta", "gamma", "alpha"])
        self.assertEqual(loop_calls[2]["speaking_to"], "Alpha")
        self.assertEqual(loop_calls[2]["conversation_type"], "agent_to_agent")
        self.assertIn("请你从技术落地角度补两条", loop_calls[2]["content"])
        self.assertNotIn("继续补技术落地细节", loop_calls[2]["content"])
        self.assertEqual(loop_calls[3]["speaking_to"], "用户")
        self.assertEqual(loop_calls[3]["conversation_type"], "user_to_agent")
        self.assertIn("请基于当前团队对话历史", loop_calls[3]["content"])

    async def test_group_chat_summary_turn_does_not_loop_on_plaintext_mentions(self):
        fake_agent_manager = FakeAgentManager()
        fake_workspace_manager = FakeWorkspaceManager()
        loop_calls: list[dict] = []
        outputs = {
            "alpha": [
                "@Beta 请你先从风险角度拆一下，等你拆完我来总结。",
                "我结合 @Beta 的意见，给出最终总结。",
            ],
            "beta": "@Alpha 风险部分我补完了，你来收尾。",
        }

        loops = {
            agent_id: FakeAgentLoop(agent_id, outputs, loop_calls)
            for agent_id in outputs
        }

        async def fake_get_agent_loop_with_session_manager(agent_id, session_manager):
            return loops[agent_id]

        with tempfile.TemporaryDirectory() as tmpdir:
            session_manager = SessionManager(workspace=Path(tmpdir))
            request = StreamRequest(
                content="请开始讨论并最后总结",
                session_key="web:team_team-001",
                group_chat=True,
                team_id="team-001",
                mentioned_agents=["alpha"],
                conversation_id="team_team-001",
                conversation_type="team",
            )

            fake_team_manager = FakeTeamManager({
                "team-001": FakeTeam("team-001", ["alpha", "beta"]),
            })

            with (
                patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager),
                patch("horbot.workspace.manager.get_workspace_manager", return_value=fake_workspace_manager),
                patch("horbot.team.manager.get_team_manager", return_value=fake_team_manager),
                patch("horbot.web.api.get_session_manager", return_value=session_manager),
                patch(
                    "horbot.web.api.get_agent_loop_with_session_manager",
                    side_effect=fake_get_agent_loop_with_session_manager,
                ),
            ):
                raw_events = [
                    item
                    async for item in _group_chat_stream_generator(request, "req-group-chat-summary-no-loop")
                ]

        events = _decode_sse(raw_events)
        agent_done_events = [event for event in events if event["event"] == "agent_done"]
        self.assertEqual(
            [(event["agent_id"], event["content"]) for event in agent_done_events],
            [
                ("alpha", "@Beta 请你先从风险角度拆一下，等你拆完我来总结。"),
                ("beta", "@Alpha 风险部分我补完了，你来收尾。"),
                ("alpha", "我结合 @Beta 的意见，给出最终总结。"),
            ],
        )
        self.assertEqual([call["agent_id"] for call in loop_calls], ["alpha", "beta", "alpha"])

    async def test_group_chat_keeps_agent_to_agent_context_for_deep_discussion_without_summary_intent(self):
        fake_agent_manager = FakeAgentManager()
        fake_workspace_manager = FakeWorkspaceManager()
        loop_calls: list[dict] = []
        outputs = {
            "alpha": [
                "@Beta 你先补风险，我再继续推演成本与获客验证，不要急着总结。",
                "我继续第二轮分析：当前更像是验证阶段，@Beta 你再补一轮交付和回款节奏。",
            ],
            "beta": [
                "@Alpha 我先补完第一轮风险，你继续从成本和获客验证角度往下推演，不要急着总结。",
                "第二轮风险补充：真正的瓶颈还是交付边界和回款速度。",
            ],
        }

        loops = {
            agent_id: FakeAgentLoop(agent_id, outputs, loop_calls)
            for agent_id in outputs
        }

        async def fake_get_agent_loop_with_session_manager(agent_id, session_manager):
            return loops[agent_id]

        with tempfile.TemporaryDirectory() as tmpdir:
            session_manager = SessionManager(workspace=Path(tmpdir))
            request = StreamRequest(
                content="请深度讨论后再决定是否总结",
                session_key="web:team_team-001",
                group_chat=True,
                team_id="team-001",
                mentioned_agents=["alpha"],
                conversation_id="team_team-001",
                conversation_type="team",
            )

            fake_team_manager = FakeTeamManager({
                "team-001": FakeTeam("team-001", ["alpha", "beta"]),
            })

            with (
                patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager),
                patch("horbot.workspace.manager.get_workspace_manager", return_value=fake_workspace_manager),
                patch("horbot.team.manager.get_team_manager", return_value=fake_team_manager),
                patch("horbot.web.api.get_session_manager", return_value=session_manager),
                patch(
                    "horbot.web.api.get_agent_loop_with_session_manager",
                    side_effect=fake_get_agent_loop_with_session_manager,
                ),
            ):
                raw_events = [
                    item
                    async for item in _group_chat_stream_generator(request, "req-group-chat-deep-discussion")
                ]

        events = _decode_sse(raw_events)
        agent_done_events = [event for event in events if event["event"] == "agent_done"]
        self.assertEqual(
            [(event["agent_id"], event["content"]) for event in agent_done_events],
            [
                ("alpha", "@Beta 你先补风险，我再继续推演成本与获客验证，不要急着总结。"),
                ("beta", "@Alpha 我先补完第一轮风险，你继续从成本和获客验证角度往下推演，不要急着总结。"),
                ("alpha", "我继续第二轮分析：当前更像是验证阶段，@Beta 你再补一轮交付和回款节奏。"),
                ("beta", "第二轮风险补充：真正的瓶颈还是交付边界和回款速度。"),
            ],
        )
        self.assertEqual([call["agent_id"] for call in loop_calls], ["alpha", "beta", "alpha", "beta"])
        self.assertEqual(loop_calls[2]["conversation_type"], "agent_to_agent")
        self.assertEqual(loop_calls[2]["speaking_to"], "Beta")
        self.assertIn("继续从成本和获客验证角度往下推演", loop_calls[2]["content"])
        self.assertNotIn("请基于当前团队对话历史", loop_calls[2]["content"])

    async def test_group_chat_does_not_switch_to_user_summary_only_because_teammate_requests_summary(self):
        fake_agent_manager = FakeAgentManager()
        fake_workspace_manager = FakeWorkspaceManager()
        loop_calls: list[dict] = []
        outputs = {
            "alpha": [
                "@Beta 你先补风险，补完后我们继续往下讨论，还不要总结。",
                "我先回应你的风险点，再继续深挖范围和交付边界。",
            ],
            "beta": "@Alpha 我这边风险先补完了，你来总结给用户。",
        }

        loops = {
            agent_id: FakeAgentLoop(agent_id, outputs, loop_calls)
            for agent_id in outputs
        }

        async def fake_get_agent_loop_with_session_manager(agent_id, session_manager):
            return loops[agent_id]

        with tempfile.TemporaryDirectory() as tmpdir:
            session_manager = SessionManager(workspace=Path(tmpdir))
            request = StreamRequest(
                content="请你们先深聊，不要太快总结",
                session_key="web:team_team-001",
                group_chat=True,
                team_id="team-001",
                mentioned_agents=["alpha"],
                conversation_id="team_team-001",
                conversation_type="team",
            )

            fake_team_manager = FakeTeamManager({
                "team-001": FakeTeam("team-001", ["alpha", "beta"]),
            })

            with (
                patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager),
                patch("horbot.workspace.manager.get_workspace_manager", return_value=fake_workspace_manager),
                patch("horbot.team.manager.get_team_manager", return_value=fake_team_manager),
                patch("horbot.web.api.get_session_manager", return_value=session_manager),
                patch(
                    "horbot.web.api.get_agent_loop_with_session_manager",
                    side_effect=fake_get_agent_loop_with_session_manager,
                ),
            ):
                raw_events = [
                    item
                    async for item in _group_chat_stream_generator(request, "req-group-chat-originator-controls-summary")
                ]

        events = _decode_sse(raw_events)
        agent_done_events = [event for event in events if event["event"] == "agent_done"]
        self.assertEqual(
            [(event["agent_id"], event["content"]) for event in agent_done_events],
            [
                ("alpha", "@Beta 你先补风险，补完后我们继续往下讨论，还不要总结。"),
                ("beta", "@Alpha 我这边风险先补完了，你来总结给用户。"),
                ("alpha", "我先回应你的风险点，再继续深挖范围和交付边界。"),
            ],
        )
        self.assertEqual([call["agent_id"] for call in loop_calls], ["alpha", "beta", "alpha"])
        self.assertEqual(loop_calls[2]["conversation_type"], "agent_to_agent")
        self.assertEqual(loop_calls[2]["speaking_to"], "Beta")
        self.assertNotIn("请基于当前团队对话历史", loop_calls[2]["content"])

    async def test_group_chat_auto_returns_to_originator_for_second_round_discussion_when_originator_requested_continue(self):
        fake_agent_manager = FakeAgentManager()
        fake_workspace_manager = FakeWorkspaceManager()
        loop_calls: list[dict] = []
        outputs = {
            "alpha": [
                "@Beta 你先补风险，等你补完后我继续第二轮分析，不要急着总结。",
                "我接着第二轮讨论：先把交付边界和验证顺序再压缩一下。",
            ],
            "beta": "我先补风险：最大的变量在交付失控和回款延迟。",
        }

        loops = {
            agent_id: FakeAgentLoop(agent_id, outputs, loop_calls)
            for agent_id in outputs
        }

        async def fake_get_agent_loop_with_session_manager(agent_id, session_manager):
            return loops[agent_id]

        with tempfile.TemporaryDirectory() as tmpdir:
            session_manager = SessionManager(workspace=Path(tmpdir))
            request = StreamRequest(
                content="请先深聊两轮，再决定怎么收口",
                session_key="web:team_team-001",
                group_chat=True,
                team_id="team-001",
                mentioned_agents=["alpha"],
                conversation_id="team_team-001",
                conversation_type="team",
            )

            fake_team_manager = FakeTeamManager({
                "team-001": FakeTeam("team-001", ["alpha", "beta"]),
            })

            with (
                patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager),
                patch("horbot.workspace.manager.get_workspace_manager", return_value=fake_workspace_manager),
                patch("horbot.team.manager.get_team_manager", return_value=fake_team_manager),
                patch("horbot.web.api.get_session_manager", return_value=session_manager),
                patch(
                    "horbot.web.api.get_agent_loop_with_session_manager",
                    side_effect=fake_get_agent_loop_with_session_manager,
                ),
            ):
                raw_events = [
                    item
                    async for item in _group_chat_stream_generator(request, "req-group-chat-originator-continue-mode")
                ]

        events = _decode_sse(raw_events)
        agent_done_events = [event for event in events if event["event"] == "agent_done"]
        self.assertEqual(
            [(event["agent_id"], event["content"]) for event in agent_done_events],
            [
                ("alpha", "@Beta 你先补风险，等你补完后我继续第二轮分析，不要急着总结。"),
                ("beta", "我先补风险：最大的变量在交付失控和回款延迟。"),
                ("alpha", "我接着第二轮讨论：先把交付边界和验证顺序再压缩一下。"),
            ],
        )
        self.assertEqual([call["agent_id"] for call in loop_calls], ["alpha", "beta", "alpha"])
        self.assertEqual(loop_calls[2]["conversation_type"], "agent_to_agent")
        self.assertEqual(loop_calls[2]["speaking_to"], "Beta")
        self.assertIn("我先补风险", loop_calls[2]["content"])
        self.assertNotIn("请基于当前团队对话历史", loop_calls[2]["content"])

    async def test_group_chat_sanitizes_agent_error_message(self):
        fake_agent_manager = FakeAgentManager()
        fake_workspace_manager = FakeWorkspaceManager()
        failing_error = Exception(
            "Error calling LLM: litellm.InternalServerError: Invalid response object "
            "Traceback ... received_args={'response_object': {'choices': None}}"
        )

        async def fake_get_agent_loop_with_session_manager(agent_id, session_manager):
            return FailingAgentLoop(failing_error)

        with tempfile.TemporaryDirectory() as tmpdir:
            session_manager = SessionManager(workspace=Path(tmpdir))
            request = StreamRequest(
                content="@Alpha 请开始讨论",
                session_key="web:test_group_chat_error",
                group_chat=True,
                mentioned_agents=["alpha"],
                conversation_id="test_group_chat_error",
                conversation_type="team",
            )

            with (
                patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager),
                patch("horbot.workspace.manager.get_workspace_manager", return_value=fake_workspace_manager),
                patch("horbot.web.api.get_session_manager", return_value=session_manager),
                patch(
                    "horbot.web.api.get_agent_loop_with_session_manager",
                    side_effect=fake_get_agent_loop_with_session_manager,
                ),
            ):
                raw_events = [
                    item
                    async for item in _group_chat_stream_generator(request, "req-group-chat-error")
                ]

        events = _decode_sse(raw_events)
        agent_error_events = [e for e in events if e["event"] == "agent_error"]
        self.assertEqual(len(agent_error_events), 1)
        self.assertEqual(agent_error_events[0]["agent_id"], "alpha")
        self.assertEqual(agent_error_events[0]["error"], "模型服务返回异常，请稍后重试。")
        self.assertEqual(agent_error_events[0]["content"], "模型服务返回异常，请稍后重试。")

    async def test_group_chat_registers_stream_and_honors_stop_flag(self):
        fake_agent_manager = FakeAgentManager()
        fake_workspace_manager = FakeWorkspaceManager()
        fake_stream_manager = FakeStreamManager(stop_after_register=True)
        loop_calls: list[dict] = []
        outputs = {"alpha": "Alpha 不应真正执行"}

        loops = {
            agent_id: FakeAgentLoop(agent_id, outputs, loop_calls)
            for agent_id in outputs
        }

        async def fake_get_agent_loop_with_session_manager(agent_id, session_manager):
            return loops[agent_id]

        with tempfile.TemporaryDirectory() as tmpdir:
            session_manager = SessionManager(workspace=Path(tmpdir))
            request = StreamRequest(
                content="@Alpha 请开始讨论",
                session_key="web:test_group_chat_stop",
                group_chat=True,
                mentioned_agents=["alpha"],
                conversation_id="test_group_chat_stop",
                conversation_type="team",
            )

            with (
                patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager),
                patch("horbot.workspace.manager.get_workspace_manager", return_value=fake_workspace_manager),
                patch("horbot.web.api.get_session_manager", return_value=session_manager),
                patch("horbot.web.api.get_stream_manager", return_value=fake_stream_manager),
                patch(
                    "horbot.web.api.get_agent_loop_with_session_manager",
                    side_effect=fake_get_agent_loop_with_session_manager,
                ),
            ):
                raw_events = [
                    item
                    async for item in _group_chat_stream_generator(request, "req-group-chat-stop")
                ]

        events = _decode_sse(raw_events)
        self.assertEqual(fake_stream_manager.registered_request_ids, ["req-group-chat-stop"])
        self.assertEqual(fake_stream_manager.unregistered_request_ids, ["req-group-chat-stop"])
        self.assertEqual(events[0]["event"], "stopped")
        self.assertEqual(events[0]["content"], "Generation stopped by user")
        self.assertEqual(loop_calls, [])

    def test_validate_chat_request_rejects_non_member_mention_for_team_chat(self):
        fake_agent_manager = SimpleNamespace(
            get_agent=lambda agent_id: {
                "alpha": FakeAgent("alpha", "Alpha", is_main=True),
                "beta": FakeAgent("beta", "Beta"),
                "gamma": FakeAgent("gamma", "Gamma"),
            }.get(agent_id),
        )
        fake_team_manager = FakeTeamManager({
            "team-1": FakeTeam("team-1", ["alpha", "beta"]),
        })
        request = StreamRequest(
            content="@Gamma 请加入",
            session_key="web:test_group_chat_invalid_mention",
            group_chat=True,
            team_id="team-1",
            mentioned_agents=["gamma"],
            conversation_id="test_group_chat_invalid_mention",
            conversation_type="team",
        )

        with (
            patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager),
            patch("horbot.team.manager.get_team_manager", return_value=fake_team_manager),
            patch("horbot.web.api.get_cached_config", return_value=SimpleNamespace(get_provider=lambda: SimpleNamespace(api_key="test-key"))),
        ):
            with self.assertRaisesRegex(Exception, "not a member of team"):
                _validate_chat_request(request)

    async def test_group_chat_does_not_dispatch_to_non_member_agent_mentions(self):
        fake_workspace_manager = FakeWorkspaceManager()
        loop_calls: list[dict] = []
        outputs = {
            "alpha": "@Gamma 不应该被拉进来",
            "beta": "Beta 不应触发",
            "gamma": "Gamma 不应触发",
        }

        class ScopedAgentManager(FakeAgentManager):
            def __init__(self):
                super().__init__()
                self.agents["gamma"] = FakeAgent("gamma", "Gamma")

        fake_agent_manager = ScopedAgentManager()
        fake_team_manager = FakeTeamManager({
            "team-1": FakeTeam("team-1", ["alpha", "beta"]),
        })

        loops = {
            agent_id: FakeAgentLoop(agent_id, outputs, loop_calls)
            for agent_id in outputs
        }

        async def fake_get_agent_loop_with_session_manager(agent_id, session_manager):
            return loops[agent_id]

        with tempfile.TemporaryDirectory() as tmpdir:
            session_manager = SessionManager(workspace=Path(tmpdir))
            request = StreamRequest(
                content="@Alpha 请开始讨论",
                session_key="web:test_group_chat_scope_mentions",
                group_chat=True,
                team_id="team-1",
                mentioned_agents=["alpha"],
                conversation_id="test_group_chat_scope_mentions",
                conversation_type="team",
            )

            with (
                patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager),
                patch("horbot.team.manager.get_team_manager", return_value=fake_team_manager),
                patch("horbot.workspace.manager.get_workspace_manager", return_value=fake_workspace_manager),
                patch("horbot.web.api.get_session_manager", return_value=session_manager),
                patch(
                    "horbot.web.api.get_agent_loop_with_session_manager",
                    side_effect=fake_get_agent_loop_with_session_manager,
                ),
            ):
                raw_events = [
                    item
                    async for item in _group_chat_stream_generator(request, "req-group-chat-scope-mentions")
                ]

        events = _decode_sse(raw_events)
        agent_start_events = [e for e in events if e["event"] == "agent_start"]
        self.assertEqual([e["agent_id"] for e in agent_start_events], ["alpha"])
        self.assertEqual([call["agent_id"] for call in loop_calls], ["alpha"])


if __name__ == "__main__":
    unittest.main()
