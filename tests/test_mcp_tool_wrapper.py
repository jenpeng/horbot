from types import SimpleNamespace
import unittest

from horbot.agent.tools.mcp import MCPToolWrapper


class MCPToolWrapperTests(unittest.TestCase):
    def test_officecli_description_is_enriched_for_ppt_creation(self):
        tool_def = SimpleNamespace(
            name="officecli",
            description="Generic OfficeCLI tool.",
            inputSchema={"type": "object", "properties": {}},
        )

        wrapper = MCPToolWrapper(session=None, server_name="officecli", tool_def=tool_def)

        self.assertIn("0 slides is incomplete", wrapper.description)
        self.assertIn("command=add", wrapper.description)
        self.assertIn("command=validate", wrapper.description)


if __name__ == "__main__":
    unittest.main()
