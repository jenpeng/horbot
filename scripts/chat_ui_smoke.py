#!/usr/bin/env python3
"""Browser-level smoke tests for the chat UI."""

from __future__ import annotations

import argparse
import asyncio
import base64
import binascii
import json
import mimetypes
import re
import struct
import subprocess
import sys
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile
import zlib

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import Page
from playwright.async_api import async_playwright

from playwright_browser import launch_browser


DEFAULT_URL = "http://127.0.0.1:3000/chat"
DEFAULT_SCENARIO = "team"
PENDING_TEXT = "已被提及，等待响应..."
TRANSIENT_ERROR_MARKERS = (
    "请求失败",
    "模型异常",
    "服务异常",
    "网络异常",
    "请求超时",
    "请稍后重试",
)
REASONING_LEAK_MARKERS = (
    "思路:",
    "推理过程:",
    "reasoning_content",
    "The user is asking me",
)


def normalize_assertion_text(value: str) -> str:
    lowered = value.lower()
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", lowered)


async def fetch_json(page: Page, path: str) -> dict[str, Any]:
    return await page.evaluate(
        """async (requestPath) => {
            const response = await fetch(requestPath);
            return await response.json();
        }""",
        path,
    )


async def fetch_conversation_messages(page: Page, conversation_id: str) -> list[dict[str, Any]]:
    payload = await fetch_json(page, f"/api/conversations/{conversation_id}/messages")
    messages = payload.get("messages")
    return messages if isinstance(messages, list) else []


async def delete_session(page: Page, session_key: str) -> int:
    return await page.evaluate(
        """async (targetSessionKey) => {
            const response = await fetch(`/api/chat/sessions/${encodeURIComponent(targetSessionKey)}`, {
              method: 'DELETE',
            });
            return response.status;
        }""",
        session_key,
    )


async def wait_for_conversation_message(
    page: Page,
    conversation_id: str,
    *,
    expected_text: str,
    agent_name: str | None = None,
    timeout: int = 120000,
) -> list[dict[str, Any]]:
    deadline = asyncio.get_running_loop().time() + (timeout / 1000)
    while True:
        messages = await fetch_conversation_messages(page, conversation_id)
        for message in messages:
            if message.get("role") != "assistant":
                continue
            text = str(message.get("content", "") or "")
            if expected_text not in text:
                continue
            if agent_name:
                meta = message.get("metadata") or {}
                actual_agent_name = str(meta.get("agent_name", "") or "")
                if actual_agent_name != agent_name:
                    continue
            return messages
        if asyncio.get_running_loop().time() >= deadline:
            raise PlaywrightTimeoutError(
                f"Conversation {conversation_id} did not receive assistant message {expected_text!r}"
            )
        await page.wait_for_timeout(1000)


async def collect_tail_groups(page: Page, limit: int = 12) -> list[dict[str, Any]]:
    return await page.evaluate(
        """
        (tailLimit) => Array.from(document.querySelectorAll('[data-testid="chat-message-group"]'))
          .slice(-tailLimit)
          .map((group, index) => {
            return {
              index,
              text: group.innerText.trim(),
              rowCount: group.querySelectorAll(':scope > div').length,
              isUser: group.dataset.role === 'user',
              agentId: group.dataset.agentId || '',
              agentName: group.dataset.agentName || '',
            };
          })
        """,
        limit,
    )


async def count_assistant_groups(page: Page) -> int:
    return await page.evaluate(
        "() => document.querySelectorAll('[data-testid=\"chat-message-group\"][data-role=\"assistant\"]').length"
    )


async def wait_for_assistant_group_text(
    page: Page,
    expected_text: str,
    *,
    agent_name: str | None = None,
    timeout: int = 120000,
) -> None:
    await page.wait_for_function(
        """
        ({ expectedText, expectedAgentName }) => {
          return Array.from(document.querySelectorAll('[data-testid="chat-message-group"][data-role="assistant"]'))
            .some((group) => {
              const text = (group.innerText || '').trim();
              if (!text.includes(expectedText)) {
                return false;
              }
              if (!expectedAgentName) {
                return true;
              }
              const agentName = group.getAttribute('data-agent-name') || '';
              return agentName === expectedAgentName || text.includes(expectedAgentName);
            });
        }
        """,
        arg={"expectedText": expected_text, "expectedAgentName": agent_name},
        timeout=timeout,
    )


async def wait_for_assistant_group_agent(
    page: Page,
    agent_name: str,
    *,
    timeout: int = 120000,
) -> None:
    await page.wait_for_function(
        """
        ({ expectedAgentName }) => {
          return Array.from(document.querySelectorAll('[data-testid="chat-message-group"][data-role="assistant"]'))
            .some((group) => {
              const agentName = group.getAttribute('data-agent-name') || '';
              const text = (group.innerText || '').trim();
              return agentName === expectedAgentName || text.includes(expectedAgentName);
            });
        }
        """,
        arg={"expectedAgentName": agent_name},
        timeout=timeout,
    )


async def wait_for_assistant_group_text_exact_agent(
    page: Page,
    expected_text: str,
    *,
    agent_name: str,
    timeout: int = 120000,
) -> None:
    await page.wait_for_function(
        """
        ({ expectedText, expectedAgentName }) => {
          return Array.from(document.querySelectorAll('[data-testid="chat-message-group"][data-role="assistant"]'))
            .some((group) => {
              const text = (group.innerText || '').trim();
              const actualAgentName = group.getAttribute('data-agent-name') || '';
              return actualAgentName === expectedAgentName && text.includes(expectedText);
            });
        }
        """,
        arg={"expectedText": expected_text, "expectedAgentName": agent_name},
        timeout=timeout,
    )


async def wait_for_relay_summary_or_agent(
    page: Page,
    *,
    agent_name: str,
    timeout: int = 30000,
) -> None:
    await page.wait_for_function(
        """
        ({ expectedAgentName }) => {
          const assistantMatch = Array.from(
            document.querySelectorAll('[data-testid="chat-message-group"][data-role="assistant"]')
          ).some((group) => {
            const agentName = group.getAttribute('data-agent-name') || '';
            const text = (group.innerText || '').trim();
            return agentName === expectedAgentName || text.includes(expectedAgentName);
          });
          if (assistantMatch) {
            return true;
          }
          const relaySummary = document.querySelector('[data-testid="chat-turn-collapsed-summary"]');
          if (relaySummary) {
            return true;
          }
          const relayTimeline = document.querySelector('[data-testid="chat-turn-timeline"][data-collapsed="true"]');
          return Boolean(relayTimeline);
        }
        """,
        arg={"expectedAgentName": agent_name},
        timeout=timeout,
    )


def find_last_group(
    groups: list[dict[str, Any]],
    *,
    text_includes: str | None = None,
    is_user: bool | None = None,
) -> dict[str, Any] | None:
    for group in reversed(groups):
        if is_user is not None and bool(group.get("isUser")) != is_user:
            continue
        if text_includes and text_includes not in str(group.get("text", "")):
            continue
        return group
    return None


def last_non_empty_line(text: str) -> str:
    ignored_lines = {"复制内容", "重试上一条"}
    for line in reversed([line.strip() for line in text.splitlines()]):
        if line:
            if line in ignored_lines:
                continue
            return line
    return ""


def find_reasoning_leak(groups: list[dict[str, Any]]) -> str:
    for group in groups:
        text = str(group.get("text", ""))
        for marker in REASONING_LEAK_MARKERS:
            if marker in text:
                return marker
    return ""


async def wait_for_generation_idle(page: Page, timeout: int = 120000) -> None:
    await page.wait_for_function(
        """
        () => {
          const activeLabels = ['停止生成', '停止接力', '停止并发送'];
          return !Array.from(document.querySelectorAll('button'))
            .some((button) => {
              const label = (
                button.getAttribute('aria-label')
                || button.getAttribute('title')
                || button.innerText
                || ''
              ).trim();
              return activeLabels.includes(label);
            });
        }
        """,
        timeout=timeout,
    )


async def reset_chat_browser_state(page: Page) -> None:
    await page.goto("about:blank", wait_until="load")
    await page.evaluate(
        """
        () => {
          try {
            window.localStorage.removeItem('horbot-conversations');
                        window.sessionStorage.clear();
          } catch (error) {
            console.warn('Failed to reset browser storage for smoke test:', error);
          }
        }
        """
    )


