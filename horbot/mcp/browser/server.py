"""Browser MCP server with web-access proxy preference and Playwright fallback."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx
from loguru import logger
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("browser-automation")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
PLAYWRIGHT_ONLY_SELECTOR_PATTERNS = (
    "text=",
    "xpath=",
    ":has-text(",
    ":text(",
    ":visible",
    ">>",
)

_playwright = None
_browser = None
_context = None
_page = None
_proxy_client: "WebAccessProxyClient | None" = None
_proxy_target_id: str | None = None


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _requires_playwright_selector(selector: str | None) -> bool:
    normalized = (selector or "").strip().lower()
    return any(token in normalized for token in PLAYWRIGHT_ONLY_SELECTOR_PATTERNS)


def _coerce_proxy_text(payload: Any) -> str:
    if isinstance(payload, (dict, list)):
        return json.dumps(payload, ensure_ascii=False, indent=2)
    if payload is None:
        return ""
    text = str(payload).strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        try:
            decoded = json.loads(text)
            if isinstance(decoded, str):
                return decoded
        except Exception:
            pass
    return text


def _proxy_error_text(response: httpx.Response) -> str:
    text = response.text.strip()
    if not text:
        return f"HTTP {response.status_code}"
    return text


class ProxyUnavailableError(RuntimeError):
    """Raised when the proxy cannot be reached."""


class ProxyUnsupportedError(RuntimeError):
    """Raised when the proxy does not support an action."""


class ProxyActionError(RuntimeError):
    """Raised when a proxy action fails and should not silently fall back."""


class WebAccessProxyClient:
    """Thin async client for web-access CDP proxy endpoints."""

    def __init__(self, base_url: str, timeout: float, prefer_proxy: bool) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.prefer_proxy = prefer_proxy
        self._available_cache: tuple[float, bool] | None = None
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            follow_redirects=True,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def is_available(self) -> bool:
        if not self.prefer_proxy:
            return False
        if self._available_cache and (time.time() - self._available_cache[0]) < 5:
            return self._available_cache[1]
        available = False
        try:
            response = await self._client.get("/health")
            available = response.status_code < 500
        except httpx.HTTPError:
            available = False
        self._available_cache = (time.time(), available)
        return available

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: str | None = None,
        parse_json: bool = False,
    ) -> Any:
        try:
            response = await self._client.request(
                method,
                path,
                params=params,
                content=body.encode("utf-8") if isinstance(body, str) else None,
                headers={"content-type": "text/plain; charset=utf-8"} if body is not None else None,
            )
        except httpx.HTTPError as exc:
            raise ProxyUnavailableError(str(exc)) from exc

        if response.status_code in {404, 405, 501}:
            raise ProxyUnsupportedError(_proxy_error_text(response))
        if response.status_code >= 400:
            raise ProxyActionError(_proxy_error_text(response))

        if parse_json:
            try:
                return response.json()
            except ValueError:
                text = response.text.strip()
                if text:
                    try:
                        return json.loads(text)
                    except ValueError:
                        return text
        return response.text

    @staticmethod
    def _extract_target_id(payload: Any) -> str | None:
        if isinstance(payload, dict):
            for key in ("targetId", "target_id", "id", "target"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        text = _coerce_proxy_text(payload)
        if not text:
            return None
        try:
            parsed = json.loads(text)
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            return WebAccessProxyClient._extract_target_id(parsed)
        match = re.search(r"(?:targetId|target_id|target|id)[\"'\s:=]+([A-Za-z0-9._:-]+)", text)
        if match:
            return match.group(1)
        stripped = text.strip().strip('"').strip("'")
        if re.fullmatch(r"[A-Za-z0-9._:-]{6,}", stripped):
            return stripped
        return None

    async def ensure_target(self, *, url: str | None = None, force_new: bool = False) -> str:
        global _proxy_target_id
        if _proxy_target_id and not force_new:
            return _proxy_target_id
        payload = await self._request(
            "GET",
            "/new",
            params={"url": url or "about:blank"},
            parse_json=True,
        )
        target_id = self._extract_target_id(payload)
        if not target_id:
            raise ProxyUnavailableError(f"Cannot determine proxy target id from response: {_coerce_proxy_text(payload)}")
        _proxy_target_id = target_id
        return target_id

    async def eval(self, script: str, *, target_id: str | None = None) -> str:
        target = target_id or await self.ensure_target()
        payload = await self._request("POST", "/eval", params={"target": target}, body=script)
        return _coerce_proxy_text(payload)

    async def navigate(self, url: str) -> str:
        global _proxy_target_id
        if not _proxy_target_id:
            await self.ensure_target(url=url)
        else:
            await self.eval(f"window.location.href = {json.dumps(url)}; 'navigating';")
        await self.wait_ready(timeout=20000)
        return url

    async def new_tab(self, url: str = "") -> str:
        target_id = await self.ensure_target(url=url or "about:blank", force_new=True)
        return target_id

    async def click(self, selector: str) -> str:
        target = await self.ensure_target()
        payload = await self._request("POST", "/click", params={"target": target}, body=selector)
        return _coerce_proxy_text(payload)

    async def type(self, selector: str, text: str) -> str:
        script = f"""
