"""System status, environment, log, and restart API routes."""

from pathlib import Path
from typing import Any, Callable
import os
import re
import sys
import threading
import time

from fastapi import APIRouter
from loguru import logger


def _resolve_app_version() -> str:
    try:
        import importlib.metadata
        return importlib.metadata.version("horbot")
    except Exception:
        return "0.1.4.post2"


def _format_uptime(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds_remaining = total_seconds % 60
    return f"{hours}h {minutes}m {seconds_remaining}s"


def build_system_status_payload(
    *,
    config: Any,
    started_at: float,
    cron_status_fn: Callable[[], dict[str, Any]],
    agent_initialized_fn: Callable[[], bool],
) -> dict[str, Any]:
    import psutil

    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
    except Exception:
        cpu_percent = 0

    try:
        memory = psutil.virtual_memory()
        memory_info = {
            "total": memory.total,
            "available": memory.available,
            "used": memory.used,
            "percent": memory.percent,
        }
    except Exception:
        memory_info = {
            "total": 0,
            "available": 0,
            "used": 0,
            "percent": 0,
        }

    try:
        disk = psutil.disk_usage("/")
        disk_info = {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent,
        }
    except Exception:
        disk_info = {
            "total": 0,
            "used": 0,
            "free": 0,
            "percent": 0,
        }

    try:
        uptime_seconds = time.time() - started_at
        uptime_str = _format_uptime(uptime_seconds)
    except Exception:
        uptime_seconds = 0
        uptime_str = "Unknown"

    try:
        cron_status = cron_status_fn()
    except Exception:
        cron_status = {"enabled": False, "jobs": 0}

    return {
        "status": "running",
        "version": _resolve_app_version(),
        "uptime": uptime_str,
        "uptime_seconds": uptime_seconds,
        "system": {
            "cpu_percent": cpu_percent,
            "memory": memory_info,
            "disk": disk_info,
        },
        "services": {
            "cron": {
                "enabled": cron_status.get("enabled", False),
                "jobs_count": cron_status.get("jobs", 0),
                "next_wake_at_ms": cron_status.get("next_wake_at_ms"),
            },
            "agent": {
                "initialized": agent_initialized_fn(),
            },
        },
        "config": {
            "workspace": str(config.workspace_path),
            "model": config.agents.defaults.model if config.agents else None,
            "provider": config.get_provider_name() if config else None,
        },
    }


def create_system_router(
    *,
    get_config: Callable[[], Any],
    started_at: float,
    cron_status_fn: Callable[[], dict[str, Any]],
    agent_initialized_fn: Callable[[], bool],
) -> APIRouter:
    router = APIRouter()

    @router.get("/status")
    async def get_system_status():
        """Get system status."""
        return build_system_status_payload(
            config=get_config(),
            started_at=started_at,
            cron_status_fn=cron_status_fn,
            agent_initialized_fn=agent_initialized_fn,
        )

    @router.get("/environment")
    async def get_environment_info():
        """Get runtime environment information."""
        import importlib.metadata
        import platform
        import psutil

        config = get_config()
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

        os_info = {
            "name": platform.system(),
            "version": platform.version(),
            "platform": platform.platform(),
        }

        dependencies = []
        package_names = ["litellm", "fastapi", "pydantic", "loguru", "psutil", "httpx", "aiofiles"]

        for pkg_name in package_names:
            try:
                version = importlib.metadata.version(pkg_name)
                dependencies.append({"name": pkg_name, "version": version})
            except Exception:
                dependencies.append({"name": pkg_name, "version": "not installed"})

        try:
            disk = psutil.disk_usage("/")
            disk_info = {
                "total_gb": round(disk.total / (1024 ** 3), 2),
                "used_gb": round(disk.used / (1024 ** 3), 2),
                "free_gb": round(disk.free / (1024 ** 3), 2),
                "usage_percent": disk.percent,
            }
        except Exception:
            disk_info = {
                "total_gb": 0,
                "used_gb": 0,
                "free_gb": 0,
                "usage_percent": 0,
            }

        try:
            memory = psutil.virtual_memory()
            memory_info = {
                "total_gb": round(memory.total / (1024 ** 3), 2),
                "used_gb": round(memory.used / (1024 ** 3), 2),
                "available_gb": round(memory.available / (1024 ** 3), 2),
                "usage_percent": memory.percent,
            }
        except Exception:
            memory_info = {
                "total_gb": 0,
                "used_gb": 0,
                "available_gb": 0,
                "usage_percent": 0,
            }

        try:
            cpu_info = {
                "count": psutil.cpu_count(logical=True),
                "percent": psutil.cpu_percent(interval=0.1),
            }
        except Exception:
            cpu_info = {
                "count": 0,
                "percent": 0,
            }

        workspace_path = Path(config.workspace_path)
        workspace_info = {
            "path": str(workspace_path),
            "label": workspace_path.name or str(workspace_path),
            "role": "global-workspace-baseline",
            "metadata_dirname": ".horbot-agent",
            "note": "This is the global workspace baseline. Agent runtime metadata stays under each workspace in .horbot-agent/.",
            "exists": workspace_path.exists(),
            "files_count": 0,
        }

        if workspace_path.exists():
            try:
                files_count = sum(1 for _ in workspace_path.rglob("*") if _.is_file())
                workspace_info["files_count"] = files_count
            except Exception:
                pass

        return {
            "python_version": python_version,
            "os_info": os_info,
            "dependencies": dependencies,
            "disk": disk_info,
            "memory": memory_info,
            "cpu": cpu_info,
            "workspace": workspace_info,
        }

    @router.get("/api-metrics")
    async def get_api_metrics(lines: int = 100):
        """Get API request metrics from api_requests.log."""
        config = get_config()
        log_dir = Path(config.workspace_path) / "logs"
        log_file = log_dir / "api_requests.log"

        metrics = {
            "recent_requests": [],
            "total_count": 0,
            "avg_process_time_ms": 0,
            "error_count": 0,
        }

        if not log_file.exists():
            return metrics

        try:
            content = log_file.read_text(encoding="utf-8")
            log_lines = [line for line in content.strip().split("\n") if line.strip()]
            recent_lines = log_lines[-lines:]
            total_time = 0

            pattern = re.compile(r"API Request:\s+(?P<method>[A-Z]+)\s+(?P<url>\S+)\s+-\s+(?P<status_code>\d+|None)\s+\((?P<time_ms>[\d.]+)ms\)\s+-\s+Client:\s+(?P<client_ip>\S+)")
            timestamp_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})")

            for line in recent_lines:
                ts_match = timestamp_pattern.match(line)
                req_match = pattern.search(line)

                if req_match:
                    ts = ts_match.group(1) if ts_match else ""
                    status_code_str = req_match.group("status_code")
                    status_code = int(status_code_str) if status_code_str != "None" else 500
                    time_ms = float(req_match.group("time_ms"))

                    if status_code >= 400:
                        metrics["error_count"] += 1

                    total_time += time_ms
                    metrics["recent_requests"].append({
                        "timestamp": ts,
                        "method": req_match.group("method"),
                        "url": req_match.group("url"),
                        "status_code": status_code,
                        "process_time_ms": time_ms,
                        "client_ip": req_match.group("client_ip"),
                    })

            metrics["total_count"] = len(metrics["recent_requests"])
            if metrics["total_count"] > 0:
                metrics["avg_process_time_ms"] = round(total_time / metrics["total_count"], 2)

            metrics["recent_requests"].reverse()

        except Exception as e:
            logger.error("Failed to read api_requests.log: {}", e)

        return metrics

    @router.get("/logs")
    async def get_logs(lines: int = 100, level: str = None):
        """Get recent logs."""
        from horbot.utils.paths import get_logs_dir

        log_dir = get_logs_dir()

        logs = []
        if log_dir.exists():
            log_files = sorted(log_dir.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
            if log_files:
                try:
                    content = log_files[0].read_text(encoding="utf-8")
                    log_lines = content.strip().split("\n")[-lines:]

                    for line in log_lines:
                        if not line.strip():
                            continue

                        log_entry = {"raw": line}

                        timestamp_match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
                        if timestamp_match:
                            log_entry["timestamp"] = timestamp_match.group(1)

                        level_match = re.search(r"\| (DEBUG|INFO|WARNING|ERROR|CRITICAL) \|", line)
                        if level_match:
                            log_entry["level"] = level_match.group(1)
                        else:
                            log_entry["level"] = "INFO"

                        if level and log_entry.get("level") != level:
                            continue

                        logs.append(log_entry)
                except Exception as e:
                    logs.append({"raw": f"Error reading log file: {e}", "level": "ERROR"})

        return {"logs": logs, "total": len(logs)}

    @router.post("/restart")
    async def restart_service():
        """Restart the horbot service."""
        def do_restart():
            time.sleep(1)
            os.execv(sys.executable, [sys.executable] + sys.argv)

        restart_thread = threading.Thread(target=do_restart, daemon=True)
        restart_thread.start()

        return {"status": "success", "message": "Service restart initiated"}

    return router
