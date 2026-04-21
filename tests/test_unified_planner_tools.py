import unittest

from horbot.agent.planner.unified_generator import build_tool_descriptions_from_definitions


class UnifiedPlannerToolDescriptionTests(unittest.TestCase):
    def test_build_tool_descriptions_enriches_generic_officecli_tool(self):
        definitions = [
            {
                "type": "function",
                "function": {
                    "name": "mcp_officecli_officecli",
                    "description": "Generic OfficeCLI MCP wrapper",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "OfficeCLI command"},
                            "file": {"type": "string", "description": "Target file path"},
                            "commands": {"type": "string", "description": "Batch payload"},
                        },
                    },
                },
            }
        ]

        descriptions = build_tool_descriptions_from_definitions(definitions)

        self.assertEqual(len(descriptions), 1)
        description = descriptions[0]
        self.assertEqual(description.name, "mcp_officecli_officecli")
        self.assertIn("create -> add slide -> add textbox", description.description)
        self.assertIn("batch", description.description)
        self.assertIn("JSON object for props", description.description)
        self.assertEqual(description.parameters["command"], "OfficeCLI command")
        self.assertEqual(description.parameters["file"], "Target file path")


if __name__ == "__main__":
    unittest.main()
