"""
浏览器自动化 MCP Server
提供浏览器控制工具，让 AI 可以自动化操作浏览器

启动方式：
    python -m horbot.mcp.browser_server

或添加到 config.json:
    "tools": {
        "mcp_servers": {
            "browser": {
                "command": "python",
                "args": ["-m", "horbot.mcp.browser_server"],
                "tool_timeout": 120
            }
        }
    }
"""

import asyncio
import base64
import json
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from mcp.server.fastmcp import FastMCP

# 创建 MCP Server 实例
mcp = FastMCP("browser-automation")

# 全局浏览器实例
_playwright = None
_browser = None
_page = None


async def get_browser():
    """获取或创建浏览器实例（异步）"""
    global _playwright, _browser, _page
    
    if _browser is None:
        try:
            from playwright.async_api import async_playwright
            
            _playwright = await async_playwright().start()
            
            # 尝试使用系统 Chrome，如果失败则回退到 Chromium
            try:
                _browser = await _playwright.chromium.launch(
                    channel="chrome",  # 使用系统安装的 Chrome
                    headless=False,
                    args=[
                        '--start-maximized',
                        '--disable-blink-features=AutomationControlled'
                    ]
                )
                logger.info("使用系统 Chrome 启动浏览器")
            except Exception as e:
                logger.warning(f"无法使用系统 Chrome: {e}，尝试使用 Chromium")
                _browser = await _playwright.chromium.launch(
                    headless=False,
                    args=[
                        '--start-maximized',
                        '--disable-blink-features=AutomationControlled'
                    ]
                )
                logger.info("使用 Chromium 启动浏览器")
        except ImportError:
            raise RuntimeError(
                "Playwright 未安装。请运行：\n"
                "  pip install playwright\n"
                "  playwright install chromium"
            )
    
    return _browser


