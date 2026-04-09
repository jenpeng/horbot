"""User-facing error message normalization."""

from __future__ import annotations

from horbot.providers.diagnostics import diagnose_provider_error


FRIENDLY_PROVIDER_ERROR_MESSAGES = frozenset(
    {
        "模型服务鉴权失败，请检查配置。",
        "当前模型或接口不存在，请检查配置。",
        "模型服务当前负载较高，请稍后重试。",
        "模型服务响应超时，请稍后重试。",
        "模型服务连接失败，请稍后重试。",
        "模型服务返回异常，请稍后重试。",
        "当前模型不支持本次请求所需能力，请检查模型配置。",
        "模型服务暂时不可用，请稍后重试。",
    }
)


def friendly_provider_error_message(
    error: Exception | None = None,
    *,
    status_code: int | None = None,
    error_text: str | None = None,
) -> str:
    """Return a provider-safe error message without exposing raw backend details."""
    raw_text = " ".join(
        part for part in (str(error or ""), error_text or "", str(status_code or "")) if part
    ).strip()
    if raw_text in FRIENDLY_PROVIDER_ERROR_MESSAGES:
        return raw_text
    return str(
        diagnose_provider_error(
            error,
            status_code=status_code,
            error_text=error_text,
        )["message"]
    )


def public_error_message(
    error: Exception | str | None = None,
    *,
    status_code: int | None = None,
    error_text: str | None = None,
    default_message: str = "服务处理失败，请稍后重试。",
) -> str:
    """Return a client-safe message for arbitrary backend errors."""
    provider_message = friendly_provider_error_message(
        error if isinstance(error, Exception) else None,
        status_code=status_code,
        error_text=error_text if error_text is not None else (error if isinstance(error, str) else None),
    )
    if provider_message != "模型服务暂时不可用，请稍后重试。":
        return provider_message
    return default_message if error is None and error_text is None and status_code is None else provider_message


def is_retryable_provider_error(
    error: Exception | str | None = None,
    *,
    status_code: int | None = None,
    error_text: str | None = None,
) -> bool:
    """Return True when retrying the provider request is usually safe."""
    return bool(
        diagnose_provider_error(
            error,
            status_code=status_code,
            error_text=error_text,
        )["retryable"]
    )