(() => {{
  const el = document.querySelector({json.dumps(selector)});
  if (!el) throw new Error("Element not found: {selector}");
  el.focus();
  if ("value" in el) {{
    el.value = "";
    el.value = {json.dumps(text)};
  }} else {{
    el.textContent = {json.dumps(text)};
  }}
  el.dispatchEvent(new Event("input", {{ bubbles: true }}));
  el.dispatchEvent(new Event("change", {{ bubbles: true }}));
  return "typed";
}})()
"""
        return await self.eval(script)

    async def scroll(self, direction: str, distance: int) -> str:
        signed_distance = distance if direction == "down" else -distance
        return await self.eval(f"window.scrollBy({{ top: {signed_distance}, behavior: 'smooth' }}); 'scrolled';")

    async def screenshot(self, path: str) -> str:
        target = await self.ensure_target()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        await self._request("GET", "/screenshot", params={"target": target, "file": str(Path(path).resolve())})
        return path

    async def get_text(self, selector: str) -> str:
        script = f"""
(() => {{
  const el = document.querySelector({json.dumps(selector)});
  if (!el) throw new Error("Element not found: {selector}");
  return (el.innerText || el.textContent || "").trim();
}})()
"""
        return await self.eval(script)

    async def get_html(self, selector: str) -> str:
        script = f"""
(() => {{
  const el = document.querySelector({json.dumps(selector)});
  if (!el) throw new Error("Element not found: {selector}");
  return el.outerHTML || "";
}})()
"""
        return await self.eval(script)

    async def wait_for(self, selector: str, timeout: int) -> str:
        deadline = time.time() + (timeout / 1000)
        script = f"Boolean(document.querySelector({json.dumps(selector)}))"
        while time.time() < deadline:
            result = (await self.eval(script)).strip().lower()
            if result in {"true", "1"}:
                return selector
            await asyncio.sleep(0.25)
        raise ProxyActionError(f"等待元素超时: {selector}")

    async def wait_ready(self, timeout: int) -> None:
        deadline = time.time() + (timeout / 1000)
        while time.time() < deadline:
            result = (await self.eval("document.readyState")).strip().lower()
            if result in {"interactive", "complete"}:
                return
            await asyncio.sleep(0.25)

    async def get_url(self) -> str:
        return await self.eval("window.location.href")

    async def get_title(self) -> str:
        return await self.eval("document.title")

    async def find_elements(self, selector: str) -> str:
        script = f"""
