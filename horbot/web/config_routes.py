"""Configuration API routes."""

from __future__ import annotations

import inspect
from typing import Any, Callable, Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from horbot.config.schema import Config, ModelsConfig


_hot_reload_test_counter = 0


class ModelConfigUpdate(BaseModel):
    """Model configuration update request."""

    provider: str
    model: str
    description: str = ""
    capabilities: list[str] = []


class AgentDefaultsUpdateRequest(BaseModel):
    """Partial update request for agent defaults."""

    workspace: Optional[str] = None
    maxTokens: Optional[int] = None
    temperature: Optional[float] = None
    models: Optional[dict[str, Any]] = None


class WebSearchConfigUpdateRequest(BaseModel):
    """Partial update request for web search config."""

    enabled: Optional[bool] = None
    provider: Optional[str] = None
    tavilyEnabled: Optional[bool] = None
    langsearchEnabled: Optional[bool] = None
    apiKey: Optional[str] = None
    maxResults: Optional[int] = None


def _resolve_web_search_provider_api_key(search_config: Any, provider: str | None = None) -> str:
    """Return the effective API key for the requested web-search provider."""
    resolved_provider = str(provider or getattr(search_config, "provider", "") or "").strip().lower()
    provider_api_keys = getattr(search_config, "provider_api_keys", {}) or {}
    if resolved_provider and isinstance(provider_api_keys, dict):
        provider_key = provider_api_keys.get(resolved_provider)
        if isinstance(provider_key, str) and provider_key:
            return provider_key
        if provider_api_keys:
            return ""
    return str(getattr(search_config, "api_key", "") or "")


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


def _validation_payload(result) -> dict[str, Any]:
    return {
        "valid": result.valid,
        "errors": [
            {
                "code": msg.code,
                "message": msg.message,
                "field_path": msg.field_path,
                "suggestion": msg.suggestion,
            }
            for msg in result.errors
        ],
        "warnings": [
            {
                "code": msg.code,
                "message": msg.message,
                "field_path": msg.field_path,
                "suggestion": msg.suggestion,
            }
            for msg in result.warnings
        ],
        "infos": [
            {
                "code": msg.code,
                "message": msg.message,
                "field_path": msg.field_path,
                "suggestion": msg.suggestion,
            }
            for msg in result.infos
        ],
    }