def build_default_dm_prompt(expected_substring: str) -> str:
    return f"请只回复这个字符串，不要添加任何其他内容：{expected_substring}"


def build_default_team_prompt(secondary_agent_name: str, expected_substring: str) -> str:
    return (
        "这是一条正常的端到端健康检查消息，不是注入测试。"
        f"请把下一棒明确交给 {secondary_agent_name}，并由 {secondary_agent_name} 最终只回复这个字符串："
        f"{expected_substring}。不要额外解释，不要寒暄。"
    )


def should_retry_result(result: dict[str, Any]) -> bool:
    if result.get("ok"):
        return False

    errors = {str(error) for error in result.get("errors") or []}
    if not errors:
        return False

    retryable_errors = {
        "secondary_agent_group_missing",
        "secondary_agent_group_unexpected_final_content",
        "dm_agent_group_missing_expected_content",
        "timeout",
    }
    if not errors.isdisjoint(retryable_errors):
        return True

    timeout_errors = [error for error in errors if error.startswith("timeout:")]
    if timeout_errors:
        return True

    if errors.isdisjoint(retryable_errors):
        return False

    tail_groups = result.get("tail_groups") or []
    for group in tail_groups:
        text = str(group.get("text", ""))
        if any(marker in text for marker in TRANSIENT_ERROR_MARKERS):
            return True

    return False


async def resolve_dm_agent_name(page: Page, requested_name: str | None) -> str:
    agents_data = await fetch_json(page, "/api/agents")
    agents = agents_data.get("agents") or []
    if not agents:
        raise RuntimeError("No agents available for DM smoke test")

    if requested_name:
        for agent in agents:
            if agent.get("name") == requested_name:
                return requested_name
        raise RuntimeError(f'DM agent "{requested_name}" not found')

    for agent in agents:
        if agent.get("is_main"):
            return str(agent["name"])

    return str(agents[0]["name"])


async def resolve_team_targets(
    page: Page,
    requested_team_name: str | None,
    requested_secondary_agent_name: str | None,
) -> tuple[str, str, str]:
    agents_data = await fetch_json(page, "/api/agents")
    teams_data = await fetch_json(page, "/api/teams")

    agents = agents_data.get("agents") or []
    teams = teams_data.get("teams") or []
    if not teams:
        raise RuntimeError("No teams available for team smoke test")

    team = None
    if requested_team_name:
        team = next((item for item in teams if item.get("name") == requested_team_name), None)
        if not team:
            raise RuntimeError(f'Team "{requested_team_name}" not found')
    else:
        team = teams[0]

    agent_by_id = {str(agent.get("id")): agent for agent in agents if agent.get("id")}

    if requested_secondary_agent_name:
        secondary_name = requested_secondary_agent_name
    else:
        secondary_name = ""
        for member_id in team.get("members") or []:
            member = agent_by_id.get(str(member_id))
            if member and not member.get("is_main"):
                secondary_name = str(member["name"])
                break
        if not secondary_name and team.get("members"):
            member = agent_by_id.get(str(team["members"][0]))
            if member:
                secondary_name = str(member["name"])

    if not secondary_name:
        raise RuntimeError(f'Unable to resolve a secondary agent for team "{team.get("name")}"')

    return str(team["id"]), str(team["name"]), secondary_name


async def resolve_dm_team_dispatch_targets(
    page: Page,
    requested_team_name: str | None,
    requested_secondary_agent_name: str | None,
    requested_dm_agent_name: str | None,
) -> tuple[str, str, str, str]:
    agents_data = await fetch_json(page, "/api/agents")
    teams_data = await fetch_json(page, "/api/teams")

    agents = agents_data.get("agents") or []
    teams = teams_data.get("teams") or []
    if not teams:
        raise RuntimeError("No teams available for dm-team-dispatch smoke test")

    team = None
    if requested_team_name:
        team = next((item for item in teams if item.get("name") == requested_team_name), None)
        if not team:
            raise RuntimeError(f'Team "{requested_team_name}" not found')
    else:
        team = teams[0]

    agent_by_id = {str(agent.get("id")): agent for agent in agents if agent.get("id")}
    member_ids = [str(member_id) for member_id in team.get("members") or []]
    if len(member_ids) < 2:
        raise RuntimeError(f'Team "{team.get("name")}" needs at least two members for dm-team-dispatch smoke test')

    if requested_secondary_agent_name:
        secondary_agent = next(
            (
                agent_by_id.get(member_id)
                for member_id in member_ids
                if (agent_by_id.get(member_id) or {}).get("name") == requested_secondary_agent_name
            ),
            None,
        )
        if secondary_agent is None:
            raise RuntimeError(f'Secondary agent "{requested_secondary_agent_name}" not found in team "{team.get("name")}"')
    else:
        secondary_agent = next(
            (agent_by_id.get(member_id) for member_id in member_ids if (agent_by_id.get(member_id) or {}).get("is_main")),
            None,
        )
        if secondary_agent is None:
            secondary_agent = next(
                (agent_by_id.get(member_id) for member_id in reversed(member_ids) if agent_by_id.get(member_id)),
                None,
            )
    if secondary_agent is None:
        raise RuntimeError(f'Unable to resolve a secondary agent for team "{team.get("name")}"')

    secondary_agent_id = str(secondary_agent.get("id"))
    secondary_agent_name = str(secondary_agent.get("name"))

    if requested_dm_agent_name:
        dm_agent = next(
            (
                agent_by_id.get(member_id)
                for member_id in member_ids
                if (agent_by_id.get(member_id) or {}).get("name") == requested_dm_agent_name
            ),
            None,
        )
        if dm_agent is None:
            raise RuntimeError(f'DM agent "{requested_dm_agent_name}" not found in team "{team.get("name")}"')
        if str(dm_agent.get("id")) == secondary_agent_id:
            raise RuntimeError("DM agent and secondary agent must be different for dm-team-dispatch smoke test")
    else:
        dm_agent = next(
            (
                agent_by_id.get(member_id)
                for member_id in member_ids
                if agent_by_id.get(member_id) and str(agent_by_id.get(member_id).get("id")) != secondary_agent_id
            ),
            None,
        )
    if dm_agent is None:
        raise RuntimeError(f'Unable to resolve a DM initiator for team "{team.get("name")}"')

    return (
        str(team["id"]),
        str(team["name"]),
        str(dm_agent.get("name")),
        secondary_agent_name,
    )


async def open_chat(page: Page, url: str) -> None:
    await reset_chat_browser_state(page)
    await page.goto(url, wait_until="domcontentloaded", timeout=120000)
    try:
        await page.wait_for_load_state("load", timeout=10000)
    except PlaywrightTimeoutError:
        pass
    await page.locator("textarea").first.wait_for(timeout=30000)


async def reload_chat(page: Page) -> None:
    await page.reload(wait_until="domcontentloaded", timeout=120000)
    try:
        await page.wait_for_load_state("load", timeout=10000)
    except PlaywrightTimeoutError:
        pass
    await page.locator("textarea").first.wait_for(timeout=30000)


async def select_conversation(page: Page, name: str) -> None:
    button = page.locator("button").filter(has_text=name).first
    await button.wait_for(timeout=30000)
    await button.click()
    await page.locator("h2").filter(has_text=name).first.wait_for(timeout=30000)


async def send_message(page: Page, prompt: str) -> None:
    textarea = page.locator("textarea").first
    await textarea.wait_for(timeout=30000)
    await textarea.fill(prompt)
    await page.get_by_role("button", name="发送消息").click()


