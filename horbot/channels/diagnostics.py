"""Endpoint-level diagnostics helpers for chat channels."""

from __future__ import annotations

import time
from typing import Any

import httpx


def _normalize_error(value: str | None) -> str:
    return str(value or "").strip().lower()


def _detect_error_kind(error: str | None) -> str:
    raw_error = _normalize_error(error)
    if not raw_error:
        return "generic"

    if (
        "not configured" in raw_error
        or "missing" in raw_error
        or "required" in raw_error
        or "empty" in raw_error
    ):
        return "missing"

    if (
        "401" in raw_error
        or "invalid token" in raw_error
        or "invalid access token" in raw_error
        or "invalid_auth" in raw_error
        or "authentication failed" in raw_error
        or "login failed" in raw_error
        or "app id or secret" in raw_error
        or "client id or secret" in raw_error
        or "bot token" in raw_error
        or "app token" in raw_error
        or "secret" in raw_error
    ):
        return "credential"

    if (
        "403" in raw_error
        or "forbidden" in raw_error
        or "permission" in raw_error
        or "scope" in raw_error
        or "not allowed" in raw_error
        or "insufficient" in raw_error
        or "no authority" in raw_error
    ):
        return "permission"

    if "timeout" in raw_error or "timed out" in raw_error:
        return "timeout"

    if (
        "resolve" in raw_error
        or "name or service not known" in raw_error
        or "nodename nor servname" in raw_error
        or "dns" in raw_error
        or "getaddrinfo" in raw_error
    ):
        return "dns"

    if "ssl" in raw_error or "certificate" in raw_error or "tls" in raw_error:
        return "ssl"

    if "429" in raw_error or "rate limit" in raw_error or "too many requests" in raw_error:
        return "rate_limit"

    if (
        "connection refused" in raw_error
        or "connecterror" in raw_error
        or "network is unreachable" in raw_error
        or "connection reset" in raw_error
    ):
        return "network"

    return "generic"


def _error_code_for_kind(kind: str) -> str:
    mapping = {
        "missing": "MISSING_REQUIRED_CONFIG",
        "credential": "INVALID_CREDENTIALS",
        "permission": "INSUFFICIENT_PERMISSIONS",
        "timeout": "NETWORK_TIMEOUT",
        "dns": "DNS_RESOLUTION_FAILED",
        "ssl": "SSL_VERIFICATION_FAILED",
        "rate_limit": "RATE_LIMITED",
        "network": "NETWORK_CONNECT_FAILED",
        "generic": "CHANNEL_TEST_FAILED",
    }
    return mapping.get(kind, "CHANNEL_TEST_FAILED")


def _generic_remediation(kind: str) -> list[str]:
    mapping = {
        "missing": [
            "先补齐当前通道的必填字段，再重新测试，避免被无效错误干扰排查。",
        ],
        "credential": [
            "确认当前密钥、Token、App Secret 没有填错，也没有把测试环境和生产环境的凭据混用。",
        ],
        "permission": [
            "去对应平台后台检查应用权限、scope、事件订阅或机器人能力配置是否完整。",
        ],
        "timeout": [
            "先重新测试一次；如果连续超时，再排查本机网络、代理、VPN 或平台服务可用性。",
        ],
        "dns": [
            "确认当前机器能解析并访问目标平台域名，必要时检查 DNS、代理和公司网络策略。",
        ],
        "ssl": [
            "检查当前网络是否存在企业代理、自签证书或 HTTPS 检查设备导致的证书校验失败。",
        ],
        "rate_limit": [
            "先间隔一段时间再重试，避免短时间连续调用触发平台频控。",
        ],
        "network": [
            "优先检查目标地址是否可达、服务是否在线，以及本机到平台之间的网络链路是否正常。",
        ],
        "generic": [
            "先根据原始错误定位是凭据、权限还是网络问题，再决定是否保存该通道实例。",
        ],
    }
    return mapping.get(kind, mapping["generic"])


