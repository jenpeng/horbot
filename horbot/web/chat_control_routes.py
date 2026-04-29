"""Chat control API routes."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel


class ConfirmRequest(BaseModel):
    confirmation_id: str
    action: str
    session_key: str = "default"


class StopRequest(BaseModel):
    request_id: str


def create_chat_control_router(
    *,
    get_config: Callable[[], Any],
    get_stream_manager_fn: Callable[[], Any],
    get_session_manager_fn: Callable[[], Any],
    get_agent_loop_fn: Callable[[], Awaitable[Any]],
) -> APIRouter:
    """Create chat control routes."""

    router = APIRouter()

    @router.get("/chat/health")
    async def chat_health_check():
        """Health check endpoint for chat service."""
        config = get_config()
        provider_config = config.get_provider() if config else None

        return {
            "status": "healthy",
            "provider_configured": provider_config is not None and provider_config.api_key is not None,
            "active_streams": len(get_stream_manager_fn()._streams),
            "timestamp": datetime.now().isoformat(),
        }

    @router.post("/chat/stop")
    async def stop_chat_generation(request: StopRequest):
        """Stop an ongoing chat generation."""
        request_id = request.request_id
        stream_manager = get_stream_manager_fn()

        if not stream_manager.exists(request_id):
            logger.info("[ChatAPI][{}] Stop requested for inactive stream", request_id)
            return {"status": "success", "message": "Request already completed"}

        success = await stream_manager.cancel(request_id)
        if success:
            return {"status": "success", "message": "Stop signal sent"}

        logger.info("[ChatAPI][{}] Stop requested after stream completed", request_id)
        return {"status": "success", "message": "Request already completed"}

    @router.post("/chat/confirm")
    async def confirm_tool_execution(request: ConfirmRequest):
        """Confirm or cancel a pending tool execution."""
        session_manager = get_session_manager_fn()
        session = session_manager.get_or_create(request.session_key)

        pending_confirmations = getattr(session, "_pending_confirmations", {})

        if request.confirmation_id not in pending_confirmations:
            raise HTTPException(status_code=404, detail="Confirmation not found or expired")

        conf = pending_confirmations.pop(request.confirmation_id)

        if request.action == "cancel":
            session_manager.save(session)
            return {
                "status": "cancelled",
                "message": f"Tool `{conf['tool_name']}` execution cancelled.",
                "tool_name": conf["tool_name"],
            }

        if request.action == "confirm":
            agent_loop = await get_agent_loop_fn()

            try:
                with agent_loop.tools.audit_context(
                    session_key=request.session_key,
                    origin="web_confirm",
                    source_channel="web",
                    source_chat_id=request.session_key,
                ):
                    result = await agent_loop.tools.execute_confirmed(conf["tool_name"], conf["arguments"])

                messages = conf["messages"]
                from horbot.agent.context import ContextBuilder

                context = ContextBuilder(Path(session_manager.workspace))
                messages = context.add_tool_result(
                    messages,
                    conf["tool_call_id"],
                    conf["tool_name"],
                    result,
                )

                final_content, _, all_msgs, new_confirmations = await agent_loop._run_agent_loop(
                    messages,
                    pending_confirmations=pending_confirmations,
                    session_key=request.session_key,
                )

                if new_confirmations:
                    session._pending_confirmations = new_confirmations

                for msg in all_msgs[len(messages):]:
                    if msg.get("role") == "assistant":
                        session.add_message("assistant", msg.get("content", ""), dedup=True)

                session_manager.save(session)

                return {
                    "status": "confirmed",
                    "result": result,
                    "final_content": final_content,
                    "tool_name": conf["tool_name"],
                }
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Tool execution failed: {str(exc)}")

        raise HTTPException(status_code=400, detail="Invalid action. Use 'confirm' or 'cancel'.")

    return router
