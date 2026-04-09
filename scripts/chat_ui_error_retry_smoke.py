#!/usr/bin/env python3
"""Browser smoke test for chat error state and retry flow."""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from typing import Any

from playwright.async_api import Page
from playwright.async_api import Route
from playwright.async_api import async_playwright

from chat_ui_smoke import (
    collect_tail_groups,
    fetch_json,
    find_reasoning_leak,
    open_chat,
    select_conversation,
    send_message,
)
from playwright_browser import launch_browser


DEFAULT_URL = "http://127.0.0.1:3000/chat"


async def resolve_dm_agent(page: Page) -> dict[str, Any]:
    agents_data = await fetch_json(page, "/api/agents")
    agents = agents_data.get("agents") or []
    if not agents:
        raise RuntimeError("No agents available for retry smoke test")

    for agent in agents:
        if agent.get("is_main"):
            return agent

    return agents[0]


def build_success_sse(agent_id: str, agent_name: str, content: str) -> str:
    events = [
        {
            "event": "agent_start",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "turn_id": "retry-turn",
            "message_id": "retry-message",
        },
        {
            "event": "progress",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "turn_id": "retry-turn",
            "message_id": "retry-message",
            "content": content,
        },
        {
            "event": "agent_done",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "turn_id": "retry-turn",
            "message_id": "retry-message",
            "content": content,
        },
        {
            "event": "done",
            "total_agents": 1,
        },
    ]
    return "".join(f"data: {json.dumps(event, ensure_ascii=False)}\n\n" for event in events)


async def run_error_retry_smoke(url: str = DEFAULT_URL, headless: bool = True) -> dict[str, Any]:
    expected_content = f"RETRY_UI_OK_{uuid.uuid4().hex[:8]}"
    result: dict[str, Any] = {
        "ok": False,
        "scenario": "dm-error-retry",
        "request_count": 0,
        "expected_content": expected_content,
        "error_visible": False,
        "retry_visible": False,
        "success_visible": False,
        "tail_groups": [],
        "reasoning_leak_marker": "",
        "errors": [],
    }

    async with async_playwright() as p:
        browser = await launch_browser(p, headless=headless)
        page = await browser.new_page(viewport={"width": 1440, "height": 1100})

        try:
            await open_chat(page, url)
            agent = await resolve_dm_agent(page)
            agent_id = str(agent["id"])
            agent_name = str(agent["name"])

            async def handle_stream(route: Route) -> None:
                result["request_count"] += 1
                if result["request_count"] == 1:
                    await route.fulfill(
                        status=503,
                        headers={"content-type": "application/json"},
                        body='{"detail":"mock upstream failure"}',
                    )
                    return

                await route.fulfill(
                    status=200,
                    headers={
                        "content-type": "text/event-stream",
                        "cache-control": "no-cache",
                        "x-request-id": "retry-mock-request",
                    },
                    body=build_success_sse(agent_id, agent_name, expected_content),
                )

            await page.route("**/api/chat/stream", handle_stream)

            await select_conversation(page, agent_name)
            await send_message(page, "请测试失败后重试")

            await page.wait_for_function(
                "() => document.body.innerText.includes('服务请求失败，请稍后重试。')",
                timeout=30000,
            )
            result["error_visible"] = True

            await page.locator("[data-testid='chat-message-group']").last.hover()
            retry_button = page.get_by_role("button", name="重试上一条").first
            await retry_button.wait_for(timeout=30000)
            result["retry_visible"] = True
            await retry_button.click()

            await page.wait_for_function(
                f"() => document.body.innerText.includes({json.dumps(expected_content)})",
                timeout=30000,
            )
            result["success_visible"] = True
            await page.wait_for_timeout(1000)
            result["tail_groups"] = await collect_tail_groups(page)
            result["reasoning_leak_marker"] = find_reasoning_leak(result["tail_groups"])

        finally:
            await browser.close()

    if result["request_count"] != 2:
        result["errors"].append(f"unexpected_request_count={result['request_count']}")
    if not result["error_visible"]:
        result["errors"].append("error_message_not_visible")
    if not result["retry_visible"]:
        result["errors"].append("retry_button_not_visible")
    if not result["success_visible"]:
        result["errors"].append("success_message_not_visible")
    if result["reasoning_leak_marker"]:
        result["errors"].append(f"reasoning_leak_detected={result['reasoning_leak_marker']}")

    result["ok"] = not result["errors"]
    return result


def main() -> int:
    result = asyncio.run(run_error_retry_smoke())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
