#!/usr/bin/env python3
"""Browser smoke test to ensure completed DM agents do not show onboarding banner."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from playwright.async_api import async_playwright

from chat_ui_smoke import fetch_json, open_chat, reload_chat, select_conversation
from playwright_browser import launch_browser


DEFAULT_URL = "http://127.0.0.1:3000/chat"
TARGET_AGENT_ID = "horbot-02"
TARGET_AGENT_NAME = "袭人"
BANNER_TEXT = "首次私聊引导"


async def run_setup_banner_smoke(url: str = DEFAULT_URL, headless: bool = True) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "agent_id": TARGET_AGENT_ID,
        "agent_name": TARGET_AGENT_NAME,
        "api_setup_required": None,
        "api_bootstrap_setup_pending": None,
        "banner_visible_before_refresh": None,
        "banner_visible_after_refresh": None,
        "errors": [],
    }

    async with async_playwright() as playwright:
        browser = await launch_browser(playwright, headless=headless)
        page = await browser.new_page(viewport={"width": 1440, "height": 1100})
        try:
            await open_chat(page, url)
            agents_data = await fetch_json(page, "/api/agents")
            agent = next((item for item in agents_data.get("agents") or [] if item.get("id") == TARGET_AGENT_ID), None)
            if not agent:
                raise RuntimeError(f"Agent {TARGET_AGENT_ID} not found")

            result["api_setup_required"] = bool(agent.get("setup_required"))
            result["api_bootstrap_setup_pending"] = bool(agent.get("bootstrap_setup_pending"))

            if result["api_setup_required"] or result["api_bootstrap_setup_pending"]:
                result["errors"].append("api_still_marks_agent_as_pending")

            await select_conversation(page, TARGET_AGENT_NAME)
            banner = page.get_by_text(BANNER_TEXT)
            result["banner_visible_before_refresh"] = await banner.count() > 0
            if result["banner_visible_before_refresh"]:
                result["errors"].append("banner_visible_before_refresh")

            await reload_chat(page)
            await select_conversation(page, TARGET_AGENT_NAME)
            banner = page.get_by_text(BANNER_TEXT)
            result["banner_visible_after_refresh"] = await banner.count() > 0
            if result["banner_visible_after_refresh"]:
                result["errors"].append("banner_visible_after_refresh")

            result["ok"] = not result["errors"]
            return result
        finally:
            await browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run chat onboarding-banner smoke test in Chrome.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()

    result = asyncio.run(run_setup_banner_smoke(url=args.url, headless=not args.headed))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
