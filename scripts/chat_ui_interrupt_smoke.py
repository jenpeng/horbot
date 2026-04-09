#!/usr/bin/env python3
"""Browser smoke test for stopping and interrupting team relay chat."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from typing import Any

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from chat_ui_smoke import (
    collect_tail_groups,
    delete_session,
    fetch_json,
    find_reasoning_leak,
    last_non_empty_line,
    open_chat,
    select_conversation,
    send_message,
    wait_for_generation_idle,
)
from playwright_browser import launch_browser


DEFAULT_URL = "http://127.0.0.1:3000/chat"


async def resolve_team_fixture(page: Page) -> dict[str, str]:
    agents_data = await fetch_json(page, "/api/agents")
    teams_data = await fetch_json(page, "/api/teams")

    agents = agents_data.get("agents") or []
    teams = teams_data.get("teams") or []
    if not teams:
        raise RuntimeError("No teams available for interrupt smoke test")

    team = teams[0]
    agent_by_id = {str(agent.get("id")): agent for agent in agents if agent.get("id")}

    secondary_agent = None
    for member_id in team.get("members") or []:
        member = agent_by_id.get(str(member_id))
        if member and not member.get("is_main"):
            secondary_agent = member
            break

    if secondary_agent is None and team.get("members"):
        secondary_agent = agent_by_id.get(str(team["members"][0]))

    if secondary_agent is None:
        raise RuntimeError(f'Unable to resolve secondary agent for team "{team.get("name")}"')

    return {
        "team_id": str(team["id"]),
        "team_name": str(team["name"]),
        "secondary_agent_id": str(secondary_agent["id"]),
        "secondary_agent_name": str(secondary_agent["name"]),
    }


async def install_interrupt_mock(
    page: Page,
    *,
    secondary_agent_id: str,
    secondary_agent_name: str,
    success_content: str,
    long_running_request_count: int,
) -> None:
    await page.evaluate(
        """
        (config) => {
          const originalFetch = window.fetch.bind(window);
          const encoder = new TextEncoder();

          const state = {
            requestCount: 0,
            stopRequestIds: [],
            activeStreams: {},
          };
          window.__chatInterruptMock = state;

          const enqueueEvent = (controller, event) => {
            controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\\n\\n`));
          };

          const cleanupActiveStream = (requestId, emitStopped) => {
            const active = state.activeStreams[requestId];
            if (!active || active.closed) {
              return;
            }

            active.closed = true;
            active.timers.forEach((timerId) => window.clearTimeout(timerId));

            if (emitStopped) {
              enqueueEvent(active.controller, {
                event: "stopped",
                content: "Generation stopped by user",
              });
              active.controller.close();
            }

            if (active.signal && active.abortHandler) {
              active.signal.removeEventListener("abort", active.abortHandler);
            }

            delete state.activeStreams[requestId];
          };

          const scheduleEvent = (requestId, delayMs, event, closeAfter = false) => {
            const active = state.activeStreams[requestId];
            if (!active) {
              return;
            }

            const timerId = window.setTimeout(() => {
              const current = state.activeStreams[requestId];
              if (!current || current.closed) {
                return;
              }

              enqueueEvent(current.controller, event);
              if (closeAfter) {
                current.closed = true;
                current.controller.close();
                delete state.activeStreams[requestId];
              }
            }, delayMs);

            active.timers.push(timerId);
          };

          const buildLongRunningResponse = (requestIndex, signal) => {
            const requestId = `interrupt-mock-request-${requestIndex}`;
            const stream = new ReadableStream({
              start(controller) {
                state.activeStreams[requestId] = {
                  controller,
                  timers: [],
                  closed: false,
                  signal: signal || null,
                  abortHandler: null,
                };

                if (signal) {
                  const abortHandler = () => cleanupActiveStream(requestId, true);
                  state.activeStreams[requestId].abortHandler = abortHandler;
                  signal.addEventListener("abort", abortHandler, { once: true });
                }

                scheduleEvent(requestId, 10, {
                  event: "agent_start",
                  agent_id: "main",
                  agent_name: "小项 🐎",
                  turn_id: `interrupt-turn-${requestIndex}-main`,
                  message_id: `interrupt-msg-${requestIndex}-main`,
                });
                scheduleEvent(requestId, 40, {
                  event: "progress",
                  agent_id: "main",
                  agent_name: "小项 🐎",
                  turn_id: `interrupt-turn-${requestIndex}-main`,
                  message_id: `interrupt-msg-${requestIndex}-main`,
                  content: `@${config.secondaryAgentName} 请保持待命`,
                });
                scheduleEvent(requestId, 70, {
                  event: "agent_mentioned",
                  agent_id: config.secondaryAgentId,
                  agent_name: config.secondaryAgentName,
                  mentioned_by: "main",
                });
              },
              cancel() {
                cleanupActiveStream(requestId, false);
              },
            });

            return new Response(stream, {
              status: 200,
              headers: {
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "X-Request-Id": requestId,
                "Access-Control-Expose-Headers": "X-Request-Id",
              },
            });
          };

          const buildSuccessResponse = (requestIndex, signal) => {
            const requestId = `interrupt-mock-request-${requestIndex}`;
            const stream = new ReadableStream({
              start(controller) {
                state.activeStreams[requestId] = {
                  controller,
                  timers: [],
                  closed: false,
                  signal: signal || null,
                  abortHandler: null,
                };

                if (signal) {
                  const abortHandler = () => cleanupActiveStream(requestId, true);
                  state.activeStreams[requestId].abortHandler = abortHandler;
                  signal.addEventListener("abort", abortHandler, { once: true });
                }

                scheduleEvent(requestId, 10, {
                  event: "agent_start",
                  agent_id: "main",
                  agent_name: "小项 🐎",
                  turn_id: `interrupt-turn-${requestIndex}-main`,
                  message_id: `interrupt-msg-${requestIndex}-main`,
                });
                scheduleEvent(requestId, 30, {
                  event: "progress",
                  agent_id: "main",
                  agent_name: "小项 🐎",
                  turn_id: `interrupt-turn-${requestIndex}-main`,
                  message_id: `interrupt-msg-${requestIndex}-main`,
                  content: `@${config.secondaryAgentName} 请继续处理`,
                });
                scheduleEvent(requestId, 50, {
                  event: "agent_done",
                  agent_id: "main",
                  agent_name: "小项 🐎",
                  turn_id: `interrupt-turn-${requestIndex}-main`,
                  message_id: `interrupt-msg-${requestIndex}-main`,
                  content: `@${config.secondaryAgentName} 请继续处理`,
                });
                scheduleEvent(requestId, 70, {
                  event: "agent_start",
                  agent_id: config.secondaryAgentId,
                  agent_name: config.secondaryAgentName,
                  turn_id: `interrupt-turn-${requestIndex}-secondary`,
                  message_id: `interrupt-msg-${requestIndex}-secondary`,
                });
                scheduleEvent(requestId, 90, {
                  event: "progress",
                  agent_id: config.secondaryAgentId,
                  agent_name: config.secondaryAgentName,
                  turn_id: `interrupt-turn-${requestIndex}-secondary`,
                  message_id: `interrupt-msg-${requestIndex}-secondary`,
                  content: "中间接力已稳定完成",
                });
                scheduleEvent(requestId, 110, {
                  event: "agent_done",
                  agent_id: config.secondaryAgentId,
                  agent_name: config.secondaryAgentName,
                  turn_id: `interrupt-turn-${requestIndex}-secondary`,
                  message_id: `interrupt-msg-${requestIndex}-secondary`,
                  content: "中间接力已稳定完成",
                });
                scheduleEvent(requestId, 130, {
                  event: "agent_start",
                  agent_id: "main",
                  agent_name: "小项 🐎",
                  turn_id: `interrupt-turn-${requestIndex}-main-final`,
                  message_id: `interrupt-msg-${requestIndex}-main-final`,
                });
                scheduleEvent(requestId, 138, {
                  event: "step_start",
                  agent_id: "main",
                  agent_name: "小项 🐎",
                  turn_id: `interrupt-turn-${requestIndex}-main-final`,
                  message_id: `interrupt-msg-${requestIndex}-main-final`,
                  step_id: `interrupt-thinking-${requestIndex}`,
                  step_type: "thinking",
                  title: "思考中...",
                });
                scheduleEvent(requestId, 144, {
                  event: "thinking",
                  agent_id: "main",
                  agent_name: "小项 🐎",
                  turn_id: `interrupt-turn-${requestIndex}-main-final`,
                  message_id: `interrupt-msg-${requestIndex}-main-final`,
                  content: "正在整理接力结果并准备最终回复。",
                });
                scheduleEvent(requestId, 148, {
                  event: "step_complete",
                  agent_id: "main",
                  agent_name: "小项 🐎",
                  turn_id: `interrupt-turn-${requestIndex}-main-final`,
                  message_id: `interrupt-msg-${requestIndex}-main-final`,
                  step_id: `interrupt-thinking-${requestIndex}`,
                  status: "completed",
                  details: {
                    thinking: "正在整理接力结果并准备最终回复。",
                  },
                });
                scheduleEvent(requestId, 152, {
                  event: "step_start",
                  agent_id: "main",
                  agent_name: "小项 🐎",
                  turn_id: `interrupt-turn-${requestIndex}-main-final`,
                  message_id: `interrupt-msg-${requestIndex}-main-final`,
                  step_id: `interrupt-tool-${requestIndex}`,
                  step_type: "tool_call",
                  title: "执行 exec",
                });
                scheduleEvent(requestId, 156, {
                  event: "tool_start",
                  agent_id: "main",
                  agent_name: "小项 🐎",
                  turn_id: `interrupt-turn-${requestIndex}-main-final`,
                  message_id: `interrupt-msg-${requestIndex}-main-final`,
                  tool_name: "exec",
                  arguments: {
                    command: "pwd",
                  },
                });
                scheduleEvent(requestId, 160, {
                  event: "tool_result",
                  agent_id: "main",
                  agent_name: "小项 🐎",
                  turn_id: `interrupt-turn-${requestIndex}-main-final`,
                  message_id: `interrupt-msg-${requestIndex}-main-final`,
                  tool_name: "exec",
                  result: "/mock/workspace",
                  execution_time: 0.012,
                });
                scheduleEvent(requestId, 164, {
                  event: "step_complete",
                  agent_id: "main",
                  agent_name: "小项 🐎",
                  turn_id: `interrupt-turn-${requestIndex}-main-final`,
                  message_id: `interrupt-msg-${requestIndex}-main-final`,
                  step_id: `interrupt-tool-${requestIndex}`,
                  status: "success",
                  details: {
                    toolName: "exec",
                    arguments: {
                      command: "pwd",
                    },
                    result: "/mock/workspace",
                    executionTime: 0.012,
                  },
                });
                scheduleEvent(requestId, 168, {
                  event: "step_start",
                  agent_id: "main",
                  agent_name: "小项 🐎",
                  turn_id: `interrupt-turn-${requestIndex}-main-final`,
                  message_id: `interrupt-msg-${requestIndex}-main-final`,
                  step_id: `interrupt-response-${requestIndex}`,
                  step_type: "response",
                  title: "生成回复",
                });
                scheduleEvent(requestId, 174, {
                  event: "progress",
                  agent_id: "main",
                  agent_name: "小项 🐎",
                  turn_id: `interrupt-turn-${requestIndex}-main-final`,
                  message_id: `interrupt-msg-${requestIndex}-main-final`,
                  content: config.successContent,
                });
                scheduleEvent(requestId, 178, {
                  event: "step_complete",
                  agent_id: "main",
                  agent_name: "小项 🐎",
                  turn_id: `interrupt-turn-${requestIndex}-main-final`,
                  message_id: `interrupt-msg-${requestIndex}-main-final`,
                  step_id: `interrupt-response-${requestIndex}`,
                  status: "success",
                  details: {
                    content: config.successContent,
                  },
                });
                scheduleEvent(requestId, 182, {
                  event: "agent_done",
                  agent_id: "main",
                  agent_name: "小项 🐎",
                  turn_id: `interrupt-turn-${requestIndex}-main-final`,
                  message_id: `interrupt-msg-${requestIndex}-main-final`,
                  content: config.successContent,
                });
                scheduleEvent(requestId, 196, {
                  event: "done",
                  total_agents: 3,
                }, true);
              },
              cancel() {
                cleanupActiveStream(requestId, false);
              },
            });

            return new Response(stream, {
              status: 200,
              headers: {
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "X-Request-Id": requestId,
                "Access-Control-Expose-Headers": "X-Request-Id",
              },
            });
          };

          window.fetch = async (input, init = undefined) => {
            const url = typeof input === "string" ? input : input.url;

            if (url.includes("/api/chat/stream")) {
              state.requestCount += 1;
              const signal = init?.signal || null;
              if (state.requestCount <= config.longRunningRequestCount) {
                return buildLongRunningResponse(state.requestCount, signal);
              }
              return buildSuccessResponse(state.requestCount, signal);
            }

            if (url.includes("/api/chat/stop")) {
              let payload = {};
              try {
                payload = init && typeof init.body === "string" ? JSON.parse(init.body) : {};
              } catch (error) {
                payload = {};
              }

              const requestId = payload.request_id || null;
              state.stopRequestIds.push(requestId);
              if (requestId) {
                cleanupActiveStream(requestId, true);
              }

              return new Response(
                JSON.stringify({ status: "success", message: "Stop signal sent" }),
                {
                  status: 200,
                  headers: { "Content-Type": "application/json" },
                },
              );
            }

            return originalFetch(input, init);
          };
        }
        """,
        {
            "secondaryAgentId": secondary_agent_id,
            "secondaryAgentName": secondary_agent_name,
            "successContent": success_content,
            "longRunningRequestCount": long_running_request_count,
        },
    )


async def run_interrupt_smoke(url: str = DEFAULT_URL, headless: bool = True) -> dict[str, Any]:
    expected_content = f"INTERRUPT_SEND_OK_{uuid.uuid4().hex[:8]}"
    result: dict[str, Any] = {
        "ok": False,
        "scenario": "team-interrupt",
        "team_name": "",
        "secondary_agent_name": "",
        "relay_status_visible": False,
        "relay_status_text": "",
        "escape_stop_used": False,
        "turn_resume_visible": False,
        "stop_button_visible": False,
        "initial_stop_button_label": "",
        "stop_marker_visible": False,
        "interrupt_button_visible": False,
        "final_success_visible": False,
        "collapsed_summary_visible": False,
        "collapsed_summary_persisted_after_jump": False,
        "timeline_toggle_visible": False,
        "timeline_default_collapsed": False,
        "timeline_collapsed": False,
        "timeline_reexpanded": False,
        "timeline_jump_visible": False,
        "timeline_jump_highlighted": False,
        "timeline_jump_kept_collapsed": False,
        "sidebar_default_collapsed": False,
        "sidebar_expanded_after_toggle": False,
        "sidebar_expanded_persisted": False,
        "sidebar_collapsed_storage_persisted": False,
        "execution_card_visible": False,
        "execution_card_expanded": False,
        "execution_tool_badge_visible": False,
        "execution_tool_filter_visible": False,
        "execution_tool_filter_applied": False,
        "execution_tool_filter_persisted": False,
        "execution_terminal_visible": False,
        "execution_tool_detail_visible": False,
        "stop_scenario_request_count": 0,
        "stop_scenario_stop_request_ids": [],
        "interrupt_scenario_request_count": 0,
        "interrupt_scenario_stop_request_ids": [],
        "debug_button_texts": [],
        "debug_body_excerpt": "",
        "tail_groups": [],
        "reasoning_leak_marker": "",
        "errors": [],
    }

    async with async_playwright() as p:
        browser = await launch_browser(p, headless=headless)
        try:
            stop_page = await browser.new_page(viewport={"width": 1440, "height": 1100})
            await open_chat(stop_page, url)
            sidebar_toggle = stop_page.get_by_role("button", name="展开导航栏").first
            try:
                await sidebar_toggle.wait_for(timeout=30000)
                result["sidebar_default_collapsed"] = True
                await sidebar_toggle.click()
                await stop_page.get_by_role("button", name="折叠导航栏").first.wait_for(timeout=30000)
                result["sidebar_expanded_after_toggle"] = True
                result["sidebar_collapsed_storage_persisted"] = await stop_page.evaluate(
                    "() => window.localStorage.getItem('horbot.sidebar-collapsed') === 'false'"
                )
                await stop_page.reload(wait_until="networkidle", timeout=120000)
                await stop_page.locator("textarea").first.wait_for(timeout=30000)
                await stop_page.get_by_role("button", name="折叠导航栏").first.wait_for(timeout=30000)
                result["sidebar_expanded_persisted"] = True
            except PlaywrightTimeoutError:
                pass

            fixture = await resolve_team_fixture(stop_page)
            result["team_name"] = fixture["team_name"]
            result["secondary_agent_name"] = fixture["secondary_agent_name"]
            await delete_session(stop_page, f"web:team_{fixture['team_id']}")

            await install_interrupt_mock(
                stop_page,
                secondary_agent_id=fixture["secondary_agent_id"],
                secondary_agent_name=fixture["secondary_agent_name"],
                success_content=expected_content,
                long_running_request_count=1,
            )

            await select_conversation(stop_page, fixture["team_name"])

            await send_message(stop_page, "请开始第一轮长接力")
            await stop_page.wait_for_function(
                """() => Array.from(document.querySelectorAll('button'))
                    .some((button) => {
                        const label = (
                            button.getAttribute('aria-label')
                            || button.getAttribute('title')
                            || button.innerText
                            || ''
                        ).trim();
                        return ['停止生成', '停止接力', '停止并发送'].includes(label);
                    })""",
                timeout=30000,
            )
            stop_button_label = await stop_page.evaluate(
                """() => {
                    const button = Array.from(document.querySelectorAll('button'))
                      .find((item) => {
                        const label = (
                          item.getAttribute('aria-label')
                          || item.getAttribute('title')
                          || item.innerText
                          || ''
                        ).trim();
                        return ['停止生成', '停止接力', '停止并发送'].includes(label);
                      });
                    return button
                      ? (
                          button.getAttribute('aria-label')
                          || button.getAttribute('title')
                          || button.innerText
                          || ''
                        ).trim()
                      : '';
                }"""
            )
            result["initial_stop_button_label"] = stop_button_label
            stop_button = stop_page.get_by_role("button", name=stop_button_label).first
            result["stop_button_visible"] = True

            relay_status_candidates = [
                f"小项 🐎 正在处理，已唤起 {fixture['secondary_agent_name']} 待接力。",
                f"已唤起 {fixture['secondary_agent_name']}，等待接力。",
                "小项 🐎 正在接力处理中。",
                "小项 🐎 正在输入...，按 Esc 可停止。",
            ]
            stop_notice_candidates = [
                f"本轮已中断，停止于 小项 🐎，原本准备交给 {fixture['secondary_agent_name']}。可继续发送新消息。",
                "本轮已中断，停止于 小项 🐎。可继续发送新消息。",
                f"本轮已中断，已取消发给 {fixture['secondary_agent_name']} 的后续接力。可继续发送新消息。",
                "本轮已中断，可继续发送新消息。",
            ]
            try:
                await stop_page.wait_for_function(
                    """(candidates) => {
                        const text = document.querySelector('[data-testid="chat-session-status-message"]')?.textContent || '';
                        return candidates.some((candidate) => text.includes(candidate));
                    }""",
                    arg=relay_status_candidates,
                    timeout=30000,
                )
                result["relay_status_visible"] = True
                body_text = await stop_page.locator("[data-testid='chat-session-status-message']").inner_text()
                result["relay_status_text"] = next(
                    (candidate for candidate in relay_status_candidates if candidate in body_text),
                    "",
                )
            except PlaywrightTimeoutError:
                result["debug_button_texts"] = await stop_page.locator("button").all_inner_texts()
                body_text = await stop_page.locator("[data-testid='chat-session-status']").inner_text()
                result["debug_body_excerpt"] = body_text[:1500]
                pass

            await stop_page.keyboard.press("Escape")
            result["escape_stop_used"] = True

            await stop_page.wait_for_function(
                """() => !Array.from(document.querySelectorAll('button')).some((button) => {
                    const label = (
                      button.getAttribute('aria-label')
                      || button.getAttribute('title')
                      || button.innerText
                      || ''
                    ).trim();
                    return ['停止生成', '停止接力', '停止并发送'].includes(label);
                })""",
                timeout=30000,
            )

            try:
                await stop_page.wait_for_function(
                    """(candidates) => {
                        const text = document.querySelector('[data-testid="chat-session-status-message"]')?.textContent || '';
                        return candidates.some((candidate) => text.includes(candidate));
                    }""",
                    arg=stop_notice_candidates,
                    timeout=30000,
                )
                result["stop_marker_visible"] = True
            except PlaywrightTimeoutError:
                pass

            try:
                await stop_page.locator("[data-testid='chat-turn-resume']").first.wait_for(timeout=30000)
                result["turn_resume_visible"] = True
            except PlaywrightTimeoutError:
                pass

            stop_state = await stop_page.evaluate(
                """() => ({
                    requestCount: window.__chatInterruptMock?.requestCount || 0,
                    stopRequestIds: window.__chatInterruptMock?.stopRequestIds || [],
                })"""
            )
            result["stop_scenario_request_count"] = int(stop_state.get("requestCount", 0))
            result["stop_scenario_stop_request_ids"] = list(stop_state.get("stopRequestIds", []))
            await stop_page.close()

            interrupt_page = await browser.new_page(viewport={"width": 1440, "height": 1100})
            await open_chat(interrupt_page, url)
            await delete_session(interrupt_page, f"web:team_{fixture['team_id']}")
            await install_interrupt_mock(
                interrupt_page,
                secondary_agent_id=fixture["secondary_agent_id"],
                secondary_agent_name=fixture["secondary_agent_name"],
                success_content=expected_content,
                long_running_request_count=1,
            )
            await select_conversation(interrupt_page, fixture["team_name"])

            await send_message(interrupt_page, "请开始第二轮长接力")
            await interrupt_page.wait_for_function(
                """() => Array.from(document.querySelectorAll('button'))
                    .some((button) => {
                        const label = (
                            button.getAttribute('aria-label')
                            || button.getAttribute('title')
                            || button.innerText
                            || ''
                        ).trim();
                        return ['停止生成', '停止接力', '停止并发送'].includes(label);
                    })""",
                timeout=30000,
            )

            textarea = interrupt_page.locator("textarea").first
            await textarea.fill(f"请只回复这个字符串，不要添加任何其他内容：{expected_content}")

            interrupt_button = interrupt_page.get_by_role("button", name="停止并发送").first
            await interrupt_button.wait_for(timeout=30000)
            result["interrupt_button_visible"] = True
            await interrupt_button.click()

            try:
                await interrupt_page.wait_for_function(
                    f"() => document.body.innerText.includes({json.dumps(expected_content)})",
                    timeout=30000,
                )
                result["final_success_visible"] = True
                await wait_for_generation_idle(interrupt_page, timeout=30000)
                await interrupt_page.wait_for_timeout(1000)
            except PlaywrightTimeoutError:
                result["errors"].append("final_success_timeout")
                result["debug_button_texts"] = await interrupt_page.locator("button").all_inner_texts()
                body_text = await interrupt_page.locator("body").inner_text()
                result["debug_body_excerpt"] = body_text[:1500]

            if result["final_success_visible"]:
                last_turn = interrupt_page.locator("[data-testid='chat-turn-card']").last
                try:
                    await last_turn.locator("[data-testid='chat-turn-collapsed-summary']").first.wait_for(
                        timeout=30000
                    )
                    result["collapsed_summary_visible"] = True
                except PlaywrightTimeoutError:
                    pass

                turn_expanded_attr = await last_turn.get_attribute("data-expanded")
                result["timeline_jump_kept_collapsed"] = turn_expanded_attr == "false"

                turn_id = await last_turn.get_attribute("data-turn-id")
                if turn_id:
                    timeline_toggle = last_turn.locator("[data-testid='chat-turn-timeline-toggle']").first
                    try:
                        await timeline_toggle.wait_for(timeout=30000)
                        result["timeline_toggle_visible"] = True
                        await interrupt_page.wait_for_function(
                            """
                            (turnId) => {
                              const card = document.querySelector(
                                `[data-testid="chat-turn-card"][data-turn-id="${turnId}"]`
                              );
                              const timeline = card?.querySelector('[data-testid="chat-turn-timeline"]');
                              return timeline?.getAttribute("data-collapsed") === "true";
                            }
                            """,
                            arg=turn_id,
                            timeout=30000,
                        )
                        result["timeline_default_collapsed"] = True
                        await timeline_toggle.click()
                        await interrupt_page.wait_for_function(
                            """
                            (turnId) => {
                              const card = document.querySelector(
                                `[data-testid="chat-turn-card"][data-turn-id="${turnId}"]`
                              );
                              return !!card?.querySelector('[data-testid="chat-turn-timeline-step"]');
                            }
                            """,
                            arg=turn_id,
                            timeout=30000,
                        )
                        result["timeline_reexpanded"] = True
                        await timeline_toggle.click()
                        await interrupt_page.wait_for_function(
                            """
                            (turnId) => {
                              const card = document.querySelector(
                                `[data-testid="chat-turn-card"][data-turn-id="${turnId}"]`
                              );
                              const timeline = card?.querySelector('[data-testid="chat-turn-timeline"]');
                              return timeline?.getAttribute("data-collapsed") === "true";
                            }
                            """,
                            arg=turn_id,
                            timeout=30000,
                        )
                        result["timeline_collapsed"] = True
                        await timeline_toggle.click()
                    except PlaywrightTimeoutError:
                        pass

                    await last_turn.locator("[data-testid='chat-turn-timeline-step']").nth(1).click()
                    try:
                        await interrupt_page.wait_for_function(
                            """
                            ({ turnId, groupIndex }) => {
                              const group = document.querySelector(
                                `[data-testid="chat-turn-group"][data-turn-id="${turnId}"][data-group-index="${groupIndex}"]`
                              );
                              return !!group;
                            }
                            """,
                            arg={"turnId": turn_id, "groupIndex": "1"},
                            timeout=30000,
                        )
                        result["timeline_jump_visible"] = True
                    except PlaywrightTimeoutError:
                        pass

                    try:
                        await interrupt_page.wait_for_function(
                            """
                            ({ turnId, groupIndex }) => {
                              const group = document.querySelector(
                                `[data-testid="chat-turn-group"][data-turn-id="${turnId}"][data-group-index="${groupIndex}"]`
                              );
                              return group?.getAttribute("data-highlighted") === "true";
                            }
                            """,
                            arg={"turnId": turn_id, "groupIndex": "1"},
                            timeout=30000,
                        )
                        result["timeline_jump_highlighted"] = True
                    except PlaywrightTimeoutError:
                        pass

                    try:
                        await interrupt_page.wait_for_function(
                            """
                            (turnId) => {
                              const card = document.querySelector(
                                `[data-testid="chat-turn-card"][data-turn-id="${turnId}"]`
                              );
                              const summary = card?.querySelector('[data-testid="chat-turn-collapsed-summary"]');
                              return card?.getAttribute("data-expanded") === "false" && !!summary;
                            }
                            """,
                            arg=turn_id,
                            timeout=30000,
                        )
                        result["collapsed_summary_persisted_after_jump"] = True
                    except PlaywrightTimeoutError:
                        pass

                    execution_group = last_turn.locator("[data-testid='chat-turn-group']").last
                    execution_toggle = execution_group.get_by_role("button", name="执行过程").first
                    try:
                        await execution_toggle.wait_for(timeout=30000)
                        result["execution_card_visible"] = True
                        already_expanded = await execution_group.get_by_text(
                            "已展开完整步骤与工具细节。",
                            exact=True,
                        ).count() > 0
                        if not already_expanded:
                            await execution_toggle.click()
                        await execution_group.get_by_text("已展开完整步骤与工具细节。").wait_for(timeout=30000)
                        result["execution_card_expanded"] = True
                        result["execution_tool_badge_visible"] = await execution_group.get_by_text(
                            "工具 1",
                            exact=True,
                        ).count() > 0
                        tool_filter_button = execution_group.locator("[data-testid='execution-filter-tool']").first
                        if await tool_filter_button.count() > 0:
                            result["execution_tool_filter_visible"] = True
                            await tool_filter_button.click()
                            result["execution_tool_filter_applied"] = (
                                await execution_group.get_by_text("执行 exec", exact=False).count() > 0
                                and await execution_group.get_by_text("思考中...", exact=False).count() == 0
                            )
                            result["execution_tool_filter_persisted"] = await interrupt_page.evaluate(
                                "() => window.localStorage.getItem('horbot.execution-card-filter') === JSON.stringify('tool')"
                            )
                        result["execution_terminal_visible"] = await execution_group.get_by_text(
                            "终端执行",
                            exact=False,
                        ).count() > 0
                        result["execution_tool_detail_visible"] = (
                            await execution_group.get_by_text("$ pwd", exact=False).count() > 0
                            and await execution_group.get_by_text("/mock/workspace", exact=False).count() > 0
                        )
                    except PlaywrightTimeoutError:
                        pass

            result["tail_groups"] = await collect_tail_groups(interrupt_page)
            result["reasoning_leak_marker"] = find_reasoning_leak(result["tail_groups"])
            interrupt_state = await interrupt_page.evaluate(
                """() => ({
                    requestCount: window.__chatInterruptMock?.requestCount || 0,
                    stopRequestIds: window.__chatInterruptMock?.stopRequestIds || [],
                })"""
            )
            result["interrupt_scenario_request_count"] = int(interrupt_state.get("requestCount", 0))
            result["interrupt_scenario_stop_request_ids"] = list(interrupt_state.get("stopRequestIds", []))
            await interrupt_page.close()

        finally:
            await browser.close()

    if result["stop_scenario_request_count"] != 1:
        result["errors"].append(
            f"unexpected_stop_scenario_request_count={result['stop_scenario_request_count']}"
        )
    if result["interrupt_scenario_request_count"] != 2:
        result["errors"].append(
            "unexpected_interrupt_scenario_request_count="
            f"{result['interrupt_scenario_request_count']}"
        )
    if not result["stop_button_visible"]:
        result["errors"].append("stop_button_not_visible")
    if not result["escape_stop_used"]:
        result["errors"].append("escape_stop_not_used")
    if not result["relay_status_visible"]:
        result["errors"].append("relay_status_not_visible")
    if not result["turn_resume_visible"]:
        result["errors"].append("turn_resume_not_visible")
    if not result["stop_marker_visible"]:
        result["errors"].append("stop_marker_not_visible")
    if not result["interrupt_button_visible"]:
        result["errors"].append("interrupt_button_not_visible")
    if not result["final_success_visible"]:
        result["errors"].append("final_success_not_visible")
    if not result["collapsed_summary_visible"]:
        result["errors"].append("collapsed_summary_not_visible")
    if not result["timeline_toggle_visible"]:
        result["errors"].append("timeline_toggle_not_visible")
    if not result["timeline_default_collapsed"]:
        result["errors"].append("timeline_not_collapsed_by_default")
    if not result["timeline_collapsed"]:
        result["errors"].append("timeline_not_collapsed")
    if not result["timeline_reexpanded"]:
        result["errors"].append("timeline_not_reexpanded")
    if not result["timeline_jump_visible"]:
        result["errors"].append("timeline_jump_group_not_visible")
    if not result["timeline_jump_highlighted"]:
        result["errors"].append("timeline_jump_group_not_highlighted")
    if not result["timeline_jump_kept_collapsed"]:
        result["errors"].append("timeline_jump_expanded_turn")
    if not result["collapsed_summary_persisted_after_jump"]:
        result["errors"].append("collapsed_summary_not_persisted_after_jump")
    if not result["sidebar_default_collapsed"]:
        result["errors"].append("sidebar_not_collapsed_by_default")
    if not result["sidebar_expanded_after_toggle"]:
        result["errors"].append("sidebar_not_expanded_after_toggle")
    if not result["sidebar_expanded_persisted"]:
        result["errors"].append("sidebar_expanded_state_not_persisted")
    if not result["sidebar_collapsed_storage_persisted"]:
        result["errors"].append("sidebar_collapsed_storage_not_persisted")
    if not result["execution_card_visible"]:
        result["errors"].append("execution_card_not_visible")
    if not result["execution_card_expanded"]:
        result["errors"].append("execution_card_not_expanded")
    if not result["execution_tool_badge_visible"]:
        result["errors"].append("execution_tool_badge_not_visible")
    if not result["execution_tool_filter_visible"]:
        result["errors"].append("execution_tool_filter_not_visible")
    if not result["execution_tool_filter_applied"]:
        result["errors"].append("execution_tool_filter_not_applied")
    if not result["execution_tool_filter_persisted"]:
        result["errors"].append("execution_tool_filter_not_persisted")
    if not result["execution_terminal_visible"]:
        result["errors"].append("execution_terminal_not_visible")
    if not result["execution_tool_detail_visible"]:
        result["errors"].append("execution_tool_detail_not_visible")
    if result["reasoning_leak_marker"]:
        result["errors"].append(f"reasoning_leak_detected={result['reasoning_leak_marker']}")

    if result["tail_groups"]:
        last_group = result["tail_groups"][-1]
        last_group_text = str(last_group.get("text", ""))
        if expected_content not in last_group_text:
            result["errors"].append("unexpected_final_group_content")

    result["ok"] = not result["errors"]
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run chat interrupt smoke test in Chrome.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--headed", action="store_true", help="Run with a visible browser window.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = asyncio.run(run_interrupt_smoke(url=args.url, headless=not args.headed))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
