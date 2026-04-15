import unittest
from unittest.mock import AsyncMock

from horbot.agent.tools.web import WebAccessTool


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


if __name__ == "__main__":
    unittest.main()
