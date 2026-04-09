"""Adapters for external skill metadata schemas."""

from __future__ import annotations

import json
from typing import Any

CANONICAL_SCHEMA = "horbot"
CANONICAL_SCHEMA_VERSION = 1
LEGACY_SCHEMA_VERSIONS = {
    "openclaw": 1,
}
KNOWN_METADATA_KEYS = {
    "always",
    "emoji",
    "enabled",
    "install",
    "os",
    "requires",
}


def _as_metadata_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _coerce_schema_version(value: Any, fallback: int | None) -> int | None:
    if value is None or value == "":
        return fallback
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _build_canonical_metadata(
    payload: dict[str, Any],
    *,
    source_schema: str,
    source_schema_version: int | None,
) -> dict[str, Any]:
    metadata = dict(payload)
    metadata["_compat"] = {
        "source_schema": source_schema,
        "source_schema_version": source_schema_version,
        "canonical_schema": CANONICAL_SCHEMA,
        "canonical_schema_version": CANONICAL_SCHEMA_VERSION,
        "normalized_from_legacy": source_schema not in {CANONICAL_SCHEMA, "unscoped"},
    }
    return metadata


def parse_skill_metadata(raw: str) -> dict[str, Any]:
    """Parse skill metadata JSON into Horbot's canonical shape."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}

    if not isinstance(data, dict):
        return {}

    scoped_schema = data.get("schema")
    scoped_metadata = _as_metadata_dict(data.get("metadata"))
    if isinstance(scoped_schema, str) and scoped_metadata:
        source_schema = scoped_schema.strip().lower() or CANONICAL_SCHEMA
        fallback_version = LEGACY_SCHEMA_VERSIONS.get(source_schema, CANONICAL_SCHEMA_VERSION)
        return _build_canonical_metadata(
            scoped_metadata,
            source_schema=source_schema,
            source_schema_version=_coerce_schema_version(data.get("schema_version"), fallback_version),
        )

    horbot_meta = _as_metadata_dict(data.get(CANONICAL_SCHEMA))
    if horbot_meta:
        return _build_canonical_metadata(
            horbot_meta,
            source_schema=CANONICAL_SCHEMA,
            source_schema_version=_coerce_schema_version(data.get("horbot_schema_version"), CANONICAL_SCHEMA_VERSION),
        )

    for schema, default_version in LEGACY_SCHEMA_VERSIONS.items():
        legacy_meta = _as_metadata_dict(data.get(schema))
        if legacy_meta:
            return _build_canonical_metadata(
                legacy_meta,
                source_schema=schema,
                source_schema_version=_coerce_schema_version(data.get(f"{schema}_schema_version"), default_version),
            )

    if any(key in data for key in KNOWN_METADATA_KEYS):
        return _build_canonical_metadata(
            data,
            source_schema="unscoped",
            source_schema_version=None,
        )

    return {}
