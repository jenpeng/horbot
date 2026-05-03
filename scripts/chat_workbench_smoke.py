#!/usr/bin/env python3
"""Browser smoke test for the chat task workbench interactions."""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from playwright.async_api import async_playwright, expect

from playwright_browser import launch_browser


DEFAULT_URL = "http://127.0.0.1:3000/chat?agent=main"
LATEST_REQUEST = "Workbench smoke create a clean PPT summary"


def _mock_history_payload() -> dict[str, Any]:
    return {
        "conversation_id": "dm_main",
        "conversation": {
            "id": "dm_main",
            "type": "dm",
            "target_id": "main",
            "targetId": "main",
            "name": "Main",
            "agent_ids": ["main"],
            "agentIds": ["main"],
        },
        "messages": [
            {
                "id": "workbench-smoke-user",
                "role": "user",
                "content": LATEST_REQUEST,
                "timestamp": "2026-05-03T00:00:00",
                "files": [
                    {
                        "fileId": "workbench-smoke-file",
                        "filename": "workbench-smoke.pptx",
                        "originalName": "workbench-smoke.pptx",
                        "mimeType": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        "size": 2048,
                        "category": "office",
                        "url": "/api/files/workbench-smoke-file",
                    }
                ],
            },
            {
                "id": "workbench-smoke-assistant",
                "role": "assistant",
                "content": "Created the summary for the smoke test.",
                "timestamp": "2026-05-03T00:00:01",
                "execution_steps": [
                    {
                        "id": "workbench-smoke-step",
                        "type": "tool_call",
                        "title": "Run officecli",
                        "status": "success",
                        "timestamp": "2026-05-03T00:00:01",
                        "details": {"toolName": "officecli"},
                    }
                ],
                "metadata": {
                    "agent_id": "main",
                    "agent_name": "Main",
                    "turn_id": "workbench-smoke-turn",
                    "request_id": "workbench-smoke-request",
                },
            },
        ],
        "page": {
            "limit": 80,
            "returned_messages": 2,
            "total_messages": 2,
            "has_more_before": False,
            "has_more_after": False,
        },
    }


async def run_chat_workbench_smoke(
    url: str = DEFAULT_URL,
    *,
    headless: bool = True,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "scenario": "chat-workbench",
        "workbench_visible": False,
        "use_summary_prefilled": False,
        "search_request_prefilled": False,
        "details_expanded": False,
        "quick_action_prefilled": False,
        "errors": [],
    }

    async with async_playwright() as playwright:
        browser = await launch_browser(playwright, headless=headless)
        page = await browser.new_page(viewport={"width": 1440, "height": 1100})

        async def mock_messages(route: Any) -> None:
            await route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(_mock_history_payload(), ensure_ascii=False),
            )

        try:
            await page.add_init_script(
                "() => window.localStorage.setItem('horbot-ui-locale', 'en')"
            )
            await page.route("**/api/conversations/dm_main/messages**", mock_messages)
            await page.goto(url, wait_until="domcontentloaded", timeout=120000)

            await expect(page.get_by_text("Task Workbench")).to_be_visible(timeout=30000)
            await expect(page.get_by_text(f"Latest request: {LATEST_REQUEST}")).to_be_visible(timeout=30000)
            result["workbench_visible"] = True

            textarea = page.locator("textarea").first
            await page.get_by_role("button", name="Use summary").click(timeout=10000)
            await expect(textarea).to_contain_text("Task Workbench", timeout=10000)
            summary_value = await textarea.input_value()
            if LATEST_REQUEST not in summary_value:
                raise AssertionError("Use summary did not include the latest request")
            result["use_summary_prefilled"] = True

            await page.get_by_role("button", name="Search request").click(timeout=10000)
            search_input = page.get_by_placeholder("Type keywords to quickly locate messages")
            await expect(search_input).to_have_value(LATEST_REQUEST, timeout=10000)
            await expect(page.get_by_text("1 matches in loaded history")).to_be_visible(timeout=10000)
            result["search_request_prefilled"] = True

            await page.get_by_role("button", name="Details").click(timeout=10000)
            workbench_details = page.get_by_test_id("chat-workbench-details")
            await expect(workbench_details).to_be_visible(timeout=10000)
            await expect(workbench_details.get_by_text("officecli")).to_be_visible(timeout=10000)
            result["details_expanded"] = True

            await page.get_by_role("button", name="Review files").click(timeout=10000)
            await expect(textarea).to_contain_text("attached files", timeout=10000)
            quick_action_value = await textarea.input_value()
            if "office" not in quick_action_value:
                raise AssertionError("Review files quick action did not include the file category")
            result["quick_action_prefilled"] = True

            result["ok"] = True
        except Exception as exc:  # pragma: no cover - smoke diagnostics path
            result["errors"].append(str(exc))
            raise
        finally:
            await browser.close()

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run chat task workbench browser smoke test in Chrome.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--headed", action="store_true", help="Run with a visible browser window.")
    args = parser.parse_args()

    result = asyncio.run(run_chat_workbench_smoke(args.url, headless=not args.headed))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
