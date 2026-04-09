#!/usr/bin/env python3
"""Browser smoke test for Configuration page save/reload flows."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import Page
from playwright.async_api import async_playwright

from chat_ui_smoke import fetch_json, reset_chat_browser_state
from playwright_browser import launch_browser


DEFAULT_URL = "http://127.0.0.1:3000/config"


async def patch_json(page: Page, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    return await page.evaluate(
        """async ({ requestPath, requestPayload }) => {
            const response = await fetch(requestPath, {
              method: 'PATCH',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(requestPayload),
            });
            return await response.json();
        }""",
        {"requestPath": path, "requestPayload": payload},
    )


async def open_config(page: Page, url: str) -> None:
    await reset_chat_browser_state(page)
    await page.goto(url, wait_until="networkidle", timeout=120000)
    await page.get_by_role("heading", name="Configuration").wait_for(timeout=30000)


async def wait_for_max_results(page: Page, expected_value: int, timeout_ms: int = 30000) -> dict[str, Any]:
    deadline = asyncio.get_running_loop().time() + timeout_ms / 1000
    latest: dict[str, Any] = {}
    while asyncio.get_running_loop().time() < deadline:
        latest = await fetch_json(page, "/api/config")
        search = (((latest.get("tools") or {}).get("web") or {}).get("search") or {})
        if int(search.get("maxResults") or 0) == expected_value:
            return latest
        await page.wait_for_timeout(500)
    raise PlaywrightTimeoutError(f"Timed out waiting for maxResults={expected_value}")


async def wait_for_provider_state(
    page: Page,
    provider_name: str,
    *,
    expected_has_api_key: bool,
    expected_api_base: str,
    timeout_ms: int = 30000,
) -> dict[str, Any]:
    deadline = asyncio.get_running_loop().time() + timeout_ms / 1000
    latest: dict[str, Any] = {}
    while asyncio.get_running_loop().time() < deadline:
      latest = await fetch_json(page, "/api/config")
      provider = ((latest.get("providers") or {}).get(provider_name) or {})
      has_api_key = bool(provider.get("hasApiKey"))
      api_base = str(provider.get("apiBase") or "")
      if has_api_key == expected_has_api_key and api_base == expected_api_base:
          return latest
      await page.wait_for_timeout(500)
    raise PlaywrightTimeoutError(
        f"Timed out waiting for provider={provider_name} state hasApiKey={expected_has_api_key} apiBase={expected_api_base}"
    )


def _normalize_workspace_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


async def _workspace_input(page: Page):
    modern = page.locator("label", has_text="Default Workspace").locator("xpath=following::input[1]").first
    legacy = page.locator("label", has_text="Workspace Path").locator("xpath=following::input[1]").first
    if await modern.count():
        return modern
    return legacy


async def _max_results_input(page: Page):
    return page.locator("label", has_text="Max Results").locator("xpath=following::input[1]").first


async def _provider_card(page: Page, provider_name: str):
    return page.locator(f"[data-testid='provider-card'][data-provider-name='{provider_name}']").first


async def run_config_smoke(url: str = DEFAULT_URL, headless: bool = True) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "scenario": "config",
        "config_heading_visible": False,
        "validation_visible": False,
        "reload_discard_confirmed": False,
        "workspace_reverted_after_reload": False,
        "web_search_saved": False,
        "web_search_persisted_after_refresh": False,
        "original": {},
        "updated": {},
        "save_button_enabled_before_click": False,
        "web_search_patch_seen": False,
        "web_search_patch_status": None,
        "provider_set_saved": False,
        "provider_clear_saved": False,
        "provider_test_target": "",
        "console_errors": [],
        "errors": [],
    }

    original_workspace = ""
    original_max_results = 5
    original_provider_api_base = ""
    provider_test_target = ""
    provider_api_base = "https://example.invalid/v1"

    try:
        async with async_playwright() as playwright:
            browser = await launch_browser(playwright, headless=headless)
            page = await browser.new_page(viewport={"width": 1440, "height": 1100})

            console_errors: list[str] = []

            def handle_console(message: Any) -> None:
                if message.type == "error":
                    console_errors.append(message.text)

            async def handle_response(response: Any) -> None:
                if "/api/config/web-search" in response.url and response.request.method == "PATCH":
                    result["web_search_patch_seen"] = True
                    result["web_search_patch_status"] = response.status

            page.on("console", handle_console)
            page.on("response", handle_response)

            try:
                await open_config(page, url)
                result["config_heading_visible"] = True

                config = await fetch_json(page, "/api/config")
                search = ((config.get("tools") or {}).get("web") or {}).get("search") or {}
                defaults = ((config.get("agents") or {}).get("defaults") or {})
                original_workspace = _normalize_workspace_value(defaults.get("workspace"))
                original_max_results = int(search.get("maxResults") or 5)
                result["original"] = {
                    "workspace": original_workspace,
                    "max_results": original_max_results,
                }
                providers = config.get("providers") or {}
                provider_test_target = next(
                    (
                        name
                        for name, provider in providers.items()
                        if not provider.get("hasApiKey") and not provider.get("apiBase")
                    ),
                    "",
                )
                if not provider_test_target:
                    raise RuntimeError("No suitable provider without API key/apiBase available for config smoke")
                result["provider_test_target"] = provider_test_target
                original_provider_api_base = str((providers.get(provider_test_target) or {}).get("apiBase") or "")

                await page.get_by_text("配置体检", exact=False).first.wait_for(timeout=30000)
                result["validation_visible"] = True

                workspace_input = await _workspace_input(page)
                await workspace_input.wait_for(timeout=30000)
                unsaved_workspace = f"{original_workspace or '.horbot/agents/main/workspace'}-smoke"
                await workspace_input.fill(unsaved_workspace)
                await page.get_by_role("button", name="重新加载").click()
                await page.get_by_role("heading", name="放弃未保存修改？").wait_for(timeout=15000)
                result["reload_discard_confirmed"] = True
                await page.get_by_role("button", name="重新加载").last.click()
                await page.wait_for_timeout(1000)
                reverted_value = await workspace_input.input_value()
                result["workspace_reverted_after_reload"] = reverted_value == original_workspace

                max_results_input = await _max_results_input(page)
                await max_results_input.wait_for(timeout=30000)
                new_max_results = 9 if original_max_results != 9 else 8
                await max_results_input.fill(str(new_max_results))
                save_button = page.get_by_role("button", name="保存 Web Search 配置")
                await save_button.wait_for(timeout=30000)
                await page.wait_for_timeout(300)
                result["save_button_enabled_before_click"] = await save_button.is_enabled()
                await save_button.click()

                updated_config = await wait_for_max_results(page, new_max_results)
                updated_search = (((updated_config.get("tools") or {}).get("web") or {}).get("search") or {})
                result["updated"] = {
                    "max_results": int(updated_search.get("maxResults") or 0),
                }
                result["web_search_saved"] = int(updated_search.get("maxResults") or 0) == new_max_results

                await page.reload(wait_until="networkidle", timeout=120000)
                await page.get_by_role("heading", name="Configuration").wait_for(timeout=30000)

                provider_card = await _provider_card(page, provider_test_target)
                await provider_card.wait_for(timeout=30000)
                await provider_card.locator("[data-testid='provider-card-toggle']").click()
                await provider_card.locator("[data-testid='provider-api-key-mode-replace']").click()
                await provider_card.locator("[data-testid='provider-card-api-key-input']").fill("smoke-provider-secret")
                await provider_card.locator("[data-testid='provider-card-api-base-input']").fill(provider_api_base)
                await provider_card.locator("[data-testid='provider-card-save']").click()

                await wait_for_provider_state(
                    page,
                    provider_test_target,
                    expected_has_api_key=True,
                    expected_api_base=provider_api_base,
                )
                result["provider_set_saved"] = True

                await page.reload(wait_until="networkidle", timeout=120000)
                provider_card = await _provider_card(page, provider_test_target)
                await provider_card.wait_for(timeout=30000)
                await provider_card.locator("[data-testid='provider-card-toggle']").click()
                await provider_card.locator("[data-testid='provider-api-key-mode-clear']").click()
                await provider_card.locator("[data-testid='provider-card-api-base-input']").fill("")
                await provider_card.locator("[data-testid='provider-card-save']").click()

                await wait_for_provider_state(
                    page,
                    provider_test_target,
                    expected_has_api_key=False,
                    expected_api_base="",
                )
                result["provider_clear_saved"] = True

                await page.reload(wait_until="networkidle", timeout=120000)
                await page.get_by_role("heading", name="Configuration").wait_for(timeout=30000)
                max_results_input = await _max_results_input(page)
                await max_results_input.wait_for(timeout=30000)
                result["web_search_persisted_after_refresh"] = (await max_results_input.input_value()) == str(new_max_results)

            except PlaywrightTimeoutError as exc:
                result["errors"].append(f"timeout:{exc}")
            finally:
                result["console_errors"] = console_errors
                try:
                    await patch_json(page, "/api/config/web-search", {"maxResults": original_max_results})
                    await patch_json(page, "/api/config/agent-defaults", {"workspace": original_workspace})
                    if provider_test_target:
                        await page.evaluate(
                            """async ({ providerName, apiBase }) => {
                                const response = await fetch(`/api/config/providers/${providerName}`, {
                                  method: 'PUT',
                                  headers: { 'Content-Type': 'application/json' },
                                  body: JSON.stringify({
                                    clearApiKey: true,
                                    apiBase,
                                  }),
                                });
                                return await response.json();
                            }""",
                            {"providerName": provider_test_target, "apiBase": original_provider_api_base},
                        )
                except Exception as exc:  # pragma: no cover - best effort cleanup
                    result["errors"].append(f"cleanup_failed:{exc}")

                await browser.close()
    except RuntimeError as exc:
        result["errors"].append(f"runtime:{exc}")

    if not result["config_heading_visible"]:
        result["errors"].append("config_heading_not_visible")
    if not result["validation_visible"]:
        result["errors"].append("config_validation_not_visible")
    if not result["reload_discard_confirmed"]:
        result["errors"].append("config_reload_confirmation_missing")
    if not result["workspace_reverted_after_reload"]:
        result["errors"].append("config_workspace_not_reverted_after_reload")
    if not result["web_search_saved"]:
        result["errors"].append("config_web_search_save_failed")
    if not result["web_search_persisted_after_refresh"]:
        result["errors"].append("config_web_search_not_persisted_after_refresh")
    if not result["provider_set_saved"]:
        result["errors"].append("config_provider_set_save_failed")
    if not result["provider_clear_saved"]:
        result["errors"].append("config_provider_clear_save_failed")

    result["ok"] = not result["errors"]
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Configuration page smoke test in Chrome.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--headed", action="store_true", help="Run with a visible browser window.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = asyncio.run(run_config_smoke(url=args.url, headless=not args.headed))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
