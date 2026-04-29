"""Shared chat message content normalization helpers."""

from __future__ import annotations

import re


def clean_message_content(content: str) -> str:
    """Remove internal wrappers and tool/status messages from chat content."""
    if not content:
        return content

    content = re.sub(r"<think[\s\S]*?</think\s*>", "", content).strip()

    message_wrapper_pattern = re.compile(
        r"^\s*<message\b[^>]*>\s*([\s\S]*?)\s*</message>\s*$",
        re.IGNORECASE,
    )
    while True:
        match = message_wrapper_pattern.match(content)
        if not match:
            break
        content = match.group(1).strip()

    message_pattern = r"^message\((['\"])(.*?)\1\)$"
    match = re.match(message_pattern, content, re.DOTALL)
    if match:
        inner_content = match.group(2)
        return inner_content.replace("\\'", "'").replace('\\"', '"').strip()

    system_patterns = [
        r"^Message sent to\s+\S+.*$",
        r"^Error\s*:.*$",
        r"^Error sending message.*$",
    ]
    for pattern in system_patterns:
        if re.match(pattern, content, re.IGNORECASE):
            return ""

    return content.strip()
