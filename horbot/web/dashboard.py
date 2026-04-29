"""Dashboard summary helpers for the web API."""

from __future__ import annotations

from typing import Any

from pydantic.alias_generators import to_camel

from horbot.config.schema import Config

_DASHBOARD_CHANNEL_REQUIRED_FIELDS: dict[str, list[str]] = {
    "whatsapp": ["bridge_url"],
    "telegram": ["token"],
    "discord": ["token"],
    "feishu": ["app_id", "app_secret"],
    "wecom": ["bot_id", "secret"],
    "dingtalk": ["client_id", "client_secret"],
    "email": [
        "consent_granted",
        "imap_host",
        "imap_username",
        "imap_password",
        "smtp_host",
        "smtp_username",
        "smtp_password",
        "from_address",
    ],
    "slack": ["bot_token", "app_token"],
    "qq": ["app_id", "secret"],
    "matrix": ["homeserver", "access_token", "user_id"],
    "mochat": ["claw_token", "agent_user_id"],
    "sharecrm": ["app_id", "app_secret"],
}

_DASHBOARD_CHANNEL_DISPLAY_NAMES: dict[str, str] = {
    "qq": "QQ",
    "mochat": "Mochat",
    "sharecrm": "ShareCRM",
    "dingtalk": "DingTalk",
    "feishu": "Feishu",
    "wecom": "WeCom",
}


def _is_channel_configured(channel_name: str, channel_config: dict[str, Any]) -> tuple[bool, list[str]]:
    required_fields = _DASHBOARD_CHANNEL_REQUIRED_FIELDS.get(channel_name, [])
    missing_fields: list[str] = []

    for field in required_fields:
        value = channel_config.get(field)
        if field not in channel_config:
            value = channel_config.get(to_camel(field))
        if isinstance(value, bool):
            if not value:
                missing_fields.append(field)
        elif value in (None, "", []):
            missing_fields.append(field)

    return len(missing_fields) == 0, missing_fields


def _build_dashboard_channel_summary(config: Config) -> dict[str, Any]:
    raw_channels = config.channels.model_dump(by_alias=True)
    items: list[dict[str, Any]] = []
    counts = {
        "total": 0,
        "enabled": 0,
        "online": 0,
        "disabled": 0,
        "misconfigured": 0,
    }

    for channel_name, channel_config in raw_channels.items():
        if not isinstance(channel_config, dict) or "enabled" not in channel_config:
            continue

        enabled = bool(channel_config.get("enabled"))
        configured, missing_fields = _is_channel_configured(channel_name, channel_config)

        if not enabled:
            status = "disabled"
            status_label = "已禁用"
            reason = "当前通道未启用"
            counts["disabled"] += 1
        elif configured:
            status = "online"
            status_label = "就绪"
            reason = None
            counts["online"] += 1
        else:
            status = "error"
            status_label = "配置缺失"
            reason = f"缺少配置: {', '.join(missing_fields)}"
            counts["misconfigured"] += 1

        if enabled:
            counts["enabled"] += 1
        counts["total"] += 1

        items.append({
            "name": channel_name,
            "display_name": _DASHBOARD_CHANNEL_DISPLAY_NAMES.get(channel_name, channel_name.capitalize()),
            "enabled": enabled,
            "configured": configured,
            "status": status,
            "status_label": status_label,
            "reason": reason,
            "missing_fields": missing_fields,
        })

    items.sort(key=lambda item: (0 if item["status"] == "online" else 1 if item["status"] == "error" else 2, item["display_name"]))

    return {
        "items": items,
        "counts": counts,
    }


def _build_dashboard_alerts(config: Config, system_status: dict[str, Any], channel_summary: dict[str, Any]) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []

    provider_name = config.get_provider_name()
    provider_configured = False
    if provider_name:
        try:
            provider = config.get_provider()
            provider_configured = bool(provider and getattr(provider, "api_key", None))
        except Exception:
            provider_configured = False

    if not provider_name:
        alerts.append({
            "id": "provider-missing",
            "level": "warning",
            "title": "未配置模型提供商",
            "message": "当前还没有可用的 AI provider，聊天和诊断能力会受限。",
        })
    elif not provider_configured:
        alerts.append({
            "id": "provider-key-missing",
            "level": "warning",
            "title": "Provider 缺少 API Key",
            "message": f"已选择 {provider_name}，但认证信息不完整。",
        })

    if channel_summary["counts"]["misconfigured"] > 0:
        alerts.append({
            "id": "channel-misconfigured",
            "level": "warning",
            "title": "存在配置不完整的通道",
            "message": f"{channel_summary['counts']['misconfigured']} 个已启用通道缺少必要配置。",
        })

    if not system_status["services"]["agent"]["initialized"]:
        alerts.append({
            "id": "agent-not-ready",
            "level": "warning",
            "title": "Agent Loop 尚未初始化",
            "message": "当前尚未检测到可用的 agent loop，首次请求前部分能力可能未完全预热。",
        })

    if system_status["system"]["memory"]["percent"] >= 85:
        alerts.append({
            "id": "memory-high",
            "level": "error",
            "title": "内存占用较高",
            "message": f"当前内存占用 {round(system_status['system']['memory']['percent'])}%，建议关注长时间运行任务。",
        })

    if system_status["system"]["disk"]["percent"] >= 90:
        alerts.append({
            "id": "disk-high",
            "level": "error",
            "title": "磁盘空间不足",
            "message": f"当前磁盘占用 {round(system_status['system']['disk']['percent'])}%，可能影响日志和会话写入。",
        })

    return alerts


def _build_dashboard_activities(
    system_status: dict[str, Any],
    channel_summary: dict[str, Any],
    alerts: list[dict[str, str]],
) -> list[dict[str, str]]:
    activities: list[dict[str, str]] = []

    if system_status["status"] == "running":
        activities.append({
            "id": "system-running",
            "type": "system",
            "message": "控制面板摘要已成功加载",
            "time": "刚刚",
            "status": "success",
        })

    if system_status["services"]["agent"]["initialized"]:
        activities.append({
            "id": "agent-ready",
            "type": "agent",
            "message": "Agent loop 已初始化",
            "time": "当前",
            "status": "success",
        })

    if system_status["services"]["cron"]["enabled"]:
        activities.append({
            "id": "cron-running",
            "type": "task",
            "message": f"{system_status['services']['cron']['jobs_count']} 个定时任务处于启用状态",
            "time": "持续中",
            "status": "info",
        })

    if channel_summary["counts"]["enabled"] > 0:
        activities.append({
            "id": "channels-enabled",
            "type": "channel",
            "message": (
                f"{channel_summary['counts']['enabled']} 个通道已启用，"
                f"{channel_summary['counts']['online']} 个配置完整"
            ),
            "time": "当前",
            "status": "success" if channel_summary["counts"]["misconfigured"] == 0 else "warning",
        })

    if alerts:
        first_alert = alerts[0]
        activities.append({
            "id": f"alert-{first_alert['id']}",
            "type": "system",
            "message": first_alert["title"],
            "time": "当前",
            "status": first_alert["level"],
        })

    return activities[:6]
