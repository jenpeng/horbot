"""Security helpers for the web surface."""

from __future__ import annotations

import json
from ipaddress import ip_address
from typing import Any

from fastapi import HTTPException, Request, WebSocket, status
from loguru import logger

from horbot.config.loader import get_cached_config


_REDACTED = "********"
_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "authorization",
    "cookie",
    "credential",
    "access_key",
    "access_token",
    "refresh_token",
)
_PUBLIC_HTTP_PATHS = frozenset(("/health",))
_EXECUTION_REASONING_KEYS = frozenset({"thinking", "reasoning", "reasoning_content"})


def is_loopback_host(host: str | None) -> bool:
    """Return True when the host points to the local machine."""
    if not host:
        return False

    normalized = host.strip().lower()
    if normalized in {"127.0.0.1", "::1", "localhost"}:
        return True

    try:
        return ip_address(normalized).is_loopback
    except ValueError:
        return False


def get_admin_token() -> str:
    """Return the configured admin token if present."""
    config = get_cached_config()
    gateway = getattr(config, "gateway", None)
    return (getattr(gateway, "admin_token", "") or "").strip()


def allow_remote_without_token() -> bool:
    """Return whether remote API access without a token is allowed."""
    config = get_cached_config()
    gateway = getattr(config, "gateway", None)
    return bool(getattr(gateway, "allow_remote_without_token", False))


def extract_admin_token_from_headers(headers: Any) -> str:
    """Extract an admin token from request headers."""
    direct = headers.get("x-horbot-admin-token")
    if direct:
        return direct.strip()

    auth = headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()

    return ""


def authorize_http_request(request: Request) -> None:
    """Raise when an HTTP request is not allowed to access the API."""
    path = request.url.path
    if not (path.startswith("/api") or path.startswith("/ws")):
        return
    if path in _PUBLIC_HTTP_PATHS:
        return

    client_host = request.client.host if request.client else ""
    if is_loopback_host(client_host):
        return

    token = get_admin_token()
    if not token and allow_remote_without_token():
        return

    provided = extract_admin_token_from_headers(request.headers)
    if token and provided == token:
        return

    if token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin token required for remote access",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Remote API access is disabled; use localhost or configure gateway.adminToken",
    )


async def authorize_websocket(websocket: WebSocket) -> None:
    """Close the websocket when the caller is not allowed."""
    client_host = websocket.client.host if websocket.client else ""
    if is_loopback_host(client_host):
        await websocket.accept()
        return

    token = get_admin_token()
    provided = extract_admin_token_from_headers(websocket.headers)

    if token and provided == token:
        await websocket.accept()
        return

    if not token and allow_remote_without_token():
        await websocket.accept()
        return

    code = 4401 if token else 4403
    reason = (
        "Admin token required for remote websocket access"
        if token
        else "Remote websocket access is disabled"
    )
    await websocket.close(code=code, reason=reason)


def mask_secret(value: str | None) -> str:
    """Return a user-friendly masked preview of a secret value."""
    if not value:
        return ""
    value = str(value)
    if len(value) <= 4:
        return "*" * len(value)
    if len(value) <= 8:
        return f"{value[:1]}***{value[-1:]}"
    return f"{value[:4]}...{value[-4:]}"


def is_sensitive_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)


def redact_sensitive_data(value: Any, *, preserve_shape: bool = True) -> Any:
    """Recursively redact sensitive fields in nested data."""
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if is_sensitive_key(str(key)):
                if preserve_shape and isinstance(item, dict):
                    redacted[key] = {nested_key: _REDACTED for nested_key in item.keys()}
                elif preserve_shape and isinstance(item, list):
                    redacted[key] = [_REDACTED for _ in item]
                elif preserve_shape and isinstance(item, str):
                    redacted[key] = _REDACTED if item else ""
                else:
                    redacted[key] = _REDACTED
            else:
                redacted[key] = redact_sensitive_data(item, preserve_shape=preserve_shape)
        return redacted

    if isinstance(value, list):
        return [redact_sensitive_data(item, preserve_shape=preserve_shape) for item in value]

    return value