(() => {{
  const items = Array.from(document.querySelectorAll({json.dumps(selector)})).slice(0, 10);
  return JSON.stringify(items.map((el, index) => ({{
    index: index + 1,
    tag: (el.tagName || "").toLowerCase(),
    text: (el.innerText || el.textContent || "").trim().slice(0, 50)
  }})));
}})()
"""
        payload = await self.eval(script)
        try:
            elements = json.loads(payload)
        except Exception as exc:
            raise ProxyActionError(f"无法解析元素列表: {payload}") from exc
        if not elements:
            return f"未找到匹配的元素: {selector}"
        lines = [f"找到 {len(elements)} 个元素:\n"]
        for item in elements:
            lines.append(f"{item['index']}. <{item['tag']}> {item['text']}")
        return "\n".join(lines)

    async def hover(self, selector: str) -> str:
        script = f"""
(() => {{
  const el = document.querySelector({json.dumps(selector)});
  if (!el) throw new Error("Element not found: {selector}");
  el.dispatchEvent(new MouseEvent("mouseover", {{ bubbles: true }}));
  el.dispatchEvent(new MouseEvent("mouseenter", {{ bubbles: true }}));
  return "hovered";
}})()
"""
        return await self.eval(script)

    async def press_key(self, key: str) -> str:
        script = f"""
