"""Web tools: web_access, web_search, and web_fetch."""

import asyncio
from contextvars import ContextVar
import html
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from horbot.agent.tools.base import Tool, ToolCategory, ToolMetadata

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_2) AppleWebKit/537.36"
MAX_REDIRECTS = 5
PLAYWRIGHT_ONLY_SELECTOR_PATTERNS = (
    "text=",
    "xpath=",
    ":has-text(",
    ":text(",
    ":visible",
    ">>",
)


def _strip_tags(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = re.sub(r'<script[\s\S]*?</script>', '', text, flags=re.I)
    text = re.sub(r'<style[\s\S]*?</style>', '', text, flags=re.I)
    text = re.sub(r'<[^>]+>', '', text)
    return html.unescape(text).strip()


def _normalize(text: str) -> str:
    """Normalize whitespace."""
    text = re.sub(r'[ \t]+', ' ', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def _validate_url(url: str) -> tuple[bool, str]:
    """Validate URL: must be http(s) with valid domain."""
    try:
        p = urlparse(url)
        if p.scheme not in ('http', 'https'):
            return False, f"Only http/https allowed, got '{p.scheme or 'none'}'"
        if not p.netloc:
            return False, "Missing domain"
        return True, ""
    except Exception as e:
        return False, str(e)


def _requires_browser_fallback(selector: str | None) -> bool:
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


class ProxyUnavailableError(RuntimeError):
    """Raised when web-access proxy is unavailable."""


class ProxyUnsupportedError(RuntimeError):
    """Raised when web-access proxy doesn't support an action."""


class ProxyActionError(RuntimeError):
    """Raised when a proxy action fails."""


class WebAccessProxyClient:
    """Thin client for web-access CDP proxy endpoints."""

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            follow_redirects=True,
        )
        self._available_cache: tuple[float, bool] | None = None
        self._target_id_var: ContextVar[str | None] = ContextVar(
            f"web_access_target_{id(self)}",
            default=None,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def is_available(self) -> bool:
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
            raise ProxyUnsupportedError(response.text.strip() or f"HTTP {response.status_code}")
        if response.status_code >= 400:
            raise ProxyActionError(response.text.strip() or f"HTTP {response.status_code}")

        if parse_json:
            try:
                return response.json()
            except ValueError:
                return response.text
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
        target_id = self._target_id_var.get()
        if target_id and not force_new:
            return target_id
        payload = await self._request(
            "GET",
            "/new",
            params={"url": url or "about:blank"},
            parse_json=True,
        )
        target_id = self._extract_target_id(payload)
        if not target_id:
            raise ProxyUnavailableError(f"Cannot determine proxy target id: {_coerce_proxy_text(payload)}")
        self._target_id_var.set(target_id)
        return target_id

    async def eval(self, script: str, *, target_id: str | None = None) -> str:
        target = target_id or await self.ensure_target()
        payload = await self._request("POST", "/eval", params={"target": target}, body=script)
        return _coerce_proxy_text(payload)

    async def navigate(self, url: str) -> str:
        if not self._target_id_var.get():
            await self.ensure_target(url=url)
        else:
            await self.eval(f"window.location.href = {json.dumps(url)}; 'navigating';")
        await self.wait_ready(timeout=20000)
        return url

    async def new_tab(self, url: str = "") -> str:
        return await self.ensure_target(url=url or "about:blank", force_new=True)

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

    async def close_target(self) -> str:
        target = self._target_id_var.get()
        if not target:
            return "noop"
        await self._request("GET", "/close", params={"target": target})
        self._target_id_var.set(None)
        return target


class WebAccessTool(Tool):
    """Native web-access orchestration tool."""

    def __init__(
        self,
        search_tool: "WebSearchTool | None" = None,
        fetch_tool: "WebFetchTool | None" = None,
        proxy_url: str | None = None,
        proxy_timeout: float | None = None,
    ) -> None:
        self._search_tool = search_tool or WebSearchTool()
        self._fetch_tool = fetch_tool or WebFetchTool()
        self._proxy_url = proxy_url or os.environ.get("WEB_ACCESS_PROXY_URL", "http://127.0.0.1:3456")
        self._proxy_timeout = proxy_timeout or float(os.environ.get("WEB_ACCESS_PROXY_TIMEOUT", "30"))
        self._proxy_client: WebAccessProxyClient | None = None

    @property
    def name(self) -> str:
        return "web_access"

    @property
    def description(self) -> str:
        return (
            "Unified native web-access tool. Use this first for web work: search, fetch page content, "
            "open URLs in the current browser, click/type on webpages, wait for elements, extract text/HTML, run JavaScript, "
            "capture screenshots, and inspect the current page."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "open",
                        "search",
                        "fetch",
                        "navigate",
                        "new_tab",
                        "click",
                        "type",
                        "scroll",
                        "screenshot",
                        "get_text",
                        "get_html",
                        "wait_for",
                        "evaluate",
                        "get_url",
                        "get_title",
                        "close",
                    ],
                    "description": "Web action to perform.",
                },
                "query": {"type": "string", "description": "Search query for action=search."},
                "count": {"type": "integer", "description": "Search result count for action=search.", "minimum": 1, "maximum": 10},
                "url": {"type": "string", "description": "URL for navigate/new_tab/fetch."},
                "extractMode": {"type": "string", "enum": ["markdown", "text"], "description": "Fetch extract mode."},
                "maxChars": {"type": "integer", "minimum": 100, "description": "Max chars for fetch."},
                "selector": {"type": "string", "description": "CSS selector for page interaction or extraction."},
                "text": {"type": "string", "description": "Text to type when action=type."},
                "timeout": {"type": "integer", "description": "Timeout in milliseconds for wait/click actions."},
                "direction": {"type": "string", "enum": ["up", "down"], "description": "Scroll direction."},
                "distance": {"type": "integer", "description": "Scroll distance in pixels."},
                "path": {"type": "string", "description": "Screenshot output path."},
                "script": {"type": "string", "description": "JavaScript code for evaluate."},
            },
            "required": ["action"],
        }

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name=self.name,
            description=self.description,
            category=ToolCategory.WEB,
            tags=["web", "browser", "search", "fetch", "web-access"],
        )

    def _proxy(self) -> WebAccessProxyClient:
        if self._proxy_client is None:
            self._proxy_client = WebAccessProxyClient(self._proxy_url, timeout=self._proxy_timeout)
        return self._proxy_client

    async def execute(self, action: str, **kwargs: Any) -> str:
        normalized_action = str(action or "").strip().lower()
        if normalized_action == "open":
            url = str(kwargs.get("url") or "").strip()
            return await self._open_in_current_browser(url)
        if normalized_action == "search":
            query = str(kwargs.get("query") or "").strip()
            return await self._search_tool.execute(query=query, count=kwargs.get("count"))
        if normalized_action == "fetch":
            url = str(kwargs.get("url") or "").strip()
            return await self._fetch_tool.execute(
                url=url,
                extractMode=str(kwargs.get("extractMode") or "markdown"),
                maxChars=kwargs.get("maxChars"),
            )

        proxy = self._proxy()
        if not await proxy.is_available():
            return (
                f"Error: web-access proxy is unavailable at {self._proxy_url}. "
                "Start the proxy first, or fall back to browser/web_fetch as needed."
            )

        try:
            return await self._execute_proxy_action(proxy, normalized_action, **kwargs)
        except ProxyUnsupportedError as exc:
            return f"Error: web-access action '{normalized_action}' is not supported by the proxy: {exc}"
        except ProxyActionError as exc:
            return f"Error: web_access {normalized_action} failed: {exc}"
        except ProxyUnavailableError as exc:
            return f"Error: web-access proxy is unavailable: {exc}"

    @staticmethod
    def _applescript_quote(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    async def _run_local_command(self, *args: str) -> tuple[int, str, str]:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return (
            int(process.returncode or 0),
            stdout.decode("utf-8", errors="ignore").strip(),
            stderr.decode("utf-8", errors="ignore").strip(),
        )

    async def _open_in_current_browser(self, url: str) -> str:
        is_valid, error = _validate_url(url)
        if not is_valid:
            return f"Error: Invalid URL for web_access open: {error}"

        if sys.platform == "darwin":
            quoted_url = self._applescript_quote(url)
            script = f'''
set targetUrl to "{quoted_url}"
set browserName to ""
tell application "System Events"
    try
        set browserName to name of first application process whose frontmost is true
    end try
end tell
if browserName is "Google Chrome" or browserName is "Arc" or browserName is "Microsoft Edge" or browserName is "Brave Browser" then
    tell application browserName
        activate
        if (count of windows) is 0 then make new window
        tell front window
            set newTab to make new tab with properties {{URL:targetUrl}}
            set active tab index to (index of newTab)
        end tell
    end tell
    return browserName
else if browserName is "Safari" then
    tell application "Safari"
        activate
        if (count of windows) is 0 then make new document
        tell front window
            set newTab to make new tab with properties {{URL:targetUrl}}
            set current tab to newTab
        end tell
    end tell
    return browserName
else
    do shell script "open " & quoted form of targetUrl
    if browserName is "" then
        return "default"
    end if
    return browserName
end if
'''
            returncode, stdout, stderr = await self._run_local_command("osascript", "-e", script)
            if returncode == 0:
                browser_name = stdout or "current browser"
                return f"✅ 已在当前浏览器打开新页签: {url}\n浏览器: {browser_name}"

            fallback_code, _, fallback_error = await self._run_local_command("open", url)
            if fallback_code == 0:
                return f"✅ 已在默认浏览器打开: {url}"
            return f"Error: web_access open failed: {stderr or fallback_error or 'unknown error'}"

        if sys.platform.startswith("linux"):
            returncode, _, stderr = await self._run_local_command("xdg-open", url)
            if returncode == 0:
                return f"✅ 已在默认浏览器打开: {url}"
            return f"Error: web_access open failed: {stderr or 'unknown error'}"

        if sys.platform.startswith("win"):
            returncode, _, stderr = await self._run_local_command("cmd", "/c", "start", "", url)
            if returncode == 0:
                return f"✅ 已在默认浏览器打开: {url}"
            return f"Error: web_access open failed: {stderr or 'unknown error'}"

        return f"Error: web_access open is not supported on platform '{sys.platform}'"

    async def _execute_proxy_action(self, proxy: WebAccessProxyClient, action: str, **kwargs: Any) -> str:
        selector = str(kwargs.get("selector") or "").strip()
        timeout = int(kwargs.get("timeout") or 30000)

        if action == "navigate":
            url = str(kwargs.get("url") or "").strip()
            await proxy.navigate(url)
            title = await proxy.get_title()
            return f"✅ 已打开: {url}\n标题: {title}"
        if action == "new_tab":
            url = str(kwargs.get("url") or "").strip()
            await proxy.new_tab(url)
            return f"✅ 新标签页已打开: {url}" if url else "✅ 新标签页已打开"
        if action == "click":
            if _requires_browser_fallback(selector):
                return f"Error: selector '{selector}' uses Playwright-only syntax. Use browser tool as fallback."
            await proxy.wait_for(selector, timeout)
            await proxy.click(selector)
            return f"✅ 已点击元素: {selector}"
        if action == "type":
            if _requires_browser_fallback(selector):
                return f"Error: selector '{selector}' uses Playwright-only syntax. Use browser tool as fallback."
            await proxy.wait_for(selector, timeout)
            await proxy.type(selector, str(kwargs.get("text") or ""))
            return f"✅ 已输入文本: {str(kwargs.get('text') or '')[:50]}..."
        if action == "scroll":
            direction = "up" if str(kwargs.get("direction") or "").lower() == "up" else "down"
            distance = int(kwargs.get("distance") or 500)
            await proxy.scroll(direction, distance)
            return f"✅ 已向{direction}滚动 {distance} 像素"
        if action == "screenshot":
            path = str(kwargs.get("path") or f"logs/web-access-screenshot-{int(time.time())}.png")
            saved_path = await proxy.screenshot(path)
            return f"✅ 截图已保存: {saved_path}"
        if action == "get_text":
            if _requires_browser_fallback(selector):
                return f"Error: selector '{selector}' uses Playwright-only syntax. Use browser tool as fallback."
            return await proxy.get_text(selector or "body")
        if action == "get_html":
            if _requires_browser_fallback(selector):
                return f"Error: selector '{selector}' uses Playwright-only syntax. Use browser tool as fallback."
            return await proxy.get_html(selector or "body")
        if action == "wait_for":
            if _requires_browser_fallback(selector):
                return f"Error: selector '{selector}' uses Playwright-only syntax. Use browser tool as fallback."
            await proxy.wait_for(selector, timeout)
            return f"✅ 元素已出现: {selector}"
        if action == "evaluate":
            return await proxy.eval(str(kwargs.get("script") or ""))
        if action == "get_url":
            return await proxy.get_url()
        if action == "get_title":
            return await proxy.get_title()
        if action == "close":
            result = await proxy.close_target()
            return "✅ web-access 页面已关闭" if result != "noop" else "⚠️ 当前没有活动页面"
        return f"Error: Unknown web_access action '{action}'."


class WebSearchTool(Tool):
    """Search the web using multiple providers: Tavily, LangSearch, Brave Search, or DuckDuckGo."""
    
    name = "web_search"
    description = "Search the web. Returns titles, URLs, and snippets."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "count": {"type": "integer", "description": "Results (1-10)", "minimum": 1, "maximum": 10}
        },
        "required": ["query"]
    }
    
    def __init__(
        self,
        provider: str = "duckduckgo",
        tavily_enabled: bool = True,
        langsearch_enabled: bool = True,
        api_key: str | None = None,
        max_results: int = 5
    ):
        self._init_provider = provider
        self._init_tavily_enabled = tavily_enabled
        self._init_langsearch_enabled = langsearch_enabled
        self._init_api_key = api_key
        self.max_results = max_results

    @property
    def tavily_enabled(self) -> bool:
        if self._init_tavily_enabled is not None:
            return bool(self._init_tavily_enabled)
        return os.environ.get("WEB_SEARCH_TAVILY_ENABLED", "1").strip().lower() not in {"0", "false", "off", "no"}

    @property
    def langsearch_enabled(self) -> bool:
        if self._init_langsearch_enabled is not None:
            return bool(self._init_langsearch_enabled)
        return os.environ.get("WEB_SEARCH_LANGSEARCH_ENABLED", "1").strip().lower() not in {"0", "false", "off", "no"}

    @staticmethod
    def _browser_cdp_suggestion() -> str:
        return (
            "如果静默搜索仍失败，建议改用打开浏览器（CDP）方式继续搜索。"
        )

    @property
    def provider(self) -> str:
        """Resolve provider at call time."""
        provider = self._init_provider or os.environ.get("WEB_SEARCH_PROVIDER", "duckduckgo")
        if str(provider).lower() == "tavily" and not self.tavily_enabled:
            return "duckduckgo"
        if str(provider).lower() == "langsearch" and not self.langsearch_enabled:
            return "duckduckgo"
        return provider

    @property
    def api_key(self) -> str:
        """Resolve API key at call time."""
        if self._init_api_key:
            return self._init_api_key
        provider = self.provider
        if provider == "tavily":
            return os.environ.get("TAVILY_API_KEY", "")
        elif provider == "langsearch":
            return os.environ.get("LANGSEARCH_API_KEY", "")
        elif provider == "brave":
            return os.environ.get("BRAVE_API_KEY", "")
        return ""

    async def execute(self, query: str, count: int | None = None, **kwargs: Any) -> str:
        n = min(max(count or self.max_results, 1), 10)
        provider = self.provider.lower()

        if provider == "tavily" and self.tavily_enabled and self.api_key:
            result = await self._search_tavily(query, n)
            return self._finalize_search_output(result, query)

        if provider == "langsearch" and self.langsearch_enabled and self.api_key:
            result = await self._search_langsearch(query, n)
            return self._finalize_search_output(result, query)

        if provider == "brave" and self.api_key:
            result = await self._search_brave(query, n)
            if result:
                return self._finalize_search_output(result, query)
            return self._finalize_search_output(await self._search_duckduckgo(query, n), query)

        return self._finalize_search_output(await self._search_duckduckgo(query, n), query)

    def _finalize_search_output(self, result: str, query: str) -> str:
        normalized = str(result or "").strip()
        if not normalized:
            return f"No results for: {query}\n\n{self._browser_cdp_suggestion()}"
        if normalized.startswith("No results for:"):
            return f"{normalized}\n\n{self._browser_cdp_suggestion()}"
        if normalized.startswith("Error"):
            return f"{normalized}\n\n{self._browser_cdp_suggestion()}"
        return normalized

    async def _search_tavily(self, query: str, max_results: int) -> str:
        """Search using Tavily API."""
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.api_key,
                        "query": query,
                        "max_results": max_results,
                        "include_answer": False,
                        "include_raw_content": False,
                    },
                    headers={"Content-Type": "application/json"},
                    timeout=15.0
                )
                r.raise_for_status()
            
            data = r.json()
            results = data.get("results", [])
            
            if not results:
                return f"No results for: {query}"
            
            lines = [f"Results for: {query} (via Tavily)\n"]
            for i, item in enumerate(results[:max_results], 1):
                lines.append(f"{i}. {item.get('title', '')}\n   {item.get('url', '')}")
                if content := item.get("content"):
                    lines.append(f"   {content}")
            
            return "\n".join(lines)
        except Exception as e:
            return f"Error searching Tavily: {e}"

    async def _search_langsearch(self, query: str, max_results: int) -> str:
        """Search using LangSearch Web Search API."""
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    "https://api.langsearch.com/v1/web-search",
                    json={"query": query, "count": max_results},
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}",
                    },
                    timeout=15.0,
                )
                r.raise_for_status()

            data = r.json()
            payload = data.get("data", {}) if isinstance(data, dict) else {}
            web_pages = payload.get("webPages", {}) if isinstance(payload, dict) else {}
            results = web_pages.get("value", []) if isinstance(web_pages, dict) else []

            if not results:
                return f"No results for: {query}"

            lines = [f"Results for: {query} (via LangSearch)\n"]
            for i, item in enumerate(results[:max_results], 1):
                title = item.get("name") or item.get("title") or ""
                url = item.get("url") or ""
                snippet = item.get("snippet") or item.get("summary") or item.get("description") or ""
                lines.append(f"{i}. {title}\n   {url}")
                if snippet:
                    lines.append(f"   {snippet}")

            return "\n".join(lines)
        except Exception as e:
            return f"Error searching LangSearch: {e}"

    async def _search_brave(self, query: str, max_results: int) -> str | None:
        """Search using Brave Search API."""
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": query, "count": max_results},
                    headers={"Accept": "application/json", "X-Subscription-Token": self.api_key},
                    timeout=10.0
                )
                r.raise_for_status()
            
            results = r.json().get("web", {}).get("results", [])
            if not results:
                return None
            
            lines = [f"Results for: {query} (via Brave)\n"]
            for i, item in enumerate(results[:max_results], 1):
                lines.append(f"{i}. {item.get('title', '')}\n   {item.get('url', '')}")
                if desc := item.get("description"):
                    lines.append(f"   {desc}")
            
            return "\n".join(lines)
        except Exception:
            return None

    async def _search_duckduckgo(self, query: str, max_results: int) -> str:
        """Search using DuckDuckGo HTML version (no API key required)."""
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": USER_AGENT},
                    timeout=10.0
                )
                r.raise_for_status()
            
            results = self._parse_ddg_html(r.text)
            
            if not results:
                return f"No results for: {query}"
            
            lines = [f"Results for: {query} (via DuckDuckGo)\n"]
            for i, item in enumerate(results[:max_results], 1):
                lines.append(f"{i}. {item['title']}\n   {item['url']}")
                if item.get('snippet'):
                    lines.append(f"   {item['snippet']}")
            
            return "\n".join(lines)
        except Exception as e:
            return f"Error searching DuckDuckGo: {e}"

    def _parse_ddg_html(self, html_content: str) -> list[dict]:
        """Parse DuckDuckGo HTML results."""
        results = []
        
        result_pattern = r'<div class="result[^"]*"[^>]*>(.*?)</div>'
        blocks = re.findall(result_pattern, html_content, re.DOTALL)
        
        for block in blocks[:20]:
            title_match = re.search(r'<a[^>]*class="result__a"[^>]*>(.*?)</a>', block, re.DOTALL)
            title = _strip_tags(title_match.group(1)) if title_match else ""
            
            url_match = re.search(r'<a[^>]*class="result__url"[^>]*>(.*?)</a>', block, re.DOTALL)
            url = _strip_tags(url_match.group(1)).strip() if url_match else ""
            
            snippet_match = re.search(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', block, re.DOTALL)
            snippet = _strip_tags(snippet_match.group(1)) if snippet_match else ""
            
            if title and url:
                results.append({
                    'title': title,
                    'url': url,
                    'snippet': snippet
                })
        
        return results


class WebFetchTool(Tool):
    """Fetch and extract content from a URL using Readability."""
    
    name = "web_fetch"
    description = "Fetch URL and extract readable content (HTML → markdown/text)."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
            "extractMode": {"type": "string", "enum": ["markdown", "text"], "default": "markdown"},
            "maxChars": {"type": "integer", "minimum": 100}
        },
        "required": ["url"]
    }
    
    def __init__(self, max_chars: int = 50000):
        self.max_chars = max_chars
    
    async def execute(self, url: str, extractMode: str = "markdown", maxChars: int | None = None, **kwargs: Any) -> str:
        from readability import Document

        max_chars = maxChars or self.max_chars

        is_valid, error_msg = _validate_url(url)
        if not is_valid:
            return json.dumps({"error": f"URL validation failed: {error_msg}", "url": url}, ensure_ascii=False)

        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                max_redirects=MAX_REDIRECTS,
                timeout=30.0
            ) as client:
                r = await client.get(url, headers={"User-Agent": USER_AGENT})
                r.raise_for_status()
            
            ctype = r.headers.get("content-type", "")
            
            if "application/json" in ctype:
                text, extractor = json.dumps(r.json(), indent=2, ensure_ascii=False), "json"
            elif "text/html" in ctype or r.text[:256].lower().startswith(("<!doctype", "<html")):
                doc = Document(r.text)
                content = self._to_markdown(doc.summary()) if extractMode == "markdown" else _strip_tags(doc.summary())
                text = f"# {doc.title()}\n\n{content}" if doc.title() else content
                extractor = "readability"
            else:
                text, extractor = r.text, "raw"
            
            truncated = len(text) > max_chars
            if truncated:
                text = text[:max_chars]
            
            return json.dumps({"url": url, "finalUrl": str(r.url), "status": r.status_code,
                              "extractor": extractor, "truncated": truncated, "length": len(text), "text": text}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e), "url": url}, ensure_ascii=False)
    
    def _to_markdown(self, html_content: str) -> str:
        """Convert HTML to markdown."""
        text = re.sub(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',
                      lambda m: f'[{_strip_tags(m[2])}]({m[1]})', html_content, flags=re.I)
        text = re.sub(r'<h([1-6])[^>]*>([\s\S]*?)</h\1>',
                      lambda m: f'\n{"#" * int(m[1])} {_strip_tags(m[2])}\n', text, flags=re.I)
        text = re.sub(r'<li[^>]*>([\s\S]*?)</li>', lambda m: f'\n- {_strip_tags(m[1])}', text, flags=re.I)
        text = re.sub(r'</(p|div|section|article)>', '\n\n', text, flags=re.I)
        text = re.sub(r'<(br|hr)\s*/?>', '\n', text, flags=re.I)
        return _normalize(_strip_tags(text))
