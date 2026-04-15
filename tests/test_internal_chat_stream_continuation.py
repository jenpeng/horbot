import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from horbot.agent.loop import AgentLoop
from horbot.bus.queue import MessageBus
from horbot.config.schema import Config
from horbot.providers.base import LLMProvider, LLMResponse
from horbot.session.manager import SessionManager
from horbot.web.api import StreamRequest, _stream_generator


def _decode_sse_events(chunks: list[str]) -> list[dict]:
    events: list[dict] = []
    for chunk in chunks:
        payload = chunk.strip()
        if not payload.startswith("data: "):
            continue
        events.append(json.loads(payload[6:]))
    return events


class FakeStreamManager:
    def __init__(self) -> None:
        self.registered_request_ids: list[str] = []
        self.cleaned_request_ids: list[str] = []

    async def register(self, request_id: str, task) -> None:
        self.registered_request_ids.append(request_id)

    def should_stop(self, request_id: str) -> bool:
        return False

    async def cleanup_task(self, request_id: str, task) -> None:
        self.cleaned_request_ids.append(request_id)


class LengthContinuationProvider(LLMProvider):
    def __init__(self) -> None:
        super().__init__(api_key="stub", api_base="stub://length-stream")
        self.calls = 0

    async def chat(self, messages, on_content_delta=None, **kwargs):
        self.calls += 1
        if self.calls == 1:
            if on_content_delta:
                await on_content_delta("第一段")
            return LLMResponse(content="第一段", finish_reason="length")

        if on_content_delta:
            await on_content_delta("第二段")
        return LLMResponse(content="第二段", finish_reason="stop")

    def get_default_model(self) -> str:
        return "stub-model"


class InternalChatStreamContinuationTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_chat_stream_auto_continues_length_truncated_response(self):
        provider = LengthContinuationProvider()
        config = Config()
        config.agents.defaults.context_compact.max_tokens = 4000
        fake_stream_manager = FakeStreamManager()

        with tempfile.TemporaryDirectory() as tempdir:
            workspace = Path(tempdir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            sessions = SessionManager(workspace=Path(tempdir) / "sessions")
            fake_agent = SimpleNamespace(
                id="main",
                name="小项 🐎",
                is_main=True,
                get_workspace=lambda: workspace,
            )
            fake_agent_manager = SimpleNamespace(
                get_default_agent=lambda: fake_agent,
                get_agent=lambda agent_id: fake_agent if agent_id == "main" else None,
                get_all_agents=lambda: [fake_agent],
            )
            fake_external_agent_manager = SimpleNamespace(
                get_external_agent=lambda agent_id: None,
            )
            loop = AgentLoop(
                bus=MessageBus(),
                provider=provider,
                workspace=workspace,
                model="stub-model",
                max_iterations=config.agents.defaults.max_tool_iterations,
                temperature=config.agents.defaults.temperature,
                max_tokens=config.agents.defaults.max_tokens,
                memory_window=config.agents.defaults.memory_window,
                brave_api_key=config.tools.web.search.api_key,
                restrict_to_workspace=config.tools.restrict_to_workspace,
                mcp_servers={},
                channels_config=config.channels,
                exec_config=config.tools.exec,
                session_manager=sessions,
                use_hierarchical_context=False,
                enable_hot_reload=False,
                agent_id="main",
                agent_name="小项 🐎",
                team_ids=[],
            )
            loop._get_config = lambda: config

            request = StreamRequest(
                content="请给出完整结论",
                session_key="web:dm_main",
                agent_id="main",
            )

            with (
                patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager),
                patch("horbot.external_agents.manager.get_external_agent_manager", return_value=fake_external_agent_manager),
                patch("horbot.web.api.get_agent_loop", new=AsyncMock(return_value=loop)),
                patch("horbot.web.api.get_stream_manager", return_value=fake_stream_manager),
            ):
                chunks = [chunk async for chunk in _stream_generator(request, "req-auto-continue")]

            events = _decode_sse_events(chunks)
            progress_events = [event for event in events if event.get("event") == "progress" and not event.get("tool_hint")]
            agent_done_event = next(event for event in events if event.get("event") == "agent_done")
            content_event = next(event for event in events if event.get("event") == "content")

            self.assertGreaterEqual(len(progress_events), 2)
            self.assertEqual(progress_events[-1]["content"], "第一段第二段")
            self.assertEqual(agent_done_event["content"], "第一段第二段")
            self.assertEqual(content_event["content"], "第一段第二段")
            self.assertEqual(events[-1]["event"], "done")
            self.assertEqual(provider.calls, 2)
            self.assertEqual(fake_stream_manager.registered_request_ids, ["req-auto-continue"])
            self.assertEqual(fake_stream_manager.cleaned_request_ids, ["req-auto-continue"])

            session = sessions.get_or_create("web:dm_main")
            assistant_messages = [message for message in session.messages if message.get("role") == "assistant"]
            self.assertEqual(assistant_messages[-1]["content"], "第一段第二段")

    async def test_single_chat_stream_message_tool_media_is_exposed_as_files(self):
        config = Config()
        fake_stream_manager = FakeStreamManager()

        with tempfile.TemporaryDirectory() as tempdir:
            workspace = Path(tempdir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            sessions = SessionManager(workspace=Path(tempdir) / "sessions")
            image_path = workspace / "demo.png"
            image_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")

            fake_agent = SimpleNamespace(
                id="main",
                name="小项 🐎",
                is_main=True,
                get_workspace=lambda: workspace,
            )
            fake_agent_manager = SimpleNamespace(
                get_default_agent=lambda: fake_agent,
                get_agent=lambda agent_id: fake_agent if agent_id == "main" else None,
                get_all_agents=lambda: [fake_agent],
            )
            fake_external_agent_manager = SimpleNamespace(
                get_external_agent=lambda agent_id: None,
            )

            async def process_message(msg, **kwargs):
                on_tool_start = kwargs["on_tool_start"]
                await on_tool_start(
                    "message",
                    {
                        "content": "图发这里",
                        "media": [str(image_path)],
                    },
                )
                return SimpleNamespace(content="Message sent to web:dm_main", metadata={})

            fake_loop = SimpleNamespace(
                sessions=sessions,
                process_message=process_message,
            )

            imported_files = [
                {
                    "file_id": "file-1",
                    "filename": "file-1.png",
                    "original_name": "demo.png",
                    "mime_type": "image/png",
                    "size": 12,
                    "category": "image",
                    "url": "/api/files/file-1",
                    "preview_url": "/api/files/file-1/preview",
                }
            ]

            request = StreamRequest(
                content="把图发到当前聊天里",
                session_key="web:dm_main",
                agent_id="main",
            )

            with (
                patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager),
                patch("horbot.external_agents.manager.get_external_agent_manager", return_value=fake_external_agent_manager),
                patch("horbot.web.api.get_agent_loop", new=AsyncMock(return_value=fake_loop)),
                patch("horbot.web.api.get_stream_manager", return_value=fake_stream_manager),
                patch("horbot.web.api._import_local_media_files", return_value=imported_files),
            ):
                chunks = [chunk async for chunk in _stream_generator(request, "req-message-media")]

            events = _decode_sse_events(chunks)
            agent_done_event = next(event for event in events if event.get("event") == "agent_done")
            self.assertEqual(agent_done_event["content"], "图发这里")
            self.assertEqual(agent_done_event["files"], imported_files)

            session = sessions.get_or_create("web:dm_main")
            assistant_messages = [message for message in session.messages if message.get("role") == "assistant"]
            self.assertEqual(assistant_messages[-1]["files"], imported_files)

    async def test_single_chat_stream_remote_image_links_are_exposed_as_files(self):
        config = Config()
        fake_stream_manager = FakeStreamManager()

        with tempfile.TemporaryDirectory() as tempdir:
            workspace = Path(tempdir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            sessions = SessionManager(workspace=Path(tempdir) / "sessions")

            fake_agent = SimpleNamespace(
                id="main",
                name="小项 🐎",
                is_main=True,
                get_workspace=lambda: workspace,
            )
            fake_agent_manager = SimpleNamespace(
                get_default_agent=lambda: fake_agent,
                get_agent=lambda agent_id: fake_agent if agent_id == "main" else None,
                get_all_agents=lambda: [fake_agent],
            )
            fake_external_agent_manager = SimpleNamespace(
                get_external_agent=lambda agent_id: None,
            )
            remote_url = "https://image.pollinations.ai/prompt/pony?seed=1776249001"

            async def process_message(msg, **kwargs):
                on_tool_start = kwargs["on_tool_start"]
                await on_tool_start(
                    "message",
                    {
                        "content": f"彭老师，继续用“小马主题”给你生成了1张，见下图～\n\n1. {remote_url}",
                    },
                )
                return SimpleNamespace(content="Message sent to web:dm_main", metadata={})

            fake_loop = SimpleNamespace(
                sessions=sessions,
                process_message=process_message,
            )

            request = StreamRequest(
                content="继续用“小马主题”生成1张图片展示",
                session_key="web:dm_main",
                agent_id="main",
            )

            with (
                patch("horbot.agent.manager.get_agent_manager", return_value=fake_agent_manager),
                patch("horbot.external_agents.manager.get_external_agent_manager", return_value=fake_external_agent_manager),
                patch("horbot.web.api.get_agent_loop", new=AsyncMock(return_value=fake_loop)),
                patch("horbot.web.api.get_stream_manager", return_value=fake_stream_manager),
            ):
                chunks = [chunk async for chunk in _stream_generator(request, "req-remote-image-link")]

            events = _decode_sse_events(chunks)
            agent_done_event = next(event for event in events if event.get("event") == "agent_done")
            self.assertEqual(agent_done_event["content"], "彭老师，继续用“小马主题”给你生成了1张，见下图～")
            self.assertEqual(len(agent_done_event["files"]), 1)
            self.assertEqual(agent_done_event["files"][0]["preview_url"], remote_url)

            session = sessions.get_or_create("web:dm_main")
            assistant_messages = [message for message in session.messages if message.get("role") == "assistant"]
            self.assertEqual(assistant_messages[-1]["content"], "彭老师，继续用“小马主题”给你生成了1张，见下图～")
            self.assertEqual(assistant_messages[-1]["files"][0]["preview_url"], remote_url)
