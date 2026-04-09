#!/usr/bin/env python3
"""Browser smoke test for Skills page rendering and lazy markdown previews."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from typing import Any

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import Page
from playwright.async_api import async_playwright

from chat_ui_smoke import fetch_json, reset_chat_browser_state
from playwright_browser import launch_browser


DEFAULT_URL = "http://127.0.0.1:3000/skills"


def extract_preview_snippet(content: str, *, fallback: str = "") -> str:
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("```"):
            continue
        line = re.sub(r"^[#>\-\*\d\.\)\s`]+", "", line).strip()
        line = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", line)
        if len(line) >= 6:
            return line
    return fallback


async def open_skills(page: Page, url: str) -> None:
    await reset_chat_browser_state(page)
    await page.goto(url, wait_until="networkidle", timeout=120000)
    await page.get_by_role("heading", name="Skills & MCP").wait_for(timeout=30000)


async def run_skills_smoke(url: str = DEFAULT_URL, headless: bool = True) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "scenario": "skills",
        "skills_heading_visible": False,
        "skills_loaded": False,
        "skill_detail_opened": False,
        "skill_detail_preview_visible": False,
        "editor_opened": False,
        "editor_preview_visible": False,
        "preview_fallback_seen": False,
        "selected_skill_name": "",
        "detail_preview_snippet": "",
        "errors": [],
    }

    async with async_playwright() as playwright:
        browser = await launch_browser(playwright, headless=headless)
        page = await browser.new_page(viewport={"width": 1440, "height": 1100})

        try:
            await open_skills(page, url)
            result["skills_heading_visible"] = True

            skills_response = await fetch_json(page, "/api/skills")
            skills = skills_response.get("skills") or []
            result["skills_loaded"] = isinstance(skills, list)

            selected_skill = skills[0] if skills else None
            if selected_skill:
                skill_name = str(selected_skill.get("name") or "")
                result["selected_skill_name"] = skill_name
                skill_detail = await fetch_json(page, f"/api/skills/{skill_name}")
                preview_snippet = extract_preview_snippet(
                    str(skill_detail.get("content") or ""),
                    fallback=skill_name,
                )
                result["detail_preview_snippet"] = preview_snippet

                await page.get_by_text(skill_name, exact=True).first.click()
                await page.get_by_text(skill_name, exact=True).last.wait_for(timeout=30000)
                await page.get_by_text("Content", exact=True).last.wait_for(timeout=30000)
                result["skill_detail_opened"] = True
                if preview_snippet:
                    await page.get_by_text(preview_snippet, exact=False).last.wait_for(timeout=30000)
                    result["skill_detail_preview_visible"] = True
                await page.mouse.click(20, 20)
                await page.wait_for_timeout(500)

            await page.get_by_role("button", name="New Skill").click()
            await page.get_by_text("Create New Skill", exact=True).wait_for(timeout=30000)
            result["editor_opened"] = True

            fallback_locator = page.get_by_text("正在加载 Markdown 预览...", exact=False)
            if await fallback_locator.count() > 0:
                try:
                    await fallback_locator.first.wait_for(timeout=2000)
                    result["preview_fallback_seen"] = True
                except PlaywrightTimeoutError:
                    pass

            preview_panel = page.get_by_text("Preview", exact=True).locator("xpath=ancestor::div[contains(@class,'rounded-xl')][1]")
            await preview_panel.get_by_text("My Skill", exact=False).last.wait_for(timeout=30000)
            await preview_panel.get_by_text("Description of what this skill does.", exact=True).wait_for(timeout=30000)
            result["editor_preview_visible"] = True

        except PlaywrightTimeoutError as exc:
            result["errors"].append(f"timeout:{exc}")
        finally:
            await browser.close()

    if not result["skills_heading_visible"]:
        result["errors"].append("skills_heading_not_visible")
    if not result["skills_loaded"]:
        result["errors"].append("skills_not_loaded")
    if result["selected_skill_name"] and not result["skill_detail_opened"]:
        result["errors"].append("skill_detail_not_opened")
    if result["selected_skill_name"] and not result["skill_detail_preview_visible"]:
        result["errors"].append("skill_detail_preview_not_visible")
    if not result["editor_opened"]:
        result["errors"].append("skill_editor_not_opened")
    if not result["editor_preview_visible"]:
        result["errors"].append("skill_editor_preview_not_visible")

    result["ok"] = not result["errors"]
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Skills page smoke test in Chrome.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--headed", action="store_true", help="Run with a visible browser window.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = asyncio.run(run_skills_smoke(url=args.url, headless=not args.headed))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
