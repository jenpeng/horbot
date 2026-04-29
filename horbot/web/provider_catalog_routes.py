"""Provider catalog API routes."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/providers")
async def list_providers():
    """List all available LLM providers and their models."""
    from horbot.config.loader import load_config
    from horbot.providers.registry import PROVIDERS

    config = load_config()

    providers = []

    provider_names = [
        ("openai", "OpenAI"),
        ("anthropic", "Anthropic"),
        ("openrouter", "OpenRouter"),
        ("deepseek", "DeepSeek"),
        ("groq", "Groq"),
        ("zhipu", "智谱 AI"),
        ("dashscope", "阿里云通义"),
        ("vllm", "vLLM"),
        ("gemini", "Google Gemini"),
        ("moonshot", "Moonshot"),
        ("minimax", "MiniMax"),
        ("aihubmix", "AiHubMix"),
        ("siliconflow", "硅基流动"),
        ("volcengine", "火山引擎"),
        ("custom", "自定义"),
    ]

    known_provider_ids = {provider_id for provider_id, _ in provider_names}
    extra_provider_map = getattr(config.providers, "model_extra", {}) or {}
    for provider_id in sorted(extra_provider_map):
        provider_config = getattr(config.providers, provider_id, None)
        if provider_id in known_provider_ids:
            continue
        if provider_config and (provider_config.api_key or provider_config.api_base):
            provider_names.append((provider_id, provider_id))

    oauth_provider_ids = {spec.name for spec in PROVIDERS if spec.is_oauth}

    for provider_id, provider_name in provider_names:
        provider_config = getattr(config.providers, provider_id, None)
        has_key = False
        if provider_config:
            has_key = bool(provider_config.api_key) or provider_id in oauth_provider_ids

        providers.append({
            "id": provider_id,
            "name": provider_name,
            "configured": has_key,
            "models": _get_provider_models(provider_id),
        })

    return {
        "providers": providers,
        "default_provider": config.agents.defaults.provider,
        "default_model": config.agents.defaults.model,
    }


def _get_provider_models(provider_id: str) -> list[dict]:
    """Get available models for a provider."""
    models_map = {
        "openai": [
            {"id": "gpt-4o", "name": "GPT-4o", "description": "最新多模态模型"},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "description": "轻量多模态模型"},
            {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "description": "GPT-4 增强版"},
            {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "description": "快速经济模型"},
        ],
        "anthropic": [
            {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "description": "最新 Claude 模型"},
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "description": "平衡性能与成本"},
            {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku", "description": "快速响应模型"},
            {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus", "description": "最强能力模型"},
        ],
        "openrouter": [
            {"id": "anthropic/claude-sonnet-4", "name": "Claude Sonnet 4", "description": "通过 OpenRouter"},
            {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "description": "通过 OpenRouter"},
            {"id": "openai/gpt-4o", "name": "GPT-4o", "description": "通过 OpenRouter"},
            {"id": "google/gemini-pro-1.5", "name": "Gemini Pro 1.5", "description": "通过 OpenRouter"},
            {"id": "deepseek/deepseek-chat", "name": "DeepSeek Chat", "description": "通过 OpenRouter"},
        ],
        "deepseek": [
            {"id": "deepseek-chat", "name": "DeepSeek Chat", "description": "对话模型"},
            {"id": "deepseek-coder", "name": "DeepSeek Coder", "description": "代码专用模型"},
        ],
        "groq": [
            {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B", "description": "Meta 开源模型"},
            {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B", "description": "轻量快速模型"},
            {"id": "mixtral-8x7b-32768", "name": "Mixtral 8x7B", "description": "MoE 架构模型"},
        ],
        "zhipu": [
            {"id": "glm-4-plus", "name": "GLM-4 Plus", "description": "智谱最强模型"},
            {"id": "glm-4-0520", "name": "GLM-4", "description": "智谱旗舰模型"},
            {"id": "glm-4-flash", "name": "GLM-4 Flash", "description": "快速模型"},
        ],
        "dashscope": [
            {"id": "qwen-max", "name": "通义千问 Max", "description": "阿里最强模型"},
            {"id": "qwen-plus", "name": "通义千问 Plus", "description": "平衡模型"},
            {"id": "qwen-turbo", "name": "通义千问 Turbo", "description": "快速模型"},
        ],
        "gemini": [
            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "description": "Google 最新模型"},
            {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "description": "快速响应模型"},
            {"id": "gemini-pro", "name": "Gemini Pro", "description": "标准模型"},
        ],
        "minimax": [
            {"id": "MiniMax-Text-01", "name": "MiniMax Text 01", "description": "MiniMax 文本模型"},
            {"id": "abab6.5-chat", "name": "ABAB 6.5 Chat", "description": "MiniMax 对话模型"},
        ],
        "moonshot": [
            {"id": "moonshot-v1-8k", "name": "Moonshot V1 8K", "description": "8K 上下文"},
            {"id": "moonshot-v1-32k", "name": "Moonshot V1 32K", "description": "32K 上下文"},
            {"id": "moonshot-v1-128k", "name": "Moonshot V1 128K", "description": "128K 上下文"},
        ],
        "siliconflow": [
            {"id": "Qwen/Qwen2.5-72B-Instruct", "name": "Qwen 2.5 72B", "description": "通义千问开源版"},
            {"id": "deepseek-ai/DeepSeek-V2.5", "name": "DeepSeek V2.5", "description": "DeepSeek 最新版"},
        ],
        "volcengine": [
            {"id": "doubao-pro-32k", "name": "豆包 Pro 32K", "description": "字节豆包模型"},
            {"id": "doubao-lite-32k", "name": "豆包 Lite 32K", "description": "轻量版模型"},
        ],
        "aihubmix": [
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "description": "通过 AiHubMix"},
            {"id": "gpt-4o", "name": "GPT-4o", "description": "通过 AiHubMix"},
        ],
        "vllm": [
            {"id": "custom", "name": "自定义模型", "description": "使用 vLLM 部署的模型"},
        ],
        "custom": [
            {"id": "custom", "name": "自定义模型", "description": "自定义 OpenAI 兼容端点"},
        ],
    }

    if provider_id in models_map:
        return models_map[provider_id]
    return [
        {"id": "gpt-5.4", "name": "gpt-5.4", "description": "自定义 Provider 默认模型"},
        {"id": "custom", "name": "自定义模型", "description": "手动输入模型名称"},
    ]
