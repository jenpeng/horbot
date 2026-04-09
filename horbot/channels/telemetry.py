"""Channel endpoint telemetry shared across processes via runtime files."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime
import json
from threading import Lock
from typing import Any

from horbot.utils.helpers import safe_filename
from horbot.utils.paths import get_runtime_dir

_EVENTS: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=100))
_SUMMARY: dict[str, dict[str, Any]] = defaultdict(dict)
_LOCK = Lock()
_MAX_EVENTS = 100


def _telemetry_dir():
    path = get_runtime_dir() / "channels" / "telemetry"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _telemetry_file(endpoint_id: str):
    return _telemetry_dir() / f"{safe_filename(endpoint_id)}.json"


def _base_summary(endpoint_id: str) -> dict[str, Any]:
    return {
        "endpoint_id": endpoint_id,
        "messages_sent": 0,
        "messages_received": 0,
        "errors": 0,
        "last_event_at": None,
        "last_event_type": None,
        "last_status": None,
        "last_message": None,
        "last_inbound_at": None,
        "last_outbound_at": None,
        "last_error_at": None,
        "last_error_message": None,
    }


def _load_persisted_payload(endpoint_id: str) -> dict[str, Any]:
    path = _telemetry_file(endpoint_id)
    if not path.exists():
        return {"summary": _base_summary(endpoint_id), "events": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"summary": _base_summary(endpoint_id), "events": []}

    summary = _base_summary(endpoint_id)
    summary.update(payload.get("summary") or {})
    events = payload.get("events")
    if not isinstance(events, list):
        events = []
    return {"summary": summary, "events": events[:_MAX_EVENTS]}


def _persist_payload(endpoint_id: str, *, summary: dict[str, Any], events: list[dict[str, Any]]) -> None:
    path = _telemetry_file(endpoint_id)
    payload = {
        "summary": summary,
        "events": events[:_MAX_EVENTS],
    }
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)


def _sync_in_memory(endpoint_id: str, summary: dict[str, Any], events: list[dict[str, Any]]) -> None:
    _SUMMARY[endpoint_id] = dict(summary)
    _EVENTS[endpoint_id] = deque(events[:_MAX_EVENTS], maxlen=_MAX_EVENTS)


def record_channel_event(
    endpoint_id: str,
    *,
    channel_type: str,
    event_type: str,
    status: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Record a channel lifecycle or traffic event."""
    if not endpoint_id:
        return

    now = datetime.now().isoformat()
    event = {
        "timestamp": now,
        "endpoint_id": endpoint_id,
        "channel_type": channel_type,
        "event_type": event_type,
        "status": status,
        "message": message,
        "details": details or {},
    }

    with _LOCK:
        persisted = _load_persisted_payload(endpoint_id)
        events = list(persisted.get("events") or [])
        events.insert(0, event)
        events = events[:_MAX_EVENTS]
        summary = dict(_base_summary(endpoint_id))
        summary.update(persisted.get("summary") or {})
        summary.update({
            "endpoint_id": endpoint_id,
            "channel_type": channel_type,
            "last_event_at": now,
            "last_event_type": event_type,
            "last_status": status,
            "last_message": message,
        })
        if event_type == "inbound" and status == "ok":
            summary["messages_received"] = int(summary.get("messages_received", 0)) + 1
            summary["last_inbound_at"] = now
        if event_type == "outbound" and status == "ok":
            summary["messages_sent"] = int(summary.get("messages_sent", 0)) + 1
            summary["last_outbound_at"] = now
        if status == "error":
            summary["errors"] = int(summary.get("errors", 0)) + 1
            summary["last_error_at"] = now
            summary["last_error_message"] = message
        _persist_payload(endpoint_id, summary=summary, events=events)
        _sync_in_memory(endpoint_id, summary, events)


def get_channel_events(endpoint_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Return recent events for one endpoint."""
    with _LOCK:
        persisted = _load_persisted_payload(endpoint_id)
        _sync_in_memory(endpoint_id, persisted["summary"], persisted["events"])
        return list(persisted["events"])[:limit]


def get_channel_summary(endpoint_id: str) -> dict[str, Any]:
    """Return aggregate summary for one endpoint."""
    with _LOCK:
        persisted = _load_persisted_payload(endpoint_id)
        _sync_in_memory(endpoint_id, persisted["summary"], persisted["events"])
        base = _base_summary(endpoint_id)
        base.update(persisted["summary"])
        return base


def clear_channel_telemetry(endpoint_id: str | None = None) -> None:
    """Clear telemetry for one endpoint or all endpoints."""
    with _LOCK:
        if endpoint_id is None:
            _EVENTS.clear()
            _SUMMARY.clear()
            telemetry_dir = _telemetry_dir()
            for path in telemetry_dir.glob("*.json"):
                path.unlink(missing_ok=True)
            return
        _EVENTS.pop(endpoint_id, None)
        _SUMMARY.pop(endpoint_id, None)
        _telemetry_file(endpoint_id).unlink(missing_ok=True)