def sanitize_json_text(text: str) -> str:
    """Best-effort JSON redaction for request/response body logging."""
    try:
        parsed = json.loads(text)
    except Exception:
        return text
    return json.dumps(redact_sensitive_data(parsed), ensure_ascii=False)


def sanitize_config_for_client(data: dict[str, Any]) -> dict[str, Any]:
    """Return a client-safe config payload."""
    sanitized = redact_sensitive_data(data)

    providers = data.get("providers") or {}
    sanitized_providers = sanitized.get("providers") or {}
    for name, settings in providers.items():
        if not isinstance(settings, dict):
            continue
        target = sanitized_providers.setdefault(name, {})
        api_key = settings.get("apiKey") or settings.get("api_key")
        target["hasApiKey"] = bool(api_key)
        target["apiKeyMasked"] = mask_secret(api_key)
        if "apiKey" in target:
            target["apiKey"] = ""
        if "api_key" in target:
            target["api_key"] = ""

    channels = data.get("channels") or {}
    sanitized_channels = sanitized.get("channels") or {}
    for name, settings in channels.items():
        if not isinstance(settings, dict):
            continue
        target = sanitized_channels.setdefault(name, {})
        for key, value in settings.items():
            if is_sensitive_key(key):
                target[f"{key}Configured"] = bool(value)
                target[f"{key}Masked"] = mask_secret(value if isinstance(value, str) else "")

    web_search = ((data.get("tools") or {}).get("web") or {}).get("search")
    sanitized_tools = sanitized.setdefault("tools", {})
    sanitized_web = sanitized_tools.setdefault("web", {})
    sanitized_search = sanitized_web.setdefault("search", {})
    if isinstance(web_search, dict):
        api_key = web_search.get("apiKey") or web_search.get("api_key")
        sanitized_search["hasApiKey"] = bool(api_key)
        sanitized_search["apiKeyMasked"] = mask_secret(api_key)
        if "apiKey" in sanitized_search:
            sanitized_search["apiKey"] = ""
        if "api_key" in sanitized_search:
            sanitized_search["api_key"] = ""

    return sanitized


def sanitize_mcp_server_for_client(name: str, cfg: Any) -> dict[str, Any]:
    """Return a client-safe MCP server payload."""
    env = dict(getattr(cfg, "env", None) or {})
    headers = dict(getattr(cfg, "headers", None) or {})
    return {
        "name": name,
        "command": getattr(cfg, "command", ""),
        "args": getattr(cfg, "args", []) or [],
        "url": getattr(cfg, "url", ""),
        "env": {key: _REDACTED for key in env.keys()},
        "tool_timeout": getattr(cfg, "tool_timeout", 30),
        "headers": {key: _REDACTED for key in headers.keys()},
        "has_secret_values": bool(env or headers),
    }


def sanitize_execution_step_details(step_type: str | None, details: Any) -> dict[str, Any]:
    """Return client-safe execution-step details with secrets redacted."""
    if not isinstance(details, dict):
        return {}

    sanitized = redact_sensitive_data(details)
    return sanitized


def sanitize_execution_steps(steps: Any) -> list[dict[str, Any]]:
    """Return client-safe execution steps for streaming, history, and storage."""
    if not isinstance(steps, list):
        return []

    sanitized_steps: list[dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        sanitized_step = dict(step)
        sanitized_step["details"] = sanitize_execution_step_details(
            str(step.get("type") or ""),
            step.get("details"),
        )
        sanitized_steps.append(sanitized_step)
    return sanitized_steps


def log_security_event(message: str, **kwargs: Any) -> None:
    """Write a structured security log entry."""
    logger.bind(type="security").warning(message, **kwargs)
