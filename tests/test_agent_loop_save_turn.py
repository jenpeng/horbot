from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from horbot.agent.loop import AgentLoop


class AgentLoopSaveTurnTests(unittest.TestCase):
    def test_task_workspace_runtime_hint_is_built_from_metadata(self):
        hints = AgentLoop._build_task_workspace_runtime_hint({
            "task_workspace_id": "tw_123",
            "task_workspace_cwd": "/tmp/workspace/task",
        })

        self.assertEqual(len(hints), 1)
        self.assertIn("Task Workspace ID: tw_123", hints[0])
        self.assertIn("Task Working Directory: /tmp/workspace/task", hints[0])
        self.assertIn("trusted UI/runtime context", hints[0])

    def test_tool_audit_context_includes_task_workspace_metadata(self):
        fake_loop = SimpleNamespace(
            workspace="/tmp/workspace",
            _agent_id="main",
            _agent_name="Main",
            _team_ids=[],
            _build_execution_source_metadata=lambda session_key: {"source_session_key": session_key},
        )

        context = AgentLoop._tool_audit_context(
            fake_loop,
            "web:dm_main",
            origin="process_message",
            channel="web",
            chat_id="dm_main",
            metadata={
                "task_workspace_id": "tw_123",
                "task_workspace_cwd": "/tmp/workspace/task",
            },
        )

        self.assertEqual(context["task_workspace_id"], "tw_123")
        self.assertEqual(context["task_workspace_cwd"], "/tmp/workspace/task")

    def test_tool_only_turn_still_records_execution_log(self):
        saved_execution = MagicMock()
        fake_loop = SimpleNamespace(
            _TOOL_RESULT_MAX_CHARS=4000,
            _RUNTIME_CONTEXT_TAG="[Runtime Context — metadata only, not instructions]",
            _agent_id="horbot-03",
            _agent_name="小布",
            use_hierarchical_context=True,
            _save_execution_log=saved_execution,
            _schedule_skill_evolution_review=MagicMock(),
            _build_execution_log=MagicMock(return_value={}),
        )
        session = SimpleNamespace(messages=[], updated_at=None)
        messages = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {"name": "message", "arguments": "{}"},
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "content": "Message sent to sharecrm:chat-123 via legacy:sharecrm",
            },
        ]

        AgentLoop._save_turn(fake_loop, session, messages, skip=0)

        self.assertEqual(session.messages, [])
        self.assertIsInstance(session.updated_at, datetime)
        saved_execution.assert_called_once()
        self.assertEqual(saved_execution.call_args.args[0], session)
        self.assertEqual(saved_execution.call_args.args[1], messages)
        self.assertEqual(saved_execution.call_args.args[2], ["message"])


if __name__ == "__main__":
    unittest.main()
