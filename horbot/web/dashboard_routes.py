"""Dashboard API routes."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from fastapi import APIRouter

from horbot.web.dashboard import (
    _build_dashboard_activities,
    _build_dashboard_alerts,
    _build_dashboard_channel_summary,
)


def create_dashboard_router(
    get_config: Callable[[], Any],
    build_system_status_payload: Callable[[Any], dict[str, Any]],
) -> APIRouter:
    """Create dashboard routes."""

    router = APIRouter()

    @router.get("/dashboard/summary")
    async def get_dashboard_summary():
        """Return a lightweight dashboard summary optimized for the home page."""
        config = get_config()
        system_status = build_system_status_payload(config)
        channel_summary = _build_dashboard_channel_summary(config)
        alerts = _build_dashboard_alerts(config, system_status, channel_summary)

        provider_name = config.get_provider_name()
        provider_configured = False
        if provider_name:
            try:
                provider = config.get_provider()
                provider_configured = bool(provider and getattr(provider, "api_key", None))
            except Exception:
                provider_configured = False

        return {
            "generated_at": datetime.now().isoformat(),
            "system_status": system_status,
            "provider": {
                "name": provider_name,
                "configured": provider_configured,
            },
            "channels": channel_summary,
            "recent_activities": _build_dashboard_activities(system_status, channel_summary, alerts),
            "alerts": alerts,
        }

    return router
