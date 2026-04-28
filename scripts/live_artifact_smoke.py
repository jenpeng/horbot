#!/usr/bin/env python3
"""Browser smoke test for chat Live Artifact rendering."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from playwright.async_api import async_playwright, expect

from playwright_browser import launch_browser


DEFAULT_URL = "http://127.0.0.1:3000/chat?agent=main"


def _mock_history_payload() -> dict[str, Any]:
    return {
        "conversation_id": "dm_main",
        "conversation": {
            "id": "dm_main",
            "type": "dm",
            "targetId": "main",
            "name": "Main",
            "agentIds": ["main"],
        },
        "messages": [
            {
                "id": "live-artifact-smoke-msg",
                "role": "assistant",
                "content": (
                    "Live Artifact browser smoke.\n\n"
                    "```horbot-renderable\n"
                    "{"
                    '"title":"Live Artifact Smoke",'
                    '"summary":"Real browser render into a sandboxed iframe.",'
                    '"template":"dashboard",'
                    '"items":[{"label":"Status","value":"OK","note":"Browser smoke"}],'
                    '"points":[{"label":"A","value":3},{"label":"B","value":7}],'
                    '"sections":[{"title":"Result","body":"Rendered from structured spec."}]'
                    "}\n"
                    "```"
                ),
                "timestamp": "2026-04-28T00:00:00",
                "metadata": {"agent_id": "main", "agent_name": "Main"},
            }
        ],
        "page": {
            "limit": 80,
            "returned_messages": 1,
            "total_messages": 1,
            "has_more_before": False,
            "has_more_after": False,
        },
    }


async def run_live_artifact_smoke(url: str = DEFAULT_URL, headless: bool = True) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "scenario": "live-artifact",
        "card_visible": False,
        "iframe_visible": False,
        "iframe_rendered": False,
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
            await page.route("**/api/conversations/dm_main/messages**", mock_messages)
            await page.goto(url, wait_until="domcontentloaded", timeout=120000)

            card = page.get_by_test_id("live-artifact-card").first
            await expect(card).to_be_visible(timeout=30000)
            await expect(card).to_contain_text("Live Artifact Smoke", timeout=10000)
            result["card_visible"] = True

            await card.get_by_role("button").last.click(timeout=10000)
            frame = page.get_by_test_id("live-artifact-frame").first
            await expect(frame).to_be_visible(timeout=30000)
            result["iframe_visible"] = True

            frame_handle = await frame.element_handle(timeout=30000)
            if frame_handle is None:
                raise RuntimeError("Live Artifact iframe element was not available")
            content_frame = await frame_handle.content_frame()
            if content_frame is None:
                raise RuntimeError("Live Artifact iframe content frame was not available")
            await expect(content_frame.locator("body")).to_contain_text("Live Artifact Smoke", timeout=30000)
            result["iframe_rendered"] = True
            result["ok"] = True
        except Exception as exc:  # pragma: no cover - smoke diagnostics path
            result["errors"].append(str(exc))
            raise
        finally:
            await browser.close()

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Live Artifact browser smoke test in Chrome.")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"Chat URL to test. Default: {DEFAULT_URL}")
    parser.add_argument("--headed", action="store_true", help="Run with a visible browser.")
    args = parser.parse_args()

    try:
        result = asyncio.run(run_live_artifact_smoke(url=args.url, headless=not args.headed))
    except Exception as exc:
        print(json.dumps({"ok": False, "scenario": "live-artifact", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
