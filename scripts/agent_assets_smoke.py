#!/usr/bin/env python3
"""Browser smoke test for agent asset management on the Teams page."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from typing import Any

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import Page
from playwright.async_api import async_playwright

from chat_ui_smoke import fetch_json, reset_chat_browser_state
from playwright_browser import launch_browser


DEFAULT_URL = "http://127.0.0.1:3000/teams"


async def put_json(page: Page, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    return await page.evaluate(
        """async ({ requestPath, requestPayload }) => {
            const response = await fetch(requestPath, {
              method: 'PUT',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(requestPayload),
            });
            return {
              ok: response.ok,
              status: response.status,
              data: await response.json(),
            };
        }""",
        {"requestPath": path, "requestPayload": payload},
    )


async def open_teams(page: Page, url: str) -> None:
    await reset_chat_browser_state(page)
    await page.goto(url, wait_until="networkidle", timeout=120000)
    await page.get_by_role("heading", name="团队管理").wait_for(timeout=30000)


async def select_agent(page: Page, agent_id: str) -> None:
    selector = page.locator(f'[data-testid="agent-list-select"][data-agent-id="{agent_id}"]')
    await selector.wait_for(timeout=30000)
    await selector.click()
    await page.locator(f'[data-testid="agent-detail-view"][data-agent-id="{agent_id}"]').wait_for(timeout=30000)


async def run_agent_assets_smoke(url: str = DEFAULT_URL, headless: bool = True) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "scenario": "agent-assets",
        "agent_id": "",
        "agent_name": "",
        "detail_view_visible": False,
        "selection_synced_to_url": False,
        "selection_persisted_after_reload": False,
        "workspace_visible": False,
        "soul_saved": False,
        "user_saved": False,
        "summary_saved": False,
        "summary_persisted_after_reload": False,
        "persisted_after_reload": False,
        "debug_summary_values": {},
        "console_errors": [],
        "errors": [],
    }

    original_soul = ""
    original_user = ""
    selected_agent_id = ""

    try:
        async with async_playwright() as playwright:
            browser = await launch_browser(playwright, headless=headless)
            page = await browser.new_page(viewport={"width": 1440, "height": 1100})

            console_errors: list[str] = []

            def handle_console(message: Any) -> None:
                if message.type == "error":
                    console_errors.append(message.text)

            page.on("console", handle_console)

            try:
                await open_teams(page, url)

                agents_payload = await fetch_json(page, "/api/agents")
                agents = agents_payload.get("agents") or []
                if not agents:
                    raise RuntimeError("No agents available for agent asset smoke test")

                selected = next((agent for agent in agents if agent.get("is_main")), agents[0])
                selected_agent_id = str(selected.get("id") or "")
                result["agent_id"] = selected_agent_id
                result["agent_name"] = str(selected.get("name") or "")
                if not selected_agent_id:
                    raise RuntimeError("Selected agent has no id")

                bootstrap_payload = await fetch_json(page, f"/api/agents/{selected_agent_id}/bootstrap-files")
                original_soul = str((((bootstrap_payload.get("files") or {}).get("soul") or {}).get("content")) or "")
                original_user = str((((bootstrap_payload.get("files") or {}).get("user") or {}).get("content")) or "")

                await select_agent(page, selected_agent_id)
                result["detail_view_visible"] = True
                result["selection_synced_to_url"] = f"agent={selected_agent_id}" in page.url

                workspace_text = await page.locator('[data-testid="agent-detail-view"]').inner_text()
                result["workspace_visible"] = "实际工作区" in workspace_text

                marker = uuid.uuid4().hex[:8]
                soul_content = f"# Smoke Soul {marker}\n\nagent_id: {selected_agent_id}\n"
                user_content = f"# Smoke User {marker}\n\npreferred_language: zh-CN\n"
                summary_identity = f"定位：Smoke {marker}"
                summary_role = f"职责：验证摘要保存 {marker}"
                summary_pref = f"偏好：优先中文 {marker}"

                soul_editor = page.locator('[data-testid="agent-soul-editor"]')
                user_editor = page.locator('[data-testid="agent-user-editor"]')
                await soul_editor.fill(soul_content)
                await page.locator('[data-testid="agent-save-soul"]').click()
                await page.get_by_text("SOUL.md 已保存").wait_for(timeout=30000)
                result["soul_saved"] = True

                await user_editor.fill(user_content)
                await page.locator('[data-testid="agent-save-user"]').click()
                await page.get_by_text("USER.md 已保存").wait_for(timeout=30000)
                result["user_saved"] = True

                await page.locator('[data-testid="agent-summary-identity"]').fill(summary_identity)
                await page.locator('[data-testid="agent-summary-role_focus"]').fill(summary_role)
                await page.locator('[data-testid="agent-summary-user_preferences"]').fill(summary_pref)
                await page.locator('[data-testid="agent-save-summary"]').click()
                await page.get_by_text("配置摘要已保存，并已同步写回 SOUL.md / USER.md").wait_for(timeout=30000)
                result["summary_saved"] = True

                await page.reload(wait_until="networkidle", timeout=120000)
                await page.get_by_role("heading", name="团队管理").wait_for(timeout=30000)
                detail_view = page.locator(f'[data-testid="agent-detail-view"][data-agent-id="{selected_agent_id}"]')
                try:
                    await detail_view.wait_for(timeout=5000)
                    result["selection_persisted_after_reload"] = True
                except PlaywrightTimeoutError:
                    await select_agent(page, selected_agent_id)

                persisted_soul = await page.locator('[data-testid="agent-soul-editor"]').input_value()
                persisted_user = await page.locator('[data-testid="agent-user-editor"]').input_value()
                persisted_identity = await page.locator('[data-testid="agent-summary-identity"]').input_value()
                persisted_role = await page.locator('[data-testid="agent-summary-role_focus"]').input_value()
                persisted_pref = await page.locator('[data-testid="agent-summary-user_preferences"]').input_value()
                result["persisted_after_reload"] = (
                    soul_content.strip() in persisted_soul
                    and user_content.strip() in persisted_user
                )
                result["summary_persisted_after_reload"] = (
                    summary_identity in persisted_identity
                    and summary_role in persisted_role
                    and summary_pref in persisted_pref
                )
                result["debug_summary_values"] = {
                    "identity": persisted_identity,
                    "role_focus": persisted_role,
                    "user_preferences": persisted_pref,
                }

            except PlaywrightTimeoutError as exc:
                result["errors"].append(f"timeout:{exc}")
            finally:
                result["console_errors"] = console_errors
                if selected_agent_id:
                    try:
                        await put_json(
                            page,
                            f"/api/agents/{selected_agent_id}/bootstrap-files/soul",
                            {"content": original_soul},
                        )
                        await put_json(
                            page,
                            f"/api/agents/{selected_agent_id}/bootstrap-files/user",
                            {"content": original_user},
                        )
                    except Exception as exc:  # pragma: no cover - best effort cleanup
                        result["errors"].append(f"cleanup_failed:{exc}")
                await browser.close()
    except RuntimeError as exc:
        result["errors"].append(f"runtime:{exc}")

    if not result["detail_view_visible"]:
        result["errors"].append("agent_detail_view_missing")
    if not result["selection_synced_to_url"]:
        result["errors"].append("agent_selection_not_synced_to_url")
    if not result["selection_persisted_after_reload"]:
        result["errors"].append("agent_selection_not_persisted_after_reload")
    if not result["workspace_visible"]:
        result["errors"].append("agent_workspace_summary_missing")
    if not result["soul_saved"]:
        result["errors"].append("agent_soul_save_failed")
    if not result["user_saved"]:
        result["errors"].append("agent_user_save_failed")
    if not result["summary_saved"]:
        result["errors"].append("agent_summary_save_failed")
    if not result["persisted_after_reload"]:
        result["errors"].append("agent_asset_not_persisted_after_reload")
    if not result["summary_persisted_after_reload"]:
        result["errors"].append("agent_summary_not_persisted_after_reload")

    result["ok"] = not result["errors"]
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Teams/Agent asset smoke test in Chrome.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--headed", action="store_true", help="Run with a visible browser window.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = asyncio.run(run_agent_assets_smoke(url=args.url, headless=not args.headed))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
