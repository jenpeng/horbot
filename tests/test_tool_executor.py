import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock

from horbot.agent.tool_executor import ToolExecutor, ToolExecutionResult
from horbot.agent.tools.permission import PermissionLevel


class MockToolCall:
    def __init__(self, id, name, arguments):
        self.id = id
        self.name = name
        self.arguments = arguments


class TestToolExecutor(unittest.IsolatedAsyncioTestCase):
    async def test_execute_tool_calls_basic(self):
        # Mock Registry and ContextBuilder
        mock_registry = MagicMock()
        mock_registry.check_permission.return_value = PermissionLevel.ALLOW
        mock_registry.execute = AsyncMock(return_value="tool_result")

        mock_context = MagicMock()
        def mock_add_tool_result(messages, tool_id, name, result):
            return messages + [{"role": "tool", "tool_call_id": tool_id, "name": name, "content": result}]
        mock_context.add_tool_result.side_effect = mock_add_tool_result

        executor = ToolExecutor(tools=mock_registry, context=mock_context)

        tool_calls = [
            MockToolCall(id="call_1", name="read_file", arguments={"path": "test.txt"}),
            MockToolCall(id="call_2", name="list_dir", arguments={"path": "."}),
        ]
        messages = [{"role": "user", "content": "hello"}]
        tools_used = []

        result = await executor.execute_tool_calls(
            tool_calls=tool_calls,
            messages=messages,
            tools_used=tools_used,
            iteration=1,
        )

        self.assertIsInstance(result, ToolExecutionResult)
        self.assertFalse(result.should_break)
        self.assertIsNone(result.final_content)
        self.assertEqual(len(result.messages), 3)
        self.assertEqual(result.messages[1]["content"], "tool_result")
        self.assertEqual(result.messages[2]["content"], "tool_result")
        self.assertEqual(tools_used, ["read_file", "list_dir"])

    async def test_execute_tool_calls_with_confirm(self):
        mock_registry = MagicMock()
        mock_registry.check_permission.return_value = PermissionLevel.CONFIRM
        mock_registry.execute = AsyncMock()

        mock_context = MagicMock()

        executor = ToolExecutor(tools=mock_registry, context=mock_context)

        tool_calls = [
            MockToolCall(id="call_1", name="exec", arguments={"command": "rm -rf /"}),
        ]

        result = await executor.execute_tool_calls(
            tool_calls=tool_calls,
            messages=[],
            tools_used=[],
            iteration=1,
        )

        self.assertTrue(result.should_break)
        self.assertIsNotNone(result.final_content)
        self.assertIn("需要确认", result.final_content)
        self.assertEqual(len(result.confirmations), 1)

    async def test_execute_message_tool_only_once(self):
        mock_registry = MagicMock()
        mock_registry.check_permission.return_value = PermissionLevel.ALLOW
        mock_registry.execute = AsyncMock(return_value="Message delivered")

        mock_context = MagicMock()
        def mock_add_tool_result(messages, tool_id, name, result):
            return messages + [{"role": "tool", "content": result}]
        mock_context.add_tool_result.side_effect = mock_add_tool_result

        executor = ToolExecutor(tools=mock_registry, context=mock_context)

        tool_calls = [
            MockToolCall(id="call_1", name="message", arguments={"content": "hello"}),
        ]
        tools_used = ["message"] # already used in this turn

        result = await executor.execute_tool_calls(
            tool_calls=tool_calls,
            messages=[],
            tools_used=tools_used,
            iteration=1,
        )

        self.assertTrue(result.should_break)
        self.assertEqual(result.final_content, "Message sent.")
        self.assertEqual(len(result.messages), 1)
        self.assertEqual(result.messages[0]["content"], "Message already sent. Task complete.")

    async def test_execute_message_tool_success(self):
        mock_registry = MagicMock()
        mock_registry.check_permission.return_value = PermissionLevel.ALLOW
        mock_registry.execute = AsyncMock(return_value="Message delivered")

        mock_context = MagicMock()
        mock_context.add_tool_result.side_effect = lambda msgs, tid, name, res: msgs + [{"role": "tool", "content": res}]

        executor = ToolExecutor(tools=mock_registry, context=mock_context)

        tool_calls = [
            MockToolCall(id="call_1", name="message", arguments={"content": "hello user"}),
        ]
        
        result = await executor.execute_tool_calls(
            tool_calls=tool_calls,
            messages=[],
            tools_used=[],
            iteration=1,
        )

        self.assertTrue(result.should_break)
        self.assertEqual(result.final_content, "Message delivered")

if __name__ == "__main__":
    unittest.main()