async def open_message_file_preview(
    page: Page,
    *,
    message_text: str,
    file_name: str,
) -> dict[str, Any]:
    user_group = (
        page.locator('[data-testid="chat-message-group"][data-role="user"]')
        .filter(has_text=message_text)
        .last
    )
    await user_group.wait_for(timeout=30000)

    preview_button = user_group.get_by_test_id("message-file-open-preview").filter(has_text=file_name).first
    await preview_button.wait_for(timeout=10000)
    await preview_button.click()

    modal = page.get_by_test_id("message-file-preview-modal")
    await modal.wait_for(state="visible", timeout=10000)
    await page.wait_for_timeout(300)

    modal_text = await modal.inner_text()
    preview_state = {
        "visible": True,
        "text": modal_text,
        "has_iframe": await modal.locator("iframe").count() > 0,
        "has_audio": await modal.locator("audio").count() > 0,
        "has_image": await modal.locator("img").count() > 0,
        "open_original_visible": "打开原文件" in modal_text,
    }

    close_button = page.get_by_role("button", name="关闭").last
    if await close_button.count() > 0:
        await close_button.click()
    else:
        await page.keyboard.press("Escape")
    await modal.wait_for(state="hidden", timeout=10000)
    return preview_state


def create_attachment_samples(directory: Path) -> tuple[Path, Path, str, str]:
    pdf_token = f"PDF_TOKEN_{uuid.uuid4().hex[:8]}"
    docx_token = f"DOCX_TOKEN_{uuid.uuid4().hex[:8]}"

    pdf_path = directory / "chat-attachment-smoke.pdf"
    create_simple_pdf(pdf_path, f"Smoke PDF marker: {pdf_token}")

    docx_path = directory / "chat-attachment-smoke.docx"
    create_simple_docx(docx_path, f"Smoke DOCX marker: {docx_token}")

    return pdf_path, docx_path, pdf_token, docx_token


def create_office_attachment_samples(directory: Path) -> tuple[Path, Path, str, str]:
    xlsx_token = f"XLSX_TOKEN_{uuid.uuid4().hex[:8]}"
    pptx_token = f"PPTX_TOKEN_{uuid.uuid4().hex[:8]}"

    xlsx_path = directory / "chat-office-smoke.xlsx"
    create_simple_xlsx(xlsx_path, f"Smoke XLSX marker: {xlsx_token}")

    pptx_path = directory / "chat-office-smoke.pptx"
    create_simple_pptx(pptx_path, f"Smoke PPTX marker: {pptx_token}")

    return xlsx_path, pptx_path, xlsx_token, pptx_token


def create_media_attachment_samples(directory: Path) -> tuple[Path, Path, str]:
    image_path = directory / "chat-media-smoke.png"
    create_shape_png(image_path)

    audio_path = directory / "chat-media-smoke.wav"
    audio_phrase = "hello world"
    create_spoken_wav(audio_path, audio_phrase)

    return image_path, audio_path, audio_phrase


def create_simple_docx(path: Path, text: str) -> None:
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    document = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:r>
        <w:t>{escaped}</w:t>
      </w:r>
    </w:p>
    <w:sectPr>
      <w:pgSz w:w="12240" w:h="15840"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>
"""
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)


def create_simple_pdf(path: Path, text: str) -> None:
    def escape_pdf_text(value: str) -> str:
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    content_stream = f"BT /F1 18 Tf 72 720 Td ({escape_pdf_text(text)}) Tj ET".encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content_stream), content_stream),
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(pdf)


def create_shape_png(path: Path) -> None:
    width = 160
    height = 120
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            red, green, blue = 255, 255, 255
            if 18 <= x <= 62 and 22 <= y <= 66:
                red, green, blue = 225, 45, 45
            circle_center_x, circle_center_y, radius = 112, 60, 24
            if (x - circle_center_x) ** 2 + (y - circle_center_y) ** 2 <= radius ** 2:
                red, green, blue = 48, 105, 232
            rows.extend((red, green, blue))

    compressed = zlib.compress(bytes(rows), level=9)

    def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + chunk_type
            + data
            + struct.pack(">I", binascii.crc32(chunk_type + data) & 0xFFFFFFFF)
        )

    png = bytearray(b"\x89PNG\r\n\x1a\n")
    png.extend(png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)))
    png.extend(png_chunk(b"IDAT", compressed))
    png.extend(png_chunk(b"IEND", b""))
    path.write_bytes(png)


def create_spoken_wav(path: Path, text: str) -> None:
    aiff_path = path.with_suffix(".aiff")
    subprocess.run(
        ["say", "-v", "Samantha", "-r", "170", "-o", str(aiff_path), text],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["afconvert", "-f", "WAVE", "-d", "LEI16@16000", str(aiff_path), str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    if aiff_path.exists():
        aiff_path.unlink()


def create_simple_xlsx(path: Path, text: str) -> None:
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
"""
    workbook = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Sheet1" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
"""
    workbook_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>
"""
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    sheet = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1" t="inlineStr">
        <is><t>{escaped}</t></is>
      </c>
    </row>
  </sheetData>
</worksheet>
"""
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)


def create_simple_pptx(path: Path, text: str) -> None:
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>
"""
    presentation = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:sldIdLst>
    <p:sldId id="256" r:id="rId1"/>
  </p:sldIdLst>
