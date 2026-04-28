"""OpenAI-compatible external-agent adapter."""

from __future__ import annotations

from typing import Any

import httpx

from horbot.external_agents.adapters.base import (
    ExternalAgentAdapter,
    ExternalAgentResult,
    build_auth_headers,
    extract_content_from_payload,
)
from horbot.external_agents.models import ExternalAgentInstance


class OpenAICompatibleAdapter(ExternalAgentAdapter):
    """Adapter for OpenAI-compatible chat completion endpoints."""

    adapter_id = "openai-compatible"

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
        adapter_config = dict(config.adapter_config or {})
        endpoint = str(adapter_config.get("chat_completions_endpoint") or config.endpoint).strip()
        model = str(adapter_config.get("model") or adapter_config.get("default_model") or "").strip()
        if not endpoint:
            return {
                "ok": False,
                "detail": "OpenAI-compatible adapter requires an endpoint",
                "adapter": self.adapter_id,
                "endpoint": endpoint,
                "mode": "openai_compatible_chat",
                "content": "",
            }
        if not model:
            return {
                "ok": False,
                "detail": "OpenAI-compatible adapter requires adapter_config.model",
                "adapter": self.adapter_id,
                "endpoint": endpoint,
                "mode": "openai_compatible_chat",
                "content": "",
            }

        messages: list[dict[str, str]] = []
        system_prompt = str(adapter_config.get("system_prompt") or config.description or "").strip()
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for item in history or []:
            role = str(item.get("role") or "user").strip()
            if role not in {"system", "user", "assistant"}:
                role = "user"
            content = str(item.get("content") or "").strip()
            if content:
                messages.append({"role": role, "content": content[: max(1000, int(config.max_turn_chars or 12000))]})
        messages.append({"role": "user", "content": (message or "").strip()})

        headers = build_auth_headers(config)
        headers["Accept"] = "application/json"
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if "temperature" in adapter_config:
            payload["temperature"] = adapter_config["temperature"]
        if "max_tokens" in adapter_config:
            payload["max_tokens"] = adapter_config["max_tokens"]

        async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True) as client:
            try:
                response = await client.post(endpoint, json=payload, headers=headers)
            except httpx.TimeoutException:
                return {
                    "ok": False,
                    "detail": "OpenAI-compatible external agent request timed out",
                    "adapter": self.adapter_id,
                    "endpoint": endpoint,
                    "mode": "openai_compatible_chat",
                    "content": "",
                }
            except httpx.HTTPError as exc:
                return {
                    "ok": False,
                    "detail": f"OpenAI-compatible external agent request failed: {exc}",
                    "adapter": self.adapter_id,
                    "endpoint": endpoint,
                    "mode": "openai_compatible_chat",
                    "content": "",
                }

        content_type = response.headers.get("content-type", "")
        try:
            response_payload = response.json()
        except ValueError:
            response_payload = response.text
        content = extract_content_from_payload(response_payload)

        return {
            "ok": 200 <= response.status_code < 300 and bool(content),
            "detail": "OpenAI-compatible external agent responded successfully" if 200 <= response.status_code < 300 else f"OpenAI-compatible external agent responded with HTTP {response.status_code}",
            "adapter": self.adapter_id,
            "endpoint": endpoint,
            "mode": "openai_compatible_chat",
            "status_code": response.status_code,
            "content_type": content_type,
            "content": content,
            "session_key": session_key,
            "conversation": dict(conversation or {}),
            "metadata": dict(metadata or {}),
        }

    async def probe(self, agent: ExternalAgentInstance) -> ExternalAgentResult:
        config = agent.config
        adapter_config = dict(config.adapter_config or {})
        endpoint = str(adapter_config.get("models_endpoint") or adapter_config.get("chat_completions_endpoint") or config.endpoint).strip()
        timeout_s = min(max(int(config.timeout_s or 10), 3), 15)
        headers = build_auth_headers(config)
        headers["Accept"] = "application/json, text/plain;q=0.9, */*;q=0.8"
        async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True) as client:
            try:
                response = await client.get(endpoint, headers=headers)
            except httpx.TimeoutException:
                return {
                    "ok": False,
                    "detail": "OpenAI-compatible endpoint probe timed out",
                    "adapter": self.adapter_id,
                    "endpoint": endpoint,
                    "mode": "openai_compatible_probe",
                }
            except httpx.HTTPError as exc:
                return {
                    "ok": False,
                    "detail": f"OpenAI-compatible endpoint probe failed: {exc}",
                    "adapter": self.adapter_id,
                    "endpoint": endpoint,
                    "mode": "openai_compatible_probe",
                }

        return {
            "ok": 200 <= response.status_code < 300,
            "detail": "OpenAI-compatible endpoint responded successfully" if 200 <= response.status_code < 300 else f"OpenAI-compatible endpoint responded with HTTP {response.status_code}",
            "adapter": self.adapter_id,
            "endpoint": endpoint,
            "mode": "openai_compatible_probe",
            "status_code": response.status_code,
            "content_type": response.headers.get("content-type", ""),
        }
