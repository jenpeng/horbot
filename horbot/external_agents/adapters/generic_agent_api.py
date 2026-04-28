"""Generic HTTP/SSE/WebSocket external-agent adapter.

This adapter is Horbot's standard external-agent protocol. It keeps the
existing endpoint-based behavior as one pluggable adapter instead of baking it
into the runtime.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from websockets.exceptions import ConnectionClosed, InvalidStatus

try:
    from websockets.asyncio.client import connect as websocket_connect
except ImportError:  # pragma: no cover - optional dependency fallback
    websocket_connect = None

from horbot.external_agents.adapters.base import (
    ExternalAgentAdapter,
    ExternalAgentResult,
    build_auth_headers,
    build_standard_request_payload,
    extract_content_from_payload,
)
from horbot.external_agents.models import ExternalAgentInstance


def _extract_delta_from_payload(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("delta", "chunk", "token", "content_delta", "text_delta"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        nested_value = extract_content_from_payload(value)
        if nested_value:
            return nested_value
    return ""


def _is_done_payload(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False

    for key in ("done", "final", "complete", "completed", "finished"):
        if payload.get(key) is True:
            return True

    for key in ("event", "type", "status", "phase"):
        value = str(payload.get(key) or "").strip().lower()
        if value in {"done", "end", "final", "complete", "completed", "finished"}:
            return True

    return bool(payload.get("finish_reason"))


class GenericAgentApiAdapter(ExternalAgentAdapter):
    """Adapter for Horbot-compatible and simple HTTP/SSE/WebSocket agents."""

    adapter_id = "generic-agent-api"

    async def complete(
        self,
        agent: ExternalAgentInstance,
        *,
        message: str,
        session_key: str,
        history: list[dict[str, Any]] | None = None,
        conversation: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExternalAgentResult:
        config = agent.config
        timeout_s = min(max(int(config.timeout_s or 30), 5), 120)
        headers = build_auth_headers(config)
        payload = build_standard_request_payload(
            agent,
            message=message,
            session_key=session_key,
            history=history,
            conversation=conversation,
            metadata=metadata,
        )

        if config.transport == "websocket":
            return await self._complete_websocket(config.endpoint, headers, payload, timeout_s, config.transport)
        if config.transport == "http":
            return await self._complete_http(config.endpoint, headers, payload, timeout_s, config.transport)
        return await self._complete_sse(config.endpoint, headers, payload, timeout_s, config.transport)

    async def _complete_websocket(
        self,
        endpoint: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_s: int,
        transport: str,
    ) -> ExternalAgentResult:
        if websocket_connect is None:
            return {
                "ok": False,
                "detail": "WebSocket support is not installed",
                "transport": transport,
                "endpoint": endpoint,
                "mode": "websocket_chat",
                "content": "",
            }

        try:
            async with websocket_connect(
                endpoint,
                additional_headers=headers,
                open_timeout=timeout_s,
                close_timeout=min(timeout_s, 10),
                ping_interval=None,
            ) as websocket:
                await websocket.send(json.dumps(payload, ensure_ascii=False))
                content_parts: list[str] = []

                while True:
                    try:
                        frame = await asyncio.wait_for(websocket.recv(), timeout=timeout_s)
                    except asyncio.TimeoutError:
                        content = "".join(content_parts).strip()
                        return {
                            "ok": bool(content),
                            "detail": "External agent websocket response completed after idle timeout" if content else "External agent websocket response timed out",
                            "transport": transport,
                            "endpoint": endpoint,
                            "mode": "websocket_chat",
                            "content": content,
                        }
                    except ConnectionClosed:
                        break

                    if frame is None:
                        break

                    text_frame = frame.decode(errors="ignore") if isinstance(frame, bytes) else str(frame)
                    text_frame = text_frame.strip()
                    if not text_frame:
                        continue

                    try:
                        parsed = json.loads(text_frame)
                    except json.JSONDecodeError:
                        content_parts.append(text_frame)
                        break

                    delta = _extract_delta_from_payload(parsed)
                    if delta:
                        content_parts.append(delta)
                    else:
                        content = extract_content_from_payload(parsed)
                        if content:
                            content_parts.append(content)

                    if _is_done_payload(parsed) or (not delta and bool(extract_content_from_payload(parsed))):
                        break

                content = "".join(content_parts).strip()
                return {
                    "ok": bool(content),
                    "detail": "External agent websocket response completed" if content else "External agent websocket ended without content",
                    "transport": transport,
                    "endpoint": endpoint,
                    "mode": "websocket_chat",
                    "content": content,
                }
        except InvalidStatus as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code in {401, 403}:
                detail = "External agent websocket authentication was rejected"
            elif status_code == 404:
                detail = "External agent websocket path was not found"
            else:
                detail = f"External agent websocket handshake failed: HTTP {status_code}" if status_code else str(exc)
            return {
                "ok": False,
                "detail": detail,
                "transport": transport,
                "endpoint": endpoint,
                "mode": "websocket_chat",
                "status_code": status_code,
                "content": "",
            }
        except (OSError, TimeoutError) as exc:
            return {
                "ok": False,
                "detail": f"External agent websocket request failed: {exc}",
                "transport": transport,
                "endpoint": endpoint,
                "mode": "websocket_chat",
                "content": "",
            }

    async def _complete_http(
        self,
        endpoint: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_s: int,
        transport: str,
    ) -> ExternalAgentResult:
        headers["Accept"] = "application/json, text/plain;q=0.9, */*;q=0.8"
        async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True) as client:
            try:
                response = await client.post(endpoint, json=payload, headers=headers)
            except httpx.TimeoutException:
                return {
                    "ok": False,
                    "detail": "External agent request timed out",
                    "transport": transport,
                    "endpoint": endpoint,
                    "mode": "http_chat",
                    "content": "",
                }
            except httpx.HTTPError as exc:
                return {
                    "ok": False,
                    "detail": f"External agent request failed: {exc}",
                    "transport": transport,
                    "endpoint": endpoint,
                    "mode": "http_chat",
                    "content": "",
                }

        content_type = response.headers.get("content-type", "")
        try:
            content = extract_content_from_payload(response.json()) if "json" in content_type else ""
            if not content:
                content = response.text.strip()
        except (ValueError, json.JSONDecodeError):
            content = response.text.strip()

        return {
            "ok": 200 <= response.status_code < 300 and bool(content),
            "detail": "External agent responded successfully" if 200 <= response.status_code < 300 else f"External agent responded with HTTP {response.status_code}",
            "transport": transport,
            "endpoint": endpoint,
            "mode": "http_chat",
            "status_code": response.status_code,
            "content_type": content_type,
            "content": content,
        }

    async def _complete_sse(
        self,
        endpoint: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_s: int,
        transport: str,
    ) -> ExternalAgentResult:
        headers["Accept"] = "text/event-stream, application/json, text/plain;q=0.9, */*;q=0.8"
        content_parts: list[str] = []
        async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True) as client:
            try:
                async with client.stream("POST", endpoint, json=payload, headers=headers) as response:
                    content_type = response.headers.get("content-type", "")
                    if "text/event-stream" not in content_type.lower():
                        body = await response.aread()
                        text_body = body.decode(errors="ignore").strip()
                        if "json" in content_type.lower():
                            try:
                                text_body = extract_content_from_payload(json.loads(text_body)) or text_body
                            except json.JSONDecodeError:
                                pass
                        return {
                            "ok": 200 <= response.status_code < 300 and bool(text_body),
                            "detail": "External agent responded successfully" if 200 <= response.status_code < 300 else f"External agent responded with HTTP {response.status_code}",
                            "transport": transport,
                            "endpoint": endpoint,
                            "mode": "http_sse_fallback",
                            "status_code": response.status_code,
                            "content_type": content_type,
                            "content": text_body,
                        }

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if not data or data == "[DONE]":
                            continue
                        try:
                            parsed = json.loads(data)
                        except json.JSONDecodeError:
                            content_parts.append(data)
                            continue

                        delta = ""
                        if isinstance(parsed, dict):
                            delta = extract_content_from_payload(parsed) or extract_content_from_payload(parsed.get("delta"))
                        elif isinstance(parsed, str):
                            delta = parsed.strip()
                        if delta:
                            content_parts.append(delta)

                    content = "".join(content_parts).strip()
                    return {
                        "ok": bool(content),
                        "detail": "External agent stream completed" if content else "External agent stream ended without content",
                        "transport": transport,
                        "endpoint": endpoint,
                        "mode": "http_sse_chat",
                        "content_type": content_type,
                        "content": content,
                    }
            except httpx.TimeoutException:
                return {
                    "ok": False,
                    "detail": "External agent stream timed out",
                    "transport": transport,
                    "endpoint": endpoint,
                    "mode": "http_sse_chat",
                    "content": "",
                }
            except httpx.HTTPError as exc:
                return {
                    "ok": False,
                    "detail": f"External agent stream failed: {exc}",
                    "transport": transport,
                    "endpoint": endpoint,
                    "mode": "http_sse_chat",
                    "content": "",
                }

    async def probe(self, agent: ExternalAgentInstance) -> ExternalAgentResult:
        config = agent.config
        timeout_s = min(max(int(config.timeout_s or 10), 3), 15)
        headers = build_auth_headers(config)
        if config.transport == "websocket":
            return await self._probe_websocket(config.endpoint, headers, timeout_s, config.transport)
        return await self._probe_http(config.endpoint, headers, timeout_s, config.transport)

    async def _probe_websocket(
        self,
        endpoint: str,
        headers: dict[str, str],
        timeout_s: int,
        transport: str,
    ) -> ExternalAgentResult:
        if websocket_connect is None:
            return {
                "ok": False,
                "detail": "WebSocket support is not installed",
                "transport": transport,
                "endpoint": endpoint,
                "mode": "websocket_probe",
            }
        try:
            async with websocket_connect(
                endpoint,
                additional_headers=headers,
                open_timeout=timeout_s,
                close_timeout=min(timeout_s, 10),
                ping_interval=None,
            ):
                return {
                    "ok": True,
                    "detail": "Endpoint accepted websocket connection",
                    "transport": transport,
                    "endpoint": endpoint,
                    "mode": "websocket_probe",
                }
        except InvalidStatus as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code in {401, 403}:
                detail = "Endpoint reachable but websocket authentication was rejected"
            elif status_code == 404:
                detail = "Endpoint reachable but websocket path was not found"
            else:
                detail = f"Endpoint rejected websocket connection: HTTP {status_code}" if status_code else str(exc)
            return {
                "ok": False,
                "detail": detail,
                "transport": transport,
                "endpoint": endpoint,
                "status_code": status_code,
                "mode": "websocket_probe",
            }
        except (OSError, TimeoutError) as exc:
            return {
                "ok": False,
                "detail": f"Connection probe failed: {exc}",
                "transport": transport,
                "endpoint": endpoint,
                "mode": "websocket_probe",
            }

    async def _probe_http(
        self,
        endpoint: str,
        headers: dict[str, str],
        timeout_s: int,
        transport: str,
    ) -> ExternalAgentResult:
        headers["Accept"] = "application/json, text/plain;q=0.9, */*;q=0.8" if transport == "http" else "text/event-stream, application/json, text/plain;q=0.9, */*;q=0.8"
        async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True) as client:
            try:
                response = await client.get(endpoint, headers=headers)
            except httpx.TimeoutException:
                return {
                    "ok": False,
                    "detail": "Connection probe timed out",
                    "transport": transport,
                    "endpoint": endpoint,
                    "mode": "http_probe",
                }
            except httpx.HTTPError as exc:
                return {
                    "ok": False,
                    "detail": f"Connection probe failed: {exc}",
                    "transport": transport,
                    "endpoint": endpoint,
                    "mode": "http_probe",
                }

        content_type = response.headers.get("content-type", "")
        if 200 <= response.status_code < 300:
            return {
                "ok": True,
                "detail": "Endpoint responded successfully",
                "transport": transport,
                "endpoint": endpoint,
                "status_code": response.status_code,
                "content_type": content_type,
                "mode": "http_probe",
            }

        if response.status_code in {401, 403}:
            detail = "Endpoint reachable but authentication was rejected"
        elif response.status_code == 404:
            detail = "Endpoint reachable but path was not found"
        else:
            detail = f"Endpoint responded with HTTP {response.status_code}"

        return {
            "ok": False,
            "detail": detail,
            "transport": transport,
            "endpoint": endpoint,
            "status_code": response.status_code,
            "content_type": content_type,
            "mode": "http_probe",
        }
