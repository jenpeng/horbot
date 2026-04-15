import unittest
from unittest.mock import AsyncMock, patch

from horbot.mcp.browser import server


class BrowserMCPServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_with_backend_prefers_proxy_when_available(self):
        proxy = AsyncMock()
        proxy.prefer_proxy = True
        proxy.is_available = AsyncMock(return_value=True)

        async def proxy_op(client):
            self.assertIs(client, proxy)
            return "proxy-ok"

        playwright_op = AsyncMock(return_value="playwright-ok")

        with patch.object(server, "get_proxy_client", return_value=proxy):
            result = await server._with_backend(
                "导航",
                proxy_operation=proxy_op,
                playwright_operation=playwright_op,
            )

        self.assertEqual(result, "proxy-ok")
        playwright_op.assert_not_awaited()

    async def test_with_backend_falls_back_when_proxy_unavailable(self):
        proxy = AsyncMock()
        proxy.prefer_proxy = True
        proxy.is_available = AsyncMock(return_value=False)
        playwright_op = AsyncMock(return_value="playwright-ok")

        with patch.object(server, "get_proxy_client", return_value=proxy):
            result = await server._with_backend(
                "导航",
                proxy_operation=AsyncMock(return_value="proxy-ok"),
                playwright_operation=playwright_op,
            )

        self.assertEqual(result, "playwright-ok")
        playwright_op.assert_awaited_once()

    async def test_browser_click_skips_proxy_for_playwright_only_selectors(self):
        class FakeElement:
            async def bounding_box(self):
                return None

            async def click(self):
                return None

        class FakePage:
            async def wait_for_selector(self, selector, timeout):
                self.selector = selector
                self.timeout = timeout
                return FakeElement()

        proxy = AsyncMock()
        proxy.prefer_proxy = True
        proxy.is_available = AsyncMock(return_value=True)
        fake_page = FakePage()

        with patch.object(server, "get_proxy_client", return_value=proxy), patch.object(
            server,
            "get_page",
            AsyncMock(return_value=fake_page),
        ):
            result = await server.browser_click("text=登录", timeout=1234)

        self.assertEqual(result, "✅ 已点击元素: text=登录")
        proxy.is_available.assert_not_awaited()

    def test_extract_target_id_supports_dict_and_plain_text(self):
        self.assertEqual(server.WebAccessProxyClient._extract_target_id({"targetId": "abc123"}), "abc123")
        self.assertEqual(server.WebAccessProxyClient._extract_target_id("targetId=xyz789"), "xyz789")


if __name__ == "__main__":
    unittest.main()
