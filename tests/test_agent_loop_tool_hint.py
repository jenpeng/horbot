import json
import unittest

from horbot.agent.loop import AgentLoop
from horbot.providers.base import ToolCallRequest


class AgentLoopToolHintTests(unittest.TestCase):
    def test_tool_hint_accepts_non_dict_arguments(self):
        tool_calls = [
            ToolCallRequest(
                id="call_1",
                name="mcp_officecli_officecli",
                arguments=[{"path": "/tmp/demo.pptx"}, {"command": "create"}],  # type: ignore[arg-type]
            )
        ]

        hint = AgentLoop._tool_hint(tool_calls)

        self.assertIn("mcp_officecli_officecli", hint)
        self.assertIn("/tmp/demo.pptx", hint)

    def test_build_officecli_retry_prompt_for_empty_ppt(self):
        messages = [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "mcp_officecli_officecli",
                            "arguments": json.dumps({"command": "create", "file": "/tmp/demo.pptx"}),
                        }
                    }
                ],
            },
            {
                "role": "tool",
                "content": "Created /tmp/demo.pptx",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "mcp_officecli_officecli",
                            "arguments": json.dumps({"command": "view", "mode": "outline", "file": "/tmp/demo.pptx"}),
                        }
                    }
                ],
            },
            {
                "role": "tool",
                "content": "File: demo.pptx | 0 slides",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "mcp_officecli_officecli",
                            "arguments": json.dumps({"command": "help", "format": "pptx"}),
                        }
                    }
                ],
            },
            {
                "role": "tool",
                "content": "## Strategy\nUse view ...\n# PPTX Reference",
            },
        ]

        prompt = AgentLoop._build_officecli_retry_prompt(
            user_message="请创建一个简单而漂亮布局的 3 页 PowerPoint，保存到 /tmp/demo.pptx",
            messages=messages,
            start_index=0,
            clean="## Strategy\nUse view ...\n# PPTX Reference",
        )

        self.assertIsNotNone(prompt)
        self.assertIn("3 slides", prompt)
        self.assertIn("incomplete", prompt)


if __name__ == "__main__":
    unittest.main()
