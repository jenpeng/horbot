"""Memory and tool-audit API routes."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from loguru import logger

from horbot.config.loader import get_cached_config

_TOOL_AUDIT_BLOCK_EVENT_TYPES = {
    "tool_denied",
    "tool_confirmation_required",
    "tool_path_denied",
    "tool_cancelled",
}
_TOOL_AUDIT_OUTBOUND_TOOLS = {"message"}
_TOOL_AUDIT_RISK_KINDS = {"all", "blocked", "exec", "outbound", "error"}


def _resolve_agent_for_memory_request(agent_id: Optional[str] = None):
    from horbot.agent.manager import get_agent_manager

    agent_manager = get_agent_manager()
    if agent_id:
        agent = agent_manager.get_agent(agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        return agent
    return agent_manager.get_default_agent()


def _build_memory_store(agent_id: Optional[str] = None):
    from horbot.agent.memory import MemoryStore

    agent = _resolve_agent_for_memory_request(agent_id)
    if agent is not None:
        workspace_path = agent.get_workspace()
        return agent, workspace_path, MemoryStore(
            workspace=workspace_path,
            agent_id=agent.id,
            team_ids=agent.teams,
        )
    workspace_path = Path(get_cached_config().workspace_path)
    return agent, workspace_path, MemoryStore(workspace=workspace_path)


def _get_memory_roots(memory_store) -> tuple[Path, Path]:
    context_manager = getattr(memory_store, "_context_manager", None)
    if context_manager is not None:
        return (
            Path(context_manager.context_dir) / context_manager.MEMORIES_DIR,
            Path(context_manager.context_dir) / context_manager.EXECUTIONS_DIR,
        )
    base = Path(memory_store.memory_dir)
    return base, base.parent / "executions"


def _parse_tool_audit_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone().replace(tzinfo=None)
    return parsed


def _is_blocked_tool_audit(item: dict[str, Any]) -> bool:
    event_type = str((item.get("audit_event") or {}).get("event_type") or "").strip()
    return bool(item.get("guard_blocked")) or event_type in _TOOL_AUDIT_BLOCK_EVENT_TYPES


def _is_exec_tool_audit(item: dict[str, Any]) -> bool:
    return str(item.get("tool_name") or "").strip() == "exec"


def _is_outbound_tool_audit(item: dict[str, Any]) -> bool:
    tool_name = str(item.get("tool_name") or "").strip()
    return (
        tool_name in _TOOL_AUDIT_OUTBOUND_TOOLS
        or tool_name.startswith("web_")
        or tool_name.startswith("browser_")
    )


def _filter_tool_audits_by_window(items: list[dict[str, Any]], window_hours: int) -> list[dict[str, Any]]:
    cutoff = datetime.now() - timedelta(hours=window_hours)
    return [
        item
        for item in items
        if (timestamp := _parse_tool_audit_timestamp(item.get("timestamp"))) is not None and timestamp >= cutoff
    ]


def _build_tool_audit_summary(items: list[dict[str, Any]], window_hours: int) -> dict[str, Any]:
    recent_items = _filter_tool_audits_by_window(items, window_hours)
    return {
        "window_hours": window_hours,
        "total_count": len(recent_items),
        "blocked_count": sum(1 for item in recent_items if _is_blocked_tool_audit(item)),
        "error_count": sum(1 for item in recent_items if bool(item.get("error"))),
        "exec_count": sum(1 for item in recent_items if _is_exec_tool_audit(item)),
        "outbound_count": sum(1 for item in recent_items if _is_outbound_tool_audit(item)),
    }


def _matches_tool_audit_risk(item: dict[str, Any], risk_kind: str) -> bool:
    if risk_kind == "all":
        return True
    if risk_kind == "blocked":
        return _is_blocked_tool_audit(item)
    if risk_kind == "exec":
        return _is_exec_tool_audit(item)
    if risk_kind == "outbound":
        return _is_outbound_tool_audit(item)
    if risk_kind == "error":
        return bool(item.get("error"))
    return False


router = APIRouter()


@router.get("/memory")
async def get_memory_stats(agent_id: Optional[str] = None):
    """Get AI memory storage usage statistics."""
    try:
        agent, _, memory_store = _build_memory_store(agent_id)
        stats = memory_store.get_memory_stats()

        total_entries = 0
        total_size_bytes = 0
        oldest_entry = None
        newest_entry = None

        if stats.get("hierarchical"):
            hierarchical_stats = stats["hierarchical"]
            memories = hierarchical_stats.get("memories", {})

            for _level, level_stats in memories.items():
                total_entries += level_stats.get("count", 0)
                total_size_bytes += level_stats.get("total_size", 0)

            memory_dir, _ = _get_memory_roots(memory_store)

            all_files = []
            for level in ["L0", "L1", "L2"]:
                level_dir = memory_dir / level
                if level_dir.exists():
                    for f in level_dir.glob("*.md"):
                        if f.name != "README.md":
                            all_files.append((f, f.stat().st_mtime))

            if all_files:
                all_files.sort(key=lambda x: x[1])
                oldest_entry = datetime.fromtimestamp(all_files[0][1]).isoformat()
                newest_entry = datetime.fromtimestamp(all_files[-1][1]).isoformat()

        total_size_kb = total_size_bytes / 1024

        return {
            "agent_id": agent.id if agent is not None else None,
            "total_entries": total_entries,
            "total_size_kb": round(total_size_kb, 2),
            "oldest_entry": oldest_entry,
            "newest_entry": newest_entry,
            "details": stats,
        }
    except Exception as e:
        logger.error("Failed to get memory stats: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to get memory stats: {str(e)}")


@router.get("/memory/tool-audits")
async def get_tool_audit_events(
    agent_id: Optional[str] = None,
    session_key: Optional[str] = None,
    limit: int = 20,
    summary_window_hours: int = 24,
    window_hours: Optional[int] = None,
    risk_kind: str = "all",
):
    """Get recent tool audit events for an agent/session."""
    try:
        bounded_limit = max(1, min(limit, 100))
        bounded_window_hours = max(1, min(summary_window_hours, 168))
        bounded_list_window_hours = max(1, min(window_hours or bounded_window_hours, 168))
        normalized_risk_kind = str(risk_kind or "all").strip().lower()
        if normalized_risk_kind not in _TOOL_AUDIT_RISK_KINDS:
            raise HTTPException(status_code=400, detail=f"Unsupported risk_kind '{risk_kind}'.")
        agent, _, memory_store = _build_memory_store(agent_id)
        summary_scan_limit = max(200, bounded_limit * 5)
        recent_items = memory_store.get_execution_history(
            session_key=session_key,
            limit=summary_scan_limit,
            execution_type="tool_audit",
        )
        window_items = _filter_tool_audits_by_window(recent_items, bounded_list_window_hours)
        matched_items = [
            item for item in window_items
            if _matches_tool_audit_risk(item, normalized_risk_kind)
        ]
        items = matched_items[:bounded_limit]
        blocked_count = sum(1 for item in items if _is_blocked_tool_audit(item))
        error_count = sum(1 for item in items if bool(item.get("error")))
        return {
            "agent_id": agent.id if agent is not None else None,
            "session_key": session_key,
            "risk_kind": normalized_risk_kind,
            "window_hours": bounded_list_window_hours,
            "limit": bounded_limit,
            "total_returned": len(items),
            "total_matches": len(matched_items),
            "blocked_count": blocked_count,
            "error_count": error_count,
            "summary": _build_tool_audit_summary(recent_items, bounded_window_hours),
            "items": items,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get tool audit events: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to get tool audit events: {str(e)}")


@router.delete("/memory")
async def clear_memory(days: int = 30, agent_id: Optional[str] = None):
    """Clear expired memory data."""
    try:
        agent, _, memory_store = _build_memory_store(agent_id)
        memory_dir, executions_dir = _get_memory_roots(memory_store)

        deleted_count = 0
        freed_bytes = 0
        cutoff_time = datetime.now() - timedelta(days=days)

        for level in ["L0", "L1"]:
            level_dir = memory_dir / level
            if not level_dir.exists():
                continue

            for file_path in level_dir.glob("*.md"):
                if file_path.name == "README.md":
                    continue

                try:
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime < cutoff_time:
                        freed_bytes += file_path.stat().st_size
                        file_path.unlink()
                        deleted_count += 1
                        logger.info("Deleted expired memory: {}", file_path.name)
                except Exception as e:
                    logger.warning("Failed to delete memory {}: {}", file_path.name, e)

        archived_dir = executions_dir / "archived"
        if archived_dir.exists():
            for file_path in archived_dir.glob("*.json"):
                try:
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime < cutoff_time:
                        freed_bytes += file_path.stat().st_size
                        file_path.unlink()
                        deleted_count += 1
                        logger.info("Deleted archived execution: {}", file_path.name)
                except Exception as e:
                    logger.warning("Failed to delete execution {}: {}", file_path.name, e)

        freed_kb = freed_bytes / 1024

        return {
            "agent_id": agent.id if agent is not None else None,
            "deleted_count": deleted_count,
            "freed_kb": round(freed_kb, 2),
            "cutoff_days": days,
        }
    except Exception as e:
        logger.error("Failed to clear memory: {}", e)
        raise HTTPException(status_code=500, detail=f"Failed to clear memory: {str(e)}")
