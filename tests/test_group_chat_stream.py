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


class FakeWorkspaceManager:
    def get_team_workspace(self, team_id: str):
        return None


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


if __name__ == "__main__":
    unittest.main()
