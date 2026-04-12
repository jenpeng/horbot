"""LiteLLM provider implementation for multi-provider support."""

import asyncio
import json
import json_repair
import os
from typing import Any, Awaitable, Callable
from loguru import logger
import httpx

import litellm
from litellm import acompletion

from horbot.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from horbot.providers.diagnostics import diagnose_provider_error
from horbot.providers.registry import find_by_model, find_gateway
from horbot.utils.error_messages import friendly_provider_error_message, is_retryable_provider_error


# Standard OpenAI chat-completion message keys plus reasoning_content for
# thinking-enabled models (Kimi k2.5, DeepSeek-R1, etc.).
_ALLOWED_MSG_KEYS = frozenset({"role", "content", "tool_calls", "tool_call_id", "name", "reasoning_content"})


class LiteLLMProvider(LLMProvider):
    """
    LLM provider using LiteLLM for multi-provider support.
    
    Supports OpenRouter, Anthropic, OpenAI, Gemini, MiniMax, and many other providers through
    a unified interface.  Provider-specific logic is driven by the registry
    (see providers/registry.py) — no if-elif chains needed here.
    """
    
    def __init__(
        self, 
        api_key: str | None = None, 
        api_base: str | None = None,
        default_model: str = "anthropic/claude-opus-4-5",
        extra_headers: dict[str, str] | None = None,
        provider_name: str | None = None,
        upload_dir: str | None = None,
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self.extra_headers = extra_headers or {}
        self.name = provider_name
        
        if upload_dir is None:
            from horbot.utils.paths import get_uploads_dir
            upload_dir = str(get_uploads_dir())
        self.upload_dir = upload_dir
        
        # Detect gateway / local deployment.
        # provider_name (from config key) is the primary signal;
        # api_key / api_base are fallback for auto-detection.
        self._gateway = find_gateway(provider_name, api_key, api_base)
        
        # Configure environment variables
        if api_key:
            self._setup_env(api_key, api_base, default_model)
        
        if api_base:
            litellm.api_base = api_base
        
        # Disable LiteLLM logging noise
        litellm.suppress_debug_info = True
        # Drop unsupported parameters for providers (e.g., gpt-5 rejects some params)
        litellm.drop_params = True
    
    def _setup_env(self, api_key: str, api_base: str | None, model: str) -> None:
        """Set environment variables based on detected provider."""
        spec = self._gateway or find_by_model(model)
        if not spec:
            return
        if not spec.env_key:
            # OAuth/provider-only specs (for example: openai_codex)
            return

        # Gateway/local overrides existing env; standard provider doesn't
        if self._gateway:
            os.environ[spec.env_key] = api_key
        else:
            os.environ.setdefault(spec.env_key, api_key)

        # Resolve env_extras placeholders:
        #   {api_key}  → user's API key
        #   {api_base} → user's api_base, falling back to spec.default_api_base
        effective_base = api_base or spec.default_api_base
        for env_name, env_val in spec.env_extras:
            resolved = env_val.replace("{api_key}", api_key)
            resolved = resolved.replace("{api_base}", effective_base)
            os.environ.setdefault(env_name, resolved)
    
    def _resolve_model(self, model: str) -> str:
        """Resolve model name by applying provider/gateway prefixes."""
        if self._gateway:
            # Gateway mode: apply gateway prefix, skip provider-specific prefixes
            prefix = self._gateway.litellm_prefix
            if self._gateway.strip_model_prefix:
                model = model.split("/")[-1]
            if prefix and not model.startswith(f"{prefix}/"):
                model = f"{prefix}/{model}"
            return model
        
        # Standard mode: auto-prefix for known providers
        spec = find_by_model(model)
        if spec and spec.litellm_prefix:
            model = self._canonicalize_explicit_prefix(model, spec.name, spec.litellm_prefix)
            if not any(model.startswith(s) for s in spec.skip_prefixes):
                model = f"{spec.litellm_prefix}/{model}"

        return model

    @staticmethod
    def _canonicalize_explicit_prefix(model: str, spec_name: str, canonical_prefix: str) -> str:
        """Normalize explicit provider prefixes like `github-copilot/...`."""
        if "/" not in model:
            return model
        prefix, remainder = model.split("/", 1)
        if prefix.lower().replace("-", "_") != spec_name:
            return model
        return f"{canonical_prefix}/{remainder}"
    
    def _supports_cache_control(self, model: str) -> bool:
        """Return True when the provider supports cache_control on content blocks."""
        if self._gateway is not None:
            return self._gateway.supports_prompt_caching
        spec = find_by_model(model)
        return spec is not None and spec.supports_prompt_caching

    def _apply_cache_control(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]] | None]:
        """Return copies of messages and tools with cache_control injected."""
        new_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                content = msg["content"]
                if isinstance(content, str):
                    new_content = [{"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}]
                else:
                    new_content = list(content)
                    new_content[-1] = {**new_content[-1], "cache_control": {"type": "ephemeral"}}
                new_messages.append({**msg, "content": new_content})
            else:
                new_messages.append(msg)

        new_tools = tools
        if tools:
            new_tools = list(tools)
            new_tools[-1] = {**new_tools[-1], "cache_control": {"type": "ephemeral"}}

        return new_messages, new_tools

    def _apply_model_overrides(self, model: str, kwargs: dict[str, Any]) -> None:
        """Apply model-specific parameter overrides from the registry."""
        model_lower = model.lower()
        spec = find_by_model(model)
        if spec:
            for pattern, overrides in spec.model_overrides:
                if pattern in model_lower:
                    kwargs.update(overrides)
                    return

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
                    extracted = LiteLLMProvider._extract_text(text)
                    if extracted:
                        parts.append(extracted)
            return "".join(parts)
        if isinstance(payload, dict):
            text = payload.get("text") or payload.get("content") or payload.get("value") or payload.get("output_text")
            return LiteLLMProvider._extract_text(text)
        text = (
            getattr(payload, "text", None)
            or getattr(payload, "content", None)
            or getattr(payload, "value", None)
            or getattr(payload, "output_text", None)
        )
        if text is not None and text is not payload:
            return LiteLLMProvider._extract_text(text)
        return ""
    
    @staticmethod
    def _sanitize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Strip non-standard keys and ensure assistant messages have a content key."""
        sanitized = []
        for msg in messages:
            clean = {k: v for k, v in msg.items() if k in _ALLOWED_MSG_KEYS}
            # Strict providers require "content" even when assistant only has tool_calls
            if clean.get("role") == "assistant" and "content" not in clean:
                clean["content"] = None
            sanitized.append(clean)
        return sanitized

    @staticmethod
    def _friendly_provider_error_message(
        error: Exception | None = None,
        *,
        status_code: int | None = None,
        error_text: str | None = None,
    ) -> str:
        """Return a user-facing provider error without leaking raw backend details."""
        return friendly_provider_error_message(
            error,
            status_code=status_code,
            error_text=error_text,
        )

    async def _chat_streaming(
        self,
        kwargs: dict[str, Any],
        on_content_delta: Callable[[str], Awaitable[None] | None] | None = None,
    ) -> LLMResponse:
        stream = await acompletion(
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

                content = LiteLLMProvider._extract_text(getattr(delta, "content", None))
                if content:
                    content_parts.append(content)
                    if on_content_delta:
                        maybe_result = on_content_delta("".join(content_parts))
                        if maybe_result is not None:
                            await maybe_result

                reasoning = (
                    LiteLLMProvider._extract_text(getattr(delta, "reasoning_content", None))
                    or LiteLLMProvider._extract_text(getattr(delta, "reasoning", None))
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
        files: list[dict] | None = None,
        on_content_delta: Callable[[str], Awaitable[None] | None] | None = None,
    ) -> LLMResponse:
        """
        Send a chat completion request via LiteLLM.
        
        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool definitions in OpenAI format.
            model: Model identifier (e.g., 'anthropic/claude-sonnet-4-5').
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.
            file_ids: Optional list of MiniMax file IDs for document processing.
            files: Optional list of file objects (images, audio, etc.).
        
        Returns:
            LLMResponse with content and/or tool calls.
        """
        original_model = model or self.default_model
        model = self._resolve_model(original_model)

        if self._supports_cache_control(original_model):
            messages, tools = self._apply_cache_control(messages, tools)

        # Clamp max_tokens to at least 1 — negative or zero values cause
        # LiteLLM to reject the request with "max_tokens must be at least 1".
        max_tokens = max(1, max_tokens)
        
        # Check if this is a MiniMax model with file_ids or files - use native API
        is_minimax = self._is_minimax_model(original_model)
        if is_minimax and (file_ids or files):
            return await self._chat_minimax_native(
                messages=messages,
                model=original_model,
                max_tokens=max_tokens,
                temperature=temperature,
                file_ids=file_ids,
                tools=tools,
                files=files,
            )
        
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": self._sanitize_messages(self._sanitize_empty_content(messages)),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        # Apply model-specific overrides (e.g. kimi-k2.5 temperature)
        self._apply_model_overrides(model, kwargs)
        
        # Pass api_key directly — more reliable than env vars alone
        if self.api_key:
            kwargs["api_key"] = self.api_key
        
        # Pass api_base for custom endpoints
        if self.api_base:
            kwargs["api_base"] = self.api_base
        
        # Pass extra headers (e.g. APP-Code for AiHubMix)
        extra_headers = self.extra_headers.copy() if self.extra_headers else {}

        logger.info(
            "LiteLLM request prepared: provider={}, original_model={}, resolved_model={}, api_base={}",
            self.name or "auto",
            original_model,
            model,
            self.api_base or "",
        )
        
        # Add Anthropic Prompt Caching header if supported
        if self._supports_cache_control(original_model) and ("anthropic" in model.lower() or "claude" in model.lower()):
            if "anthropic-beta" not in extra_headers:
                extra_headers["anthropic-beta"] = "prompt-caching-2024-07-31"
        
        if extra_headers:
            kwargs["extra_headers"] = extra_headers
        
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        
        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                if on_content_delta:
                    return await self._chat_streaming(kwargs, on_content_delta=on_content_delta)
                response = await acompletion(**kwargs)
                return self._parse_response(response)
            except Exception as e:
                should_retry = attempt < max_attempts and is_retryable_provider_error(e)
                if should_retry:
                    delay = 0.6 * attempt
                    logger.warning(
                        "LiteLLM chat call failed for model {} on attempt {}/{}: {}. Retrying in {:.1f}s",
                        original_model,
                        attempt,
                        max_attempts,
                        e,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                logger.exception("LiteLLM chat call failed for model {}: {}", original_model, e)
                error_info = diagnose_provider_error(
                    e,
                    provider_name=self.name,
                    model=original_model,
                )
                return LLMResponse(
                    content=error_info["message"],
                    finish_reason="error",
                    error_info=error_info,
                )
    
    def _is_minimax_model(self, model: str | None) -> bool:
        """Check if the model is a MiniMax model."""
        if not model:
            return False
        model_lower = model.lower()
        return "minimax" in model_lower or "abab" in model_lower
    
    async def _chat_minimax_native(
        self,
        messages: list[dict[str, Any]],
        model: str,
        max_tokens: int,
        temperature: float,
        file_ids: list[str] | None = None,
        tools: list[dict[str, Any]] | None = None,
        files: list[dict] | None = None,
    ) -> LLMResponse:
        """
        Call MiniMax native API for document processing and multimodal input.
        
        MiniMax API requires file_ids to be passed at the top level,
        which LiteLLM doesn't support. This method calls MiniMax API directly.
        
        API Reference: https://platform.minimaxi.com/document/guides/chat-conversation
        """
        import base64
        from pathlib import Path
        
        # Use api_base from config, default to MiniMax API
        # Note: api_base should be the base URL without /v1/chat/completions path
        # e.g., https://api.minimaxi.com or https://api.minimax.chat
        base_url = self.api_base or "https://api.minimaxi.com"
        
        # Remove trailing /v1 if present (we'll add it later)
        if base_url.endswith("/v1"):
            base_url = base_url[:-3]
        
        # Use the model name directly from config
        # No forced mapping - user can specify any model the API supports
        api_model = model
        

        
        # Process files (images, audio) into multimodal message format
        processed_messages = self._sanitize_messages(self._sanitize_empty_content(messages))
        
        # If there are image or audio files, convert to multimodal format
        if files:
            for msg_idx, msg in enumerate(processed_messages):
                if msg.get("role") == "user":
                    # Build multimodal content
                    content_parts = []
                    text_content = msg.get("content", "")
                    if text_content:
                        content_parts.append({"type": "text", "text": text_content})
                    
                    # Add images and audio to the message
                    for file_info in files:
                        if file_info.get("category") == "image":
                            # Read image file and convert to base64
                            file_path = Path(self.upload_dir) / file_info.get("filename", "")
                            logger.debug(f"Looking for image file: {file_path}")
                            if file_path.exists():
                                with open(file_path, "rb") as f:
                                    image_data = base64.b64encode(f.read()).decode("utf-8")
                                mime_type = file_info.get("mime_type", "image/png")
                                content_parts.append({
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime_type};base64,{image_data}"
                                    }
                                })
                                logger.debug(f"Added image to message: {file_info.get('filename')}")
                            else:
                                logger.warning(f"Image file not found: {file_path}")
                        elif file_info.get("category") == "audio":
                            # Read audio file and convert to base64
                            file_path = Path(self.upload_dir) / file_info.get("filename", "")
                            logger.debug(f"Looking for audio file: {file_path}")
                            if file_path.exists():
                                with open(file_path, "rb") as f:
                                    audio_data = base64.b64encode(f.read()).decode("utf-8")
                                # Determine audio format
                                mime_type = file_info.get("mime_type", "audio/mp3")
                                audio_format = mime_type.split("/")[-1] if "/" in mime_type else "mp3"
                                content_parts.append({
                                    "type": "input_audio",
                                    "input_audio": {
                                        "data": audio_data,
                                        "format": audio_format
                                    }
                                })
                                logger.debug(f"Added audio to message: {file_info.get('filename')}")
                            else:
                                logger.warning(f"Audio file not found: {file_path}")
                    
                    # Update message with multimodal content
                    if len(content_parts) > 1:
                        processed_messages[msg_idx] = {
                            "role": msg["role"],
                            "content": content_parts
                        }
        
        payload = {
            "model": api_model,
            "messages": processed_messages,
            "temperature": temperature,
        }
        
        # MiniMax API does not support max_tokens parameter
        # The model automatically determines the output length
        
        # Add file_ids for document processing
        if file_ids:
            payload["file_ids"] = file_ids
        
        # Add tools if provided
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        logger.debug(f"MiniMax API request payload: model={api_model}, messages_count={len(processed_messages)}")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        # MiniMax API uses /v1/chat/completions for all requests
        # Reference: https://api.minimax.chat/v1/chat/completions
        url = f"{base_url}/v1/chat/completions"
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                
                if response.status_code != 200:
                    error_text = response.text
                    logger.error(f"MiniMax API error: {response.status_code} - {error_text}")
                    error_info = diagnose_provider_error(
                        status_code=response.status_code,
                        error_text=error_text,
                        provider_name=self.name or "minimax",
                        model=model,
                    )
                    return LLMResponse(
                        content=error_info["message"],
                        finish_reason="error",
                        error_info=error_info,
                    )
                
                data = response.json()
                return self._parse_minimax_response(data)
                
        except Exception as e:
            logger.exception("MiniMax native API call failed for model {}: {}", model, e)
            error_info = diagnose_provider_error(
                e,
                provider_name=self.name or "minimax",
                model=model,
            )
            return LLMResponse(
                content=error_info["message"],
                finish_reason="error",
                error_info=error_info,
            )
    
    def _parse_minimax_response(self, data: dict) -> LLMResponse:
        """Parse MiniMax API response into LLMResponse.
        
        MiniMax web_search returns a messages array with complete conversation:
        - messages[0]: user message
        - messages[1]: assistant tool_calls (plugin_web_search)
        - messages[2]: tool result (search results)
        - messages[3]: assistant final response
        """
        choices = data.get("choices", [])
        if not choices:
            return LLMResponse(
                content="No response from MiniMax",
                finish_reason="stop",
            )
        
        choice = choices[0]
        
        # Check for messages array (MiniMax web_search format)
        messages = choice.get("messages", [])
        if messages:
            # Find the final assistant message
            final_content = ""
            for msg in messages:
                if msg.get("role") == "assistant" and not msg.get("tool_calls"):
                    final_content = msg.get("content", "")
                    break
            
            if final_content:
                return LLMResponse(
                    content=final_content,
                    finish_reason="stop",
                    usage=data.get("usage", {}),
                )
        
        # Fallback to single message format (non-web-search or MiniMax-Text-01)
        message = choice.get("message", {})
        content = message.get("content", "")
        finish_reason = choice.get("finish_reason", "stop")
        
        tool_calls = []
        if message.get("tool_calls"):
            for tc in message["tool_calls"]:
                args = tc.get("function", {}).get("arguments", "{}")
                if isinstance(args, str):
                    args = json_repair.loads(args)
                
                tool_calls.append(ToolCallRequest(
                    id=tc.get("id", ""),
                    name=tc.get("function", {}).get("name", ""),
                    arguments=args,
                ))
        
        usage = data.get("usage", {})
        
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
        )
    
    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse LiteLLM response into our standard format."""
        choice = response.choices[0]
        message = choice.message
        
        tool_calls = []
        if hasattr(message, "tool_calls") and message.tool_calls:
            for tc in message.tool_calls:
                # Parse arguments from JSON string if needed
                args = tc.function.arguments
                if isinstance(args, str):
                    args = json_repair.loads(args)
                
                tool_calls.append(ToolCallRequest(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))
        
        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        
        reasoning_content = getattr(message, "reasoning_content", None) or None
        
        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
            reasoning_content=reasoning_content,
        )
    
    def get_default_model(self) -> str:
        """Get the default model."""
        return self.default_model
