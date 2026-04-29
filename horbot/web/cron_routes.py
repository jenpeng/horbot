"""Cron task API routes."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException

from horbot.cron.types import CronSchedule


def _serialize_job(job) -> dict[str, Any]:
    payload = {
        "kind": job.payload.kind,
        "message": job.payload.message,
        "deliver": job.payload.deliver,
        "channel": job.payload.channel,
        "to": job.payload.to,
    }
    if hasattr(job.payload, "channels"):
        payload["channels"] = [{"channel": c.channel, "to": c.to} for c in job.payload.channels] if job.payload.channels else None
    if hasattr(job.payload, "notify"):
        payload["notify"] = job.payload.notify

    return {
        "id": job.id,
        "name": job.name,
        "enabled": job.enabled,
        "schedule": {
            "kind": job.schedule.kind,
            "at_ms": job.schedule.at_ms,
            "every_ms": job.schedule.every_ms,
            "expr": job.schedule.expr,
            "tz": job.schedule.tz,
        },
        "payload": payload,
        "state": {
            "next_run_at_ms": job.state.next_run_at_ms,
            "last_run_at_ms": job.state.last_run_at_ms,
            "last_status": job.state.last_status,
            "last_error": job.state.last_error,
        },
        "created_at_ms": job.created_at_ms,
        "updated_at_ms": job.updated_at_ms,
        "delete_after_run": job.delete_after_run,
    }


def create_cron_router(get_cron_service: Callable[[], Any]) -> APIRouter:
    """Create routes for scheduled tasks."""

    router = APIRouter()

    @router.get("/tasks")
    async def get_tasks(cron_service=Depends(get_cron_service)):
        """Get all cron tasks."""
        jobs = cron_service.list_jobs(include_disabled=True)
        return {"tasks": [_serialize_job(job) for job in jobs]}

    @router.post("/tasks")
    async def add_task(request_data: dict[str, Any], cron_service=Depends(get_cron_service)):
        """Add a new task."""
        try:
            name = request_data.get("name")
            schedule_data = request_data.get("schedule")
            message = request_data.get("message")
            deliver = request_data.get("deliver", False)
            channel = request_data.get("channel")
            to = request_data.get("to")
            delete_after_run = request_data.get("delete_after_run", False)

            if not name or not schedule_data or not message:
                raise HTTPException(status_code=400, detail="Name, schedule, and message are required")

            schedule = CronSchedule(
                kind=schedule_data.get("kind"),
                at_ms=schedule_data.get("at_ms"),
                every_ms=schedule_data.get("every_ms"),
                expr=schedule_data.get("expr"),
                tz=schedule_data.get("tz"),
            )
            job = cron_service.add_job(
                name=name,
                schedule=schedule,
                message=message,
                deliver=deliver,
                channel=channel,
                to=to,
                delete_after_run=delete_after_run,
            )
            return _serialize_job(job)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @router.delete("/tasks/{task_id}")
    async def delete_task(task_id: str, cron_service=Depends(get_cron_service)):
        """Delete a task."""
        removed = cron_service.remove_job(task_id)
        if not removed:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"status": "success", "message": "Task deleted"}

    @router.put("/tasks/{task_id}/enable")
    async def enable_task(task_id: str, request_data: dict[str, bool], cron_service=Depends(get_cron_service)):
        """Enable or disable a task."""
        enabled = request_data.get("enabled", True)
        job = cron_service.enable_job(task_id, enabled)
        if not job:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"id": job.id, "name": job.name, "enabled": job.enabled}

    @router.post("/tasks/{task_id}/run")
    async def run_task(task_id: str, cron_service=Depends(get_cron_service)):
        """Run a task manually."""
        result = await cron_service.run_job(task_id, force=True)
        if not result:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"status": "success", "message": "Task run started"}

    return router
