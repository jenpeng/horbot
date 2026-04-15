"""Base helpers for external third-party agent adapters."""

from __future__ import annotations

from horbot.config.schema import ExternalAgentConfig


def build_auth_headers(config: ExternalAgentConfig) -> dict[str, str]:
    """Build outbound auth headers for an external agent probe/call."""

    if config.auth_type == "none" or not config.auth_secret:
        return {}

    header_name = (config.auth_header or "Authorization").strip() or "Authorization"
    if config.auth_type == "bearer":
        return {header_name: f"Bearer {config.auth_secret}"}
    return {header_name: config.auth_secret}
