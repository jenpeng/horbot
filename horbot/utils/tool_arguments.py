"""Helpers for normalizing tool-call argument payloads."""

from typing import Any


def normalize_tool_arguments(arguments: Any) -> dict[str, Any]:
    """Coerce provider/tool-call argument payloads into a dict.

    Some providers occasionally emit list-shaped payloads such as:
    `[{"path": "..."}, {"command": "create"}]`.
    Merge dict items left-to-right so downstream permission checks and tool
    execution continue to see a normal object payload.
    """
    if arguments is None:
        return {}

    if isinstance(arguments, dict):
        return dict(arguments)

    if isinstance(arguments, list):
        merged: dict[str, Any] = {}
        saw_dict = False
        for item in arguments:
            if not isinstance(item, dict):
                return {"items": arguments}
            merged.update(item)
            saw_dict = True
        return merged if saw_dict else {}

    return {"value": arguments}
