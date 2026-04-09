from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from horbot.agent.loop import AgentLoop


class AgentLoopSaveTurnTests(unittest.TestCase):
    def test_tool_only_turn_still_records_execution_log(self):
        saved_execution = MagicMock()
        fake_loop = SimpleNamespace(
            _TOOL_RESULT_MAX_CHARS=4000,
            _RUNTIME_CONTEXT_TAG="[Runtime Context — metadata only, not instructions]",
            _agent_id="horbot-03",
            _agent_name="小布",
            use_hierarchical_context=True,
            _save_execution_log=saved_execution,
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
