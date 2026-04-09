import asyncio
import unittest

from horbot.web.api import (
    _build_chat_stream_event,
    _create_chat_stream_callbacks,
    _sse_event,
)


class FakeStreamManager:
    def __init__(self, should_stop: bool = False):
        self._should_stop = should_stop

    def should_stop(self, request_id: str) -> bool:
        return self._should_stop


class ChatStreamEventTests(unittest.TestCase):
    def test_build_chat_stream_event_includes_ids(self):
        event = _build_chat_stream_event(
            "progress",
            agent_id="main",
            agent_name="Main Agent",
            turn_id="turn-1",
            message_id="msg-1",
            content="hello",
            tool_hint=False,
        )

        self.assertEqual(
            event,
            {
                "event": "progress",
                "content": "hello",
                "tool_hint": False,
                "agent_id": "main",
                "agent_name": "Main Agent",
                "turn_id": "turn-1",
                "message_id": "msg-1",
            },
        )

    def test_sse_event_wraps_payload(self):
        payload = {"event": "heartbeat"}
        self.assertEqual(_sse_event(payload), 'data: {"event": "heartbeat"}\n\n')


class ChatStreamCallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_callbacks_emit_events_and_track_state(self):
        queue: asyncio.Queue = asyncio.Queue()
        execution_steps: list[dict] = []
        content_state = {"content": ""}
        message_tool_contents: list[str] = []

        def on_message_tool_content(content: str) -> None:
            message_tool_contents.append(content)
            content_state["content"] = content

        callbacks = _create_chat_stream_callbacks(
            queue=queue,
            stream_manager=FakeStreamManager(),
            request_id="req-1",
            agent_id="main",
            agent_name="Main Agent",
            turn_id="turn-1",
            message_id="msg-1",
            execution_steps=execution_steps,
            content_state=content_state,
            on_message_tool_content=on_message_tool_content,
        )

        await callbacks["on_progress"]("hello")
        progress_event = await queue.get()
        self.assertEqual(progress_event["event"], "progress")
        self.assertEqual(progress_event["content"], "hello")
        self.assertEqual(content_state["content"], "hello")

        await callbacks["on_progress"]("tool hint", tool_hint=True)
        tool_hint_event = await queue.get()
        self.assertEqual(tool_hint_event["event"], "progress")
        self.assertTrue(tool_hint_event["tool_hint"])
        self.assertEqual(content_state["content"], "hello")

        await callbacks["on_step_start"]("step-1", "thinking", "思考中")
        step_start_event = await queue.get()
        self.assertEqual(step_start_event["event"], "step_start")
        self.assertEqual(len(execution_steps), 1)
        self.assertEqual(execution_steps[0]["status"], "running")

        await callbacks["on_step_complete"]("step-1", "success", {"thinking": "ok"})
        step_complete_event = await queue.get()
        self.assertEqual(step_complete_event["event"], "step_complete")
        self.assertEqual(execution_steps[0]["status"], "success")
        self.assertEqual(execution_steps[0]["details"], {})
        self.assertEqual(step_complete_event["details"], {})

        await callbacks["on_tool_start"]("message", {"content": "tool text"})
        tool_start_event = await queue.get()
        self.assertEqual(tool_start_event["event"], "tool_start")
        self.assertEqual(message_tool_contents, ["tool text"])
        self.assertEqual(content_state["content"], "tool text")

    async def test_callbacks_cancel_when_stream_is_stopped(self):
        callbacks = _create_chat_stream_callbacks(
            queue=asyncio.Queue(),
            stream_manager=FakeStreamManager(should_stop=True),
            request_id="req-1",
            agent_id="main",
            agent_name="Main Agent",
            turn_id="turn-1",
            message_id="msg-1",
            execution_steps=[],
            content_state={"content": ""},
        )

        with self.assertRaises(asyncio.CancelledError):
            await callbacks["on_status"]("stopped")


if __name__ == "__main__":
    unittest.main()