def create_config_router(
    get_config: Callable[[], Any],
    save_config_fn: Callable[[Any], Any],
    reset_agent_loop_fn: Callable[[], Any],
    sanitize_config_for_client_fn: Callable[[dict[str, Any]], dict[str, Any]],
    redact_sensitive_data_fn: Callable[[Any], Any],
    validate_config_fn: Callable[[Any], Any],
) -> APIRouter:
    """Create configuration routes."""

    router = APIRouter()

    @router.get("/config")
    async def get_config_endpoint():
        """Get current configuration."""
        config = get_config()
        raw_data = config.model_dump(by_alias=True)
        data = sanitize_config_for_client_fn(raw_data)

        search_config = getattr(getattr(config.tools, "web", None), "search", None)
        sanitized_search = data.setdefault("tools", {}).setdefault("web", {}).setdefault("search", {})
        sanitized_search["enabled"] = bool(getattr(search_config, "enabled", True))
        sanitized_search["tavilyEnabled"] = bool(getattr(search_config, "tavily_enabled", True))
        sanitized_search["langsearchEnabled"] = bool(getattr(search_config, "langsearch_enabled", True))

        predefined_providers = {
            "custom", "anthropic", "openai", "openrouter", "deepseek", "groq",
            "zhipu", "dashscope", "vllm", "gemini", "moonshot", "minimax",
            "aihubmix", "siliconflow", "volcengine", "openaiCodex", "githubCopilot",
        }
        if "providers" in data:
            providers = raw_data.get("providers", {})
            sanitized_providers = data["providers"]
            data["providers"] = {
                name: sanitized_providers.get(name, {})
                for name, settings in providers.items()
                if name in predefined_providers or (settings and (settings.get("apiKey") or settings.get("api_key")))
            }

        return data

    @router.get("/config/validate")
    async def validate_config_endpoint():
        """Validate current configuration and return structured result."""
        return _validation_payload(validate_config_fn(get_config()))

    @router.put("/config")
    async def update_config(config_data: dict[str, Any]):
        """Update configuration."""
        try:
            logger.info("[Config Update] Received config data keys: {}", list(config_data.keys()))
            logger.debug("[Config Update] Config data: {}", redact_sensitive_data_fn(config_data))
            config = Config.model_validate(config_data)
            saved_path = save_config_fn(config)
            await _maybe_await(reset_agent_loop_fn())
            return {
                "status": "success",
                "message": "Configuration updated and agent reloaded",
                "path": str(saved_path),
            }
        except PermissionError as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Permission denied: {str(exc)}. The application may be running in a sandbox environment. Please run outside of sandbox or check file permissions.",
            )
        except ValueError as exc:
            logger.error("[Config Update] Validation error: {}", exc)
            raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(exc)}")
        except Exception as exc:
            logger.error("[Config Update] Error: {}", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to save configuration: {str(exc)}")

    @router.put("/config/models/{scenario}")
    async def update_model_config(scenario: str, model_data: ModelConfigUpdate):
        """Update a single model configuration."""
        valid_scenarios = ["main", "planning", "file", "image", "webSearch", "audio", "video"]
        if scenario not in valid_scenarios:
            raise HTTPException(status_code=400, detail=f"Invalid scenario: {scenario}. Valid scenarios are: {valid_scenarios}")

        try:
            config = get_config()
            models = config.agents.defaults.models
            if not hasattr(models, scenario):
                raise HTTPException(status_code=400, detail=f"Model scenario not found: {scenario}")

            model_config = getattr(models, scenario)
            model_config.provider = model_data.provider
            model_config.model = model_data.model
            model_config.description = model_data.description
            model_config.capabilities = model_data.capabilities
            saved_path = save_config_fn(config)

            return {
                "status": "success",
                "message": f"Model '{scenario}' updated successfully",
                "scenario": scenario,
                "path": str(saved_path),
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to update model configuration: {str(exc)}")

    @router.patch("/config/agent-defaults")
    async def update_agent_defaults(request: AgentDefaultsUpdateRequest):
        """Patch agent default settings without replacing the full config."""
        try:
            config = get_config()
            defaults = config.agents.defaults
            if request.workspace is not None:
                defaults.workspace = request.workspace
            if request.maxTokens is not None:
                defaults.max_tokens = request.maxTokens
            if request.temperature is not None:
                defaults.temperature = request.temperature
            if request.models is not None:
                defaults.models = ModelsConfig.model_validate(request.models)

            saved_path = save_config_fn(config)
            await _maybe_await(reset_agent_loop_fn())
            return {
                "status": "success",
                "message": "Agent defaults updated successfully",
                "path": str(saved_path),
            }
        except PermissionError as exc:
            raise HTTPException(status_code=500, detail=f"Permission denied: {str(exc)}. The application may be running in a sandbox environment.")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(exc)}")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to update agent defaults: {str(exc)}")

    @router.patch("/config/web-search")
    async def update_web_search_config(request: WebSearchConfigUpdateRequest):
        """Patch web search config without replacing the full config."""
        try:
            config = get_config()
            search_config = config.tools.web.search
            provider_api_keys = dict(getattr(search_config, "provider_api_keys", {}) or {})
            current_provider = str(getattr(search_config, "provider", "") or "duckduckgo").strip().lower() or "duckduckgo"
            legacy_api_key = str(getattr(search_config, "api_key", "") or "")
            if legacy_api_key and not provider_api_keys:
                provider_api_keys[current_provider] = legacy_api_key
            search_config.provider_api_keys = provider_api_keys
            target_provider = str(request.provider or search_config.provider or "duckduckgo").strip().lower() or "duckduckgo"

            if request.enabled is not None:
                search_config.enabled = request.enabled
            if request.provider is not None:
                search_config.provider = target_provider
            if request.tavilyEnabled is not None:
                search_config.tavily_enabled = request.tavilyEnabled
            if request.langsearchEnabled is not None:
                search_config.langsearch_enabled = request.langsearchEnabled
            if request.apiKey is not None:
                provider_api_keys = dict(getattr(search_config, "provider_api_keys", {}) or {})
                if request.apiKey:
                    provider_api_keys[target_provider] = request.apiKey
                else:
                    provider_api_keys.pop(target_provider, None)
                search_config.provider_api_keys = provider_api_keys
            if request.maxResults is not None:
                search_config.max_results = request.maxResults
            search_config.api_key = _resolve_web_search_provider_api_key(search_config, search_config.provider)

            saved_path = save_config_fn(config)
            await _maybe_await(reset_agent_loop_fn())
            return {
                "status": "success",
                "message": "Web search config updated successfully",
                "path": str(saved_path),
            }
        except PermissionError as exc:
            raise HTTPException(status_code=500, detail=f"Permission denied: {str(exc)}. The application may be running in a sandbox environment.")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(exc)}")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to update web search config: {str(exc)}")

    @router.get("/hot-reload-test")
    async def hot_reload_test():
        """Test endpoint to verify hot reload is working."""
        global _hot_reload_test_counter
        _hot_reload_test_counter += 1
        return {
            "status": "hot_reload_working",
            "counter": _hot_reload_test_counter,
            "message": "HOT RELOAD SUCCESS! This message was updated after code modification.",
            "version": "v2",
        }

    return router
