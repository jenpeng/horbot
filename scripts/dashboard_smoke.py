#!/usr/bin/env python3
"""Browser smoke test for dashboard summary rendering."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from chat_ui_smoke import fetch_json, reset_chat_browser_state
from playwright_browser import launch_browser


DEFAULT_URL = "http://127.0.0.1:3000/"


async def open_dashboard(page: Any, url: str) -> None:
    await reset_chat_browser_state(page)
    await page.goto(url, wait_until="networkidle", timeout=120000)
    await page.get_by_role("heading", name="Dashboard").wait_for(timeout=30000)


async def run_dashboard_smoke(url: str = DEFAULT_URL, headless: bool = True) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "scenario": "dashboard",
        "summary_loaded": False,
        "status_card_visible": False,
        "activity_card_visible": False,
        "channel_card_visible": False,
        "system_info_card_visible": False,
        "alert_visible": False,
        "activity_visible": False,
        "channel_visible": False,
        "channel_status_label_visible": False,
        "online_badge_matches": False,
        "summary": {},
        "errors": [],
    }

    async with async_playwright() as playwright:
        browser = await launch_browser(playwright, headless=headless)
        page = await browser.new_page(viewport={"width": 1440, "height": 1100})

        try:
            await open_dashboard(page, url)
            summary = await fetch_json(page, "/api/dashboard/summary")
            result["summary"] = {
                "generated_at": summary.get("generated_at"),
                "channel_counts": (summary.get("channels") or {}).get("counts") or {},
                "alert_count": len(summary.get("alerts") or []),
                "activity_count": len(summary.get("recent_activities") or []),
            }
            result["summary_loaded"] = bool(summary.get("generated_at")) and bool(summary.get("system_status"))

            await page.locator("[data-testid='dashboard-system-status-card']").first.wait_for(timeout=30000)
            result["status_card_visible"] = True
            await page.locator("[data-testid='dashboard-activity-card']").first.wait_for(timeout=30000)
            result["activity_card_visible"] = True
            await page.locator("[data-testid='dashboard-channel-card']").first.wait_for(timeout=30000)
            result["channel_card_visible"] = True
            await page.locator("[data-testid='dashboard-system-info-card']").first.wait_for(timeout=30000)
            result["system_info_card_visible"] = True

            alerts = summary.get("alerts") or []
            if alerts:
                alert_id = str(alerts[0].get("id", ""))
                alert_title = str(alerts[0].get("title", ""))
                try:
                    await page.locator(f"[data-testid='dashboard-alert-{alert_id}']").first.wait_for(timeout=15000)
                    result["alert_visible"] = True
                except PlaywrightTimeoutError:
                    if alert_title:
                        await page.get_by_text(alert_title, exact=False).first.wait_for(timeout=15000)
                        result["alert_visible"] = True

            activities = summary.get("recent_activities") or []
            if activities:
                activity_id = str(activities[0].get("id", ""))
                activity_message = str(activities[0].get("message", ""))
                try:
                    await page.locator(f"[data-testid='dashboard-activity-{activity_id}']").first.wait_for(timeout=15000)
                    result["activity_visible"] = True
                except PlaywrightTimeoutError:
                    if activity_message:
                        await page.get_by_text(activity_message, exact=False).first.wait_for(timeout=15000)
                        result["activity_visible"] = True

            channels = (summary.get("channels") or {}).get("items") or []
            if channels:
                channel = channels[0]
                channel_name = str(channel.get("name", ""))
                channel_row = page.locator(f"[data-testid='dashboard-channel-{channel_name}']").first
                await channel_row.wait_for(timeout=30000)
                result["channel_visible"] = True
                row_text = await channel_row.inner_text()
                result["channel_status_label_visible"] = str(channel.get("status_label", "")) in row_text

            counts = (summary.get("channels") or {}).get("counts") or {}
            online_count = counts.get("online")
            if isinstance(online_count, int):
                result["online_badge_matches"] = await page.evaluate(
                    """(count) => {
                        return Array.from(document.querySelectorAll('*'))
                          .some((node) => node.textContent?.trim() === `${count} Online`);
                    }""",
                    online_count,
                )

        except PlaywrightTimeoutError as exc:
            result["errors"].append(f"timeout:{exc}")
        finally:
            await browser.close()

    if not result["summary_loaded"]:
        result["errors"].append("dashboard_summary_not_loaded")
    if not result["status_card_visible"]:
        result["errors"].append("dashboard_status_card_not_visible")
    if not result["activity_card_visible"]:
        result["errors"].append("dashboard_activity_card_not_visible")
    if not result["channel_card_visible"]:
        result["errors"].append("dashboard_channel_card_not_visible")
    if not result["system_info_card_visible"]:
        result["errors"].append("dashboard_system_info_card_not_visible")
    if result["summary"].get("alert_count", 0) > 0 and not result["alert_visible"]:
        result["errors"].append("dashboard_alert_not_visible")
    if result["summary"].get("activity_count", 0) > 0 and not result["activity_visible"]:
        result["errors"].append("dashboard_activity_not_visible")
    channel_counts = result["summary"].get("channel_counts") or {}
    if channel_counts.get("total", 0) > 0 and not result["channel_visible"]:
        result["errors"].append("dashboard_channel_row_not_visible")
    if channel_counts.get("total", 0) > 0 and not result["channel_status_label_visible"]:
        result["errors"].append("dashboard_channel_status_label_not_visible")
    if not result["online_badge_matches"]:
        result["errors"].append("dashboard_online_badge_mismatch")

    result["ok"] = not result["errors"]
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run dashboard smoke test in Chrome.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--headed", action="store_true", help="Run with a visible browser window.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = asyncio.run(run_dashboard_smoke(url=args.url, headless=not args.headed))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