</p:presentation>
"""
    presentation_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>
</Relationships>
"""
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    slide = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:sp>
        <p:txBody>
          <a:p>
            <a:r><a:t>{escaped}</a:t></a:r>
          </a:p>
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>
"""
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("ppt/presentation.xml", presentation)
        archive.writestr("ppt/_rels/presentation.xml.rels", presentation_rels)
        archive.writestr("ppt/slides/slide1.xml", slide)


async def send_message_with_attachments(page: Page, prompt: str, files: list[Path]) -> None:
    textarea = page.locator("textarea").first
    file_input = page.locator('input[type="file"]').first
    await textarea.wait_for(timeout=30000)
    await file_input.set_input_files([str(file_path) for file_path in files])
    await textarea.fill(prompt)
    await page.get_by_role("button", name="发送消息").click()


async def paste_files_via_clipboard(page: Page, files: list[Path]) -> None:
    encoded_files = [
        {
            "name": file_path.name,
            "mime": mimetypes.guess_type(file_path.name)[0] or "application/octet-stream",
            "base64": base64.b64encode(file_path.read_bytes()).decode("ascii"),
        }
        for file_path in files
    ]
    await page.evaluate(
        """
        async ({ files }) => {
          const textarea = document.querySelector('textarea');
          if (!textarea) {
            throw new Error('textarea_not_found');
          }
          const dataTransfer = new DataTransfer();
          for (const file of files) {
            const binary = Uint8Array.from(atob(file.base64), (char) => char.charCodeAt(0));
            dataTransfer.items.add(new File([binary], file.name, { type: file.mime }));
          }
          const event = new ClipboardEvent('paste', {
            clipboardData: dataTransfer,
            bubbles: true,
            cancelable: true,
          });
          textarea.dispatchEvent(event);
        }
        """,
        {"files": encoded_files},
    )


async def dispatch_drag_files(page: Page, files: list[Path], event_types: list[str]) -> None:
    encoded_files = [
        {
            "name": file_path.name,
            "mime": mimetypes.guess_type(file_path.name)[0] or "application/octet-stream",
            "base64": base64.b64encode(file_path.read_bytes()).decode("ascii"),
        }
        for file_path in files
    ]
    await page.evaluate(
        """
        async ({ files, eventTypes }) => {
          const textarea = document.querySelector('textarea');
          if (!textarea) {
            throw new Error('textarea_not_found');
          }
          const dataTransfer = new DataTransfer();
          for (const file of files) {
            const binary = Uint8Array.from(atob(file.base64), (char) => char.charCodeAt(0));
            dataTransfer.items.add(new File([binary], file.name, { type: file.mime }));
          }
          const dispatch = (type) => {
            const event = new DragEvent(type, {
              dataTransfer,
              bubbles: true,
              cancelable: true,
            });
            textarea.dispatchEvent(event);
          };
          for (const eventType of eventTypes) {
            dispatch(eventType);
          }
        }
        """,
        {"files": encoded_files, "eventTypes": event_types},
    )


async def drag_files_into_composer(page: Page, files: list[Path]) -> None:
    await dispatch_drag_files(page, files, ["dragenter", "dragover", "drop", "dragleave"])


async def install_single_upload_failure(page: Page, error_message: str = "smoke upload failure") -> None:
    failed_once = {"done": False}

    async def handler(route):
        if route.request.method == "POST" and not failed_once["done"]:
            failed_once["done"] = True
            await route.fulfill(
                status=500,
                content_type="application/json",
                body=json.dumps({"detail": error_message}),
            )
            return
        await route.continue_()

    await page.route("**/api/upload", handler)


async def run_team_smoke(
    *,
    page: Page,
    team_name: str | None,
    secondary_agent_name: str | None,
    prompt: str | None,
) -> dict[str, Any]:
    resolved_team_id, resolved_team_name, resolved_secondary_agent_name = await resolve_team_targets(
        page,
        team_name,
        secondary_agent_name,
    )
    resolved_expected = f"TEAM_SMOKE_OK_{uuid.uuid4().hex[:8]}"
    actual_prompt = prompt or build_default_team_prompt(
        resolved_secondary_agent_name,
        resolved_expected,
    )

    result: dict[str, Any] = {
        "ok": False,
        "scenario": "team",
        "team_name": resolved_team_name,
        "secondary_agent_name": resolved_secondary_agent_name,
        "expected_substring": resolved_expected,
        "secondary_forbidden_substring": "不要额外解释，不要寒暄",
        "team_selected": False,
        "pending_appeared": False,
        "pending_cleared": False,
        "pending_visible_at_end": False,
        "tail_groups": [],
        "last_group_for_secondary": None,
        "session_delete_status": None,
        "reasoning_leak_marker": "",
        "errors": [],
    }

    delete_status = await delete_session(page, f"web:team_{resolved_team_id}")
    if delete_status not in {200, 404}:
        result["errors"].append(f"unexpected_session_delete_status={delete_status}")
    result["session_delete_status"] = delete_status

    await select_conversation(page, resolved_team_name)
    result["team_selected"] = True
    await send_message(page, actual_prompt)

    try:
        await page.wait_for_function(
            f"() => document.body.innerText.includes({json.dumps(PENDING_TEXT)})",
            timeout=30000,
        )
        result["pending_appeared"] = True
    except PlaywrightTimeoutError:
        pass

    await page.wait_for_function(
        f"() => !document.body.innerText.includes({json.dumps(PENDING_TEXT)})",
        timeout=120000,
    )
    result["pending_cleared"] = True
    await wait_for_assistant_group_text(
        page,
        resolved_expected,
        agent_name=resolved_secondary_agent_name,
        timeout=120000,
    )
    await wait_for_generation_idle(page)
    await page.wait_for_timeout(2000)

    tail_groups = await collect_tail_groups(page)
    result["tail_groups"] = tail_groups
    result["pending_visible_at_end"] = PENDING_TEXT in await page.locator("body").inner_text()
    result["reasoning_leak_marker"] = find_reasoning_leak(tail_groups)

    last_secondary = find_last_group(
        tail_groups,
        text_includes=resolved_secondary_agent_name,
        is_user=False,
    )
    result["last_group_for_secondary"] = last_secondary

    if result["pending_visible_at_end"]:
        result["errors"].append("pending_placeholder_still_visible")
    if result["reasoning_leak_marker"]:
        result["errors"].append(f"reasoning_leak_detected={result['reasoning_leak_marker']}")
    if not last_secondary:
        result["errors"].append("secondary_agent_group_missing")
    else:
        if last_secondary["rowCount"] != 1:
            result["errors"].append(
                f"secondary_agent_group_row_count={last_secondary['rowCount']}"
            )
        if resolved_expected not in last_secondary["text"]:
            result["errors"].append("secondary_agent_group_unexpected_final_content")
        if result["secondary_forbidden_substring"] in last_secondary["text"]:
            result["errors"].append("secondary_agent_group_contains_forwarded_instruction")

    result["ok"] = not result["errors"]
    return result


async def run_dm_smoke(
    *,
    page: Page,
    agent_name: str | None,
    prompt: str | None,
    expected_substring: str | None,
) -> dict[str, Any]:
    resolved_agent_name = await resolve_dm_agent_name(page, agent_name)
    resolved_expected = expected_substring or f"DM_SMOKE_OK_{uuid.uuid4().hex[:8]}"
    actual_prompt = prompt or build_default_dm_prompt(resolved_expected)

    result: dict[str, Any] = {
        "ok": False,
        "scenario": "dm",
        "agent_name": resolved_agent_name,
        "expected_substring": resolved_expected,
        "agent_selected": False,
        "tail_groups": [],
        "last_group_for_agent": None,
        "reasoning_leak_marker": "",
        "message_wrapper_leak": False,
        "errors": [],
    }

    await select_conversation(page, resolved_agent_name)
    result["agent_selected"] = True
    await send_message(page, actual_prompt)

    await wait_for_assistant_group_text(
        page,
        resolved_expected,
        agent_name=resolved_agent_name,
        timeout=120000,
    )
    await wait_for_generation_idle(page)
    await page.wait_for_timeout(2000)

    tail_groups = await collect_tail_groups(page)
    result["tail_groups"] = tail_groups
    result["reasoning_leak_marker"] = find_reasoning_leak(tail_groups)
    result["message_wrapper_leak"] = any(
        "<message from=" in str(group.get("text", ""))
        for group in tail_groups
    )

    last_agent_group = find_last_group(
        tail_groups,
        text_includes=resolved_agent_name,
        is_user=False,
    )
    result["last_group_for_agent"] = last_agent_group

    if not last_agent_group:
        result["errors"].append("dm_agent_group_missing")
    else:
        if last_agent_group["rowCount"] != 1:
            result["errors"].append(f"dm_agent_group_row_count={last_agent_group['rowCount']}")
        if resolved_expected not in last_agent_group["text"]:
            result["errors"].append("dm_agent_group_missing_expected_content")
    if result["reasoning_leak_marker"]:
        result["errors"].append(f"reasoning_leak_detected={result['reasoning_leak_marker']}")
    if result["message_wrapper_leak"]:
        result["errors"].append("dm_agent_group_contains_message_wrapper")

    result["ok"] = not result["errors"]
    return result


async def run_dm_team_dispatch_smoke(
    *,
    page: Page,
    team_name: str | None,
    secondary_agent_name: str | None,
    dm_agent_name: str | None,
    prompt: str | None,
) -> dict[str, Any]:
    (
        resolved_team_id,
        resolved_team_name,
        resolved_dm_agent_name,
        resolved_secondary_agent_name,
    ) = await resolve_dm_team_dispatch_targets(
        page,
        team_name,
        secondary_agent_name,
        dm_agent_name,
    )

    expected_final = f"DM_TEAM_DISPATCH_OK_{uuid.uuid4().hex[:8]}"
    actual_prompt = prompt or (
        f"请使用 message 工具把一条消息发到团队群聊，chat_id 用 team_{resolved_team_id}，并触发群内后续处理。"
        f"请明确 @ {resolved_secondary_agent_name} 接手，"
        f"要求 {resolved_secondary_agent_name} 在团队群里最终只回复这个字符串：{expected_final}。"
        "你发完后自己只回复发送确认，不要解释。"
    )

    result: dict[str, Any] = {
        "ok": False,
        "scenario": "dm-team-dispatch",
        "team_name": resolved_team_name,
        "dm_agent_name": resolved_dm_agent_name,
        "secondary_agent_name": resolved_secondary_agent_name,
        "expected_final": expected_final,
        "team_selected": False,
        "dm_selected": False,
        "dm_confirmation_visible": False,
        "team_dispatch_visible": False,
        "team_final_visible": False,
        "tail_groups_dm": [],
        "tail_groups_team": [],
        "dm_group": None,
        "team_dispatch_group": None,
        "team_final_group": None,
        "team_relay_summary_visible": False,
        "team_api_messages": [],
        "team_session_delete_status": None,
        "reasoning_leak_marker_dm": "",
        "reasoning_leak_marker_team": "",
        "errors": [],
    }

    delete_status = await delete_session(page, f"web:team_{resolved_team_id}")
    result["team_session_delete_status"] = delete_status
    if delete_status not in {200, 404}:
        result["errors"].append(f"unexpected_team_session_delete_status={delete_status}")

    await select_conversation(page, resolved_dm_agent_name)
    result["dm_selected"] = True
    assistant_count_before_dm = await count_assistant_groups(page)
    await send_message(page, actual_prompt)

    await page.wait_for_function(
        """
        (expectedCount) => document.querySelectorAll('[data-testid="chat-message-group"][data-role="assistant"]').length > expectedCount
        """,
        arg=assistant_count_before_dm,
        timeout=120000,
    )
    await wait_for_generation_idle(page)
    await page.wait_for_timeout(1500)

    tail_groups_dm = await collect_tail_groups(page)
    result["tail_groups_dm"] = tail_groups_dm
    result["reasoning_leak_marker_dm"] = find_reasoning_leak(tail_groups_dm)
    dm_group = find_last_group(
        tail_groups_dm,
        is_user=False,
    )
    result["dm_group"] = dm_group
    result["dm_confirmation_visible"] = bool(
        dm_group
        and str(dm_group.get("agentName", "") or "") == resolved_dm_agent_name
        and "执行过程" in str(dm_group.get("text", ""))
        and "message" in str(dm_group.get("text", ""))
    )

    await select_conversation(page, resolved_team_name)
    result["team_selected"] = True
    team_conversation_id = f"team_{resolved_team_id}"
    await wait_for_conversation_message(
        page,
        team_conversation_id,
        expected_text="@",
        agent_name=resolved_dm_agent_name,
        timeout=120000,
    )
    team_messages = await wait_for_conversation_message(
        page,
        team_conversation_id,
        expected_text=expected_final,
        agent_name=resolved_secondary_agent_name,
        timeout=120000,
    )
    result["team_api_messages"] = team_messages[-8:]
    await reload_chat(page)
    await select_conversation(page, resolved_team_name)
    await wait_for_relay_summary_or_agent(page, agent_name=resolved_dm_agent_name, timeout=30000)
    await wait_for_assistant_group_text_exact_agent(
        page,
        expected_final,
        agent_name=resolved_secondary_agent_name,
        timeout=30000,
    )
    await wait_for_generation_idle(page)
    await page.wait_for_timeout(2000)

    tail_groups_team = await collect_tail_groups(page)
    result["tail_groups_team"] = tail_groups_team
    result["reasoning_leak_marker_team"] = find_reasoning_leak(tail_groups_team)
    dispatch_group = next(
        (
            group
            for group in reversed(tail_groups_team)
            if not group.get("isUser")
            and str(group.get("agentName", "") or "") == resolved_dm_agent_name
        ),
        None,
    )
    final_group = next(
        (
            group
            for group in reversed(tail_groups_team)
            if not group.get("isUser")
            and str(group.get("agentName", "") or "") == resolved_secondary_agent_name
            and expected_final in str(group.get("text", ""))
        ),
        None,
    )
    result["team_dispatch_group"] = dispatch_group
    result["team_final_group"] = final_group
    result["team_relay_summary_visible"] = await page.evaluate(
        """
        () => Boolean(
          document.querySelector('[data-testid="chat-turn-collapsed-summary"]')
          || document.querySelector('[data-testid="chat-turn-timeline"][data-collapsed="true"]')
        )
        """
    )
    result["team_dispatch_visible"] = dispatch_group is not None
    result["team_final_visible"] = final_group is not None

    if not dm_group:
        result["errors"].append("dm_confirmation_missing")
    elif not result["dm_confirmation_visible"]:
        result["errors"].append("dm_confirmation_unexpected_content")
    if result["reasoning_leak_marker_dm"]:
        result["errors"].append(f"reasoning_leak_detected_dm={result['reasoning_leak_marker_dm']}")
    dispatch_found_in_api = any(
        isinstance(message, dict)
        and (message.get("metadata") or {}).get("agent_name") == resolved_dm_agent_name
        for message in result["team_api_messages"]
    )
    if not dispatch_group and not dispatch_found_in_api and not result["team_relay_summary_visible"]:
        result["errors"].append("team_dispatch_group_missing")
    else:
        dispatch_agent_name = str(dispatch_group.get("agentName", "") or "") if dispatch_group else ""
        if dispatch_agent_name and dispatch_agent_name != resolved_dm_agent_name:
            result["errors"].append(f"team_dispatch_agent_mismatch={dispatch_agent_name}")
    if not final_group:
        result["errors"].append("team_final_group_missing")
    else:
        final_agent_name = str(final_group.get("agentName", "") or "")
        if final_agent_name and final_agent_name != resolved_secondary_agent_name:
            result["errors"].append(f"team_final_agent_mismatch={final_agent_name}")
        if expected_final not in str(final_group.get("text", "")):
            result["errors"].append("team_final_expected_content_missing")
    if result["reasoning_leak_marker_team"]:
        result["errors"].append(f"reasoning_leak_detected_team={result['reasoning_leak_marker_team']}")

    result["ok"] = not result["errors"]
    return result


async def run_attachment_smoke(
    *,
    page: Page,
    agent_name: str | None,
) -> dict[str, Any]:
    resolved_agent_name = await resolve_dm_agent_name(page, agent_name)

    result: dict[str, Any] = {
        "ok": False,
        "scenario": "attachments",
        "agent_name": resolved_agent_name,
        "pdf_attachment_visible": False,
        "docx_attachment_visible": False,
        "user_group_contains_attachment_names": False,
        "assistant_contains_pdf_token": False,
        "assistant_contains_docx_token": False,
        "pdf_preview_modal_visible": False,
        "pdf_preview_has_iframe": False,
        "docx_preview_modal_visible": False,
        "docx_preview_has_preview_state": False,
        "docx_preview_open_original_visible": False,
        "tail_groups": [],
        "errors": [],
    }

    await select_conversation(page, resolved_agent_name)

    with TemporaryDirectory() as tmpdir:
        pdf_path, docx_path, pdf_token, docx_token = create_attachment_samples(Path(tmpdir))
        prompt = (
            "请阅读我刚上传的 PDF 和 DOCX 文档，"
            f"并只回复这两个标记，用中文逗号分隔：{pdf_token}，{docx_token}"
        )

        await send_message_with_attachments(page, prompt, [pdf_path, docx_path])

        await page.wait_for_function(
            """
            () => {
              const bodyText = document.body.innerText || '';
              return bodyText.includes('chat-attachment-smoke.pdf') && bodyText.includes('chat-attachment-smoke.docx');
            }
            """,
            timeout=30000,
        )

        await wait_for_assistant_group_text(
            page,
            pdf_token,
            agent_name=resolved_agent_name,
            timeout=120000,
        )
        await wait_for_assistant_group_text(
            page,
            docx_token,
            agent_name=resolved_agent_name,
            timeout=120000,
        )
        await wait_for_generation_idle(page)
        await page.wait_for_timeout(2000)

        pdf_preview = await open_message_file_preview(
            page,
            message_text=prompt,
            file_name="chat-attachment-smoke.pdf",
        )
        result["pdf_preview_modal_visible"] = bool(pdf_preview["visible"])
        result["pdf_preview_has_iframe"] = bool(pdf_preview["has_iframe"])

        docx_preview = await open_message_file_preview(
            page,
            message_text=prompt,
            file_name="chat-attachment-smoke.docx",
        )
        result["docx_preview_modal_visible"] = bool(docx_preview["visible"])
        docx_preview_text = str(docx_preview["text"])
        result["docx_preview_has_preview_state"] = any(
            marker in docx_preview_text
            for marker in (
                docx_token,
                "当前预览展示的是解析出的文本内容",
                "当前类型暂不支持直接内嵌预览",
            )
        )
        result["docx_preview_open_original_visible"] = bool(docx_preview["open_original_visible"])

        tail_groups = await collect_tail_groups(page)
        result["tail_groups"] = tail_groups
        result["pdf_attachment_visible"] = any("chat-attachment-smoke.pdf" in str(group.get("text", "")) for group in tail_groups)
        result["docx_attachment_visible"] = any("chat-attachment-smoke.docx" in str(group.get("text", "")) for group in tail_groups)

        last_user_group = find_last_group(tail_groups, text_includes="chat-attachment-smoke", is_user=True)
        last_agent_group = find_last_group(tail_groups, text_includes=resolved_agent_name, is_user=False)

        if last_user_group:
            result["user_group_contains_attachment_names"] = (
                "chat-attachment-smoke.pdf" in last_user_group["text"]
                and "chat-attachment-smoke.docx" in last_user_group["text"]
            )

        if last_agent_group:
            agent_text = str(last_agent_group.get("text", ""))
            result["assistant_contains_pdf_token"] = pdf_token in agent_text
            result["assistant_contains_docx_token"] = docx_token in agent_text

        if not result["pdf_attachment_visible"]:
            result["errors"].append("pdf_attachment_not_visible")
        if not result["docx_attachment_visible"]:
            result["errors"].append("docx_attachment_not_visible")
        if not result["user_group_contains_attachment_names"]:
            result["errors"].append("user_group_missing_attachment_names")
        if not result["assistant_contains_pdf_token"]:
            result["errors"].append("assistant_missing_pdf_token")
        if not result["assistant_contains_docx_token"]:
            result["errors"].append("assistant_missing_docx_token")
        if not result["pdf_preview_modal_visible"]:
            result["errors"].append("pdf_preview_modal_not_visible")
        if not result["pdf_preview_has_iframe"]:
            result["errors"].append("pdf_preview_iframe_missing")
        if not result["docx_preview_modal_visible"]:
            result["errors"].append("docx_preview_modal_not_visible")
        if not result["docx_preview_has_preview_state"]:
            result["errors"].append("docx_preview_missing_preview_state")
        if not result["docx_preview_open_original_visible"]:
            result["errors"].append("docx_preview_missing_open_original")

    result["ok"] = not result["errors"]
    return result


async def run_office_attachment_smoke(
    *,
    page: Page,
    agent_name: str | None,
) -> dict[str, Any]:
    resolved_agent_name = await resolve_dm_agent_name(page, agent_name)

    result: dict[str, Any] = {
        "ok": False,
        "scenario": "office-attachments",
        "agent_name": resolved_agent_name,
        "xlsx_attachment_visible": False,
        "pptx_attachment_visible": False,
        "user_group_contains_attachment_names": False,
        "assistant_contains_xlsx_token": False,
        "assistant_contains_pptx_token": False,
        "tail_groups": [],
        "errors": [],
    }

    await select_conversation(page, resolved_agent_name)

    with TemporaryDirectory() as tmpdir:
        xlsx_path, pptx_path, xlsx_token, pptx_token = create_office_attachment_samples(Path(tmpdir))
        prompt = (
            "请阅读我刚上传的 XLSX 和 PPTX 文件，"
            f"并只回复这两个标记，用中文逗号分隔：{xlsx_token}，{pptx_token}"
        )

        await send_message_with_attachments(page, prompt, [xlsx_path, pptx_path])

        await page.wait_for_function(
            """
            () => {
              const bodyText = document.body.innerText || '';
              return bodyText.includes('chat-office-smoke.xlsx') && bodyText.includes('chat-office-smoke.pptx');
            }
            """,
            timeout=30000,
        )

        await wait_for_assistant_group_text(
            page,
            xlsx_token,
            agent_name=resolved_agent_name,
            timeout=120000,
        )
        await wait_for_assistant_group_text(
            page,
            pptx_token,
            agent_name=resolved_agent_name,
            timeout=120000,
        )
        await wait_for_generation_idle(page)
        await page.wait_for_timeout(2000)

        tail_groups = await collect_tail_groups(page)
        result["tail_groups"] = tail_groups
        result["xlsx_attachment_visible"] = any("chat-office-smoke.xlsx" in str(group.get("text", "")) for group in tail_groups)
        result["pptx_attachment_visible"] = any("chat-office-smoke.pptx" in str(group.get("text", "")) for group in tail_groups)

        last_user_group = find_last_group(tail_groups, text_includes="chat-office-smoke", is_user=True)
        last_agent_group = find_last_group(tail_groups, text_includes=resolved_agent_name, is_user=False)

        if last_user_group:
            result["user_group_contains_attachment_names"] = (
                "chat-office-smoke.xlsx" in last_user_group["text"]
                and "chat-office-smoke.pptx" in last_user_group["text"]
            )

        if last_agent_group:
            agent_text = str(last_agent_group.get("text", ""))
            result["assistant_contains_xlsx_token"] = xlsx_token in agent_text
            result["assistant_contains_pptx_token"] = pptx_token in agent_text

        if not result["xlsx_attachment_visible"]:
            result["errors"].append("xlsx_attachment_not_visible")
        if not result["pptx_attachment_visible"]:
            result["errors"].append("pptx_attachment_not_visible")
        if not result["user_group_contains_attachment_names"]:
            result["errors"].append("user_group_missing_office_attachment_names")
        if not result["assistant_contains_xlsx_token"]:
            result["errors"].append("assistant_missing_xlsx_token")
        if not result["assistant_contains_pptx_token"]:
            result["errors"].append("assistant_missing_pptx_token")

    result["ok"] = not result["errors"]
    return result


async def run_media_attachment_smoke(
    *,
    page: Page,
    agent_name: str | None,
) -> dict[str, Any]:
    resolved_agent_name = await resolve_dm_agent_name(page, agent_name)

    result: dict[str, Any] = {
        "ok": False,
        "scenario": "media-attachments",
        "agent_name": resolved_agent_name,
        "image_attachment_visible": False,
        "audio_attachment_visible": False,
        "assistant_mentions_red_square": False,
        "assistant_mentions_blue_circle": False,
        "assistant_mentions_audio_phrase": False,
        "image_preview_modal_visible": False,
        "image_preview_has_image": False,
        "audio_preview_modal_visible": False,
        "audio_preview_has_audio": False,
        "audio_preview_open_original_visible": False,
        "tail_groups": [],
        "errors": [],
    }

    await select_conversation(page, resolved_agent_name)

    with TemporaryDirectory() as tmpdir:
        image_path, audio_path, audio_phrase = create_media_attachment_samples(Path(tmpdir))
        initial_assistant_count = await count_assistant_groups(page)
        prompt = (
            "请识别我刚上传的图片和音频。"
            "先说图片里的两个主要彩色图形，再说音频里的英文短语。"
            "请用一句中文回答。"
        )

        await send_message_with_attachments(page, prompt, [image_path, audio_path])

        await page.wait_for_function(
            """
            () => {
              const bodyText = document.body.innerText || '';
              return bodyText.includes('chat-media-smoke.png') && bodyText.includes('chat-media-smoke.wav');
            }
            """,
            timeout=30000,
        )

        await page.wait_for_function(
            """
            (expectedCount) => document.querySelectorAll('[data-testid="chat-message-group"][data-role="assistant"]').length > expectedCount
            """,
            arg=initial_assistant_count,
            timeout=120000,
        )
        await wait_for_generation_idle(page)
        await page.wait_for_timeout(2000)

        image_preview = await open_message_file_preview(
            page,
            message_text=prompt,
            file_name="chat-media-smoke.png",
        )
        result["image_preview_modal_visible"] = bool(image_preview["visible"])
        result["image_preview_has_image"] = bool(image_preview["has_image"])

        audio_preview = await open_message_file_preview(
            page,
            message_text=prompt,
            file_name="chat-media-smoke.wav",
        )
        result["audio_preview_modal_visible"] = bool(audio_preview["visible"])
        result["audio_preview_has_audio"] = bool(audio_preview["has_audio"])
        result["audio_preview_open_original_visible"] = bool(audio_preview["open_original_visible"])

        tail_groups = await collect_tail_groups(page)
        result["tail_groups"] = tail_groups
        result["image_attachment_visible"] = any("chat-media-smoke.png" in str(group.get("text", "")) for group in tail_groups)
        result["audio_attachment_visible"] = any("chat-media-smoke.wav" in str(group.get("text", "")) for group in tail_groups)

        last_agent_group = find_last_group(tail_groups, text_includes=resolved_agent_name, is_user=False)
        if last_agent_group:
            agent_text = str(last_agent_group.get("text", "")).lower()
            result["assistant_mentions_red_square"] = "红" in agent_text and ("方块" in agent_text or "正方形" in agent_text)
            result["assistant_mentions_blue_circle"] = "蓝" in agent_text and ("圆" in agent_text)
            result["assistant_mentions_audio_phrase"] = normalize_assertion_text(audio_phrase) in normalize_assertion_text(agent_text)

        if not result["image_attachment_visible"]:
            result["errors"].append("image_attachment_not_visible")
        if not result["audio_attachment_visible"]:
            result["errors"].append("audio_attachment_not_visible")
        if not result["assistant_mentions_red_square"]:
            result["errors"].append("assistant_missing_red_square")
        if not result["assistant_mentions_blue_circle"]:
            result["errors"].append("assistant_missing_blue_circle")
        if not result["assistant_mentions_audio_phrase"]:
            result["errors"].append("assistant_missing_audio_phrase")
        if not result["image_preview_modal_visible"]:
            result["errors"].append("image_preview_modal_not_visible")
        if not result["image_preview_has_image"]:
            result["errors"].append("image_preview_image_missing")
        if not result["audio_preview_modal_visible"]:
            result["errors"].append("audio_preview_modal_not_visible")
        if not result["audio_preview_has_audio"]:
            result["errors"].append("audio_preview_audio_missing")
        if not result["audio_preview_open_original_visible"]:
            result["errors"].append("audio_preview_missing_open_original")

    result["ok"] = not result["errors"]
    return result


async def run_paste_attachment_smoke(
    *,
    page: Page,
    agent_name: str | None,
) -> dict[str, Any]:
    resolved_agent_name = await resolve_dm_agent_name(page, agent_name)

    result: dict[str, Any] = {
        "ok": False,
        "scenario": "paste-attachments",
        "agent_name": resolved_agent_name,
        "pasted_image_visible": False,
        "pasted_file_visible": False,
        "assistant_contains_summary": False,
        "tail_groups": [],
        "errors": [],
    }

    await select_conversation(page, resolved_agent_name)

    with TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        image_path = tmpdir_path / "chat-paste-smoke.png"
        create_shape_png(image_path)
        text_path = tmpdir_path / "chat-paste-smoke.txt"
        text_path.write_text("paste smoke text file", encoding="utf-8")
        initial_assistant_count = await count_assistant_groups(page)

        await paste_files_via_clipboard(page, [image_path, text_path])

        await page.wait_for_function(
            """
            () => {
              const bodyText = document.body.innerText || '';
              return bodyText.includes('chat-paste-smoke.png') && bodyText.includes('chat-paste-smoke.txt');
            }
            """,
            timeout=30000,
        )

        await send_message(page, "请确认你收到了我粘贴的图片和文本文件，并用一句话概括文本文件内容。")
        await page.wait_for_function(
            """
            (expectedCount) => document.querySelectorAll('[data-testid="chat-message-group"][data-role="assistant"]').length > expectedCount
            """,
            arg=initial_assistant_count,
            timeout=120000,
        )
        await wait_for_generation_idle(page)
        await page.wait_for_timeout(2000)

        tail_groups = await collect_tail_groups(page)
        result["tail_groups"] = tail_groups
        result["pasted_image_visible"] = any("chat-paste-smoke.png" in str(group.get("text", "")) for group in tail_groups)
        result["pasted_file_visible"] = any("chat-paste-smoke.txt" in str(group.get("text", "")) for group in tail_groups)

        last_agent_group = find_last_group(tail_groups, text_includes=resolved_agent_name, is_user=False)
        if last_agent_group:
            agent_text = str(last_agent_group.get("text", "")).lower()
            result["assistant_contains_summary"] = "paste smoke text file" in agent_text or "文本文件" in agent_text

        if not result["pasted_image_visible"]:
            result["errors"].append("pasted_image_not_visible")
        if not result["pasted_file_visible"]:
            result["errors"].append("pasted_file_not_visible")
        if not result["assistant_contains_summary"]:
            result["errors"].append("assistant_missing_paste_summary")

    result["ok"] = not result["errors"]
    return result


async def run_drag_attachment_smoke(
    *,
    page: Page,
    agent_name: str | None,
) -> dict[str, Any]:
    resolved_agent_name = await resolve_dm_agent_name(page, agent_name)

    result: dict[str, Any] = {
        "ok": False,
        "scenario": "drag-attachments",
        "agent_name": resolved_agent_name,
        "drag_overlay_visible": False,
        "dragged_image_visible": False,
        "dragged_file_visible": False,
        "assistant_contains_summary": False,
        "tail_groups": [],
        "errors": [],
    }

    await select_conversation(page, resolved_agent_name)

    with TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        image_path = tmpdir_path / "chat-drag-smoke.png"
        create_shape_png(image_path)
        text_path = tmpdir_path / "chat-drag-smoke.txt"
        text_path.write_text("drag smoke text file", encoding="utf-8")
        initial_assistant_count = await count_assistant_groups(page)

        await dispatch_drag_files(page, [image_path, text_path], ["dragenter", "dragover"])
        await page.get_by_test_id("composer-drag-overlay").wait_for(timeout=5000)
        result["drag_overlay_visible"] = True
        await dispatch_drag_files(page, [image_path, text_path], ["drop", "dragleave"])

        await page.wait_for_function(
            """
            () => {
              const bodyText = document.body.innerText || '';
              return bodyText.includes('chat-drag-smoke.png') && bodyText.includes('chat-drag-smoke.txt');
            }
            """,
            timeout=30000,
        )

        await send_message(page, "请确认你收到了我拖拽上传的图片和文本文件，并用一句话概括文本文件内容。")
        await page.wait_for_function(
            """
            (expectedCount) => document.querySelectorAll('[data-testid="chat-message-group"][data-role="assistant"]').length > expectedCount
            """,
            arg=initial_assistant_count,
            timeout=120000,
        )
        await wait_for_generation_idle(page)
        await page.wait_for_timeout(2000)

        tail_groups = await collect_tail_groups(page)
        result["tail_groups"] = tail_groups
        result["dragged_image_visible"] = any("chat-drag-smoke.png" in str(group.get("text", "")) for group in tail_groups)
        result["dragged_file_visible"] = any("chat-drag-smoke.txt" in str(group.get("text", "")) for group in tail_groups)

        last_agent_group = find_last_group(tail_groups, text_includes=resolved_agent_name, is_user=False)
        if last_agent_group:
            agent_text = str(last_agent_group.get("text", "")).lower()
            result["assistant_contains_summary"] = "drag smoke text file" in agent_text or "文本文件" in agent_text

        if not result["dragged_image_visible"]:
            result["errors"].append("dragged_image_not_visible")
        if not result["dragged_file_visible"]:
            result["errors"].append("dragged_file_not_visible")
        if not result["drag_overlay_visible"]:
            result["errors"].append("drag_overlay_not_visible")
        if not result["assistant_contains_summary"]:
            result["errors"].append("assistant_missing_drag_summary")

    result["ok"] = not result["errors"]
    return result


async def run_retry_attachment_smoke(
    *,
    page: Page,
    agent_name: str | None,
) -> dict[str, Any]:
    resolved_agent_name = await resolve_dm_agent_name(page, agent_name)

    result: dict[str, Any] = {
        "ok": False,
        "scenario": "retry-attachments",
        "agent_name": resolved_agent_name,
        "failed_attachment_visible": False,
        "failure_hint_visible": False,
        "retry_button_visible": False,
        "retry_successful": False,
        "assistant_contains_summary": False,
        "tail_groups": [],
        "errors": [],
    }

    await install_single_upload_failure(page)
    await select_conversation(page, resolved_agent_name)

    with TemporaryDirectory() as tmpdir:
        text_path = Path(tmpdir) / "chat-retry-smoke.txt"
        text_path.write_text("retry smoke text file", encoding="utf-8")
        initial_assistant_count = await count_assistant_groups(page)

        file_input = page.locator('input[type="file"]').first
        await file_input.set_input_files(str(text_path))

        await page.wait_for_function(
            """
            () => {
              const bodyText = document.body.innerText || '';
              return bodyText.includes('chat-retry-smoke.txt')
                && (bodyText.includes('上传失败后附件已保留') || bodyText.includes('上传失败，附件已保留，可直接重试'));
            }
            """,
            timeout=30000,
        )

        result["failed_attachment_visible"] = True
        result["failure_hint_visible"] = True
        retry_button = page.get_by_role("button", name="重试上传附件 chat-retry-smoke.txt")
        await retry_button.wait_for(timeout=30000)
        result["retry_button_visible"] = True
        await retry_button.click()

        await page.wait_for_function(
            """
            () => {
              const bodyText = document.body.innerText || '';
              return bodyText.includes('chat-retry-smoke.txt') && bodyText.includes('retry smoke text file');
            }
            """,
            timeout=30000,
        )
        result["retry_successful"] = True

        await send_message(page, "请确认你已经读到我重试上传成功的文本文件，并用一句话概括文件内容。")
        await page.wait_for_function(
            """
            (expectedCount) => document.querySelectorAll('[data-testid="chat-message-group"][data-role="assistant"]').length > expectedCount
            """,
            arg=initial_assistant_count,
            timeout=120000,
        )
        await wait_for_generation_idle(page)
        await page.wait_for_timeout(2000)

        tail_groups = await collect_tail_groups(page)
        result["tail_groups"] = tail_groups
        last_agent_group = find_last_group(tail_groups, text_includes=resolved_agent_name, is_user=False)
        if last_agent_group:
            agent_text = str(last_agent_group.get("text", "")).lower()
            result["assistant_contains_summary"] = "retry smoke text file" in agent_text or "文本文件" in agent_text

        if not result["assistant_contains_summary"]:
            result["errors"].append("assistant_missing_retry_summary")

    await page.unroute("**/api/upload")

    if not result["failed_attachment_visible"]:
        result["errors"].append("failed_attachment_not_visible")
    if not result["failure_hint_visible"]:
        result["errors"].append("failure_hint_not_visible")
    if not result["retry_button_visible"]:
        result["errors"].append("retry_button_not_visible")
    if not result["retry_successful"]:
        result["errors"].append("retry_not_successful")

    result["ok"] = not result["errors"]
    return result


async def run_attachment_order_smoke(
    *,
    page: Page,
    agent_name: str | None,
) -> dict[str, Any]:
    resolved_agent_name = await resolve_dm_agent_name(page, agent_name)

    result: dict[str, Any] = {
        "ok": False,
        "scenario": "order-attachments",
        "agent_name": resolved_agent_name,
        "original_order": [],
        "reordered_ui": [],
        "request_file_order": [],
        "order_matches_request": False,
        "errors": [],
    }

    await select_conversation(page, resolved_agent_name)

    with TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        first_path = tmpdir_path / "chat-order-a.txt"
        second_path = tmpdir_path / "chat-order-b.txt"
        first_path.write_text("order smoke file A", encoding="utf-8")
        second_path.write_text("order smoke file B", encoding="utf-8")

        file_input = page.locator('input[type="file"]').first
        await file_input.set_input_files([str(first_path), str(second_path)])

        await page.wait_for_function(
            """
            () => {
              const bodyText = document.body.innerText || '';
              return bodyText.includes('chat-order-a.txt') && bodyText.includes('chat-order-b.txt');
            }
            """,
            timeout=30000,
        )

        result["original_order"] = await page.evaluate(
            """
            () => Array.from(document.querySelectorAll('[aria-label^="移除附件 "]'))
              .map((button) => button.getAttribute('aria-label')?.replace('移除附件 ', '') || '')
            """
        )

        await page.get_by_role("button", name="将附件 chat-order-b.txt 前移").click()

        reordered_ui = await page.evaluate(
            """
            () => Array.from(document.querySelectorAll('[aria-label^="移除附件 "]'))
              .map((button) => button.getAttribute('aria-label')?.replace('移除附件 ', '') || '')
            """
        )
        result["reordered_ui"] = reordered_ui

        async with page.expect_request(lambda request: request.url.endswith("/api/chat/stream") and request.method == "POST") as request_info:
            await send_message(page, "请确认附件顺序测试已发送。")

        request = await request_info.value
        payload = request.post_data_json or {}
        request_file_order = [
            file.get("original_name") or file.get("filename") or ""
            for file in (payload.get("files") or [])
            if isinstance(file, dict)
        ]
        result["request_file_order"] = request_file_order
        result["order_matches_request"] = reordered_ui == request_file_order

        if reordered_ui[:2] != ["chat-order-b.txt", "chat-order-a.txt"]:
            result["errors"].append("ui_reorder_failed")
        if not result["order_matches_request"]:
            result["errors"].append("request_order_mismatch")

    result["ok"] = not result["errors"]
    return result


async def run_smoke(
    *,
    url: str,
    scenario: str,
    team_name: str | None,
    secondary_agent_name: str | None,
    dm_agent_name: str | None,
    prompt: str | None,
    expected_substring: str | None,
    headless: bool,
) -> dict[str, Any]:
    async with async_playwright() as p:
        browser = await launch_browser(p, headless=headless)
        page = await browser.new_page(viewport={"width": 1440, "height": 1100})

        try:
            max_attempts = 2
            final_result: dict[str, Any] | None = None

            for attempt in range(1, max_attempts + 1):
                await open_chat(page, url)

                try:
                    if scenario == "team":
                        result = await run_team_smoke(
                            page=page,
                            team_name=team_name,
                            secondary_agent_name=secondary_agent_name,
                            prompt=prompt,
                        )
                    elif scenario == "dm":
                        result = await run_dm_smoke(
                            page=page,
                            agent_name=dm_agent_name,
                            prompt=prompt,
                            expected_substring=expected_substring,
                        )
                    elif scenario == "dm-team-dispatch":
                        result = await run_dm_team_dispatch_smoke(
                            page=page,
                            team_name=team_name,
                            secondary_agent_name=secondary_agent_name,
                            dm_agent_name=dm_agent_name,
                            prompt=prompt,
                        )
                    elif scenario == "attachments":
                        result = await run_attachment_smoke(
                            page=page,
                            agent_name=dm_agent_name,
                        )
                    elif scenario == "office-attachments":
                        result = await run_office_attachment_smoke(
                            page=page,
                            agent_name=dm_agent_name,
                        )
                    elif scenario == "media-attachments":
                        result = await run_media_attachment_smoke(
                            page=page,
                            agent_name=dm_agent_name,
                        )
                    elif scenario == "paste-attachments":
                        result = await run_paste_attachment_smoke(
                            page=page,
                            agent_name=dm_agent_name,
                        )
                    elif scenario == "drag-attachments":
                        result = await run_drag_attachment_smoke(
                            page=page,
                            agent_name=dm_agent_name,
                        )
                    elif scenario == "retry-attachments":
                        result = await run_retry_attachment_smoke(
                            page=page,
                            agent_name=dm_agent_name,
                        )
                    elif scenario == "order-attachments":
                        result = await run_attachment_order_smoke(
                            page=page,
                            agent_name=dm_agent_name,
                        )
                    else:
                        raise RuntimeError(f"Unsupported scenario: {scenario}")
                except PlaywrightTimeoutError as exc:
                    tail_groups: list[dict[str, Any]] = []
                    try:
                        tail_groups = await collect_tail_groups(page)
                    except Exception:
                        tail_groups = []
                    result = {
                        "ok": False,
                        "scenario": scenario,
                        "tail_groups": tail_groups,
                        "errors": [f"timeout:{exc}"],
                    }

                result["attempt"] = attempt
                final_result = result

                if result.get("ok") or attempt >= max_attempts or not should_retry_result(result):
                    break

                await page.wait_for_timeout(1500)

            if final_result is None:
                raise RuntimeError("Smoke test did not produce a result")

            return final_result
        finally:
            await browser.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run chat UI smoke test in Chrome.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument(
        "--scenario",
        choices=("team", "dm", "dm-team-dispatch", "attachments", "office-attachments", "media-attachments", "paste-attachments", "drag-attachments", "retry-attachments", "order-attachments"),
        default=DEFAULT_SCENARIO,
        help="Smoke test scenario to run.",
    )
    parser.add_argument("--team-name", default=None)
    parser.add_argument("--secondary-agent-name", default=None)
    parser.add_argument("--dm-agent-name", default=None)
    parser.add_argument("--prompt", default=None)
    parser.add_argument("--expected-substring", default=None)
    parser.add_argument("--headed", action="store_true", help="Run with a visible browser window.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = asyncio.run(
        run_smoke(
            url=args.url,
            scenario=args.scenario,
            team_name=args.team_name,
            secondary_agent_name=args.secondary_agent_name,
            dm_agent_name=args.dm_agent_name,
            prompt=args.prompt,
            expected_substring=args.expected_substring,
            headless=not args.headed,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