def _channel_specific_remediation(channel_type: str, kind: str) -> list[str]:
    if channel_type == "feishu":
        if kind == "missing":
            return [
                "至少补齐 App ID 和 App Secret；如果启用了事件订阅，再检查 Encrypt Key 和 Verification Token 是否与飞书后台一致。",
                "如果这是企业内网环境，确认是否需要启用“跳过 SSL 校验”来绕过公司代理证书。",
            ]
        if kind == "credential":
            return [
                "去飞书开放平台“凭证与基础信息”核对 App ID、App Secret 是否来自同一个应用。",
                "如果最近在飞书后台重置过密钥，记得同步更新这里的配置后再测试。",
            ]
        if kind == "permission":
            return [
                "去飞书开放平台检查应用权限、机器人能力和事件订阅是否已开启，尤其是消息接收和群聊相关权限。",
            ]
        if kind == "ssl":
            return [
                "如果网络经过公司代理或 HTTPS 检查设备，先确认代理证书可信；仅在受信任内网中临时启用“跳过 SSL 校验”。",
            ]
        return [
            "如果凭据看起来没问题，再去飞书开放平台查看最近调用日志和应用可用性。",
        ]

    if channel_type == "sharecrm":
        if kind == "missing":
            return [
                "至少补齐 App ID 和 App Secret；如果不是默认环境，还要核对 Gateway Base URL。",
            ]
        if kind in {"credential", "permission"}:
            return [
                "去纷享销客 IM Gateway / 开放平台检查 bot 的 App ID、App Secret 是否已启用且未过期。",
                "确认该机器人具备获取 token、接收会话和发送消息所需权限。",
            ]
        return [
            "如果报网关类错误，优先核对 Gateway Base URL 是否指向正确环境，再检查平台侧服务状态。",
        ]

    if channel_type == "telegram":
        if kind in {"missing", "credential"}:
            return [
                "直接调用 `https://api.telegram.org/bot<TOKEN>/getMe`，先独立验证这枚 Bot Token 是否有效。",
                "如果 BotFather 刚重新生成过 token，需要把旧 token 全部替换掉。",
            ]
        return [
            "如果网络受限，优先检查代理是否可用，以及 Telegram API 是否被当前网络出口拦截。",
        ]

    if channel_type == "slack":
        if kind in {"missing", "credential"}:
            return [
                "去 Slack App 后台核对 Bot Token 和 App Token 是否来自同一个应用和同一个 workspace。",
            ]
        if kind == "permission":
            return [
                "去 Slack App 后台检查 OAuth scopes、Event Subscriptions 和 Socket Mode 是否已开启。",
            ]
        return [
            "如果 `auth.test` 能通过但真实收发不通，通常是 scope 或事件订阅没有配齐。",
        ]

    if channel_type == "discord":
        if kind in {"missing", "credential"}:
            return [
                "去 Discord Developer Portal 检查 Bot Token 是否被重置；重置后旧 token 会立即失效。",
            ]
        if kind == "permission":
            return [
                "检查 Privileged Gateway Intents，尤其是 Message Content Intent 是否已开启。",
                "再确认目标服务器里机器人的角色具备读取频道和发送消息权限。",
            ]
        return [
            "如果连接能通过但收不到消息，优先排查 intents 和服务器角色权限。",
        ]

    if channel_type == "email":
        if kind == "missing":
            return [
                "IMAP/SMTP 主机、账号、密码和发件地址需要成套配置，缺一项都会失败。",
            ]
        if kind == "credential":
            return [
                "很多邮箱不能直接使用登录密码，而必须使用 IMAP/SMTP 授权码。",
                "去邮箱后台确认已开启 IMAP/SMTP，并生成新的授权码后再测试。",
            ]
        if kind == "ssl":
            return [
                "检查 IMAP/SMTP 的端口和 SSL/TLS 组合是否匹配，例如 IMAP 993 + SSL、SMTP 587 + STARTTLS。",
            ]
        return [
            "如果是企业邮箱，再检查是否存在 IP 白名单、异地登录限制或安全策略拦截。",
        ]

    if channel_type == "dingtalk":
        if kind in {"missing", "credential"}:
            return [
                "去钉钉开放平台核对 Client ID / Client Secret，确认当前应用已开通 Stream 模式。",
            ]
        if kind == "permission":
            return [
                "检查钉钉机器人消息接收、会话访问等权限是否已授权给当前应用。",
            ]

    if channel_type == "matrix":
        if kind in {"missing", "credential"}:
            return [
                "先用当前 homeserver 调 `/_matrix/client/v3/account/whoami` 验证 access token 是否有效。",
            ]
        return [
            "如果是自建 homeserver，优先检查地址路径、反向代理和证书配置。",
        ]

    if channel_type == "mochat":
        if kind in {"missing", "credential"}:
            return [
                "核对 Mochat Base URL、Claw Token 和 Agent User ID 是否对应同一个环境实例。",
            ]
        return [
            "如果 `/api/health` 都打不通，先检查 Mochat 服务本身是否在线。",
        ]

    if channel_type == "qq":
        if kind in {"missing", "credential"}:
            return [
                "去 QQ 开放平台核对 App ID 和 Secret，确认机器人应用已启用并且密钥未失效。",
            ]

    if channel_type == "whatsapp":
        if kind in {"missing", "credential"}:
            return [
                "如果 bridge 开启了鉴权，确认这里的 Bridge Token 与桥接服务配置一致。",
            ]
        return [
            "先直接访问 bridge 的 `/health` 接口确认桥接服务在线，再检查账号侧会话是否已建立。",
        ]

    return []