async def get_page():
    """获取或创建页面实例（异步）"""
    global _page
    
    browser = await get_browser()
    
    if _page is None:
        context = await browser.new_context(
            viewport=None,  # 使用完整窗口
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        _page = await context.new_page()
        logger.info("新页面已创建")
    
    return _page


@mcp.tool()
async def browser_navigate(url: str) -> str:
    """
    导航到指定 URL
    
    Args:
        url: 要访问的网址
        
    Returns:
        操作结果
    """
    try:
        page = await get_page()
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        title = await page.title()
        return f"✅ 已打开: {url}\n标题: {title}"
    except Exception as e:
        return f"❌ 导航失败: {str(e)}"


@mcp.tool()
async def browser_click(selector: str, timeout: int = 10000) -> str:
    """
    点击页面元素
    
    Args:
        selector: CSS 选择器 (如 'button.submit', '#login-btn', 'text=登录')
        timeout: 等待超时时间(毫秒)
        
    Returns:
        操作结果
    """
    try:
        page = await get_page()
        
        # 等待元素出现
        element = await page.wait_for_selector(selector, timeout=timeout)
        
        # 模拟人类行为：移动到元素
        box = await element.bounding_box()
        if box:
            x = box['x'] + box['width'] / 2
            y = box['y'] + box['height'] / 2
            await page.mouse.move(x, y, steps=10)
        
        # 点击
        await element.click()
        
        return f"✅ 已点击元素: {selector}"
    except Exception as e:
        return f"❌ 点击失败: {str(e)}"


@mcp.tool()
async def browser_type(selector: str, text: str, delay: int = 50) -> str:
    """
    在输入框中输入文本（模拟人工打字）
    
    Args:
        selector: CSS 选择器
        text: 要输入的文本
        delay: 每个字符的延迟(毫秒)，模拟人类打字速度
        
    Returns:
        操作结果
    """
    try:
        page = await get_page()
        
        # 点击输入框
        await page.click(selector)
        
        # 清空现有内容
        await page.fill(selector, '')
        
        # 模拟人类打字
        await page.type(selector, text, delay=delay)
        
        return f"✅ 已输入文本: {text[:50]}..."
    except Exception as e:
        return f"❌ 输入失败: {str(e)}"


@mcp.tool()
async def browser_scroll(direction: str = "down", distance: int = 500) -> str:
    """
    滚动页面
    
    Args:
        direction: 滚动方向 ('up' 或 'down')
        distance: 滚动距离(像素)
        
    Returns:
        操作结果
    """
    try:
        page = await get_page()
        
        if direction == "down":
            await page.mouse.wheel(0, distance)
        else:
            await page.mouse.wheel(0, -distance)
        
        return f"✅ 已向{direction}滚动 {distance} 像素"
    except Exception as e:
        return f"❌ 滚动失败: {str(e)}"


@mcp.tool()
async def browser_screenshot(path: str = "") -> str:
    """
    截取当前页面截图
    
    Args:
        path: 保存路径(可选，默认保存到 logs 目录)
        
    Returns:
        截图保存路径
    """
    try:
        page = await get_page()
        
        if not path:
            import time
            path = f"logs/browser-screenshot-{int(time.time())}.png"
        
        # 确保目录存在
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        # 截图
        await page.screenshot(path=path)
        
        return f"✅ 截图已保存: {path}"
    except Exception as e:
        return f"❌ 截图失败: {str(e)}"


@mcp.tool()
async def browser_get_text(selector: str = "body") -> str:
    """
    获取页面元素的文本内容
    
    Args:
        selector: CSS 选择器(默认获取整个页面)
        
    Returns:
        元素的文本内容
    """
    try:
        page = await get_page()
        text = await page.text_content(selector)
        return text or "(无内容)"
    except Exception as e:
        return f"❌ 获取文本失败: {str(e)}"


@mcp.tool()
async def browser_get_html(selector: str = "body") -> str:
    """
    获取页面元素的 HTML
    
    Args:
        selector: CSS 选择器(默认获取整个页面)
        
    Returns:
        元素的 HTML
    """
    try:
        page = await get_page()
        html = await page.inner_html(selector)
        
        # 限制返回长度
        if len(html) > 10000:
            return html[:10000] + "\n\n... (内容过长，已截断)"
        
        return html
    except Exception as e:
        return f"❌ 获取 HTML 失败: {str(e)}"


@mcp.tool()
async def browser_wait_for(selector: str, timeout: int = 30000) -> str:
    """
    等待元素出现
    
    Args:
        selector: CSS 选择器
        timeout: 超时时间(毫秒)
        
    Returns:
        操作结果
    """
    try:
        page = await get_page()
        await page.wait_for_selector(selector, timeout=timeout)
        return f"✅ 元素已出现: {selector}"
    except Exception as e:
        return f"❌ 等待超时: {str(e)}"


@mcp.tool()
async def browser_evaluate(script: str) -> str:
    """
    在页面中执行 JavaScript 代码
    
    Args:
        script: JavaScript 代码
        
    Returns:
        执行结果
    """
    try:
        page = await get_page()
        result = await page.evaluate(script)
        
        if result is None:
            return "✅ 执行成功"
        
        # 格式化结果
        if isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        return str(result)
    except Exception as e:
        return f"❌ 执行失败: {str(e)}"


@mcp.tool()
async def browser_get_url() -> str:
    """
    获取当前页面 URL
    
    Returns:
        当前 URL
    """
    try:
        page = await get_page()
        return page.url
    except Exception as e:
        return f"❌ 获取 URL 失败: {str(e)}"


@mcp.tool()
async def browser_get_title() -> str:
    """
    获取当前页面标题
    
    Returns:
        页面标题
    """
    try:
        page = await get_page()
        return await page.title()
    except Exception as e:
        return f"❌ 获取标题失败: {str(e)}"


@mcp.tool()
async def browser_close() -> str:
    """
    关闭浏览器
    
    Returns:
        操作结果
    """
    global _playwright, _browser, _page
    
    try:
        if _browser:
            await _browser.close()
            _browser = None
            _page = None
            if _playwright:
                await _playwright.stop()
                _playwright = None
            return "✅ 浏览器已关闭"
        return "⚠️ 浏览器未运行"
    except Exception as e:
        return f"❌ 关闭失败: {str(e)}"


@mcp.tool()
def browser_new_tab(url: str = "") -> str:
    """
    打开新标签页
    
    Args:
        url: 可选的 URL
        
    Returns:
        操作结果
    """
    try:
        browser = get_browser()
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()
        
        if url:
            page.goto(url, wait_until='domcontentloaded')
            return f"✅ 新标签页已打开: {url}"
        
        return "✅ 新标签页已打开"
    except Exception as e:
        return f"❌ 打开失败: {str(e)}"


@mcp.tool()
def browser_press_key(key: str) -> str:
    """
    按下键盘按键
    
    Args:
        key: 按键名称 (如 'Enter', 'Escape', 'Tab', 'ArrowDown' 等)
        
    Returns:
        操作结果
    """
    try:
        page = get_page()
        page.keyboard.press(key)
        return f"✅ 已按下: {key}"
    except Exception as e:
        return f"❌ 按键失败: {str(e)}"


@mcp.tool()
def browser_find_elements(selector: str) -> str:
    """
    查找页面上的元素并返回信息
    
    Args:
        selector: CSS 选择器
        
    Returns:
        找到的元素数量和基本信息
    """
    try:
        page = get_page()
        elements = page.query_selector_all(selector)
        
        if not elements:
            return f"未找到匹配的元素: {selector}"
        
        result = [f"找到 {len(elements)} 个元素:\n"]
        
        for i, elem in enumerate(elements[:10]):  # 最多显示前10个
            text = elem.text_content()
            if text:
                text = text.strip()[:50]
            tag = elem.evaluate('el => el.tagName')
            result.append(f"{i+1}. <{tag}> {text}")
        
        if len(elements) > 10:
            result.append(f"\n... 还有 {len(elements) - 10} 个元素")
        
        return "\n".join(result)
    except Exception as e:
        return f"❌ 查找失败: {str(e)}"


@mcp.tool()
def browser_hover(selector: str) -> str:
    """
    鼠标悬停在元素上
    
    Args:
        selector: CSS 选择器
        
    Returns:
        操作结果
    """
    try:
        page = get_page()
        page.hover(selector)
        return f"✅ 已悬停在元素上: {selector}"
    except Exception as e:
        return f"❌ 悬停失败: {str(e)}"


@mcp.tool()
def browser_goto_back() -> str:
    """
    后退到上一页
    
    Returns:
        操作结果
    """
    try:
        page = get_page()
        page.go_back()
        return f"✅ 已后退到上一页"
    except Exception as e:
        return f"❌ 后退失败: {str(e)}"


@mcp.tool()
def browser_goto_forward() -> str:
    """
    前进到下一页
    
    Returns:
        操作结果
    """
    try:
        page = get_page()
        page.go_forward()
        return f"✅ 已前进到下一页"
    except Exception as e:
        return f"❌ 前进失败: {str(e)}"


@mcp.tool()
def browser_reload() -> str:
    """
    刷新当前页面
    
    Returns:
        操作结果
    """
    try:
        page = get_page()
        page.reload()
        return f"✅ 页面已刷新"
    except Exception as e:
        return f"❌ 刷新失败: {str(e)}"


if __name__ == "__main__":
    # 启动 MCP Server
    logger.info("启动浏览器自动化 MCP Server...")
    mcp.run()