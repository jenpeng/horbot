#!/usr/bin/env python3
"""Capture real Web UI screenshots for README and docs."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from playwright.async_api import Page, async_playwright

from chat_ui_smoke import fetch_json, reset_chat_browser_state
from playwright_browser import launch_browser


DEFAULT_BASE_URL = "http://127.0.0.1:3000"
LOCALE_STORAGE_KEY = "horbot-ui-locale"

PAGE_HEADINGS = {
    "en": {
        "dashboard": "Dashboard",
        "skills": "Skills & MCP",
        "teams": "Team Management",
        "chat": "Conversations",
    },
    "zh-CN": {
        "dashboard": "控制台",
        "skills": "Skills & MCP",
        "teams": "团队管理",
        "chat": "对话",
    },
    "th": {
        "dashboard": "แดชบอร์ด",
        "skills": "Skills & MCP",
        "teams": "จัดการทีม",
        "chat": "บทสนทนา",
    },
}


async def wait_for_heading(page: Page, text: str) -> None:
    await page.get_by_role("heading", name=text).first.wait_for(timeout=45000)


async def open_dashboard(page: Page, base_url: str, locale: str) -> None:
    await reset_chat_browser_state(page)
    await page.goto(f"{base_url}/", wait_until="networkidle", timeout=120000)
    await wait_for_heading(page, PAGE_HEADINGS[locale]["dashboard"])
    await page.locator("[data-testid='dashboard-system-status-card']").first.wait_for(timeout=30000)


async def open_skills(page: Page, base_url: str, locale: str) -> None:
    await reset_chat_browser_state(page)
    await page.goto(f"{base_url}/skills", wait_until="networkidle", timeout=120000)
    await wait_for_heading(page, PAGE_HEADINGS[locale]["skills"])
    await page.wait_for_timeout(1500)


async def open_teams(page: Page, base_url: str, locale: str) -> None:
    await reset_chat_browser_state(page)
    await page.goto(f"{base_url}/teams", wait_until="networkidle", timeout=120000)
    await wait_for_heading(page, PAGE_HEADINGS[locale]["teams"])

    teams_payload = await fetch_json(page, "/api/teams")
    teams = teams_payload.get("teams") if isinstance(teams_payload, dict) else None
    if isinstance(teams, list) and teams:
        team_id = str((teams[0] or {}).get("id") or "").strip()
        if team_id:
            await page.goto(
                f"{base_url}/teams?team={team_id}",
                wait_until="networkidle",
                timeout=120000,
            )
            await wait_for_heading(page, PAGE_HEADINGS[locale]["teams"])
    await page.locator("[data-testid='team-detail-view'], [data-testid='agent-detail-view']").first.wait_for(timeout=30000)
    await page.wait_for_timeout(1500)


async def open_chat(page: Page, base_url: str, locale: str) -> None:
    await reset_chat_browser_state(page)
    await page.goto(f"{base_url}/chat", wait_until="networkidle", timeout=120000)
    await page.get_by_text(PAGE_HEADINGS[locale]["chat"], exact=True).first.wait_for(timeout=45000)

    teams_payload = await fetch_json(page, "/api/teams")
    teams = teams_payload.get("teams") if isinstance(teams_payload, dict) else None
    if isinstance(teams, list) and teams:
        team_id = str((teams[0] or {}).get("id") or "").strip()
        if team_id:
            await page.goto(
                f"{base_url}/chat?team={team_id}",
                wait_until="networkidle",
                timeout=120000,
            )
            await page.get_by_text(PAGE_HEADINGS[locale]["chat"], exact=True).first.wait_for(timeout=45000)
            try:
                await page.locator("[data-testid='chat-turn-card']").first.wait_for(timeout=20000)
            except Exception:
                await page.locator("[data-testid='chat-history-loading']").first.wait_for(timeout=10000)
    await page.wait_for_timeout(1500)


async def capture(output_dir: Path, base_url: str, headless: bool, locale: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as playwright:
        browser = await launch_browser(playwright, headless=headless)
        try:
            context = await browser.new_context(viewport={"width": 1600, "height": 1080}, device_scale_factor=1)
            await context.add_init_script(
                f"""
                (() => {{
                  try {{
                    window.localStorage.setItem({json.dumps(LOCALE_STORAGE_KEY)}, {json.dumps(locale)});
                  }} catch (error) {{
                    console.warn('Failed to set locale for screenshot capture:', error);
                  }}
                }})();
                """
            )
            page = await context.new_page()

            scenarios = [
                ("preview-dashboard.png", open_dashboard),
                ("preview-chat.png", open_chat),
                ("preview-skills.png", open_skills),
                ("preview-teams.png", open_teams),
            ]

            for filename, opener in scenarios:
                await opener(page, base_url, locale)
                await page.screenshot(path=str(output_dir / filename), full_page=False)
        finally:
            await browser.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture README screenshots from the running Horbot Web UI.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--output-dir", default="docs/assets")
    parser.add_argument("--locale", choices=tuple(PAGE_HEADINGS.keys()), default="en")
    parser.add_argument("--headed", action="store_true", help="Run with a visible browser window.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    asyncio.run(
        capture(
            output_dir=Path(args.output_dir),
            base_url=args.base_url.rstrip("/"),
            headless=not args.headed,
            locale=args.locale,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
