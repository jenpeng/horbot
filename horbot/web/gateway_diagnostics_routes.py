"""Gateway diagnostics API routes."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable

import httpx
from fastapi import APIRouter


GatewayTestFn = Callable[[str, Any], Awaitable[dict[str, Any]]]
GetConfigFn = Callable[[], Any]


def _disabled(name: str) -> dict[str, Any]:
    return {"name": name, "enabled": False, "status": "disabled", "latency_ms": 0, "error": None}


def _config_error(name: str, message: str) -> dict[str, Any]:
    return {"name": name, "enabled": True, "status": "error", "latency_ms": 0, "error": message}


def _ok(name: str, latency_ms: int) -> dict[str, Any]:
    return {"name": name, "enabled": True, "status": "ok", "latency_ms": latency_ms, "error": None}


def _http_error(name: str, latency_ms: int, message: str) -> dict[str, Any]:
    return {"name": name, "enabled": True, "status": "error", "latency_ms": latency_ms, "error": message}


def _exception_error(name: str, exc: Exception) -> dict[str, Any]:
    return {"name": name, "enabled": True, "status": "error", "latency_ms": 0, "error": str(exc)}


def _latency_ms(start: float) -> int:
    return int((time.time() - start) * 1000)


def create_gateway_diagnostics_router(
    get_config: GetConfigFn,
    test_channel_connection_fn: GatewayTestFn,
) -> APIRouter:
    """Create routes for channel gateway diagnostics."""

    router = APIRouter()

    @router.get("/gateway/diagnostics")
    async def get_gateway_diagnostics():
        """Diagnose connection status for all channel gateways."""
        config = get_config()
        channels_config = config.channels

        async def test_telegram() -> dict[str, Any]:
            tg_config = channels_config.telegram
            if not tg_config.enabled:
                return _disabled("telegram")
            if not tg_config.token:
                return _config_error("telegram", "Token not configured")

            start = time.time()
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        f"https://api.telegram.org/bot{tg_config.token}/getMe",
                        proxy=tg_config.proxy,
                    )
                latency = _latency_ms(start)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        return _ok("telegram", latency)
                    return _http_error("telegram", latency, data.get("description", "Unknown error"))
                return _http_error("telegram", latency, f"HTTP {response.status_code}")
            except Exception as exc:
                return _exception_error("telegram", exc)

        async def test_discord() -> dict[str, Any]:
            dc_config = channels_config.discord
            if not dc_config.enabled:
                return _disabled("discord")
            if not dc_config.token:
                return _config_error("discord", "Token not configured")

            start = time.time()
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        "https://discord.com/api/v10/users/@me",
                        headers={"Authorization": f"Bot {dc_config.token}"},
                    )
                latency = _latency_ms(start)
                if response.status_code == 200:
                    return _ok("discord", latency)
                if response.status_code == 401:
                    return _http_error("discord", latency, "Invalid token")
                return _http_error("discord", latency, f"HTTP {response.status_code}")
            except Exception as exc:
                return _exception_error("discord", exc)

        async def test_whatsapp() -> dict[str, Any]:
            wa_config = channels_config.whatsapp
            if not wa_config.enabled:
                return _disabled("whatsapp")

            start = time.time()
            try:
                bridge_url = wa_config.bridge_url.replace("ws://", "http://").replace("wss://", "https://")
                headers = {}
                if wa_config.bridge_token:
                    headers["Authorization"] = f"Bearer {wa_config.bridge_token}"
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(f"{bridge_url}/health", headers=headers)
                latency = _latency_ms(start)
                if response.status_code == 200:
                    return _ok("whatsapp", latency)
                return _http_error("whatsapp", latency, f"HTTP {response.status_code}")
            except Exception as exc:
                return _exception_error("whatsapp", exc)

        async def test_feishu() -> dict[str, Any]:
            fs_config = channels_config.feishu
            if not fs_config.enabled:
                return _disabled("feishu")
            if not fs_config.app_id or not fs_config.app_secret:
                return _config_error("feishu", "App ID or Secret not configured")

            start = time.time()
            try:
                async with httpx.AsyncClient(timeout=10.0, verify=not fs_config.skip_ssl_verify) as client:
                    response = await client.post(
                        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                        json={"app_id": fs_config.app_id, "app_secret": fs_config.app_secret},
                    )
                latency = _latency_ms(start)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 0:
                        return _ok("feishu", latency)
                    return _http_error("feishu", latency, data.get("msg", "Unknown error"))
                return _http_error("feishu", latency, f"HTTP {response.status_code}")
            except Exception as exc:
                return _exception_error("feishu", exc)

        async def test_wecom() -> dict[str, Any]:
            wc_config = channels_config.wecom
            if not wc_config.enabled:
                return _disabled("wecom")

            result = await test_channel_connection_fn("wecom", wc_config)
            return {
                "name": "wecom",
                "enabled": bool(result.get("enabled", True)),
                "status": result.get("status", "error"),
                "latency_ms": int(result.get("latency_ms", 0) or 0),
                "error": result.get("error"),
            }

        async def test_dingtalk() -> dict[str, Any]:
            dt_config = channels_config.dingtalk
            if not dt_config.enabled:
                return _disabled("dingtalk")
            if not dt_config.client_id or not dt_config.client_secret:
                return _config_error("dingtalk", "Client ID or Secret not configured")

            start = time.time()
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        "https://api.dingtalk.com/v1.0/oauth2/accessToken",
                        json={"appKey": dt_config.client_id, "appSecret": dt_config.client_secret},
                    )
                latency = _latency_ms(start)
                if response.status_code == 200:
                    data = response.json()
                    if "accessToken" in data:
                        return _ok("dingtalk", latency)
                    return _http_error("dingtalk", latency, data.get("message", "Unknown error"))
                return _http_error("dingtalk", latency, f"HTTP {response.status_code}")
            except Exception as exc:
                return _exception_error("dingtalk", exc)

        async def test_slack() -> dict[str, Any]:
            slack_config = channels_config.slack
            if not slack_config.enabled:
                return _disabled("slack")
            if not slack_config.bot_token:
                return _config_error("slack", "Bot token not configured")

            start = time.time()
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        "https://slack.com/api/auth.test",
                        headers={"Authorization": f"Bearer {slack_config.bot_token}"},
                    )
                latency = _latency_ms(start)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        return _ok("slack", latency)
                    return _http_error("slack", latency, data.get("error", "Unknown error"))
                return _http_error("slack", latency, f"HTTP {response.status_code}")
            except Exception as exc:
                return _exception_error("slack", exc)

        async def test_email() -> dict[str, Any]:
            email_config = channels_config.email
            if not email_config.enabled:
                return _disabled("email")
            if not email_config.imap_host or not email_config.imap_username:
                return _config_error("email", "IMAP host or username not configured")

            start = time.time()
            try:
                import imaplib

                if email_config.imap_use_ssl:
                    imap = imaplib.IMAP4_SSL(email_config.imap_host, email_config.imap_port, timeout=10)
                else:
                    imap = imaplib.IMAP4(email_config.imap_host, email_config.imap_port)
                    imap.starttls()

                imap.login(email_config.imap_username, email_config.imap_password)
                latency = _latency_ms(start)
                imap.logout()
                return _ok("email", latency)
            except Exception as exc:
                return _exception_error("email", exc)

        async def test_matrix() -> dict[str, Any]:
            mx_config = channels_config.matrix
            if not mx_config.enabled:
                return _disabled("matrix")
            if not mx_config.access_token or not mx_config.homeserver:
                return _config_error("matrix", "Access token or homeserver not configured")

            start = time.time()
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        f"{mx_config.homeserver}/_matrix/client/v3/account/whoami",
                        headers={"Authorization": f"Bearer {mx_config.access_token}"},
                    )
                latency = _latency_ms(start)
                if response.status_code == 200:
                    data = response.json()
                    if "user_id" in data:
                        return _ok("matrix", latency)
                    return _http_error("matrix", latency, "Invalid response")
                if response.status_code == 401:
                    return _http_error("matrix", latency, "Invalid access token")
                return _http_error("matrix", latency, f"HTTP {response.status_code}")
            except Exception as exc:
                return _exception_error("matrix", exc)

        async def test_mochat() -> dict[str, Any]:
            mc_config = channels_config.mochat
            if not mc_config.enabled:
                return _disabled("mochat")
            if not mc_config.claw_token:
                return _config_error("mochat", "Claw token not configured")

            start = time.time()
            try:
                base_url = mc_config.base_url or "https://mochat.io"
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        f"{base_url}/api/health",
                        headers={"Authorization": f"Bearer {mc_config.claw_token}"},
                    )
                latency = _latency_ms(start)
                if response.status_code == 200:
                    return _ok("mochat", latency)
                if response.status_code == 401:
                    return _http_error("mochat", latency, "Invalid claw token")
                return _http_error("mochat", latency, f"HTTP {response.status_code}")
            except Exception as exc:
                return _exception_error("mochat", exc)

        async def test_qq() -> dict[str, Any]:
            qq_config = channels_config.qq
            if not qq_config.enabled:
                return _disabled("qq")
            if not qq_config.app_id or not qq_config.secret:
                return _config_error("qq", "App ID or Secret not configured")

            start = time.time()
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        "https://bots.qq.com/app/getAppAccessToken",
                        json={"appId": qq_config.app_id, "clientSecret": qq_config.secret},
                    )
                latency = _latency_ms(start)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 0:
                        return _ok("qq", latency)
                    return _http_error("qq", latency, data.get("message", "Unknown error"))
                return _http_error("qq", latency, f"HTTP {response.status_code}")
            except Exception as exc:
                return _exception_error("qq", exc)

        async def test_sharecrm() -> dict[str, Any]:
            crm_config = channels_config.sharecrm
            if not crm_config.enabled:
                return _disabled("sharecrm")
            if not crm_config.app_id or not crm_config.app_secret:
                return _config_error("sharecrm", "App ID or Secret not configured")

            start = time.time()
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        f"{crm_config.gateway_base_url}/im-gateway/auth/token",
                        json={"appId": crm_config.app_id, "appSecret": crm_config.app_secret},
                        headers={"Content-Type": "application/json"},
                    )
                latency = _latency_ms(start)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 0 and data.get("data", {}).get("accessToken"):
                        return _ok("sharecrm", latency)
                    return _http_error("sharecrm", latency, data.get("msg", "Unknown error"))
                return _http_error("sharecrm", latency, f"HTTP {response.status_code}")
            except Exception as exc:
                return _exception_error("sharecrm", exc)

        results = await asyncio.gather(
            test_telegram(),
            test_discord(),
            test_whatsapp(),
            test_feishu(),
            test_wecom(),
            test_dingtalk(),
            test_slack(),
            test_email(),
            test_matrix(),
            test_mochat(),
            test_qq(),
            test_sharecrm(),
        )

        enabled_channels = [r for r in results if r.get("enabled", False)]
        ok_count = sum(1 for r in enabled_channels if r.get("status") == "ok")
        error_count = sum(1 for r in enabled_channels if r.get("status") == "error")

        if not enabled_channels or error_count == 0:
            overall_status = "healthy"
        elif ok_count > 0:
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"

        return {
            "channels": list(results),
            "overall_status": overall_status,
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    return router
