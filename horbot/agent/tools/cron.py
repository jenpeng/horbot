"""Cron tool for scheduling reminders and tasks."""

from contextvars import ContextVar
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from horbot.agent.tools.base import Tool
from horbot.cron.service import CronService
from horbot.cron.types import CronSchedule, DeliveryTarget


class CronTool(Tool):
    """Tool to schedule reminders and recurring tasks."""
    
    def __init__(self, cron_service: CronService):
        self._cron = cron_service
        self._channel_var: ContextVar[str] = ContextVar(
            f"cron_channel_{id(self)}",
            default="",
        )
        self._chat_id_var: ContextVar[str] = ContextVar(
            f"cron_chat_id_{id(self)}",
            default="",
        )
    
    def set_context(self, channel: str, chat_id: str) -> None:
        """Set the current session context for delivery."""
        self._channel_var.set(channel)
        self._chat_id_var.set(chat_id)
    
    @property
    def name(self) -> str:
        return "cron"
    
    @property
    def description(self) -> str:
        return """Schedule reminders and recurring tasks with flexible delivery options.

Actions:
- add: Create a new scheduled task
- list: List all scheduled tasks
- remove: Remove a task by ID
- enable: Enable a disabled task
- disable: Disable an enabled task

Schedule Types:
- every_seconds: Interval-based (e.g., every 3600 seconds = every hour)
- cron_expr: Cron expression (e.g., '0 9 * * *' = daily at 9 AM)
- at: One-time execution at specific datetime

Delivery Channels:
- web: Push to web session (default: current session)
- whatsapp: Send to WhatsApp number
- telegram: Send to Telegram chat
- feishu: Send to Feishu/Lark
- sharecrm: Send to ShareCRM
- email: Send email

Examples:
- Simple reminder: cron(action='add', message='Drink water!', every_seconds=7200)
- Daily report: cron(action='add', message='Generate daily report', cron_expr='0 9 * * *', tz='Asia/Shanghai')
- Multi-channel: cron(action='add', message='Alert!', every_seconds=3600, channels=[{'channel':'web','to':'user1'},{'channel':'telegram','to':'123456'}])
"""
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "list", "remove", "enable", "disable"],
                    "description": "Action to perform"
                },
                "name": {
                    "type": "string",
                    "description": "Task name (optional, defaults to message prefix)"
                },
                "message": {
                    "type": "string",
                    "description": "Task message/prompt to execute (for add)"
                },
                "every_seconds": {
                    "type": "integer",
                    "description": "Interval in seconds for recurring tasks (e.g., 3600 = every hour)"
                },
                "cron_expr": {
                    "type": "string",
                    "description": "Cron expression (e.g., '0 9 * * *' for daily at 9 AM, '0 9 * * 1-5' for weekdays at 9 AM)"
                },
                "tz": {
                    "type": "string",
                    "description": "IANA timezone for cron expressions (e.g., 'Asia/Shanghai', 'America/New_York')"
                },
                "at": {
                    "type": "string",
                    "description": "ISO datetime for one-time execution (e.g., '2026-03-20T10:30:00')"
                },
                "channels": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "channel": {
                                "type": "string",
                                "description": "Channel type: web, whatsapp, telegram, feishu, sharecrm, email"
                            },
                            "to": {
                                "type": "string",
                                "description": "Target identifier (session ID, phone number, chat ID, email)"
                            }
                        },
                        "required": ["channel", "to"]
                    },
                    "description": "Delivery channels for results. Each item has 'channel' and 'to' fields."
                },
                "notify": {
                    "type": "boolean",
                    "description": "Send system notification (MacOS). Default: true"
                },
                "deliver": {
                    "type": "boolean",
                    "description": "Whether to deliver results to channels. Default: true"
                },
                "job_id": {
                    "type": "string",
                    "description": "Job ID (for remove, enable, disable)"
                }
            },
            "required": ["action"]
        }
    
    async def execute(
        self,
        action: str,
        name: str = "",
        message: str = "",
        every_seconds: int | None = None,
        cron_expr: str | None = None,
        tz: str | None = None,
        at: str | None = None,
        channels: list[dict] | None = None,
        notify: bool = True,
        deliver: bool = True,
        job_id: str | None = None,
        **kwargs: Any
    ) -> str:
        if action == "add":
            return self._add_job(name, message, every_seconds, cron_expr, tz, at, channels, notify, deliver)
        elif action == "list":
            return self._list_jobs()
        elif action == "remove":
            return self._remove_job(job_id)
        elif action == "enable":
            return self._enable_job(job_id, True)
        elif action == "disable":
            return self._enable_job(job_id, False)
        return f"Unknown action: {action}"
    
    def _add_job(
        self,
        name: str,
        message: str,
        every_seconds: int | None,
        cron_expr: str | None,
        tz: str | None,
        at: str | None,
        channels: list[dict] | None,
        notify: bool,
        deliver: bool,
    ) -> str:
        if not message:
            return "Error: message is required for add"
        if tz:
            try:
                ZoneInfo(tz)
            except (KeyError, Exception):
                return f"Error: unknown timezone '{tz}'"
        if tz and not cron_expr and not at:
            return "Error: tz can only be used with cron_expr or at"
        
        # Build schedule
        delete_after = False
        if every_seconds:
            schedule = CronSchedule(kind="every", every_ms=every_seconds * 1000)
        elif cron_expr:
            schedule = CronSchedule(kind="cron", expr=cron_expr, tz=tz)
        elif at:
            from datetime import datetime
            dt = datetime.fromisoformat(at)
            if tz and dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo(tz))
            at_ms = int(dt.timestamp() * 1000)
            schedule = CronSchedule(kind="at", at_ms=at_ms)
            delete_after = True
        else:
            return "Error: either every_seconds, cron_expr, or at is required"
        
        # Build delivery targets
        delivery_targets: list[DeliveryTarget] = []
        if channels:
            for ch in channels:
                if "channel" in ch and "to" in ch:
                    delivery_targets.append(DeliveryTarget(channel=ch["channel"], to=ch["to"]))
        
        # If no channels specified, use current session as default
        default_channel = self._channel_var.get()
        default_chat_id = self._chat_id_var.get()
        if not delivery_targets and default_channel and default_chat_id:
            delivery_targets.append(DeliveryTarget(channel=default_channel, to=default_chat_id))
        
        # Use provided name or derive from message
        task_name = name if name else message[:50]
        
        job = self._cron.add_job(
            name=task_name,
            schedule=schedule,
            message=message,
            deliver=deliver,
            channels=delivery_targets,
            delete_after_run=delete_after,
            notify=notify,
        )
        
        # Build response
        schedule_desc = self._describe_schedule(schedule)
        channels_desc = self._describe_channels(delivery_targets)
        notify_status = "with notification" if notify else "without notification"
        
        return f"Created task '{job.name}' (id: {job.id})\nSchedule: {schedule_desc}\nDelivery: {channels_desc}\nStatus: {notify_status}"
    
    def _describe_schedule(self, schedule: CronSchedule) -> str:
        """Human-readable schedule description."""
        if schedule.kind == "every" and schedule.every_ms:
            seconds = schedule.every_ms // 1000
            if seconds >= 86400:
                return f"Every {seconds // 86400} day(s)"
            elif seconds >= 3600:
                return f"Every {seconds // 3600} hour(s)"
            elif seconds >= 60:
                return f"Every {seconds // 60} minute(s)"
            return f"Every {seconds} seconds"
        elif schedule.kind == "cron" and schedule.expr:
            tz_desc = f" ({schedule.tz})" if schedule.tz else ""
            return f"Cron: {schedule.expr}{tz_desc}"
        elif schedule.kind == "at" and schedule.at_ms:
            from datetime import datetime
            dt = datetime.fromtimestamp(schedule.at_ms / 1000)
            return f"One-time at {dt.isoformat()}"
        return "Unknown schedule"
    
    def _describe_channels(self, channels: list[DeliveryTarget]) -> str:
        """Human-readable channel description."""
        if not channels:
            return "None"
        return ", ".join(f"{ch.channel}:{ch.to}" for ch in channels)
    
    def _list_jobs(self) -> str:
        jobs = self._cron.list_jobs(include_disabled=True)
        if not jobs:
            return "No scheduled tasks."
        
        lines = ["Scheduled tasks:"]
        for j in jobs:
            status = "✓" if j.enabled else "✗"
            schedule_desc = self._describe_schedule(j.schedule)
            channels = j.payload.get_delivery_targets()
            channels_desc = self._describe_channels(channels)
            next_run = ""
            if j.state.next_run_at_ms:
                from datetime import datetime
                dt = datetime.fromtimestamp(j.state.next_run_at_ms / 1000)
                next_run = f"\n  Next run: {dt.strftime('%Y-%m-%d %H:%M:%S')}"
            lines.append(f"\n{status} [{j.id}] {j.name}")
            lines.append(f"  Schedule: {schedule_desc}")
            lines.append(f"  Delivery: {channels_desc}{next_run}")
        return "\n".join(lines)
    
    def _remove_job(self, job_id: str | None) -> str:
        if not job_id:
            return "Error: job_id is required for remove"
        if self._cron.remove_job(job_id):
            return f"Removed task {job_id}"
        return f"Task {job_id} not found"
    
    def _enable_job(self, job_id: str | None, enabled: bool) -> str:
        if not job_id:
            return f"Error: job_id is required for {'enable' if enabled else 'disable'}"
        job = self._cron.enable_job(job_id, enabled)
        if job:
            status = "enabled" if enabled else "disabled"
            return f"Task '{job.name}' ({job_id}) {status}"
        return f"Task {job_id} not found"


