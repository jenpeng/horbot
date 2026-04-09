"""Skill package validation, compatibility, and import helpers."""

from __future__ import annotations

import io
import os
import platform
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

from horbot.agent.skill_metadata_adapter import parse_skill_metadata

SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
ALLOWED_TOP_LEVEL_NAMES = {"SKILL.md", "agents", "scripts", "references", "assets"}


def _extract_frontmatter(content: str) -> tuple[dict[str, str], str]:
    if not content.startswith("---"):
        return {}, content

    match = re.match(r"^---\n(.*?)\n---\n?(.*)$", content, re.DOTALL)
    if not match:
        return {}, content

    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip("\"'")
    return metadata, match.group(2)


def _current_os() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "darwin"
    if system == "linux":
        return "linux"
    if system.startswith("win"):
        return "windows"
    return system


def validate_skill_content(
    content: str,
    *,
    expected_name: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []

    frontmatter, body = _extract_frontmatter(content)
    if not frontmatter:
        issues.append("SKILL.md is missing YAML frontmatter.")
        return {
            "valid": False,
            "issues": issues,
            "warnings": warnings,
            "metadata": {},
            "skill_name": expected_name or "",
            "description": "",
            "meta": {},
        }

    skill_name = (frontmatter.get("name") or expected_name or "").strip()
    description = (frontmatter.get("description") or "").strip()

    if not skill_name:
        issues.append("SKILL.md frontmatter must include a non-empty 'name'.")
    elif not SKILL_NAME_PATTERN.match(skill_name):
        issues.append("Skill name must use lowercase letters, numbers, '-' or '_', and be 2-64 characters long.")

    if expected_name and skill_name and skill_name != expected_name:
        issues.append(f"Skill name '{skill_name}' does not match expected name '{expected_name}'.")

    if not description:
        issues.append("SKILL.md frontmatter must include a non-empty 'description'.")

    if not body.strip():
        issues.append("SKILL.md body cannot be empty.")

    meta = parse_skill_metadata(frontmatter.get("metadata", ""))
    if frontmatter.get("metadata") and not meta:
        warnings.append("Skill metadata is present but could not be parsed into canonical horbot metadata.")

    if root is not None:
        for raw_target in MARKDOWN_LINK_PATTERN.findall(content):
            target = raw_target.strip()
            if (
                not target
                or target.startswith(("http://", "https://", "mailto:", "#"))
                or "://" in target
            ):
                continue
            target_path = (root / target).resolve()
            try:
                target_path.relative_to(root.resolve())
            except ValueError:
                issues.append(f"Relative reference '{target}' escapes the skill package root.")
                continue
            if not target_path.exists():
                issues.append(f"Referenced file '{target}' does not exist in the skill package.")

    return {
        "valid": not issues,
        "issues": issues,
        "warnings": warnings,
        "metadata": frontmatter,
        "skill_name": skill_name,
        "description": description,
        "meta": meta,
    }


def _resolve_skill_root(extracted_root: Path) -> tuple[Path | None, list[str]]:
    candidates = []
    if (extracted_root / "SKILL.md").exists():
        candidates.append(extracted_root)
    candidates.extend(path.parent for path in extracted_root.glob("*/SKILL.md"))

    unique_candidates: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_candidates.append(candidate)

    if not unique_candidates:
        return None, ["Package does not contain a SKILL.md file at the root or in a single top-level folder."]
    if len(unique_candidates) > 1:
        return None, ["Package contains multiple candidate skill roots. A .skill/.zip package must contain exactly one skill."]
    return unique_candidates[0], []


def validate_skill_directory(root: Path, *, expected_name: str | None = None) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []

    skill_file = root / "SKILL.md"
    if not skill_file.exists():
        issues.append("Skill package is missing SKILL.md.")
        return {
            "valid": False,
            "issues": issues,
            "warnings": warnings,
            "skill_name": expected_name or root.name,
            "description": "",
            "metadata": {},
            "meta": {},
            "files": [],
        }

    for child in root.iterdir():
        if child.name not in ALLOWED_TOP_LEVEL_NAMES:
            warnings.append(f"Unexpected top-level entry '{child.name}' is not part of the standard skill layout.")

    if (root / "agents").exists() and not (root / "agents" / "openai.yaml").exists():
        warnings.append("agents/ exists without agents/openai.yaml; UI metadata may be incomplete.")

    relative_files = sorted(
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file()
    )

    content_validation = validate_skill_content(
        skill_file.read_text(encoding="utf-8"),
        expected_name=expected_name or root.name,
        root=root,
    )
    issues.extend(content_validation["issues"])
    warnings.extend(content_validation["warnings"])

    return {
        "valid": not issues,
        "issues": issues,
        "warnings": warnings,
        "skill_name": content_validation["skill_name"] or root.name,
        "description": content_validation["description"],
        "metadata": content_validation["metadata"],
        "meta": content_validation["meta"],
        "files": relative_files,
    }


def validate_skill_archive_bytes(data: bytes, filename: str) -> dict[str, Any]:
    issues: list[str] = []

    suffix = Path(filename).suffix.lower()
    if suffix not in {".skill", ".zip"}:
        return {
            "valid": False,
            "issues": ["Only .skill and .zip files are supported for skill imports."],
            "warnings": [],
            "skill_name": "",
            "description": "",
            "metadata": {},
            "meta": {},
            "files": [],
        }

    try:
        with ZipFile(io.BytesIO(data)) as archive:
            names = [name for name in archive.namelist() if name and not name.endswith("/")]
            if not names:
                return {
                    "valid": False,
                    "issues": ["Skill archive is empty."],
                    "warnings": [],
                    "skill_name": "",
                    "description": "",
                    "metadata": {},
                    "meta": {},
                    "files": [],
                }

            for info in archive.infolist():
                name = info.filename
                if not name or name.endswith("/"):
                    continue
                path = Path(name)
                if path.is_absolute() or ".." in path.parts:
                    issues.append(f"Archive entry '{name}' is not safe to extract.")
                unix_mode = (info.external_attr >> 16) & 0o170000
                if unix_mode == 0o120000:
                    issues.append(f"Archive entry '{name}' is a symbolic link, which is not allowed.")
            if issues:
                return {
                    "valid": False,
                    "issues": issues,
                    "warnings": [],
                    "skill_name": "",
                    "description": "",
                    "metadata": {},
                    "meta": {},
                    "files": [],
                }

            with tempfile.TemporaryDirectory() as tmpdir:
                extracted_root = Path(tmpdir)
                archive.extractall(extracted_root)
                package_root, root_issues = _resolve_skill_root(extracted_root)
                if root_issues:
                    return {
                        "valid": False,
                        "issues": root_issues,
                        "warnings": [],
                        "skill_name": "",
                        "description": "",
                        "metadata": {},
                        "meta": {},
                        "files": [],
                    }
                return validate_skill_directory(package_root)
    except BadZipFile:
        return {
            "valid": False,
            "issues": ["Uploaded file is not a valid zip archive."],
            "warnings": [],
            "skill_name": "",
            "description": "",
            "metadata": {},
            "meta": {},
            "files": [],
        }


def import_skill_archive_bytes(
    data: bytes,
    filename: str,
    *,
    skills_dir: Path,
    replace_existing: bool = False,
) -> dict[str, Any]:
    validation = validate_skill_archive_bytes(data, filename)
    if not validation["valid"]:
        return validation

    skill_name = validation["skill_name"]
    target_dir = skills_dir / skill_name
    if target_dir.exists():
        if not replace_existing:
            return {
                **validation,
                "valid": False,
                "issues": [f"Skill '{skill_name}' already exists. Re-import with replace enabled to overwrite it."],
            }
        shutil.rmtree(target_dir)

    with tempfile.TemporaryDirectory() as tmpdir:
        extracted_root = Path(tmpdir)
        with ZipFile(io.BytesIO(data)) as archive:
            archive.extractall(extracted_root)
        package_root, root_issues = _resolve_skill_root(extracted_root)
        if root_issues or package_root is None:
            return {
                **validation,
                "valid": False,
                "issues": root_issues or ["Failed to resolve skill root during import."],
            }
        shutil.copytree(package_root, target_dir)

    return {
        **validation,
        "path": str(target_dir / "SKILL.md"),
    }


def build_skill_compatibility(
    *,
    meta: dict[str, Any],
    normalized_from_legacy: bool = False,
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []

    current_os = _current_os()
    allowed_os = [str(item).lower() for item in (meta.get("os") or []) if str(item).strip()]
    if allowed_os and current_os not in allowed_os:
        issues.append(f"OS mismatch: current host is {current_os}, but the skill declares support for {', '.join(allowed_os)}.")

    requires = meta.get("requires", {}) or {}
    for binary in requires.get("bins", []):
        if not shutil.which(binary):
            issues.append(f"Missing CLI dependency: {binary}")
    for env_var in requires.get("env", []):
        if not os.environ.get(env_var):
            issues.append(f"Missing environment variable: {env_var}")

    if normalized_from_legacy:
        warnings.append("This skill uses legacy metadata and was normalized to the horbot schema.")

    status = "compatible"
    if issues:
        status = "incompatible"
    elif warnings:
        status = "warning"

    return {
        "status": status,
        "issues": issues,
        "warnings": warnings,
    }
