#!/usr/bin/env python3
"""Browser smoke test for chat memory reference detail and navigation."""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from typing import Any

from playwright.async_api import Page
from playwright.async_api import Route
from playwright.async_api import async_playwright

from chat_ui_smoke import fetch_json, open_chat, select_conversation, send_message
from playwright_browser import launch_browser


DEFAULT_URL = "http://127.0.0.1:3000/chat"


async def resolve_targets(page: Page) -> tuple[dict[str, Any], dict[str, Any]]:
    agents_data = await fetch_json(page, "/api/agents")
    teams_data = await fetch_json(page, "/api/teams")
    agents = agents_data.get("agents") or []
    teams = teams_data.get("teams") or []
    if not agents:
        raise RuntimeError("No agents available for memory trace smoke test")
    if not teams:
        raise RuntimeError("No teams available for memory trace smoke test")

    agent = next((item for item in agents if item.get("is_main")), agents[0])
    team = teams[0]
    return agent, team


def build_team_memory_trace_sse(
    *,
    agent_id: str,
    agent_name: str,
    expected_content: str,
    team_id: str,
    team_name: str,
) -> str:
    memory_sources = [
        {
            "category": "team",
            "level": "Team",
            "file": "active_handoff.md",
            "path": f"/virtual/teams/{team_id}/shared_memory/active_handoff.md",
            "title": f"{team_id} / Active Handoff / Browser Handoff",
            "snippet": "Playwright timeout 已通过一次重试和上下文清理规避，下一步核对浏览器页面状态并回到团队管理确认交接。",
            "relevance": 0.91,
            "reasons": ["关键词命中", "团队共享记忆", "交接上下文"],
            "matched_terms": ["playwright", "timeout"],
            "section_index": 0,
            "origin": "team_shared",
            "owner_id": team_id,
            "scope": "active_handoff",
            "scope_label": "Active Handoff",
        }
    ]
    recall = {
        "latency_ms": 9.8,
        "candidates_count": 4,
        "selected_count": 1,
        "query": "playwright timeout 交接",
        "selected_memory_ids": [f"/virtual/teams/{team_id}/shared_memory/active_handoff.md#0"],
    }

    events = [
        {
            "event": "agent_start",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "turn_id": "memory-trace-turn",
            "message_id": "memory-trace-message",
        },
        {
            "event": "memory_sources",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "turn_id": "memory-trace-turn",
            "message_id": "memory-trace-message",
            "sources": memory_sources,
            "recall": recall,
        },
        {
            "event": "progress",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "turn_id": "memory-trace-turn",
            "message_id": "memory-trace-message",
            "content": expected_content,
        },
        {
            "event": "agent_done",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "turn_id": "memory-trace-turn",
            "message_id": "memory-trace-message",
            "content": expected_content,
            "memory_sources": memory_sources,
            "memory_recall": recall,
        },
        {
            "event": "done",
            "total_agents": 1,
            "team_name": team_name,
        },
    ]
    return "".join(f"data: {json.dumps(event, ensure_ascii=False)}\n\n" for event in events)


def build_agent_memory_trace_sse(
    *,
    agent_id: str,
    agent_name: str,
    expected_content: str,
) -> str:
    memory_sources = [
        {
            "category": "memory",
            "level": "L2",
            "file": "USER.md",
            "path": f"/virtual/agents/{agent_id}/workspace/USER.md",
            "title": f"{agent_name} / USER.md / Preferences",
            "snippet": "用户偏好：默认使用中文回复；涉及端到端验证时优先给出可复现结论，再补充原因和下一步建议。",
            "relevance": 0.88,
            "reasons": ["关键词命中", "用户偏好"],
            "matched_terms": ["中文", "验证"],
            "section_index": 0,
            "origin": "bootstrap_profile",
        }
    ]
    recall = {
        "latency_ms": 7.4,
        "candidates_count": 3,
        "selected_count": 1,
        "query": "中文 验证 偏好",
        "selected_memory_ids": [f"/virtual/agents/{agent_id}/workspace/USER.md#0"],
    }

    events = [
        {
            "event": "agent_start",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "turn_id": "memory-agent-turn",
            "message_id": "memory-agent-message",
        },
        {
            "event": "memory_sources",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "turn_id": "memory-agent-turn",
            "message_id": "memory-agent-message",
            "sources": memory_sources,
            "recall": recall,
        },
        {
            "event": "progress",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "turn_id": "memory-agent-turn",
            "message_id": "memory-agent-message",
            "content": expected_content,
        },
        {
            "event": "agent_done",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "turn_id": "memory-agent-turn",
            "message_id": "memory-agent-message",
            "content": expected_content,
            "memory_sources": memory_sources,
            "memory_recall": recall,
        },
        {
            "event": "done",
            "total_agents": 1,
        },
    ]
    return "".join(f"data: {json.dumps(event, ensure_ascii=False)}\n\n" for event in events)


