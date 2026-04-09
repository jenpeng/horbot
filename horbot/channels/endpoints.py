"""Helpers for channel endpoint configuration and legacy compatibility."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from horbot.config.schema import (
    ChannelEndpointConfig,
    ChannelsConfig,
    Config,
    DingTalkConfig,
    DiscordConfig,
    EmailConfig,
    FeishuConfig,
    MatrixConfig,
    MochatConfig,
    QQConfig,
    ShareCrmConfig,
    SlackConfig,
    TelegramConfig,
    WhatsAppConfig,
)

CHANNEL_TYPE_MODELS = {
    "whatsapp": WhatsAppConfig,
    "telegram": TelegramConfig,
    "discord": DiscordConfig,
    "feishu": FeishuConfig,
    "mochat": MochatConfig,
    "dingtalk": DingTalkConfig,
    "email": EmailConfig,
    "slack": SlackConfig,
    "qq": QQConfig,
    "matrix": MatrixConfig,
    "sharecrm": ShareCrmConfig,
}

CHANNEL_CATALOG: dict[str, dict[str, Any]] = {
    "telegram": {
        "label": "Telegram",
        "description": "使用 Bot Token 对接 Telegram 机器人。",
        "required_fields": ["token"],
        "fields": [
            {"key": "token", "label": "Bot Token", "secret": True, "placeholder": "123456:ABC..."},
            {"key": "proxy", "label": "代理", "placeholder": "http://127.0.0.1:7890"},
            {"key": "reply_to_message", "label": "回复时引用原消息", "type": "boolean"},
        ],
    },
    "feishu": {
        "label": "飞书",
        "description": "使用 App ID / App Secret 对接飞书账号。",
        "required_fields": ["app_id", "app_secret"],
        "fields": [
            {"key": "app_id", "label": "App ID", "placeholder": "cli_xxx"},
            {"key": "app_secret", "label": "App Secret", "secret": True},
            {"key": "encrypt_key", "label": "Encrypt Key", "secret": True},
            {"key": "verification_token", "label": "Verification Token", "secret": True},
            {"key": "skip_ssl_verify", "label": "跳过 SSL 校验", "type": "boolean"},
        ],
    },
    "discord": {
        "label": "Discord",
        "description": "使用 Bot Token 对接 Discord 服务器。",
        "required_fields": ["token"],
        "fields": [
            {"key": "token", "label": "Bot Token", "secret": True},
            {"key": "gateway_url", "label": "Gateway URL"},
            {"key": "intents", "label": "Intents", "type": "number"},
        ],
    },
    "whatsapp": {
        "label": "WhatsApp",
        "description": "通过 bridge 服务对接 WhatsApp。",
        "required_fields": ["bridge_url"],
        "fields": [
            {"key": "bridge_url", "label": "Bridge URL", "placeholder": "ws://localhost:3001"},
            {"key": "bridge_token", "label": "Bridge Token", "secret": True},
        ],
    },
    "dingtalk": {
        "label": "钉钉",
        "description": "使用 Stream 模式对接钉钉机器人。",
        "required_fields": ["client_id", "client_secret"],
        "fields": [
            {"key": "client_id", "label": "Client ID"},
            {"key": "client_secret", "label": "Client Secret", "secret": True},
        ],
    },
    "slack": {
        "label": "Slack",
        "description": "使用 Bot Token 与 App Token 对接 Slack。",
        "required_fields": ["bot_token", "app_token"],
        "fields": [
            {"key": "bot_token", "label": "Bot Token", "secret": True},
            {"key": "app_token", "label": "App Token", "secret": True},
            {"key": "mode", "label": "模式"},
            {"key": "reply_in_thread", "label": "在线程回复", "type": "boolean"},
        ],
    },
    "email": {
        "label": "Email",
        "description": "通过 IMAP/SMTP 对接邮箱。",
        "required_fields": ["imap_host", "imap_username", "imap_password", "smtp_host", "smtp_username", "smtp_password", "from_address"],
        "fields": [
            {"key": "imap_host", "label": "IMAP Host"},
            {"key": "imap_port", "label": "IMAP Port", "type": "number"},
            {"key": "imap_username", "label": "IMAP 用户名"},
            {"key": "imap_password", "label": "IMAP 密码", "secret": True},
            {"key": "smtp_host", "label": "SMTP Host"},
            {"key": "smtp_port", "label": "SMTP Port", "type": "number"},
            {"key": "smtp_username", "label": "SMTP 用户名"},
            {"key": "smtp_password", "label": "SMTP 密码", "secret": True},
            {"key": "from_address", "label": "发件地址"},
            {"key": "auto_reply_enabled", "label": "自动回复", "type": "boolean"},
        ],
    },
    "qq": {
        "label": "QQ",
        "description": "使用 QQ 机器人 AppID 与密钥接入。",
        "required_fields": ["app_id", "secret"],
        "fields": [
            {"key": "app_id", "label": "App ID"},
            {"key": "secret", "label": "Secret", "secret": True},
        ],
    },
    "matrix": {
        "label": "Matrix",
        "description": "接入 Matrix / Element 房间与私聊。",
        "required_fields": ["homeserver", "access_token", "user_id"],
        "fields": [
            {"key": "homeserver", "label": "Homeserver"},
            {"key": "access_token", "label": "Access Token", "secret": True},
            {"key": "user_id", "label": "User ID"},
            {"key": "device_id", "label": "Device ID"},
            {"key": "e2ee_enabled", "label": "启用 E2EE", "type": "boolean"},
        ],
    },
    "mochat": {
        "label": "Mochat",
        "description": "接入 Mochat 企业微信生态账号。",
        "required_fields": ["base_url", "claw_token", "agent_user_id"],
        "fields": [
            {"key": "base_url", "label": "Base URL"},
            {"key": "socket_url", "label": "Socket URL"},
            {"key": "claw_token", "label": "Claw Token", "secret": True},
            {"key": "agent_user_id", "label": "Agent User ID"},
        ],
    },
    "sharecrm": {
        "label": "ShareCRM",
        "description": "接入纷享销客 IM Gateway。",
        "required_fields": ["app_id", "app_secret"],
        "fields": [
            {"key": "gateway_base_url", "label": "Gateway Base URL"},
            {"key": "app_id", "label": "App ID"},
            {"key": "app_secret", "label": "App Secret", "secret": True},
            {"key": "dm_policy", "label": "私聊策略"},
            {"key": "group_policy", "label": "群聊策略"},
        ],
    },
}


@dataclass
class ResolvedChannelEndpoint:
    id: str
    type: str
    name: str
    enabled: bool
    agent_id: str
    allow_from: list[str]
    config: dict[str, Any]
    source: str
    missing_fields: list[str]
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def legacy_endpoint_id(channel_type: str) -> str:
    """Stable synthetic identifier for a legacy global channel config."""
    return f"legacy:{channel_type}"


def get_default_agent_id(config: Config) -> str:
    """Pick the first configured agent as the default external-channel target."""
    return next(iter(config.agents.instances.keys()), "")


def get_channel_catalog() -> list[dict[str, Any]]:
    """Return channel catalog metadata for the frontend."""
    result: list[dict[str, Any]] = []
    for channel_type in CHANNEL_TYPE_MODELS:
        meta = CHANNEL_CATALOG.get(channel_type, {})
        result.append({
            "type": channel_type,
            "label": meta.get("label", channel_type.title()),
            "description": meta.get("description", ""),
            "required_fields": list(meta.get("required_fields", [])),
            "fields": list(meta.get("fields", [])),
        })
    return result


def _get_bound_agent_id(config: Config, endpoint_id: str, fallback: str = "") -> str:
    for agent_id, agent in config.agents.instances.items():
        bindings = getattr(agent, "channel_bindings", []) or []
        if endpoint_id in bindings:
            return agent_id
    return fallback


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    return False


def _get_endpoint_missing_fields(channel_type: str, values: dict[str, Any]) -> list[str]:
    required_fields = CHANNEL_CATALOG.get(channel_type, {}).get("required_fields", [])
    return [field for field in required_fields if _is_blank(values.get(field))]


def _get_endpoint_status(enabled: bool, missing_fields: list[str]) -> str:
    if not enabled:
        return "disabled"
    if missing_fields:
        return "incomplete"
    return "ready"


def _has_legacy_channel_payload(channel_type: str, channel_config: Any) -> bool:
    defaults = CHANNEL_TYPE_MODELS[channel_type]()
    current = channel_config.model_dump()
    baseline = defaults.model_dump()
    if current.get("enabled"):
        return True
    for key, value in current.items():
        if key == "enabled":
            continue
        if value != baseline.get(key):
            return True
    return False


def build_legacy_endpoint(config: Config, channel_type: str) -> ResolvedChannelEndpoint | None:
    """Project a legacy global channel config into endpoint view data."""
    if channel_type not in CHANNEL_TYPE_MODELS:
        return None
    channel_config = getattr(config.channels, channel_type)
    if not _has_legacy_channel_payload(channel_type, channel_config):
        return None
    values = channel_config.model_dump()
    allow_from = list(values.pop("allow_from", []) or [])
    enabled = bool(values.pop("enabled", False))
    endpoint_id = legacy_endpoint_id(channel_type)
    agent_id = _get_bound_agent_id(config, endpoint_id, fallback=get_default_agent_id(config))
    missing_fields = _get_endpoint_missing_fields(channel_type, values)
    return ResolvedChannelEndpoint(
        id=endpoint_id,
        type=channel_type,
        name=CHANNEL_CATALOG.get(channel_type, {}).get("label", channel_type.title()),
        enabled=enabled,
        agent_id=agent_id,
        allow_from=allow_from,
        config=values,
        source="legacy",
        missing_fields=missing_fields,
        status=_get_endpoint_status(enabled, missing_fields),
    )


def build_custom_endpoint(config: Config, endpoint: ChannelEndpointConfig) -> ResolvedChannelEndpoint:
    """Convert stored endpoint config into view/runtime data."""
    channel_type = endpoint.type.strip().lower()
    endpoint_id = endpoint.id.strip()
    values = dict(endpoint.config or {})
    allow_from = list(endpoint.allow_from or [])
    agent_id = endpoint.agent_id.strip() or _get_bound_agent_id(config, endpoint_id)
    missing_fields = _get_endpoint_missing_fields(channel_type, values)
    display_name = endpoint.name.strip() or CHANNEL_CATALOG.get(channel_type, {}).get("label", channel_type.title())
    return ResolvedChannelEndpoint(
        id=endpoint_id,
        type=channel_type,
        name=display_name,
        enabled=bool(endpoint.enabled),
        agent_id=agent_id,
        allow_from=allow_from,
        config=values,
        source="custom",
        missing_fields=missing_fields,
        status=_get_endpoint_status(bool(endpoint.enabled), missing_fields),
    )


def list_channel_endpoints(config: Config) -> list[ResolvedChannelEndpoint]:
    """Return the merged list of custom endpoints and compatible legacy endpoints."""
    endpoints: list[ResolvedChannelEndpoint] = []

    for endpoint in config.channels.endpoints:
        channel_type = endpoint.type.strip().lower()
        endpoint_id = endpoint.id.strip()
        if not endpoint_id or channel_type not in CHANNEL_TYPE_MODELS:
            continue
        endpoints.append(build_custom_endpoint(config, endpoint))

    for channel_type in CHANNEL_TYPE_MODELS:
        legacy_endpoint = build_legacy_endpoint(config, channel_type)
        if legacy_endpoint is not None:
            endpoints.append(legacy_endpoint)

    endpoints.sort(key=lambda item: (item.type, item.source != "legacy", item.name.lower(), item.id))
    return endpoints


def find_channel_endpoint(config: Config, endpoint_id: str) -> ResolvedChannelEndpoint | None:
    """Find either a custom or projected legacy endpoint by identifier."""
    for endpoint in list_channel_endpoints(config):
        if endpoint.id == endpoint_id:
            return endpoint
    return None


def build_runtime_channel_config(channels: ChannelsConfig, endpoint: ResolvedChannelEndpoint) -> Any:
    """Merge endpoint values into the typed runtime config for a channel implementation."""
    model_cls = CHANNEL_TYPE_MODELS[endpoint.type]
    base_config = getattr(channels, endpoint.type)
    payload = base_config.model_dump()
    payload["enabled"] = endpoint.enabled
    payload["allow_from"] = list(endpoint.allow_from)
    payload.update(endpoint.config or {})
    return model_cls.model_validate(payload)
