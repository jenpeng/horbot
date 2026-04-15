import unittest
from unittest.mock import AsyncMock

from horbot.agent.tools.web import WebAccessTool, WebSearchTool


class WebAccessToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_action_delegates_to_web_search_tool(self):
        search_tool = AsyncMock()
        search_tool.execute = AsyncMock(return_value="search-ok")
        fetch_tool = AsyncMock()

        tool = WebAccessTool(search_tool=search_tool, fetch_tool=fetch_tool)

        result = await tool.execute(action="search", query="ai agent", count=3)

        self.assertEqual(result, "search-ok")
        search_tool.execute.assert_awaited_once_with(query="ai agent", count=3)

    async def test_fetch_action_delegates_to_web_fetch_tool(self):
        search_tool = AsyncMock()
        fetch_tool = AsyncMock()
        fetch_tool.execute = AsyncMock(return_value="fetch-ok")

        tool = WebAccessTool(search_tool=search_tool, fetch_tool=fetch_tool)

        result = await tool.execute(
            action="fetch",
            url="https://example.com",
            extractMode="text",
            maxChars=1234,
        )

        self.assertEqual(result, "fetch-ok")
        fetch_tool.execute.assert_awaited_once_with(
            url="https://example.com",
            extractMode="text",
            maxChars=1234,
        )

    async def test_navigate_action_uses_proxy(self):
        proxy = AsyncMock()
        proxy.is_available = AsyncMock(return_value=True)
        proxy.navigate = AsyncMock()
        proxy.get_title = AsyncMock(return_value="Example")

        tool = WebAccessTool()
        tool._proxy_client = proxy

        result = await tool.execute(action="navigate", url="https://example.com")

        self.assertEqual(result, "✅ 已打开: https://example.com\n标题: Example")
        proxy.navigate.assert_awaited_once_with("https://example.com")
        proxy.get_title.assert_awaited_once()

    async def test_click_action_returns_browser_fallback_hint_for_playwright_selector(self):
        proxy = AsyncMock()
        proxy.is_available = AsyncMock(return_value=True)

        tool = WebAccessTool()
        tool._proxy_client = proxy

        result = await tool.execute(action="click", selector="text=登录", timeout=5000)

        self.assertIn("Playwright-only syntax", result)
        proxy.wait_for.assert_not_called()

    async def test_proxy_unavailable_returns_clear_error(self):
        proxy = AsyncMock()
        proxy.is_available = AsyncMock(return_value=False)

        tool = WebAccessTool(proxy_url="http://127.0.0.1:3456")
        tool._proxy_client = proxy

        result = await tool.execute(action="get_title")

        self.assertIn("web-access proxy is unavailable", result)


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
