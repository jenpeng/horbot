#!/usr/bin/env python3
"""Browser performance smoke for key routes."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import Page
from playwright.async_api import async_playwright

from chat_ui_smoke import reset_chat_browser_state
from playwright_browser import launch_browser


DEFAULT_BASE_URL = "http://127.0.0.1:3000"


async def collect_route_metrics(page: Page) -> dict[str, Any]:
    return await page.evaluate(
        """
        () => {
          const navigation = performance.getEntriesByType('navigation')[0];
          const resources = performance.getEntriesByType('resource')
            .filter((entry) => entry.name.startsWith(window.location.origin));

          const scriptResources = resources.filter((entry) => {
            const name = entry.name || '';
            return name.endsWith('.js') || name.includes('.js?');
          });
          const cssResources = resources.filter((entry) => {
            const name = entry.name || '';
            return name.endsWith('.css') || name.includes('.css?');
          });

          const simplify = (entry) => ({
            name: entry.name.replace(window.location.origin, ''),
            transferSize: entry.transferSize || 0,
            decodedBodySize: entry.decodedBodySize || 0,
            duration: Number((entry.duration || 0).toFixed(2)),
          });

          return {
            navigation: navigation ? {
              domContentLoadedMs: Number((navigation.domContentLoadedEventEnd || 0).toFixed(2)),
              loadMs: Number((navigation.loadEventEnd || 0).toFixed(2)),
              durationMs: Number((navigation.duration || 0).toFixed(2)),
              responseEndMs: Number((navigation.responseEnd || 0).toFixed(2)),
            } : null,
            scripts: scriptResources.map(simplify),
            styles: cssResources.map(simplify),
            scriptCount: scriptResources.length,
            styleCount: cssResources.length,
            totalScriptBytes: scriptResources.reduce((sum, entry) => sum + (entry.decodedBodySize || 0), 0),
            totalStyleBytes: cssResources.reduce((sum, entry) => sum + (entry.decodedBodySize || 0), 0),
          };
        }
        """
    )


async def open_route(page: Page, url: str, ready_text: str, *, role: str = "heading") -> None:
    await reset_chat_browser_state(page)
    await page.goto(url, wait_until="networkidle", timeout=120000)
    if role == "heading":
        await page.get_by_role("heading", name=ready_text).wait_for(timeout=30000)
    elif role == "textbox":
        await page.locator("textarea").first.wait_for(timeout=30000)
    else:
        await page.get_by_text(ready_text, exact=False).first.wait_for(timeout=30000)


async def run_performance_smoke(base_url: str = DEFAULT_BASE_URL, headless: bool = True) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "scenario": "performance",
        "routes": [],
        "errors": [],
    }

    route_specs = [
        {
            "name": "dashboard",
            "url": f"{base_url}/",
            "ready_text": "Dashboard",
            "ready_role": "heading",
            "expected_chunks": ["DashboardPage"],
            "forbidden_chunks": [],
        },
        {
            "name": "chat",
            "url": f"{base_url}/chat",
            "ready_text": "textarea",
            "ready_role": "textbox",
            "expected_chunks": ["ChatPage"],
            "forbidden_chunks": [],
        },
        {
            "name": "skills",
            "url": f"{base_url}/skills",
            "ready_text": "Skills & MCP",
            "ready_role": "heading",
            "expected_chunks": ["SkillsPage"],
            "forbidden_chunks": ["MarkdownRenderer"],
        },
    ]

    async with async_playwright() as playwright:
        browser = await launch_browser(playwright, headless=headless)
        page = await browser.new_page(viewport={"width": 1440, "height": 1100})

        try:
            for spec in route_specs:
                route_result: dict[str, Any] = {
                    "name": spec["name"],
                    "url": spec["url"],
                    "resourceMode": "unknown",
                    "navigation": {},
                    "scriptCount": 0,
                    "styleCount": 0,
                    "totalScriptKB": 0.0,
                    "totalStyleKB": 0.0,
                    "scriptNames": [],
                    "expectedChunksPresent": True,
                    "forbiddenChunksAbsent": True,
                    "errors": [],
                }
                try:
                    await open_route(
                        page,
                        spec["url"],
                        spec["ready_text"],
                        role=spec["ready_role"],
                    )
                    metrics = await collect_route_metrics(page)
                    navigation = metrics.get("navigation") or {}
                    scripts = metrics.get("scripts") or []
                    styles = metrics.get("styles") or []
                    script_names = [str(item.get("name", "")) for item in scripts]

                    route_result["navigation"] = navigation
                    route_result["scriptCount"] = int(metrics.get("scriptCount") or 0)
                    route_result["styleCount"] = int(metrics.get("styleCount") or 0)
                    route_result["totalScriptKB"] = round((metrics.get("totalScriptBytes") or 0) / 1024, 2)
                    route_result["totalStyleKB"] = round((metrics.get("totalStyleBytes") or 0) / 1024, 2)
                    route_result["scriptNames"] = script_names
                    is_vite_dev = any("/node_modules/.vite/deps/" in name for name in script_names)
                    route_result["resourceMode"] = "vite-dev" if is_vite_dev else "built-chunks"

                    if not navigation:
                        route_result["errors"].append("navigation_metrics_missing")

                    if not is_vite_dev:
                        for chunk in spec["expected_chunks"]:
                            if not any(chunk in name for name in script_names):
                                route_result["expectedChunksPresent"] = False
                                route_result["errors"].append(f"missing_expected_chunk={chunk}")

                    for chunk in spec["forbidden_chunks"]:
                        if any(chunk in name for name in script_names):
                            route_result["forbiddenChunksAbsent"] = False
                            route_result["errors"].append(f"unexpected_initial_chunk={chunk}")

                except PlaywrightTimeoutError as exc:
                    route_result["errors"].append(f"timeout:{exc}")

                result["routes"].append(route_result)

        finally:
            await browser.close()

    for route in result["routes"]:
        if route.get("errors"):
            result["errors"].append(f"{route['name']}:{';'.join(route['errors'])}")

    result["ok"] = not result["errors"]
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run performance smoke test in Chrome.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--headed", action="store_true", help="Run with a visible browser window.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = asyncio.run(run_performance_smoke(base_url=args.base_url, headless=not args.headed))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