class TaskToolWrapper(Tool):
    """High-level reminder/task wrapper backed by CronTool."""

    def __init__(self, cron_tool: CronTool):
        self._cron_tool = cron_tool

    def set_context(self, channel: str, chat_id: str) -> None:
        self._cron_tool.set_context(channel, chat_id)

    @property
    def name(self) -> str:
        return "task"

    @property
    def description(self) -> str:
        return (
            "High-level reminder and scheduled task tool. Prefer this for natural requests like "
            "'30分钟后提醒我喝水', '明天9点提醒我开会', '列出我的任务', '删除任务 abc123'. "
            "Use action='add' to create a reminder, action='list' to view tasks, and action='remove' "
            "or enable/disable to manage an existing task."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "list", "remove", "enable", "disable"],
                    "description": "Task action to perform.",
                },
                "title": {
                    "type": "string",
                    "description": "Human-friendly task title.",
                },
                "message": {
                    "type": "string",
                    "description": "Reminder content or task payload.",
                },
                "after_minutes": {
                    "type": "integer",
                    "description": "Create a one-time reminder this many minutes from now.",
                },
                "after_hours": {
                    "type": "integer",
                    "description": "Create a one-time reminder this many hours from now.",
                },
                "at": {
                    "type": "string",
                    "description": "ISO datetime for one-time execution.",
                },
                "every_minutes": {
                    "type": "integer",
                    "description": "Recurring interval in minutes.",
                },
                "every_hours": {
                    "type": "integer",
                    "description": "Recurring interval in hours.",
                },
                "cron_expr": {
                    "type": "string",
                    "description": "Cron expression for recurring schedules.",
                },
                "tz": {
                    "type": "string",
                    "description": "Timezone name like Asia/Shanghai.",
                },
                "task_id": {
                    "type": "string",
                    "description": "Existing task ID for remove/enable/disable.",
                },
                "notify": {
                    "type": "boolean",
                    "description": "Whether to show a local system notification.",
                },
                "deliver": {
                    "type": "boolean",
                    "description": "Whether to deliver the result back to the current chat.",
                },
                "channels": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string"},
                            "to": {"type": "string"},
                        },
                        "required": ["channel", "to"],
                    },
                    "description": "Optional delivery targets.",
                },
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        title: str = "",
        message: str = "",
        after_minutes: int | None = None,
        after_hours: int | None = None,
        at: str | None = None,
        every_minutes: int | None = None,
        every_hours: int | None = None,
        cron_expr: str | None = None,
        tz: str | None = None,
        task_id: str | None = None,
        notify: bool = True,
        deliver: bool = True,
        channels: list[dict[str, str]] | None = None,
        **kwargs: Any,
    ) -> str:
        if action in {"list"}:
            return await self._cron_tool.execute(action="list")

        if action in {"remove", "enable", "disable"}:
            resolved_task_id = task_id or kwargs.get("job_id") or kwargs.get("id")
            return await self._cron_tool.execute(action=action, job_id=resolved_task_id)

        if action != "add":
            return f"Unknown action: {action}"

        resolved_message = message or title
        if not resolved_message:
            return "Error: message or title is required for add"

        resolved_every_seconds: int | None = None
        if every_minutes:
            resolved_every_seconds = every_minutes * 60
        elif every_hours:
            resolved_every_seconds = every_hours * 3600

        resolved_at = at
        offset = None
        if after_minutes:
            offset = timedelta(minutes=after_minutes)
        elif after_hours:
            offset = timedelta(hours=after_hours)

        if offset and not resolved_at:
            now = datetime.now(ZoneInfo(tz)) if tz else datetime.now()
            resolved_at = (now + offset).replace(second=0, microsecond=0).isoformat()

        return await self._cron_tool.execute(
            action="add",
            name=title,
            message=resolved_message,
            every_seconds=resolved_every_seconds,
            cron_expr=cron_expr,
            tz=tz,
            at=resolved_at,
            channels=channels,
            notify=notify,
            deliver=deliver,
        )
