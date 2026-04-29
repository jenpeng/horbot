"""Provider configuration API routes."""

from typing import Any, Callable, Dict
import re

from fastapi import APIRouter, HTTPException
from loguru import logger

from horbot.config.schema import ProviderConfig, ProvidersConfig
from horbot.web.security import mask_secret

PREDEFINED_PROVIDERS = {
    "custom",
    "anthropic",
    "openai",
    "openrouter",
    "deepseek",
    "groq",
    "zhipu",
    "dashscope",
    "vllm",
    "gemini",
    "moonshot",
    "minimax",
    "aihubmix",
    "siliconflow",
    "volcengine",
    "openaiCodex",
    "githubCopilot",
    "openai_codex",
    "github_copilot",
}


def create_provider_config_router(
    get_config: Callable[[], Any],
    save_config_fn: Callable[[Any], Any],
    redact_sensitive_data_fn: Callable[[Any], Any],
) -> APIRouter:
    router = APIRouter()

    @router.get("/config/providers/{provider_name}")
    async def get_provider_config(provider_name: str):
        """Get configuration for a specific provider."""
        config = get_config()

        provider_config = getattr(config.providers, provider_name, None)
        if not provider_config:
            raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found")

        return {
            "name": provider_name,
            "apiKey": "",
            "hasApiKey": bool(provider_config.api_key),
            "apiKeyMasked": mask_secret(provider_config.api_key),
            "apiBase": provider_config.api_base,
            "compatibilityProfile": getattr(provider_config, "compatibility_profile", "auto"),
            "extraHeaders": {key: "********" for key in (provider_config.extra_headers or {}).keys()},
            "hasExtraHeaders": bool(provider_config.extra_headers),
        }

    @router.put("/config/providers/{provider_name}")
    async def update_provider_config(provider_name: str, provider_data: Dict[str, Any]):
        """Update configuration for a specific provider."""
        try:
            config = get_config()

            existing_provider = getattr(config.providers, provider_name, None)
            if not existing_provider:
                raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found")

            api_key = provider_data.get("apiKey")
            clear_api_key = bool(provider_data.get("clearApiKey"))
            provider_config = ProviderConfig(
                api_key="" if clear_api_key else (existing_provider.api_key if api_key in (None, "") else api_key),
                api_base=provider_data.get("apiBase", existing_provider.api_base),
                compatibility_profile=provider_data.get(
                    "compatibilityProfile",
                    getattr(existing_provider, "compatibility_profile", "auto"),
                ),
                extra_headers=provider_data.get("extraHeaders", existing_provider.extra_headers),
            )

            setattr(config.providers, provider_name, provider_config)
            saved_path = save_config_fn(config)

            return {
                "status": "success",
                "message": f"Provider '{provider_name}' configuration updated",
                "path": str(saved_path),
            }
        except HTTPException:
            raise
        except PermissionError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Permission denied: {str(e)}. The application may be running in a sandbox environment.",
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update provider configuration: {str(e)}")

    @router.post("/config/providers")
    async def add_provider(provider_data: Dict[str, Any]):
        """Add a new custom provider."""
        try:
            logger.info("[Add Provider] Received provider data: {}", redact_sensitive_data_fn(provider_data))

            provider_name = provider_data.get("name")
            if not provider_name:
                raise HTTPException(status_code=400, detail="Provider name is required")

            config = get_config()

            existing_provider = getattr(config.providers, provider_name, None)
            if existing_provider:
                logger.warning("[Add Provider] Provider '{}' already exists", provider_name)
                raise HTTPException(status_code=400, detail=f"Provider '{provider_name}' already exists")

            provider_config = ProviderConfig(
                api_key=provider_data.get("apiKey") or "",
                api_base=provider_data.get("apiBase"),
                compatibility_profile=provider_data.get("compatibilityProfile") or "auto",
                extra_headers=provider_data.get("extraHeaders"),
            )

            logger.info("[Add Provider] Created provider config for '{}'", provider_name)

            current_providers = config.providers.model_dump()
            current_providers[provider_name] = provider_config.model_dump()
            config.providers = ProvidersConfig(**current_providers)

            logger.info("[Add Provider] Updated providers config, saving...")
            saved_path = save_config_fn(config)
            logger.info("[Add Provider] Config saved to {}", saved_path)

            return {
                "status": "success",
                "message": f"Provider '{provider_name}' added successfully",
                "path": str(saved_path),
            }
        except HTTPException:
            raise
        except PermissionError as e:
            logger.error("[Add Provider] Permission error: {}", e)
            raise HTTPException(
                status_code=500,
                detail=f"Permission denied: {str(e)}. The application may be running in a sandbox environment.",
            )
        except ValueError as e:
            logger.error("[Add Provider] Validation error: {}", e)
            raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
        except Exception as e:
            logger.error("[Add Provider] Unexpected error: {}", e, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to add provider: {str(e)}")

    @router.delete("/config/providers/{provider_name}")
    async def delete_provider(provider_name: str):
        """Delete a custom provider."""
        try:
            config = get_config()

            if provider_name in PREDEFINED_PROVIDERS:
                raise HTTPException(
                    status_code=403,
                    detail=f"Cannot delete predefined provider '{provider_name}'",
                )

            existing_provider = getattr(config.providers, provider_name, None)
            actual_name = provider_name

            if not existing_provider:
                snake_name = re.sub(r"(?<!^)(?=[A-Z])", "_", provider_name).lower()
                existing_provider = getattr(config.providers, snake_name, None)
                actual_name = snake_name

                if snake_name in PREDEFINED_PROVIDERS:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Cannot delete predefined provider '{provider_name}'",
                    )

            if not existing_provider:
                raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found")

            # Pydantic models don't support dynamic attribute deletion. Reset the provider instead.
            setattr(config.providers, actual_name, ProviderConfig())
            saved_path = save_config_fn(config)

            return {
                "status": "success",
                "message": f"Provider '{provider_name}' deleted successfully",
                "path": str(saved_path),
            }
        except HTTPException:
            raise
        except PermissionError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Permission denied: {str(e)}. The application may be running in a sandbox environment.",
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete provider: {str(e)}")

    return router