def _build_error_result(
    channel_type: str,
    *,
    enabled: bool,
    latency_ms: int,
    error: str,
    error_code: str | None = None,
    error_kind: str | None = None,
) -> dict[str, Any]:
    kind = error_kind or _detect_error_kind(error)
    code = error_code or _error_code_for_kind(kind)
    remediation = [
        *_generic_remediation(kind),
        *_channel_specific_remediation(channel_type, kind),
    ]
    deduped_remediation: list[str] = []
    for item in remediation:
        if item and item not in deduped_remediation:
            deduped_remediation.append(item)
    return _result(
        channel_type,
        enabled,
        "error",
        latency_ms,
        error,
        error_code=code,
        error_kind=kind,
        remediation=deduped_remediation,
    )


async def test_channel_connection(channel_type: str, channel_config: Any) -> dict[str, Any]:
    """Run a lightweight connection test for one typed channel config."""
    channel_type = str(channel_type or "").strip().lower()

    if channel_type == "telegram":
        if not channel_config.token:
            return _build_error_result(channel_type, enabled=False, latency_ms=0, error="Token not configured")
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"https://api.telegram.org/bot{channel_config.token}/getMe",
                    proxy=channel_config.proxy,
                )
            latency = int((time.time() - start) * 1000)
            if response.status_code == 200 and response.json().get("ok"):
                return _result(channel_type, True, "ok", latency, None)
            return _build_error_result(
                channel_type,
                enabled=True,
                latency_ms=latency,
                error=response.json().get("description") or f"HTTP {response.status_code}",
            )
        except Exception as exc:
            return _build_error_result(channel_type, enabled=True, latency_ms=0, error=str(exc))

    if channel_type == "discord":
        if not channel_config.token:
            return _build_error_result(channel_type, enabled=False, latency_ms=0, error="Token not configured")
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://discord.com/api/v10/users/@me",
                    headers={"Authorization": f"Bot {channel_config.token}"},
                )
            latency = int((time.time() - start) * 1000)
            if response.status_code == 200:
                return _result(channel_type, True, "ok", latency, None)
            if response.status_code == 401:
                return _build_error_result(
                    channel_type,
                    enabled=True,
                    latency_ms=latency,
                    error="Invalid token",
                    error_code="INVALID_CREDENTIALS",
                    error_kind="credential",
                )
            return _build_error_result(channel_type, enabled=True, latency_ms=latency, error=f"HTTP {response.status_code}")
        except Exception as exc:
            return _build_error_result(channel_type, enabled=True, latency_ms=0, error=str(exc))

    if channel_type == "whatsapp":
        start = time.time()
        try:
            bridge_url = channel_config.bridge_url.replace("ws://", "http://").replace("wss://", "https://")
            headers = {}
            if channel_config.bridge_token:
                headers["Authorization"] = f"Bearer {channel_config.bridge_token}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{bridge_url}/health", headers=headers)
            latency = int((time.time() - start) * 1000)
            if response.status_code == 200:
                return _result(channel_type, True, "ok", latency, None)
            return _build_error_result(channel_type, enabled=True, latency_ms=latency, error=f"HTTP {response.status_code}")
        except Exception as exc:
            return _build_error_result(channel_type, enabled=True, latency_ms=0, error=str(exc))

    if channel_type == "feishu":
        if not channel_config.app_id or not channel_config.app_secret:
            return _build_error_result(channel_type, enabled=False, latency_ms=0, error="App ID or Secret not configured")
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0, verify=not channel_config.skip_ssl_verify) as client:
                response = await client.post(
                    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                    json={"app_id": channel_config.app_id, "app_secret": channel_config.app_secret},
                )
            latency = int((time.time() - start) * 1000)
            if response.status_code == 200 and response.json().get("code") == 0:
                return _result(channel_type, True, "ok", latency, None)
            return _build_error_result(
                channel_type,
                enabled=True,
                latency_ms=latency,
                error=response.json().get("msg") or f"HTTP {response.status_code}",
            )
        except Exception as exc:
            return _build_error_result(channel_type, enabled=True, latency_ms=0, error=str(exc))

    if channel_type == "dingtalk":
        if not channel_config.client_id or not channel_config.client_secret:
            return _build_error_result(channel_type, enabled=False, latency_ms=0, error="Client ID or Secret not configured")
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://api.dingtalk.com/v1.0/oauth2/accessToken",
                    json={"appKey": channel_config.client_id, "appSecret": channel_config.client_secret},
                )
            latency = int((time.time() - start) * 1000)
            if response.status_code == 200 and "accessToken" in response.json():
                return _result(channel_type, True, "ok", latency, None)
            return _build_error_result(
                channel_type,
                enabled=True,
                latency_ms=latency,
                error=response.json().get("message") or f"HTTP {response.status_code}",
            )
        except Exception as exc:
            return _build_error_result(channel_type, enabled=True, latency_ms=0, error=str(exc))

    if channel_type == "slack":
        if not channel_config.bot_token:
            return _build_error_result(channel_type, enabled=False, latency_ms=0, error="Bot token not configured")
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://slack.com/api/auth.test",
                    headers={"Authorization": f"Bearer {channel_config.bot_token}"},
                )
            latency = int((time.time() - start) * 1000)
            data = response.json() if response.content else {}
            if response.status_code == 200 and data.get("ok"):
                return _result(channel_type, True, "ok", latency, None)
            return _build_error_result(
                channel_type,
                enabled=True,
                latency_ms=latency,
                error=data.get("error") or f"HTTP {response.status_code}",
            )
        except Exception as exc:
            return _build_error_result(channel_type, enabled=True, latency_ms=0, error=str(exc))

    if channel_type == "email":
        if not channel_config.imap_host or not channel_config.imap_username:
            return _build_error_result(channel_type, enabled=False, latency_ms=0, error="IMAP host or username not configured")
        start = time.time()
        try:
            import imaplib

            if channel_config.imap_use_ssl:
                imap = imaplib.IMAP4_SSL(channel_config.imap_host, channel_config.imap_port, timeout=10)
            else:
                imap = imaplib.IMAP4(channel_config.imap_host, channel_config.imap_port)
                imap.starttls()
            imap.login(channel_config.imap_username, channel_config.imap_password)
            latency = int((time.time() - start) * 1000)
            imap.logout()
            return _result(channel_type, True, "ok", latency, None)
        except Exception as exc:
            return _build_error_result(channel_type, enabled=True, latency_ms=0, error=str(exc))

    if channel_type == "matrix":
        if not channel_config.access_token or not channel_config.homeserver:
            return _build_error_result(channel_type, enabled=False, latency_ms=0, error="Access token or homeserver not configured")
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{channel_config.homeserver}/_matrix/client/v3/account/whoami",
                    headers={"Authorization": f"Bearer {channel_config.access_token}"},
                )
            latency = int((time.time() - start) * 1000)
            if response.status_code == 200 and "user_id" in response.json():
                return _result(channel_type, True, "ok", latency, None)
            if response.status_code == 401:
                return _build_error_result(
                    channel_type,
                    enabled=True,
                    latency_ms=latency,
                    error="Invalid access token",
                    error_code="INVALID_CREDENTIALS",
                    error_kind="credential",
                )
            return _build_error_result(channel_type, enabled=True, latency_ms=latency, error=f"HTTP {response.status_code}")
        except Exception as exc:
            return _build_error_result(channel_type, enabled=True, latency_ms=0, error=str(exc))

    if channel_type == "mochat":
        if not channel_config.claw_token:
            return _build_error_result(channel_type, enabled=False, latency_ms=0, error="Claw token not configured")
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{channel_config.base_url or 'https://mochat.io'}/api/health",
                    headers={"Authorization": f"Bearer {channel_config.claw_token}"},
                )
            latency = int((time.time() - start) * 1000)
            if response.status_code == 200:
                return _result(channel_type, True, "ok", latency, None)
            if response.status_code == 401:
                return _build_error_result(
                    channel_type,
                    enabled=True,
                    latency_ms=latency,
                    error="Invalid claw token",
                    error_code="INVALID_CREDENTIALS",
                    error_kind="credential",
                )
            return _build_error_result(channel_type, enabled=True, latency_ms=latency, error=f"HTTP {response.status_code}")
        except Exception as exc:
            return _build_error_result(channel_type, enabled=True, latency_ms=0, error=str(exc))

    if channel_type == "qq":
        if not channel_config.app_id or not channel_config.secret:
            return _build_error_result(channel_type, enabled=False, latency_ms=0, error="App ID or Secret not configured")
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://bots.qq.com/app/getAppAccessToken",
                    json={"appId": channel_config.app_id, "clientSecret": channel_config.secret},
                )
            latency = int((time.time() - start) * 1000)
            data = response.json() if response.content else {}
            if response.status_code == 200 and data.get("code") == 0:
                return _result(channel_type, True, "ok", latency, None)
            return _build_error_result(
                channel_type,
                enabled=True,
                latency_ms=latency,
                error=data.get("message") or f"HTTP {response.status_code}",
            )
        except Exception as exc:
            return _build_error_result(channel_type, enabled=True, latency_ms=0, error=str(exc))

    if channel_type == "sharecrm":
        if not channel_config.app_id or not channel_config.app_secret:
            return _build_error_result(channel_type, enabled=False, latency_ms=0, error="App ID or Secret not configured")
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{channel_config.gateway_base_url}/im-gateway/auth/token",
                    json={"appId": channel_config.app_id, "appSecret": channel_config.app_secret},
                    headers={"Content-Type": "application/json"},
                )
            latency = int((time.time() - start) * 1000)
            data = response.json() if response.content else {}
            if response.status_code == 200 and data.get("code") == 0 and data.get("data", {}).get("accessToken"):
                return _result(channel_type, True, "ok", latency, None)
            return _build_error_result(
                channel_type,
                enabled=True,
                latency_ms=latency,
                error=data.get("msg") or f"HTTP {response.status_code}",
            )
        except Exception as exc:
            return _build_error_result(channel_type, enabled=True, latency_ms=0, error=str(exc))

    return _build_error_result(channel_type, enabled=False, latency_ms=0, error=f"Unsupported channel type: {channel_type}")


def _result(
    name: str,
    enabled: bool,
    status: str,
    latency_ms: int,
    error: str | None,
    *,
    error_code: str | None = None,
    error_kind: str | None = None,
    remediation: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "enabled": enabled,
        "status": status,
        "latency_ms": latency_ms,
        "error": error,
        "error_code": error_code,
        "error_kind": error_kind,
        "remediation": remediation or [],
    }