async def open_memory_detail(page: Page) -> str:
    memory_summary = page.locator("summary").filter(has_text="记忆参考").last
    await memory_summary.wait_for(timeout=30000)
    await memory_summary.click()

    detail_button = page.locator("[data-testid='memory-source-open-detail']").first
    await detail_button.wait_for(timeout=30000)
    await detail_button.click()

    modal = page.locator("[data-testid='memory-source-detail-modal']").first
    await modal.wait_for(timeout=30000)
    return await modal.inner_text()


async def install_clipboard_stub(page: Page) -> None:
    await page.evaluate(
        """
        () => {
          window.__horbotCopiedText = '';
          const clipboard = navigator.clipboard;
          if (!clipboard) {
            return;
          }
          clipboard.writeText = async (text) => {
            window.__horbotCopiedText = String(text || '');
          };
        }
        """
    )


async def read_stubbed_clipboard(page: Page) -> str:
    return await page.evaluate("() => window.__horbotCopiedText || ''")


async def run_memory_trace_smoke(url: str = DEFAULT_URL, headless: bool = True) -> dict[str, Any]:
    expected_content = f"MEMORY_TRACE_OK_{uuid.uuid4().hex[:8]}"
    result: dict[str, Any] = {
        "ok": False,
        "scenario": "dm-memory-trace",
        "request_count": 0,
        "team_expected_content": expected_content,
        "agent_expected_content": f"MEMORY_AGENT_OK_{uuid.uuid4().hex[:8]}",
        "team_memory_reference_visible": False,
        "team_detail_modal_visible": False,
        "team_detail_contains_scope": False,
        "team_detail_contains_reason": False,
        "team_detail_contains_term": False,
        "team_description_visible": False,
        "team_copy_handoff_visible": False,
        "team_copy_handoff_ok": False,
        "team_copy_summary_visible": False,
        "team_copy_summary_ok": False,
        "team_copy_context_visible": False,
        "team_copy_context_ok": False,
        "team_open_chat_visible": False,
        "team_copy_path_visible": False,
        "team_open_chat_navigated": False,
        "team_navigate_button_visible": False,
        "navigated_to_team": False,
        "team_detail_visible": False,
        "team_focus_anchor_visible": False,
        "agent_memory_reference_visible": False,
        "agent_detail_modal_visible": False,
        "agent_detail_contains_file": False,
        "agent_detail_contains_reason": False,
        "agent_detail_contains_term": False,
        "agent_description_visible": False,
        "agent_copy_handoff_visible": False,
        "agent_copy_handoff_ok": False,
        "agent_copy_summary_visible": False,
        "agent_copy_summary_ok": False,
        "agent_copy_context_visible": False,
        "agent_copy_context_ok": False,
        "agent_open_chat_visible": False,
        "agent_copy_path_visible": False,
        "agent_navigate_button_visible": False,
        "navigated_to_agent": False,
        "agent_detail_visible": False,
        "agent_focus_anchor_visible": False,
        "errors": [],
    }

    async with async_playwright() as playwright:
        browser = await launch_browser(playwright, headless=headless)
        page = await browser.new_page(viewport={"width": 1440, "height": 1100})

        try:
            await open_chat(page, url)
            await install_clipboard_stub(page)
            agent, team = await resolve_targets(page)
            agent_id = str(agent["id"])
            agent_name = str(agent["name"])
            team_id = str(team["id"])
            team_name = str(team["name"])

            async def handle_stream(route: Route) -> None:
                result["request_count"] += 1
                if result["request_count"] in {1, 2}:
                    body = build_team_memory_trace_sse(
                        agent_id=agent_id,
                        agent_name=agent_name,
                        expected_content=expected_content,
                        team_id=team_id,
                        team_name=team_name,
                    )
                else:
                    body = build_agent_memory_trace_sse(
                        agent_id=agent_id,
                        agent_name=agent_name,
                        expected_content=result["agent_expected_content"],
                    )
                await route.fulfill(
                    status=200,
                    headers={
                        "content-type": "text/event-stream",
                        "cache-control": "no-cache",
                        "x-request-id": "memory-trace-mock-request",
                    },
                    body=body,
                )

            await page.route("**/api/chat/stream", handle_stream)

            await select_conversation(page, agent_name)
            await send_message(page, "请说明这次 playwight timeout 接力怎么处理")

            await page.wait_for_function(
                f"() => document.body.innerText.includes({json.dumps(expected_content)})",
                timeout=30000,
            )
            result["team_memory_reference_visible"] = True
            modal_text = await open_memory_detail(page)
            result["team_detail_modal_visible"] = True
            result["team_detail_contains_scope"] = "Active Handoff" in modal_text
            result["team_detail_contains_reason"] = "团队共享记忆" in modal_text
            result["team_detail_contains_term"] = "playwright" in modal_text.lower()
            result["team_description_visible"] = "团队共享记忆" in await page.locator("[data-testid='memory-source-description']").inner_text()
            copy_handoff_button = page.locator("[data-testid='memory-source-copy-handoff']").first
            await copy_handoff_button.wait_for(timeout=30000)
            result["team_copy_handoff_visible"] = True
            await copy_handoff_button.click()
            copied_text = await read_stubbed_clipboard(page)
            result["team_copy_handoff_ok"] = "[Relay Handoff]" in copied_text and "关键原因：" in copied_text and "来源范围：Active Handoff" in copied_text
            copy_summary_button = page.locator("[data-testid='memory-source-copy-summary']").first
            await copy_summary_button.wait_for(timeout=30000)
            result["team_copy_summary_visible"] = True
            await copy_summary_button.click()
            copied_text = await read_stubbed_clipboard(page)
            result["team_copy_summary_ok"] = "标题:" in copied_text and "命中原因:" in copied_text
            copy_context_button = page.locator("[data-testid='memory-source-copy-context']").first
            await copy_context_button.wait_for(timeout=30000)
            result["team_copy_context_visible"] = True
            await copy_context_button.click()
            copied_text = await read_stubbed_clipboard(page)
            result["team_copy_context_ok"] = "[Memory Reference Context]" in copied_text and "source_scope=Active Handoff" in copied_text
            open_chat_button = page.locator("[data-testid='memory-source-open-chat']").first
            await open_chat_button.wait_for(timeout=30000)
            result["team_open_chat_visible"] = True
            copy_path_button = page.locator("[data-testid='memory-source-copy-path']").first
            await copy_path_button.wait_for(timeout=30000)
            result["team_copy_path_visible"] = True
            await open_chat_button.click()

            await page.wait_for_url(f"**/chat?team={team_id}", timeout=30000)
            result["team_open_chat_navigated"] = True
            await open_chat(page, url)
            await install_clipboard_stub(page)
            await select_conversation(page, agent_name)
            await send_message(page, "请说明这次 playwight timeout 接力怎么处理")
            await page.wait_for_function(
                f"() => document.body.innerText.includes({json.dumps(expected_content)})",
                timeout=30000,
            )
            await open_memory_detail(page)

            navigate_button = page.locator("[data-testid='memory-source-navigate']").first
            await navigate_button.wait_for(timeout=30000)
            result["team_navigate_button_visible"] = True
            await navigate_button.click()

            await page.wait_for_url(f"**/teams?team={team_id}&focus=team-collaboration", timeout=30000)
            result["navigated_to_team"] = True
            await page.locator(f"[data-testid='team-detail-view'][data-team-id='{team_id}']").wait_for(timeout=30000)
            result["team_detail_visible"] = True
            await page.locator("[data-focus-anchor='team-collaboration']").first.wait_for(timeout=30000)
            result["team_focus_anchor_visible"] = True

            await open_chat(page, url)
            await install_clipboard_stub(page)
            await select_conversation(page, agent_name)
            await send_message(page, "请按我的用户偏好回复并总结验证结论")

            await page.wait_for_function(
                f"() => document.body.innerText.includes({json.dumps(result['agent_expected_content'])})",
                timeout=30000,
            )
            result["agent_memory_reference_visible"] = True
            modal_text = await open_memory_detail(page)
            result["agent_detail_modal_visible"] = True
            result["agent_detail_contains_file"] = "USER.md" in modal_text
            result["agent_detail_contains_reason"] = "用户偏好" in modal_text
            result["agent_detail_contains_term"] = "中文" in modal_text
            result["agent_description_visible"] = "用户偏好档案" in await page.locator("[data-testid='memory-source-description']").inner_text()
            copy_handoff_button = page.locator("[data-testid='memory-source-copy-handoff']").first
            await copy_handoff_button.wait_for(timeout=30000)
            result["agent_copy_handoff_visible"] = True
            await copy_handoff_button.click()
            copied_text = await read_stubbed_clipboard(page)
            result["agent_copy_handoff_ok"] = "[Relay Handoff]" in copied_text and "来源路径：" in copied_text and "请输出：" in copied_text
            copy_summary_button = page.locator("[data-testid='memory-source-copy-summary']").first
            await copy_summary_button.wait_for(timeout=30000)
            result["agent_copy_summary_visible"] = True
            await copy_summary_button.click()
            copied_text = await read_stubbed_clipboard(page)
            result["agent_copy_summary_ok"] = "标题:" in copied_text and "命中词:" in copied_text and "级别:" in copied_text
            copy_context_button = page.locator("[data-testid='memory-source-copy-context']").first
            await copy_context_button.wait_for(timeout=30000)
            result["agent_copy_context_visible"] = True
            await copy_context_button.click()
            copied_text = await read_stubbed_clipboard(page)
            result["agent_copy_context_ok"] = "[Memory Reference Context]" in copied_text and "source_path=/virtual/agents/" in copied_text and "matched_terms=" in copied_text
            await page.locator("[data-testid='memory-source-open-chat']").first.wait_for(timeout=30000)
            result["agent_open_chat_visible"] = True
            await page.locator("[data-testid='memory-source-copy-path']").first.wait_for(timeout=30000)
            result["agent_copy_path_visible"] = True

            navigate_button = page.locator("[data-testid='memory-source-navigate']").first
            await navigate_button.wait_for(timeout=30000)
            result["agent_navigate_button_visible"] = True
            await navigate_button.click()

            await page.wait_for_url(f"**/teams?agent={agent_id}&focus=agent-file-user", timeout=30000)
            result["navigated_to_agent"] = True
            await page.locator(f"[data-testid='agent-detail-view'][data-agent-id='{agent_id}']").wait_for(timeout=30000)
            result["agent_detail_visible"] = True
            await page.locator("[data-focus-anchor='agent-file-user']").first.wait_for(timeout=30000)
            result["agent_focus_anchor_visible"] = True

        finally:
            await browser.close()

    if result["request_count"] != 3:
        result["errors"].append(f"unexpected_request_count={result['request_count']}")
    if not result["team_memory_reference_visible"]:
        result["errors"].append("team_memory_reference_not_visible")
    if not result["team_detail_modal_visible"]:
        result["errors"].append("team_memory_detail_modal_not_visible")
    if not result["team_detail_contains_scope"]:
        result["errors"].append("team_memory_detail_scope_missing")
    if not result["team_detail_contains_reason"]:
        result["errors"].append("team_memory_detail_reason_missing")
    if not result["team_detail_contains_term"]:
        result["errors"].append("team_memory_detail_term_missing")
    if not result["team_description_visible"]:
        result["errors"].append("team_memory_description_missing")
    if not result["team_copy_handoff_visible"]:
        result["errors"].append("team_memory_copy_handoff_not_visible")
    if not result["team_copy_handoff_ok"]:
        result["errors"].append("team_memory_copy_handoff_failed")
    if not result["team_copy_summary_visible"]:
        result["errors"].append("team_memory_copy_summary_not_visible")
    if not result["team_copy_summary_ok"]:
        result["errors"].append("team_memory_copy_summary_failed")
    if not result["team_copy_context_visible"]:
        result["errors"].append("team_memory_copy_context_not_visible")
    if not result["team_copy_context_ok"]:
        result["errors"].append("team_memory_copy_context_failed")
    if not result["team_open_chat_visible"]:
        result["errors"].append("team_memory_open_chat_not_visible")
    if not result["team_copy_path_visible"]:
        result["errors"].append("team_memory_copy_path_not_visible")
    if not result["team_open_chat_navigated"]:
        result["errors"].append("team_memory_open_chat_navigation_failed")
    if not result["team_navigate_button_visible"]:
        result["errors"].append("team_memory_navigate_button_not_visible")
    if not result["navigated_to_team"]:
        result["errors"].append("team_memory_navigation_failed")
    if not result["team_detail_visible"]:
        result["errors"].append("team_detail_not_visible")
    if not result["team_focus_anchor_visible"]:
        result["errors"].append("team_focus_anchor_not_visible")
    if not result["agent_memory_reference_visible"]:
        result["errors"].append("agent_memory_reference_not_visible")
    if not result["agent_detail_modal_visible"]:
        result["errors"].append("agent_memory_detail_modal_not_visible")
    if not result["agent_detail_contains_file"]:
        result["errors"].append("agent_memory_detail_file_missing")
    if not result["agent_detail_contains_reason"]:
        result["errors"].append("agent_memory_detail_reason_missing")
    if not result["agent_detail_contains_term"]:
        result["errors"].append("agent_memory_detail_term_missing")
    if not result["agent_description_visible"]:
        result["errors"].append("agent_memory_description_missing")
    if not result["agent_copy_handoff_visible"]:
        result["errors"].append("agent_memory_copy_handoff_not_visible")
    if not result["agent_copy_handoff_ok"]:
        result["errors"].append("agent_memory_copy_handoff_failed")
    if not result["agent_copy_summary_visible"]:
        result["errors"].append("agent_memory_copy_summary_not_visible")
    if not result["agent_copy_summary_ok"]:
        result["errors"].append("agent_memory_copy_summary_failed")
    if not result["agent_copy_context_visible"]:
        result["errors"].append("agent_memory_copy_context_not_visible")
    if not result["agent_copy_context_ok"]:
        result["errors"].append("agent_memory_copy_context_failed")
    if not result["agent_open_chat_visible"]:
        result["errors"].append("agent_memory_open_chat_not_visible")
    if not result["agent_copy_path_visible"]:
        result["errors"].append("agent_memory_copy_path_not_visible")
    if not result["agent_navigate_button_visible"]:
        result["errors"].append("agent_memory_navigate_button_not_visible")
    if not result["navigated_to_agent"]:
        result["errors"].append("agent_memory_navigation_failed")
    if not result["agent_detail_visible"]:
        result["errors"].append("agent_detail_not_visible")
    if not result["agent_focus_anchor_visible"]:
        result["errors"].append("agent_focus_anchor_not_visible")

    result["ok"] = not result["errors"]
    return result


def main() -> int:
    result = asyncio.run(run_memory_trace_smoke())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
