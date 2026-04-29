"""Task delegation and smart routing API routes."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class DelegateTaskRequest(BaseModel):
    description: str
    target_agent_id: str
    source_agent_id: str
    context: dict[str, Any] = {}
    priority: str = "normal"


class AnalyzeTaskRequest(BaseModel):
    description: str
    context: Optional[dict[str, Any]] = None


def _serialize_delegated_task(task, *, include_context: bool = False) -> dict[str, Any]:
    payload = {
        "id": task.id,
        "description": task.description,
        "target_agent_id": task.target_agent_id,
        "source_agent_id": task.source_agent_id,
        "status": task.status,
        "result": task.result,
        "error": task.error,
        "created_at": task.created_at.isoformat(),
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "priority": task.priority,
    }
    if include_context:
        payload["context"] = task.context
    return payload


def _agent_router_data(agent) -> dict[str, Any]:
    return {
        "id": agent.id,
        "capabilities": agent.config.capabilities if hasattr(agent, "config") and hasattr(agent.config, "capabilities") else [],
        "is_main": agent.is_main if hasattr(agent, "is_main") else False,
    }


router = APIRouter()


@router.get("/delegated-tasks")
async def list_delegated_tasks(status: str = None, agent_id: str = None):
    """List all delegated tasks."""
    from horbot.agent.task_delegation import get_task_delegator

    delegator = get_task_delegator()
    if status == "pending":
        tasks = delegator.get_pending_tasks()
    elif status == "completed":
        tasks = delegator.get_completed_tasks()
    elif status == "failed":
        tasks = delegator.get_failed_tasks()
    else:
        tasks = list(delegator._delegated_tasks.values())

    if agent_id:
        tasks = [task for task in tasks if task.target_agent_id == agent_id or task.source_agent_id == agent_id]

    return {
        "tasks": [_serialize_delegated_task(task) for task in tasks],
        "summary": delegator.get_status_summary(),
    }


@router.get("/delegated-tasks/{task_id}")
async def get_delegated_task(task_id: str):
    """Get a specific delegated task."""
    from horbot.agent.task_delegation import get_task_delegator

    delegator = get_task_delegator()
    task = delegator.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return _serialize_delegated_task(task, include_context=True)


@router.post("/delegated-tasks")
async def create_delegated_task(request: DelegateTaskRequest):
    """Create a new delegated task."""
    from horbot.agent.task_delegation import get_task_delegator

    delegator = get_task_delegator()
    task_id = await delegator.delegate_task(
        description=request.description,
        target_agent_id=request.target_agent_id,
        source_agent_id=request.source_agent_id,
        context=request.context,
        priority=request.priority,
    )
    return {
        "task_id": task_id,
        "status": "created",
        "message": f"Task delegated to {request.target_agent_id}",
    }


@router.post("/delegated-tasks/{task_id}/complete")
async def complete_delegated_task(task_id: str, result: dict[str, Any]):
    """Mark a delegated task as completed."""
    from horbot.agent.task_delegation import get_task_delegator

    delegator = get_task_delegator()
    success = delegator.complete_task(task_id, result)
    if not success:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return {"status": "completed", "task_id": task_id}


@router.post("/delegated-tasks/{task_id}/fail")
async def fail_delegated_task(task_id: str, error: str):
    """Mark a delegated task as failed."""
    from horbot.agent.task_delegation import get_task_delegator

    delegator = get_task_delegator()
    success = delegator.fail_task(task_id, error)
    if not success:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return {"status": "failed", "task_id": task_id, "error": error}


@router.delete("/delegated-tasks/clear")
async def clear_completed_tasks():
    """Clear completed and failed tasks."""
    from horbot.agent.task_delegation import get_task_delegator

    delegator = get_task_delegator()
    return {
        "status": "success",
        "cleared_count": delegator.clear_completed(),
    }


@router.post("/tasks/analyze")
async def analyze_task(request: AnalyzeTaskRequest):
    """Analyze a task to determine requirements and best agent."""
    from horbot.agent.manager import get_agent_manager
    from horbot.agent.task_delegation import get_smart_router

    smart_router = get_smart_router()
    agent_manager = get_agent_manager()
    analysis = smart_router.analyze_task(request.description, request.context)
    agents_data = [_agent_router_data(agent) for agent in agent_manager.get_all_agents()]
    return {
        "analysis": analysis,
        "suggested_agent_id": smart_router.find_best_agent(analysis, agents_data),
    }


@router.post("/tasks/decompose")
async def decompose_task(request: AnalyzeTaskRequest):
    """Decompose a complex task into subtasks."""
    from horbot.agent.manager import get_agent_manager
    from horbot.agent.task_delegation import get_smart_router

    smart_router = get_smart_router()
    agent_manager = get_agent_manager()
    analysis = smart_router.analyze_task(request.description, request.context)
    agents_data = [_agent_router_data(agent) for agent in agent_manager.get_all_agents()]
    return {
        "original_task": request.description,
        "analysis": analysis,
        "subtasks": smart_router.decompose_task(request.description, analysis, agents_data),
    }


@router.get("/agents/{agent_id}/metrics")
async def get_agent_performance_metrics(agent_id: str):
    """Get performance metrics for a specific agent."""
    from horbot.agent.manager import get_agent_manager
    from horbot.agent.task_delegation import get_smart_router

    smart_router = get_smart_router()
    agent = get_agent_manager().get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return {
        "agent_id": agent_id,
        "metrics": smart_router.get_agent_metrics(agent_id),
    }


@router.get("/agents/metrics/all")
async def get_all_agents_metrics():
    """Get performance metrics for all agents."""
    from horbot.agent.task_delegation import get_smart_router

    return {"metrics": get_smart_router().get_all_metrics()}
