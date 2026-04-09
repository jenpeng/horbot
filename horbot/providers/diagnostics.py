"""Structured diagnostics for provider/model invocation failures."""

from __future__ import annotations

from typing import Any


def _normalize_error(error: Exception | str | None = None, *, error_text: str | None = None) -> str:
    parts = []
    if error is not None:
        parts.append(str(error))
    if error_text:
        parts.append(str(error_text))
    return " ".join(part.strip() for part in parts if str(part).strip()).strip().lower()


def detect_provider_error_kind(
    error: Exception | str | None = None,
    *,
    status_code: int | None = None,
    error_text: str | None = None,
) -> str:
    raw = _normalize_error(error, error_text=error_text)
    if not raw and status_code is None:
        return "generic"

    if any(marker in raw for marker in ("missing api key", "provider not configured", "api key is required", "missing credentials")):
        return "missing_credentials"
    if status_code in (401, 403) or any(
        marker in raw for marker in ("unauthorized", "authentication", "invalid api key", "incorrect api key", "forbidden", "invalid_token")
    ):
        return "auth"
    if status_code == 404 or any(
        marker in raw for marker in ("model not found", "model_not_found", "does not exist", "no available channel for model")
    ):
        return "model_not_found"
    if status_code == 429 or any(
        marker in raw
        for marker in ("rate limit", "too many requests", "overloaded", "busy", "cluster load", "负载较高", "服务繁忙")
    ):
        return "rate_limit"
    if any(marker in raw for marker in ("timeout", "timed out", "readtimeout", "connecttimeout")):
        return "timeout"
    if any(marker in raw for marker in ("dns", "getaddrinfo", "name or service not known", "nodename nor servname", "resolve")):
        return "dns"
    if any(marker in raw for marker in ("connection refused", "network error", "connect error", "connection reset", "network is unreachable")):
        return "network"
    if any(marker in raw for marker in ("invalid response object", "invalid response", "json decode", "malformed", "received_args=", "modelresponse(", "assert response_object")):
        return "invalid_response"
    if any(
        marker in raw
        for marker in (
            "vision is not supported",
            "audio is not supported",
            "unsupported image",
            "unsupported audio",
            "unsupported file",
            "does not support tool",
            "does not support function calling",
        )
    ):
        return "unsupported_capability"
    if status_code is not None and status_code >= 500:
        return "upstream"
    return "generic"


def provider_error_code(kind: str) -> str:
    return {
        "missing_credentials": "PROVIDER_MISSING_CREDENTIALS",
        "auth": "PROVIDER_AUTH_FAILED",
        "model_not_found": "PROVIDER_MODEL_NOT_FOUND",
        "rate_limit": "PROVIDER_RATE_LIMITED",
        "timeout": "PROVIDER_TIMEOUT",
        "dns": "PROVIDER_DNS_FAILED",
        "network": "PROVIDER_NETWORK_FAILED",
        "invalid_response": "PROVIDER_INVALID_RESPONSE",
        "unsupported_capability": "PROVIDER_UNSUPPORTED_CAPABILITY",
        "upstream": "PROVIDER_UPSTREAM_UNAVAILABLE",
        "generic": "PROVIDER_REQUEST_FAILED",
    }.get(kind, "PROVIDER_REQUEST_FAILED")


def provider_error_message(kind: str) -> str:
    return {
        "missing_credentials": "模型服务鉴权失败，请检查配置。",
        "auth": "模型服务鉴权失败，请检查配置。",
        "model_not_found": "当前模型或接口不存在，请检查配置。",
        "rate_limit": "模型服务当前负载较高，请稍后重试。",
        "timeout": "模型服务响应超时，请稍后重试。",
        "dns": "模型服务连接失败，请稍后重试。",
        "network": "模型服务连接失败，请稍后重试。",
        "invalid_response": "模型服务返回异常，请稍后重试。",
        "unsupported_capability": "当前模型不支持本次请求所需能力，请检查模型配置。",
        "upstream": "模型服务暂时不可用，请稍后重试。",
        "generic": "模型服务暂时不可用，请稍后重试。",
    }.get(kind, "模型服务暂时不可用，请稍后重试。")


def provider_remediation(kind: str, *, provider_name: str | None = None, model: str | None = None) -> list[str]:
    provider_label = provider_name or "当前 Provider"
    model_label = model or "当前模型"

    common = {
        "missing_credentials": [
            f"先在 Configuration 或多 Agent 管理里补齐 {provider_label} 的 API Key / API Base，再重新测试。",
        ],
        "auth": [
            f"确认 {provider_label} 的 API Key、Token 或鉴权头没有填错，也没有把测试环境和生产环境的凭据混用。",
        ],
        "model_not_found": [
            f"检查模型名 `{model_label}` 是否存在、大小写是否正确，以及当前 Provider 是否真的提供这个模型。",
        ],
        "rate_limit": [
            "稍后再重试一次；如果持续出现，请降低并发或切换到同 Provider 的其他模型。",
        ],
        "timeout": [
            "先重试一次；如果持续超时，再检查本机网络、代理、VPN 或上游模型服务状态。",
        ],
        "dns": [
            "确认当前机器能解析并访问目标模型服务域名，必要时检查 DNS、代理和公司网络策略。",
        ],
        "network": [
            "检查目标模型服务地址是否可达，以及本机到 Provider API 之间的网络链路是否正常。",
        ],
        "invalid_response": [
            "优先检查是否选错了网关协议、API Base 或模型；如果是兼容层网关，再确认它是否完整兼容 OpenAI Chat Completions。",
        ],
        "unsupported_capability": [
            f"当前请求需要的能力与 `{model_label}` 不匹配。请切换到支持文档、图片、音频或工具调用的模型后再试。",
        ],
        "upstream": [
            "这是上游模型服务异常，通常先等待一段时间后重试；如果持续失败，再检查 Provider 服务状态页。",
        ],
        "generic": [
            "先结合错误类别确认是鉴权、模型名还是网络问题，再决定是否修改 Provider 配置或切换模型。",
        ],
    }
    return common.get(kind, common["generic"])


def is_retryable_provider_failure(kind: str) -> bool:
    return kind in {"rate_limit", "timeout", "dns", "network", "invalid_response", "upstream", "generic"}


def diagnose_provider_error(
    error: Exception | str | None = None,
    *,
    status_code: int | None = None,
    error_text: str | None = None,
    provider_name: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    kind = detect_provider_error_kind(error, status_code=status_code, error_text=error_text)
    return {
        "error_code": provider_error_code(kind),
        "error_kind": kind,
        "message": provider_error_message(kind),
        "remediation": provider_remediation(kind, provider_name=provider_name, model=model),
        "retryable": is_retryable_provider_failure(kind),
        "status_code": status_code,
        "provider": provider_name,
        "model": model,
    }
