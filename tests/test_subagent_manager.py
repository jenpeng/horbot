import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from horbot.agent.subagent import SubagentManager
from horbot.bus.queue import MessageBus


class DummyProvider:
    def get_default_model(self) -> str:
        return "dummy-model"


class SubagentManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancelled_session_subagent_keeps_cancelled_status(self):
        with TemporaryDirectory() as tmpdir:
            manager = SubagentManager(
                provider=DummyProvider(),
                bus=MessageBus(),
                workspace=Path(tmpdir),
            )

            started = asyncio.Event()
            blocker = asyncio.Event()

            async def blocked_run(*_args, **_kwargs):
                started.set()
                await blocker.wait()

            manager._run_subagent = blocked_run  # type: ignore[method-assign]

            await manager.spawn("long running task", session_key="web:test-session")
            await asyncio.wait_for(started.wait(), timeout=1)

            cancelled = await manager.cancel_by_session("web:test-session")
            self.assertEqual(cancelled, 1)
            await asyncio.sleep(0)

            task_id = next(iter(manager._task_info))
            self.assertEqual(manager._task_info[task_id].status, "cancelled")
            self.assertNotIn(task_id, manager._running_tasks)
            self.assertNotIn("web:test-session", manager._session_tasks)

    async def test_cancel_all_keeps_cancelled_status_after_cleanup(self):
        with TemporaryDirectory() as tmpdir:
            manager = SubagentManager(
                provider=DummyProvider(),
                bus=MessageBus(),
                workspace=Path(tmpdir),
            )

            started = asyncio.Event()
            blocker = asyncio.Event()

            async def blocked_run(*_args, **_kwargs):
                started.set()
                await blocker.wait()

            manager._run_subagent = blocked_run  # type: ignore[method-assign]

            await manager.spawn("long running task")
            await asyncio.wait_for(started.wait(), timeout=1)

            cancelled = await manager.cancel_all()
            self.assertEqual(cancelled, 1)
            await asyncio.sleep(0)

            task_id = next(iter(manager._task_info))
            self.assertEqual(manager._task_info[task_id].status, "cancelled")
            self.assertNotIn(task_id, manager._running_tasks)

    async def test_spawn_emits_lifecycle_events(self):
        with TemporaryDirectory() as tmpdir:
            events = []

            async def on_event(event):
                events.append(event)

            manager = SubagentManager(
                provider=DummyProvider(),
                bus=MessageBus(),
                workspace=Path(tmpdir),
                event_callback=on_event,
            )

            async def fast_run(task_id, *_args, **_kwargs):
                await manager._emit_event(task_id, "completed", result="finished")

            manager._run_subagent = fast_run  # type: ignore[method-assign]

            await manager.spawn(
                "summarize project",
                label="summary",
                origin_channel="web",
                origin_chat_id="dm_main",
                session_key="web:dm_main",
                metadata={"request_id": "req-1"},
            )
            await asyncio.sleep(0)

            self.assertGreaterEqual(len(events), 2)
            self.assertEqual(events[0]["event"], "subagent_update")
            self.assertEqual(events[0]["status"], "running")
            self.assertEqual(events[0]["session_key"], "web:dm_main")
            self.assertEqual(events[0]["metadata"]["request_id"], "req-1")
            self.assertEqual(events[-1]["status"], "completed")
            self.assertEqual(events[-1]["result"], "finished")


if __name__ == "__main__":
    unittest.main()
