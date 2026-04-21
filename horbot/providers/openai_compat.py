"""Helpers for adapting requests to OpenAI-compatible provider dialects."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any


PROFILE_AUTO = "auto"
PROFILE_OPENAI = "openai"
PROFILE_OPENAI_CHAT_FILES = "openai_chat_files"

_PROFILE_ALIASES = {
    "default": PROFILE_OPENAI,
    "standard": PROFILE_OPENAI,
    "openai": PROFILE_OPENAI,
    "newapi": PROFILE_OPENAI_CHAT_FILES,
    "openai_chat_files": PROFILE_OPENAI_CHAT_FILES,
}


def resolve_compatibility_profile(profile: str | None, api_base: str | None = None) -> str:
    """Resolve a configured compatibility profile to an internal canonical value."""
    normalized = str(profile or PROFILE_AUTO).strip().lower().replace("-", "_")
    if normalized in _PROFILE_ALIASES:
        return _PROFILE_ALIASES[normalized]

    if normalized in {"", PROFILE_AUTO}:
        api_base_normalized = str(api_base or "").strip().lower()
        if "newapi" in api_base_normalized:
            return PROFILE_OPENAI_CHAT_FILES
        return PROFILE_OPENAI

    return normalized


def adapt_messages_for_compatibility(
    messages: list[dict[str, Any]],
    files: list[dict[str, Any]] | None,
    *,
    upload_dir: str | None = None,
    profile: str | None = None,
    api_base: str | None = None,
) -> list[dict[str, Any]]:
    """Apply provider-dialect-specific message transformations."""
    resolved_profile = resolve_compatibility_profile(profile, api_base)
    if resolved_profile != PROFILE_OPENAI_CHAT_FILES or not files:
        return messages
    return _attach_inline_file_parts(messages, files, upload_dir)


def _attach_inline_file_parts(
    messages: list[dict[str, Any]],
    files: list[dict[str, Any]],
    upload_dir: str | None,
) -> list[dict[str, Any]]:
    file_parts = _build_file_parts(files, upload_dir)
    if not file_parts:
        return messages

    adapted_messages = [dict(message) for message in messages]
    for index in range(len(adapted_messages) - 1, -1, -1):
        message = adapted_messages[index]
        if message.get("role") != "user":
            continue

        content = message.get("content")
        if isinstance(content, list):
            content_parts = list(content)
        elif isinstance(content, str):
            content_parts = [{"type": "text", "text": content}]
        elif content is None:
            content_parts = []
        else:
            content_parts = [{"type": "text", "text": str(content)}]

        content_parts.extend(file_parts)
        message["content"] = content_parts
        adapted_messages[index] = message
        return adapted_messages

    return messages


def _build_file_parts(files: list[dict[str, Any]], upload_dir: str | None) -> list[dict[str, Any]]:
    if not upload_dir:
        return []

    upload_root = Path(upload_dir)
    file_parts: list[dict[str, Any]] = []
    for file_info in files:
        if str(file_info.get("category") or "").strip().lower() != "document":
            continue

        filename = str(file_info.get("filename") or "").strip()
        if not filename:
            continue

        file_path = upload_root / filename
        if not file_path.is_file():
            continue

        mime_type = str(file_info.get("mime_type") or "application/octet-stream").strip() or "application/octet-stream"
        original_name = str(file_info.get("original_name") or filename).strip() or filename
        encoded = base64.b64encode(file_path.read_bytes()).decode("utf-8")
        file_parts.append(
            {
                "type": "file",
                "file": {
                    "filename": original_name,
                    "file_data": f"data:{mime_type};base64,{encoded}",
                },
            }
        )

    return file_parts
