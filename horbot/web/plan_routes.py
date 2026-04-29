"""Plan management API routes."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


class PlanConfirmRequest(BaseModel):
    plan_id: str
    session_key: str = "default"


def _serialize_plan(plan) -> dict[str, Any]:
    return {
        "id": plan.id,
        "title": plan.title,
        "description": plan.description,
        "status": plan.status,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
        "session_key": plan.session_key,
        "plan_type": plan.plan_type,
        "content": plan.content,
        "spec_content": plan.spec_content,
        "tasks_content": plan.tasks_content,
        "checklist_content": plan.checklist_content,
        "subtasks": [
            {
                "id": subtask.id,
                "title": subtask.title,
                "description": subtask.description,
                "status": subtask.status,
                "tools": subtask.tools,
            }
            for subtask in plan.subtasks
        ],
        "spec": {
            "why": plan.spec.why if plan.spec else "",
            "what_changes": plan.spec.what_changes if plan.spec else [],
            "impact": plan.spec.impact if plan.spec else {},
        },
        "checklist": {
            "items": plan.checklist.items if plan.checklist else [],
        },
    }


def create_plan_router(get_agent_loop: Callable[..., Any]) -> APIRouter:
    """Create plan management routes."""

    router = APIRouter()

    @router.post("/plan/{plan_id}/confirm")
    async def confirm_plan(plan_id: str, request: PlanConfirmRequest):
        """Confirm an execution plan and start execution."""
        from horbot.agent.planner import get_plan_storage

        logger = logging.getLogger("horbot.api")
        logger.info("confirm_plan called: plan_id=%s, session_key=%s", plan_id, request.session_key)
        storage = get_plan_storage()
        agent_loop = await get_agent_loop()

        plan_dict = agent_loop.get_active_plan(request.session_key)
        if not plan_dict or plan_dict["id"] != plan_id:
            logger.warning("Plan not found or not active: plan_id=%s, session_key=%s", plan_id, request.session_key)
            raise HTTPException(status_code=404, detail="Plan not found or not active")

        storage.update_plan_status(plan_id, "confirmed")
        queue = asyncio.Queue()

        async def execute_and_stream():
            async def on_subtask_start(plan_id: str, subtask_id: str, title: str):
                await queue.put({
                    "event": "subtask_start",
                    "plan_id": plan_id,
                    "subtask_id": subtask_id,
                    "title": title,
                })

            async def on_subtask_complete(
                plan_id: str,
                subtask_id: str,
                status: str,
                result: str,
                execution_time: float = 0,
                logs: list | None = None,
                input_tokens: int = 0,
                output_tokens: int = 0,
            ):
                await queue.put({
                    "event": "subtask_complete",
                    "plan_id": plan_id,
                    "subtask_id": subtask_id,
                    "status": status,
                    "result": result,
                    "execution_time": execution_time,
                    "logs": logs or [],
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                })

            try:
                logger.info("Calling execute_plan_by_id: plan_id=%s, session_key=%s", plan_id, request.session_key)
                result = await agent_loop.execute_plan_by_id(
                    plan_id=plan_id,
                    session_key=request.session_key,
                    on_subtask_start=on_subtask_start,
                    on_subtask_complete=on_subtask_complete,
                )
                logger.info("execute_plan_by_id completed: plan_id=%s, result=%s", plan_id, result is not None)
                if result:
                    await queue.put({"event": "plan_complete", "content": result.content})
                await queue.put({"event": "done"})
            except Exception as exc:
                logger.error("Error in execute_and_stream: plan_id=%s, error=%s", plan_id, str(exc))
                await queue.put({"event": "error", "content": str(exc)})

        asyncio.create_task(execute_and_stream())

        async def event_generator():
            event_count = 0
            try:
                while True:
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=30.0)
                        event = item.get("event")
                        event_count += 1
                        logger.info("SSE event #%s: %s", event_count, event)

                        if event == "done":
                            yield f"data: {json.dumps({'event': 'done'}, ensure_ascii=False)}\n\n"
                            break
                        if event == "error":
                            yield f"data: {json.dumps({'event': 'error', 'content': item.get('content')}, ensure_ascii=False)}\n\n"
                            break
                        if event == "subtask_start":
                            yield f"data: {json.dumps({'event': 'subtask_start', 'plan_id': item.get('plan_id'), 'subtask_id': item.get('subtask_id'), 'title': item.get('title')}, ensure_ascii=False)}\n\n"
                        elif event == "subtask_complete":
                            yield f"data: {json.dumps({'event': 'subtask_complete', 'plan_id': item.get('plan_id'), 'subtask_id': item.get('subtask_id'), 'status': item.get('status'), 'result': item.get('result'), 'execution_time': item.get('execution_time'), 'logs': item.get('logs'), 'input_tokens': item.get('input_tokens', 0), 'output_tokens': item.get('output_tokens', 0)}, ensure_ascii=False)}\n\n"
                        elif event == "plan_complete":
                            yield f"data: {json.dumps({'event': 'plan_complete', 'content': item.get('content')}, ensure_ascii=False)}\n\n"
                    except asyncio.TimeoutError:
                        logger.debug("SSE keep-alive")
                        yield ": keep-alive\n\n"
            except asyncio.CancelledError:
                logger.info("SSE stream cancelled")
                yield f"data: {json.dumps({'event': 'stopped', 'content': 'Generation cancelled'}, ensure_ascii=False)}\n\n"
            logger.info("SSE stream finished, total events: %s", event_count)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    @router.post("/plan/{plan_id}/cancel")
    async def cancel_plan(plan_id: str, request: PlanConfirmRequest):
        """Cancel an execution plan."""
        from horbot.agent.planner import get_plan_storage

        storage = get_plan_storage()
        plan = storage.load_plan(plan_id)
        agent_loop = None
        if not plan:
            agent_loop = await get_agent_loop()
            plan_dict = agent_loop.get_active_plan(request.session_key)
            if plan_dict and plan_dict["id"] == plan_id:
                plan = type("obj", (object,), {"status": plan_dict["status"]})()

        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        if plan.status not in ("pending", "confirmed"):
            raise HTTPException(status_code=400, detail=f"Cannot cancel plan in {plan.status} status")

        storage.update_plan_status(plan_id, "cancelled")
        agent_loop = agent_loop or await get_agent_loop()
        cancelled_subagents = await agent_loop.subagents.cancel_by_session(request.session_key)
        return {
            "status": "cancelled",
            "message": f"计划已取消，已停止 {cancelled_subagents} 个子代理" if cancelled_subagents > 0 else "计划已取消",
            "plan_id": plan_id,
            "cancelled_subagents": cancelled_subagents,
        }

    @router.post("/plan/{plan_id}/stop")
    async def stop_plan_execution(plan_id: str, request: PlanConfirmRequest):
        """Stop the execution of a running plan."""
        from horbot.agent.planner import get_plan_storage

        logger = logging.getLogger("horbot.api")
        agent_loop = await get_agent_loop()
        logger.info("Stop plan execution request: plan_id=%s, session_key=%s", plan_id, request.session_key)
        success = agent_loop.stop_plan_execution(request.session_key)
        logger.info("Stop plan execution result: success=%s", success)

        if not success:
            logger.error("Failed to stop plan execution: plan_id=%s, session_key=%s", plan_id, request.session_key)
            raise HTTPException(status_code=400, detail="Failed to stop plan execution")

        get_plan_storage().update_plan_status(plan_id, "stopped")
        return {
            "status": "stopped",
            "message": "计划执行已停止",
            "plan_id": plan_id,
        }

    @router.get("/plan/{plan_id}/logs")
    async def get_plan_execution_logs(plan_id: str):
        """Get execution logs for a plan."""
        from horbot.agent.planner import get_plan_storage

        return {
            "plan_id": plan_id,
            "logs": get_plan_storage().load_all_execution_logs(plan_id),
        }

    @router.get("/plan/{plan_id}")
    async def get_plan(plan_id: str):
        """Get plan details."""
        from horbot.agent.planner import get_plan_storage

        plan = get_plan_storage().load_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        return _serialize_plan(plan)

    @router.get("/plans")
    async def list_plans(session_key: str = None):
        """List all plans."""
        from horbot.agent.planner import get_plan_storage

        return {"plans": get_plan_storage().list_plans(session_key)}

    return router
