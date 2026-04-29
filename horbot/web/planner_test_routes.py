"""Developer test routes for planner analysis and generation."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter


def create_planner_test_router(get_agent_loop: Callable[..., Any]) -> APIRouter:
    """Create developer-only planner test routes."""

    router = APIRouter()

    @router.post("/test-task-analysis")
    async def test_task_analysis(request: dict):
        """Test task complexity analysis."""
        from horbot.agent.planner.analyzer import TaskAnalyzer

        task = request.get("task", "")
        analysis = TaskAnalyzer().analyze(task)
        return {
            "task": task,
            "level": analysis.level.value,
            "score": analysis.score,
            "reasons": analysis.reasons,
            "needs_planning": analysis.needs_planning,
            "estimated_steps": analysis.estimated_steps,
            "suggested_mode": analysis.suggested_mode,
        }

    @router.post("/test-plan-generation")
    async def test_plan_generation(request: dict):
        """Test plan generation."""
        from horbot.agent.planner.generator import PlanGenerator

        task = request.get("task", "")
        agent_loop = await get_agent_loop()
        generator = PlanGenerator(provider=agent_loop.provider, model=agent_loop.model)

        try:
            result = await generator.generate(task=task, available_tools=agent_loop.tools.tool_names)
            if result.success and result.plan:
                return {
                    "success": True,
                    "plan": {
                        "id": result.plan.id,
                        "title": result.plan.title,
                        "description": result.plan.description,
                        "steps": [
                            {
                                "id": step.id,
                                "title": step.description[:100] if step.description else f"步骤 {index + 1}",
                                "description": step.description or "",
                                "tool_name": step.tool_name,
                            }
                            for index, step in enumerate(result.plan.steps)
                        ],
                    },
                    "raw_response": result.raw_response[:500] if result.raw_response else None,
                }
            return {
                "success": False,
                "error": result.error,
                "raw_response": result.raw_response[:500] if result.raw_response else None,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    return router
