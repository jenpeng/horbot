#!/usr/bin/env python3
"""Browser smoke test for DM onboarding flow with a pending agent."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys
from typing import Any

from playwright.async_api import async_playwright

from chat_ui_smoke import (
    delete_session,
    fetch_json,
    open_chat,
    reload_chat,
    select_conversation,
    send_message,
    wait_for_assistant_group_text,
)
from playwright_browser import launch_browser


DEFAULT_URL = "http://127.0.0.1:3000/chat"
TARGET_AGENT_ID = "horbot-03"
TARGET_AGENT_NAME = "小布"
BANNER_TEXT = "首次私聊引导"

PENDING_SOUL_TEMPLATE = """# 灵魂
<!-- HORBOT_SETUP_PENDING -->

我是 {agent_name}，运行在 horbot 中的独立 Agent。

## 工作约束
- 首轮对话时，优先帮助用户明确职责、输出风格、边界和协作方式。
- 完成首次引导后，请主动重写本文件，并移除 `HORBOT_SETUP_PENDING` 标记。
"""

PENDING_USER_TEMPLATE = """# 用户档案
<!-- HORBOT_SETUP_PENDING -->

这份 USER.md 用于记录用户与 {agent_name} 的专属协作约定。

## 备注
- 完成首次引导后，请把真实偏好写入本文件，并移除 `HORBOT_SETUP_PENDING` 标记。
"""


def _agent_workspace(agent: dict[str, Any]) -> Path:
    workspace = agent.get("effective_workspace") or agent.get("workspace")
    if not workspace:
        raise RuntimeError(f"Agent {agent.get('id') or '<unknown>'} does not expose a workspace path")
    return Path(str(workspace))


def _read_file(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _dm_history_path(agent_id: str, workspace: Path) -> Path:
    return workspace / ".horbot-agent" / "sessions" / f"web_dm_{agent_id}.jsonl"


def _write_pending_bootstrap(agent: dict[str, Any]) -> dict[str, str]:
    workspace = _agent_workspace(agent)
    workspace.mkdir(parents=True, exist_ok=True)
    soul_path = workspace / "SOUL.md"
    user_path = workspace / "USER.md"

    backup = {
        "soul": _read_file(soul_path),
        "user": _read_file(user_path),
    }

    agent_name = str(agent.get("name") or TARGET_AGENT_NAME)
    soul_path.write_text(PENDING_SOUL_TEMPLATE.format(agent_name=agent_name), encoding="utf-8")
    user_path.write_text(PENDING_USER_TEMPLATE.format(agent_name=agent_name), encoding="utf-8")
    return backup


def _restore_bootstrap(agent: dict[str, Any], backup: dict[str, str] | None) -> None:
    if not backup:
        return
    workspace = _agent_workspace(agent)
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "SOUL.md").write_text(backup.get("soul", ""), encoding="utf-8")
    (workspace / "USER.md").write_text(backup.get("user", ""), encoding="utf-8")


def _backup_and_clear_dm_history(agent: dict[str, Any]) -> str | None:
    workspace = _agent_workspace(agent)
    history_path = _dm_history_path(str(agent.get("id") or TARGET_AGENT_ID), workspace)
    if not history_path.exists():
        return None
    original = history_path.read_text(encoding="utf-8")
    history_path.unlink()
    return original


def _restore_dm_history(agent: dict[str, Any], backup: str | None) -> None:
    workspace = _agent_workspace(agent)
    history_path = _dm_history_path(str(agent.get("id") or TARGET_AGENT_ID), workspace)
    if backup is None:
        if history_path.exists():
            history_path.unlink()
        return
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(backup, encoding="utf-8")


async def _fetch_agent(page, agent_id: str) -> dict[str, Any] | None:
    agents_data = await fetch_json(page, "/api/agents")
    return next((item for item in agents_data.get("agents") or [] if item.get("id") == agent_id), None)


async def _wait_for_agent_pending_state(
    page,
    agent_id: str,
    expected_pending: bool,
    *,
    timeout_ms: int = 30000,
) -> dict[str, Any]:
    deadline = asyncio.get_running_loop().time() + timeout_ms / 1000
    last_agent: dict[str, Any] | None = None
    while asyncio.get_running_loop().time() < deadline:
        last_agent = await _fetch_agent(page, agent_id)
        if last_agent and bool(last_agent.get("bootstrap_setup_pending")) is expected_pending:
            return last_agent
        await asyncio.sleep(0.8)

    if last_agent is None:
        raise RuntimeError(f"Agent {agent_id} not found while waiting for bootstrap state")
    raise RuntimeError(
        f"Timed out waiting for bootstrap_setup_pending={expected_pending} "
        f"for agent {agent_id}; last value={bool(last_agent.get('bootstrap_setup_pending'))}"
    )


async def run_onboarding_smoke(
    url: str = DEFAULT_URL,
    headless: bool = True,
    *,
    force_reset_pending: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "agent_id": TARGET_AGENT_ID,
        "agent_name": TARGET_AGENT_NAME,
        "initial_pending": None,
        "temporary_reset_applied": False,
        "banner_visible_before": None,
        "step1_prompt_visible": None,
        "step2_prompt_visible": None,
        "final_ack_visible": None,
        "api_pending_after": None,
        "banner_visible_after_refresh": None,
        "errors": [],
    }

    async with async_playwright() as playwright:
        browser = await launch_browser(playwright, headless=headless)
        page = await browser.new_page(viewport={"width": 1440, "height": 1100})
        bootstrap_backup: dict[str, str] | None = None
        history_backup: str | None = None
        agent: dict[str, Any] | None = None
        try:
            await open_chat(page, url)
            agent = await _fetch_agent(page, TARGET_AGENT_ID)
            if not agent:
                raise RuntimeError(f"Agent {TARGET_AGENT_ID} not found")

            result["initial_pending"] = bool(agent.get("bootstrap_setup_pending"))
            if not result["initial_pending"] and force_reset_pending:
                bootstrap_backup = _write_pending_bootstrap(agent)
                result["temporary_reset_applied"] = True
                agent = await _wait_for_agent_pending_state(page, TARGET_AGENT_ID, True, timeout_ms=10000)
                result["initial_pending"] = bool(agent.get("bootstrap_setup_pending"))

            if not result["initial_pending"]:
                result["errors"].append("agent_not_pending_before_test")
                return result

            history_backup = _backup_and_clear_dm_history(agent)
            await delete_session(page, "web:dm_horbot-03")
            await reload_chat(page)
            await select_conversation(page, TARGET_AGENT_NAME)

            banner = page.get_by_text(BANNER_TEXT)
            result["banner_visible_before"] = await banner.count() > 0
            if not result["banner_visible_before"]:
                result["errors"].append("banner_not_visible_before")

            await send_message(page, "开始完善配置吧")
            await wait_for_assistant_group_text(page, "你希望我怎么称呼你", agent_name=TARGET_AGENT_NAME, timeout=120000)
            result["step1_prompt_visible"] = True

            await send_message(page, "称呼我彭老师，时区 UTC+8")
            await wait_for_assistant_group_text(page, "主要工作/角色", agent_name=TARGET_AGENT_NAME, timeout=120000)
            result["step2_prompt_visible"] = True

            await send_message(page, "我是资深产品经理，需要你和我聊天和编码工作。")
            await wait_for_assistant_group_text(page, "已保存到", agent_name=TARGET_AGENT_NAME, timeout=180000)
            result["final_ack_visible"] = True

            refreshed_agent = await _wait_for_agent_pending_state(page, TARGET_AGENT_ID, False, timeout_ms=30000)
            result["api_pending_after"] = bool(refreshed_agent.get("bootstrap_setup_pending"))
            if result["api_pending_after"]:
                result["errors"].append("agent_still_pending_after_dialogue")

            await reload_chat(page)
            await select_conversation(page, TARGET_AGENT_NAME)
            banner = page.get_by_text(BANNER_TEXT)
            result["banner_visible_after_refresh"] = await banner.count() > 0
            if result["banner_visible_after_refresh"]:
                result["errors"].append("banner_visible_after_refresh")

            result["ok"] = not result["errors"]
            return result
        finally:
            if agent is not None:
                _restore_dm_history(agent, history_backup)
            if result.get("temporary_reset_applied") and agent is not None:
                _restore_bootstrap(agent, bootstrap_backup)
            await browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run onboarding smoke test against 小布.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument(
        "--force-reset-pending",
        action="store_true",
        help="Temporarily rewrite 小布's bootstrap files back to pending templates so the onboarding flow can be replayed.",
    )
    args = parser.parse_args()

    result = asyncio.run(
        run_onboarding_smoke(
            url=args.url,
            headless=not args.headed,
            force_reset_pending=args.force_reset_pending,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
