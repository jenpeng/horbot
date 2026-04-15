import unittest
from unittest.mock import AsyncMock

from horbot.agent.tools.web import WebSearchTool


class WebSearchToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_tavily_provider_falls_back_when_disabled(self):
        tool = WebSearchTool(provider="tavily", tavily_enabled=False, api_key="secret", max_results=5)
        tool._search_tavily = AsyncMock(return_value="should-not-be-used")
        tool._search_duckduckgo = AsyncMock(return_value="Results for: agent memory (via DuckDuckGo)")

        result = await tool.execute(query="agent memory", count=3)

        self.assertEqual(tool.provider, "duckduckgo")
        self.assertEqual(result, "Results for: agent memory (via DuckDuckGo)")
        tool._search_tavily.assert_not_awaited()
        tool._search_duckduckgo.assert_awaited_once_with("agent memory", 3)

    async def test_no_results_appends_browser_fallback_hint(self):
        tool = WebSearchTool()

        result = tool._finalize_search_output("No results for: agent memory", "agent memory")

        self.assertIn("No results for: agent memory", result)
        self.assertIn("打开浏览器（CDP）方式继续搜索", result)

    async def test_error_appends_browser_fallback_hint(self):
        tool = WebSearchTool()

        result = tool._finalize_search_output("Error searching DuckDuckGo: timeout", "agent memory")

        self.assertIn("Error searching DuckDuckGo: timeout", result)
        self.assertIn("打开浏览器（CDP）方式继续搜索", result)


if __name__ == "__main__":
    unittest.main()