(() => {{
  const target = document.activeElement || document.body;
  const event = new KeyboardEvent("keydown", {{ key: {json.dumps(key)}, bubbles: true }});
  target.dispatchEvent(event);
  const up = new KeyboardEvent("keyup", {{ key: {json.dumps(key)}, bubbles: true }});
  target.dispatchEvent(up);
  return "pressed";
}})()
"""
        return await self.eval(script)

    async def back(self) -> str:
        await self.eval("history.back(); 'back';")
        return "back"

    async def forward(self) -> str:
        await self.eval("history.forward(); 'forward';")
        return "forward"

    async def reload(self) -> str:
        await self.eval("window.location.reload(); 'reload';")
        return "reload"

    async def close_target(self) -> str:
        global _proxy_target_id
        if not _proxy_target_id:
            return "noop"
        target = _proxy_target_id
        await self._request("GET", "/close", params={"target": target})
        _proxy_target_id = None
        return target


def get_proxy_client() -> WebAccessProxyClient:
    global _proxy_client
    if _proxy_client is None:
        _proxy_client = WebAccessProxyClient(
            base_url=os.getenv("WEB_ACCESS_PROXY_URL", "http://127.0.0.1:3456"),
            timeout=_env_float("WEB_ACCESS_PROXY_TIMEOUT", 30.0),
            prefer_proxy=_env_flag("WEB_ACCESS_PREFER_PROXY", True),
        )
    return _proxy_client


async def get_browser():
    """Get or create Playwright browser."""
    global _playwright, _browser

    if _browser is None:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright 未安装。请运行：\n"
                "  pip install playwright\n"
                "  playwright install chromium"
            ) from exc

        _playwright = await async_playwright().start()
        launch_kwargs = {
            "headless": _env_flag("BROWSER_HEADLESS", False),
            "args": [
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
            ],
        }
        try:
            _browser = await _playwright.chromium.launch(channel="chrome", **launch_kwargs)
            logger.info("Browser MCP: using system Chrome fallback")
        except Exception as exc:
            logger.warning("Browser MCP: cannot launch Chrome fallback: {}", exc)
            _browser = await _playwright.chromium.launch(**launch_kwargs)
            logger.info("Browser MCP: using Chromium fallback")

    return _browser


async def get_context():
    """Get or create Playwright browser context."""
    global _context
    browser = await get_browser()
    if _context is None:
        _context = await browser.new_context(viewport=None, user_agent=DEFAULT_USER_AGENT)
    return _context


async def get_page():
    """Get current Playwright page, creating one when needed."""
    global _page
    if _page is not None:
        try:
            if not _page.is_closed():
                return _page
        except Exception:
            _page = None
    context = await get_context()
    _page = await context.new_page()
    logger.info("Browser MCP: created Playwright page")
    return _page


async def _with_backend(
    action_name: str,
    *,
    proxy_operation=None,
    playwright_operation=None,
    allow_proxy: bool = True,
) -> str:
    proxy = get_proxy_client()
    if allow_proxy and proxy.prefer_proxy:
        try:
            if await proxy.is_available():
                return await proxy_operation(proxy)
        except (ProxyUnavailableError, ProxyUnsupportedError) as exc:
            logger.warning("Browser MCP: proxy unavailable for {}: {}", action_name, exc)
        except ProxyActionError as exc:
            return f"❌ {action_name}失败: {exc}"
        except Exception as exc:
            logger.exception("Browser MCP: unexpected proxy error for {}", action_name)
            return f"❌ {action_name}失败: {exc}"
    if playwright_operation is None:
        return f"❌ {action_name}失败: 未配置可用后端"
    try:
        return await playwright_operation()
    except Exception as exc:
        return f"❌ {action_name}失败: {exc}"


@mcp.tool()
async def browser_navigate(url: str) -> str:
    async def proxy_op(proxy: WebAccessProxyClient) -> str:
        await proxy.navigate(url)
        title = await proxy.get_title()
        return f"✅ 已打开: {url}\n标题: {title}"

    async def playwright_op() -> str:
        page = await get_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        return f"✅ 已打开: {url}\n标题: {await page.title()}"

    return await _with_backend("导航", proxy_operation=proxy_op, playwright_operation=playwright_op)


@mcp.tool()
async def browser_click(selector: str, timeout: int = 10000) -> str:
    allow_proxy = not _requires_playwright_selector(selector)

    async def proxy_op(proxy: WebAccessProxyClient) -> str:
        await proxy.wait_for(selector, timeout)
        await proxy.click(selector)
        return f"✅ 已点击元素: {selector}"

    async def playwright_op() -> str:
        page = await get_page()
        element = await page.wait_for_selector(selector, timeout=timeout)
        box = await element.bounding_box()
        if box:
            x = box["x"] + box["width"] / 2
            y = box["y"] + box["height"] / 2
            await page.mouse.move(x, y, steps=10)
        await element.click()
        return f"✅ 已点击元素: {selector}"

    return await _with_backend(
        "点击",
        proxy_operation=proxy_op,
        playwright_operation=playwright_op,
        allow_proxy=allow_proxy,
    )


@mcp.tool()
async def browser_type(selector: str, text: str, delay: int = 50) -> str:
    allow_proxy = not _requires_playwright_selector(selector)

    async def proxy_op(proxy: WebAccessProxyClient) -> str:
        await proxy.wait_for(selector, 10000)
        await proxy.type(selector, text)
        return f"✅ 已输入文本: {text[:50]}..."

    async def playwright_op() -> str:
        page = await get_page()
        await page.click(selector)
        await page.fill(selector, "")
        await page.type(selector, text, delay=delay)
        return f"✅ 已输入文本: {text[:50]}..."

    return await _with_backend(
        "输入",
        proxy_operation=proxy_op,
        playwright_operation=playwright_op,
        allow_proxy=allow_proxy,
    )


@mcp.tool()
async def browser_scroll(direction: str = "down", distance: int = 500) -> str:
    direction = "up" if str(direction).lower() == "up" else "down"

    async def proxy_op(proxy: WebAccessProxyClient) -> str:
        await proxy.scroll(direction, distance)
        return f"✅ 已向{direction}滚动 {distance} 像素"

    async def playwright_op() -> str:
        page = await get_page()
        await page.mouse.wheel(0, distance if direction == "down" else -distance)
        return f"✅ 已向{direction}滚动 {distance} 像素"

    return await _with_backend("滚动", proxy_operation=proxy_op, playwright_operation=playwright_op)


@mcp.tool()
async def browser_screenshot(path: str = "") -> str:
    if not path:
        path = f"logs/browser-screenshot-{int(time.time())}.png"
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    async def proxy_op(proxy: WebAccessProxyClient) -> str:
        saved_path = await proxy.screenshot(path)
        return f"✅ 截图已保存: {saved_path}"

    async def playwright_op() -> str:
        page = await get_page()
        await page.screenshot(path=path)
        return f"✅ 截图已保存: {path}"

    return await _with_backend("截图", proxy_operation=proxy_op, playwright_operation=playwright_op)


@mcp.tool()
async def browser_get_text(selector: str = "body") -> str:
    allow_proxy = not _requires_playwright_selector(selector)

    async def proxy_op(proxy: WebAccessProxyClient) -> str:
        return await proxy.get_text(selector)

    async def playwright_op() -> str:
        page = await get_page()
        text = await page.text_content(selector)
        return text or "(无内容)"

    return await _with_backend(
        "获取文本",
        proxy_operation=proxy_op,
        playwright_operation=playwright_op,
        allow_proxy=allow_proxy,
    )


@mcp.tool()
async def browser_get_html(selector: str = "body") -> str:
    allow_proxy = not _requires_playwright_selector(selector)

    async def proxy_op(proxy: WebAccessProxyClient) -> str:
        html = await proxy.get_html(selector)
        if len(html) > 10000:
            return html[:10000] + "\n\n... (内容过长，已截断)"
        return html

    async def playwright_op() -> str:
        page = await get_page()
        html = await page.inner_html(selector)
        if len(html) > 10000:
            return html[:10000] + "\n\n... (内容过长，已截断)"
        return html

    return await _with_backend(
        "获取 HTML",
        proxy_operation=proxy_op,
        playwright_operation=playwright_op,
        allow_proxy=allow_proxy,
    )


@mcp.tool()
async def browser_wait_for(selector: str, timeout: int = 30000) -> str:
    allow_proxy = not _requires_playwright_selector(selector)

    async def proxy_op(proxy: WebAccessProxyClient) -> str:
        await proxy.wait_for(selector, timeout)
        return f"✅ 元素已出现: {selector}"

    async def playwright_op() -> str:
        page = await get_page()
        await page.wait_for_selector(selector, timeout=timeout)
        return f"✅ 元素已出现: {selector}"

    return await _with_backend(
        "等待",
        proxy_operation=proxy_op,
        playwright_operation=playwright_op,
        allow_proxy=allow_proxy,
    )


@mcp.tool()
async def browser_evaluate(script: str) -> str:
    async def proxy_op(proxy: WebAccessProxyClient) -> str:
        return await proxy.eval(script)

    async def playwright_op() -> str:
        page = await get_page()
        result = await page.evaluate(script)
        if result is None:
            return "✅ 执行成功"
        if isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False, indent=2)
        return str(result)

    return await _with_backend("执行", proxy_operation=proxy_op, playwright_operation=playwright_op)


@mcp.tool()
async def browser_get_url() -> str:
    async def proxy_op(proxy: WebAccessProxyClient) -> str:
        return await proxy.get_url()

    async def playwright_op() -> str:
        page = await get_page()
        return page.url

    return await _with_backend("获取 URL", proxy_operation=proxy_op, playwright_operation=playwright_op)


@mcp.tool()
async def browser_get_title() -> str:
    async def proxy_op(proxy: WebAccessProxyClient) -> str:
        return await proxy.get_title()

    async def playwright_op() -> str:
        page = await get_page()
        return await page.title()

    return await _with_backend("获取标题", proxy_operation=proxy_op, playwright_operation=playwright_op)


@mcp.tool()
async def browser_close() -> str:
    global _playwright, _browser, _context, _page

    proxy_result: str | None = None
    proxy = get_proxy_client()
    if proxy.prefer_proxy:
        try:
            if await proxy.is_available():
                result = await proxy.close_target()
                proxy_result = "✅ web-access 页面已关闭" if result != "noop" else None
        except Exception as exc:
            logger.warning("Browser MCP: proxy close failed: {}", exc)

    try:
        if _browser:
            await _browser.close()
            _browser = None
            _context = None
            _page = None
            if _playwright:
                await _playwright.stop()
                _playwright = None
            return proxy_result or "✅ 浏览器已关闭"
        return proxy_result or "⚠️ 浏览器未运行"
    except Exception as exc:
        return f"❌ 关闭失败: {exc}"


@mcp.tool()
async def browser_new_tab(url: str = "") -> str:
    async def proxy_op(proxy: WebAccessProxyClient) -> str:
        await proxy.new_tab(url)
        return f"✅ 新标签页已打开: {url}" if url else "✅ 新标签页已打开"

    async def playwright_op() -> str:
        global _page
        context = await get_context()
        _page = await context.new_page()
        if url:
            await _page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return f"✅ 新标签页已打开: {url}"
        return "✅ 新标签页已打开"

    return await _with_backend("打开新标签页", proxy_operation=proxy_op, playwright_operation=playwright_op)


@mcp.tool()
async def browser_press_key(key: str) -> str:
    async def proxy_op(proxy: WebAccessProxyClient) -> str:
        await proxy.press_key(key)
        return f"✅ 已按下: {key}"

    async def playwright_op() -> str:
        page = await get_page()
        await page.keyboard.press(key)
        return f"✅ 已按下: {key}"

    return await _with_backend("按键", proxy_operation=proxy_op, playwright_operation=playwright_op)


@mcp.tool()
async def browser_find_elements(selector: str) -> str:
    allow_proxy = not _requires_playwright_selector(selector)

    async def proxy_op(proxy: WebAccessProxyClient) -> str:
        return await proxy.find_elements(selector)

    async def playwright_op() -> str:
        page = await get_page()
        elements = await page.query_selector_all(selector)
        if not elements:
            return f"未找到匹配的元素: {selector}"
        result = [f"找到 {len(elements)} 个元素:\n"]
        for index, elem in enumerate(elements[:10], start=1):
            text = await elem.text_content()
            if text:
                text = text.strip()[:50]
            tag = await elem.evaluate("el => el.tagName")
            result.append(f"{index}. <{str(tag).lower()}> {text or ''}")
        if len(elements) > 10:
            result.append(f"\n... 还有 {len(elements) - 10} 个元素")
        return "\n".join(result)

    return await _with_backend(
        "查找元素",
        proxy_operation=proxy_op,
        playwright_operation=playwright_op,
        allow_proxy=allow_proxy,
    )


@mcp.tool()
async def browser_hover(selector: str) -> str:
    allow_proxy = not _requires_playwright_selector(selector)

    async def proxy_op(proxy: WebAccessProxyClient) -> str:
        await proxy.hover(selector)
        return f"✅ 已悬停在元素上: {selector}"

    async def playwright_op() -> str:
        page = await get_page()
        await page.hover(selector)
        return f"✅ 已悬停在元素上: {selector}"

    return await _with_backend(
        "悬停",
        proxy_operation=proxy_op,
        playwright_operation=playwright_op,
        allow_proxy=allow_proxy,
    )


@mcp.tool()
async def browser_goto_back() -> str:
    async def proxy_op(proxy: WebAccessProxyClient) -> str:
        await proxy.back()
        return "✅ 已后退到上一页"

    async def playwright_op() -> str:
        page = await get_page()
        await page.go_back()
        return "✅ 已后退到上一页"

    return await _with_backend("后退", proxy_operation=proxy_op, playwright_operation=playwright_op)


@mcp.tool()
async def browser_goto_forward() -> str:
    async def proxy_op(proxy: WebAccessProxyClient) -> str:
        await proxy.forward()
        return "✅ 已前进到下一页"

    async def playwright_op() -> str:
        page = await get_page()
        await page.go_forward()
        return "✅ 已前进到下一页"

    return await _with_backend("前进", proxy_operation=proxy_op, playwright_operation=playwright_op)


@mcp.tool()
async def browser_reload() -> str:
    async def proxy_op(proxy: WebAccessProxyClient) -> str:
        await proxy.reload()
        return "✅ 页面已刷新"

    async def playwright_op() -> str:
        page = await get_page()
        await page.reload()
        return "✅ 页面已刷新"

    return await _with_backend("刷新", proxy_operation=proxy_op, playwright_operation=playwright_op)


if __name__ == "__main__":
    logger.info("启动浏览器自动化 MCP Server...")
    mcp.run()
