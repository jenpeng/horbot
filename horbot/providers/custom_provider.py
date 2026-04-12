"""Direct OpenAI-compatible provider — bypasses LiteLLM."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

import json_repair
from openai import AsyncOpenAI

from horbot.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from horbot.providers.diagnostics import diagnose_provider_error


class CustomProvider(LLMProvider):

    def __init__(self, api_key: str = "no-key", api_base: str = "http://localhost:8000/v1", default_model: str = "default"):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self._client = AsyncOpenAI(api_key=api_key, base_url=api_base)

    @staticmethod
    def _extract_text(payload: Any) -> str:
        if isinstance(payload, str):
            return payload
        if isinstance(payload, list):
            parts: list[str] = []
            for item in payload:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("content") or item.get("value") or item.get("output_text")
                    if isinstance(text, str):
                        parts.append(text)
                else:
                    text = (
                        getattr(item, "text", None)
                        or getattr(item, "content", None)
                        or getattr(item, "value", None)
                        or getattr(item, "output_text", None)
                    )
                    extracted = CustomProvider._extract_text(text)
                    if extracted:
                        parts.append(extracted)
            return "".join(parts)
        if isinstance(payload, dict):
            text = payload.get("text") or payload.get("content") or payload.get("value") or payload.get("output_text")
            return CustomProvider._extract_text(text)
        text = (
            getattr(payload, "text", None)
            or getattr(payload, "content", None)
            or getattr(payload, "value", None)
            or getattr(payload, "output_text", None)
        )
        if text is not None and text is not payload:
            return CustomProvider._extract_text(text)
        return ""

    async def _chat_streaming(
        self,
        kwargs: dict[str, Any],
        on_content_delta: Callable[[str], Awaitable[None] | None] | None = None,
    ) -> LLMResponse:
        stream = await self._client.chat.completions.create(
            **kwargs,
            stream=True,
            stream_options={"include_usage": True},
        )

        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls: dict[int, dict[str, Any]] = {}
        finish_reason = "stop"
        usage: dict[str, int] = {}

        async for chunk in stream:
            if getattr(chunk, "usage", None):
                usage = {
                    "prompt_tokens": getattr(chunk.usage, "prompt_tokens", 0) or 0,
                    "completion_tokens": getattr(chunk.usage, "completion_tokens", 0) or 0,
                    "total_tokens": getattr(chunk.usage, "total_tokens", 0) or 0,
                }

            for choice in getattr(chunk, "choices", []) or []:
                finish_reason = choice.finish_reason or finish_reason
                delta = getattr(choice, "delta", None)
                if delta is None:
                    continue

                content = self._extract_text(getattr(delta, "content", None))
                if content:
                    content_parts.append(content)
                    if on_content_delta:
                        maybe_result = on_content_delta("".join(content_parts))
                        if maybe_result is not None:
                            await maybe_result

                reasoning = (
                    self._extract_text(getattr(delta, "reasoning_content", None))
                    or self._extract_text(getattr(delta, "reasoning", None))
                )
                if reasoning:
                    reasoning_parts.append(reasoning)

                for index, tc in enumerate(getattr(delta, "tool_calls", None) or []):
                    bucket = tool_calls.setdefault(index, {"id": None, "name": "", "arguments": []})
                    if getattr(tc, "id", None):
                        bucket["id"] = tc.id
                    function = getattr(tc, "function", None)
                    if function is None:
                        continue
                    if getattr(function, "name", None):
                        bucket["name"] = function.name
                    if getattr(function, "arguments", None):
                        bucket["arguments"].append(function.arguments)

        parsed_tool_calls = [
            ToolCallRequest(
                id=data["id"] or f"tool_{index}",
                name=data["name"],
                arguments=json_repair.loads("".join(data["arguments"])) if data["arguments"] else {},
            )
            for index, data in sorted(tool_calls.items())
            if data["name"]
        ]

        reasoning_content = "".join(reasoning_parts) or None
        content = "".join(content_parts) or None
        if not content and reasoning_content and not parsed_tool_calls:
            content = reasoning_content

        return LLMResponse(
            content=content,
            tool_calls=parsed_tool_calls,
            finish_reason=finish_reason,
            usage=usage,
            reasoning_content=reasoning_content,
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        file_ids: list[str] | None = None,
        files: list[dict[str, Any]] | None = None,
        on_content_delta: Callable[[str], Awaitable[None] | None] | None = None,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": self._sanitize_empty_content(messages),
            "max_tokens": max(1, max_tokens),
            "temperature": temperature,
        }
        if tools:
            kwargs.update(tools=tools, tool_choice="auto")
        try:
            if on_content_delta:
                return await self._chat_streaming(kwargs, on_content_delta=on_content_delta)
            return self._parse(await self._client.chat.completions.create(**kwargs))
        except Exception as e:
            if "Stream must be set to true" in str(e):
                try:
                    return await self._chat_streaming(kwargs, on_content_delta=on_content_delta)
                except Exception as stream_error:
                    error_info = diagnose_provider_error(
                        stream_error,
                        provider_name="custom",
                        model=kwargs.get("model"),
                    )
                    return LLMResponse(
                        content=error_info["message"],
                        finish_reason="error",
                        error_info=error_info,
                    )
            error_info = diagnose_provider_error(
                e,
                provider_name="custom",
                model=kwargs.get("model"),
            )
            return LLMResponse(
                content=error_info["message"],
                finish_reason="error",
                error_info=error_info,
            )

    def _parse(self, response: Any) -> LLMResponse:
        choice = response.choices[0]
        msg = choice.message
        tool_calls = [
            ToolCallRequest(id=tc.id, name=tc.function.name,
                            arguments=json_repair.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments)
            for tc in (msg.tool_calls or [])
        ]
        u = response.usage
        content = (
            self._extract_text(getattr(msg, "content", None))
            or self._extract_text(getattr(msg, "output_text", None))
            or None
        )
        reasoning_content = (
            self._extract_text(getattr(msg, "reasoning_content", None))
            or self._extract_text(getattr(msg, "reasoning", None))
            or None
        )
        if not content and reasoning_content and not tool_calls:
            content = reasoning_content
        return LLMResponse(
            content=content, tool_calls=tool_calls, finish_reason=choice.finish_reason or "stop",
            usage={"prompt_tokens": u.prompt_tokens, "completion_tokens": u.completion_tokens, "total_tokens": u.total_tokens} if u else {},
            reasoning_content=reasoning_content,
        )

    def get_default_model(self) -> str:
        return self.default_model
