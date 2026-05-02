"""Skill graph construction and persistence."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from horbot.agent.skill_package import MARKDOWN_LINK_PATTERN
from horbot.workspace.manager import AGENT_METADATA_DIRNAME

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_GENERIC_TOKENS = {
    "auto",
    "skill",
    "skills",
    "guide",
    "guides",
    "workflow",
    "workflows",
    "reference",
    "references",
    "checklist",
    "checklists",
    "pattern",
    "patterns",
    "helper",
    "helpers",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_skill_graph_path(workspace: Path) -> Path:
    return Path(workspace) / AGENT_METADATA_DIRNAME / "skill_graph.json"


def _extract_frontmatter(content: str) -> tuple[dict[str, str], str]:
    if not content.startswith("---"):
        return {}, content
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", content, re.DOTALL)
    if not match:
        return {}, content
    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip("\"'")
    return metadata, match.group(2)


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall(value.lower())
        if len(token) >= 3 and token not in _GENERIC_TOKENS
    }


def _similarity(left: str, right: str) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if len(left_tokens) < 2 or len(right_tokens) < 2:
        return 0.0
    overlap = left_tokens & right_tokens
    if len(overlap) < 2:
        return 0.0
    union = left_tokens | right_tokens
    if not union:
        return 0.0
    return round(len(overlap) / len(union), 3)


def _domain_prefix(skill_name: str) -> str:
    tokens = [token for token in _tokens(skill_name.replace("auto-", "", 1)) if token]
    if len(tokens) < 2:
        return ""
    return "-".join(tokens[:2])


def _reference_title(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip() or path.stem
    except Exception:
        pass
    return path.stem.replace("-", " ").replace("_", " ").title()


def _collect_reference_paths(skill_root: Path, content: str) -> set[Path]:
    resolved_skill_root = skill_root.resolve()
    reference_paths: set[Path] = set()
    references_dir = skill_root / "references"
    if references_dir.exists():
        reference_paths.update(ref for ref in references_dir.rglob("*.md") if ref.is_file())
    for raw_link in MARKDOWN_LINK_PATTERN.findall(content):
        target = raw_link.strip().split("#", 1)[0].split("?", 1)[0]
        if not target or target.startswith(("http://", "https://", "mailto:", "#")) or "://" in target:
            continue
        candidate = (skill_root / target).resolve()
        try:
            candidate.relative_to(resolved_skill_root)
        except ValueError:
            continue
        if candidate.exists() and candidate.is_file():
            reference_paths.add(candidate)
    return reference_paths


def _file_signature(path: Path) -> dict[str, Any] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return {
        "path": str(path),
        "mtime_ns": stat.st_mtime_ns,
        "size": stat.st_size,
    }


def build_skill_graph_fingerprint(skills: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a compact filesystem fingerprint for graph staleness checks."""
    files: dict[str, dict[str, Any]] = {}
    skill_count = 0
    reference_count = 0
    for skill in skills:
        path = Path(str(skill.get("path") or ""))
        if not path.exists():
            continue
        signature = _file_signature(path)
        if signature:
            files[signature["path"]] = signature
        skill_count += 1
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            content = ""
        skill_root = path.parent if path.name == "SKILL.md" else path.parent
        for reference_path in _collect_reference_paths(skill_root, content):
            reference_signature = _file_signature(reference_path)
            if reference_signature:
                files[reference_signature["path"]] = reference_signature
                reference_count += 1

    ordered_files = sorted(files.values(), key=lambda item: item["path"])
    latest_mtime_ns = max((int(item["mtime_ns"]) for item in ordered_files), default=0)
    return {
        "skill_count": skill_count,
        "reference_count": reference_count,
        "file_count": len(ordered_files),
        "latest_mtime_ns": latest_mtime_ns,
        "files": ordered_files,
    }


def is_skill_graph_stale(graph: dict[str, Any] | None, skills: list[dict[str, Any]]) -> bool:
    """Return true when a persisted graph no longer matches current skill files."""
    if not graph:
        return True
    current_fingerprint = build_skill_graph_fingerprint(skills)
    return graph.get("source_fingerprint") != current_fingerprint


def _source_origin_from_path(skill_path: Path, metadata: dict[str, str]) -> tuple[str, str, str | None]:
    if metadata.get("generated_by") == "skill-evolution":
        agent_id: str | None = None
        parts = list(skill_path.parts)
        if ".horbot" in parts and "agents" in parts:
            try:
                agents_index = parts.index("agents")
                agent_id = parts[agents_index + 1]
            except Exception:
                agent_id = None
        return "custom", "agent", agent_id
    return "custom", "manual", None


def build_skill_graph(
    *,
    workspace: Path,
    skills_dir: Path,
    skills: list[dict[str, Any]],
) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    descriptors: dict[str, str] = {}
    edge_ids: set[str] = set()
    source_fingerprint = build_skill_graph_fingerprint(skills)

    def add_edge(source: str, target: str, edge_type: str, confidence: float, reason: str) -> None:
        if source == target:
            return
        edge_id = f"{edge_type}:{source}->{target}"
        if edge_id in edge_ids:
            return
        edge_ids.add(edge_id)
        edges.append({
            "id": edge_id,
            "source": source,
            "target": target,
            "type": edge_type,
            "confidence": round(confidence, 3),
            "reason": reason,
        })

    for skill in sorted(skills, key=lambda item: str(item.get("name") or "")):
        name = str(skill.get("name") or "").strip()
        path = Path(str(skill.get("path") or ""))
        if not name or not path.exists():
            continue

        content = path.read_text(encoding="utf-8")
        metadata, body = _extract_frontmatter(content)
        description = metadata.get("description") or str(skill.get("description") or name)
        source_group = "system" if skill.get("source") == "builtin" else "custom"
        origin_kind = "builtin" if skill.get("source") == "builtin" else None
        origin_agent_id: str | None = None
        if origin_kind is None:
            source_group, origin_kind, origin_agent_id = _source_origin_from_path(path, metadata)

        node = {
            "id": name,
            "name": name,
            "kind": "skill",
            "source": skill.get("source") or "user",
            "source_group": source_group,
            "origin_kind": origin_kind,
            "origin_agent_id": origin_agent_id,
            "description": description,
            "path": str(path),
            "reference_count": 0,
            "updated_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
        }
        nodes.append(node)
        descriptors[name] = f"{name} {description} {body[:1200]}"

        skill_root = path.parent if path.name == "SKILL.md" else path.parent
        resolved_skill_root = skill_root.resolve()
        reference_paths = _collect_reference_paths(skill_root, content)

        node["reference_count"] = len(reference_paths)
        for reference_path in sorted(reference_paths):
            relative_reference_path = reference_path.resolve().relative_to(resolved_skill_root).as_posix()
            ref_id = f"{name}::{relative_reference_path}"
            nodes.append({
                "id": ref_id,
                "name": _reference_title(reference_path),
                "kind": "reference",
                "source": skill.get("source") or "user",
                "source_group": source_group,
                "origin_kind": origin_kind,
                "origin_agent_id": origin_agent_id,
                "description": f"Reference note for {name}",
                "path": str(reference_path),
                "reference_count": 0,
                "updated_at": datetime.fromtimestamp(reference_path.stat().st_mtime, timezone.utc).isoformat(),
            })
            add_edge(name, ref_id, "has_reference", 1.0, "Reference file is linked or stored under this skill family.")

    skill_nodes = [node for node in nodes if node["kind"] == "skill"]
    for index, left in enumerate(skill_nodes):
        for right in skill_nodes[index + 1:]:
            left_id = left["id"]
            right_id = right["id"]
            score = _similarity(descriptors.get(left_id, ""), descriptors.get(right_id, ""))
            if score >= 0.28:
                reason = "Skill names, descriptions, or reference summaries share multiple meaningful terms."
                add_edge(left_id, right_id, "similar_to", score, reason)
                add_edge(right_id, left_id, "similar_to", score, reason)
                continue

            left_prefix = _domain_prefix(left_id)
            right_prefix = _domain_prefix(right_id)
            if left_prefix and left_prefix == right_prefix:
                reason = f"Both skills share the `{left_prefix}` domain prefix."
                add_edge(left_id, right_id, "related_to", 0.62, reason)
                add_edge(right_id, left_id, "related_to", 0.62, reason)

    return {
        "version": 1,
        "generated_at": _now_iso(),
        "workspace": str(Path(workspace)),
        "skills_dir": str(Path(skills_dir)),
        "source_fingerprint": source_fingerprint,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
    }


def save_skill_graph(graph: dict[str, Any], *, workspace: Path) -> Path:
    path = resolve_skill_graph_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def refresh_skill_graph_safely(
    *,
    workspace: Path,
    skills_dir: Path,
    agent_id: str | None = None,
    reason: str = "skill_change",
) -> dict[str, Any] | None:
    """Rebuild the persisted skill graph without blocking the caller on failure."""
    try:
        from horbot.agent.skills import SkillsLoader

        loader = SkillsLoader(workspace=workspace, agent_id=agent_id, skills_dir=skills_dir)
        skills = loader.list_skills(filter_unavailable=False, include_disabled=True)
        graph = build_skill_graph(workspace=workspace, skills_dir=skills_dir, skills=skills)
        path = save_skill_graph(graph, workspace=workspace)
        graph["persisted"] = True
        graph["path"] = str(path)
        logger.debug(
            "Refreshed skill graph after {} for agent_id={} nodes={} edges={}",
            reason,
            agent_id or "main",
            graph["node_count"],
            graph["edge_count"],
        )
        return graph
    except Exception as exc:
        logger.warning(
            "Failed to refresh skill graph after {} for agent_id={}: {}",
            reason,
            agent_id or "main",
            exc,
        )
        return None


def load_skill_graph(*, workspace: Path) -> dict[str, Any] | None:
    path = resolve_skill_graph_path(workspace)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def build_skill_graph_runtime_hints(
    graph: dict[str, Any] | None,
    *,
    max_references_per_skill: int = 3,
    max_related_per_skill: int = 3,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Build compact graph hints for prompt-time skill discovery.

    The runtime prompt should point the agent to relevant local files, not inline
    the whole graph or reference contents.
    """
    if not graph:
        return {}

    nodes = {
        str(node.get("id")): node
        for node in graph.get("nodes", [])
        if isinstance(node, dict) and node.get("id")
    }
    skill_ids = {
        node_id
        for node_id, node in nodes.items()
        if node.get("kind") == "skill"
    }
    hints: dict[str, dict[str, list[dict[str, Any]]]] = {
        skill_id: {"references": [], "related": []}
        for skill_id in skill_ids
    }

    relationship_rank = {
        "depends_on": 0,
        "composes_with": 1,
        "supersedes": 2,
        "similar_to": 3,
        "related_to": 4,
    }

    for edge in graph.get("edges", []):
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        edge_type = str(edge.get("type") or "")
        if source not in skill_ids or not target:
            continue

        target_node = nodes.get(target)
        if edge_type == "has_reference" and target_node and target_node.get("kind") == "reference":
            references = hints[source]["references"]
            if len(references) < max_references_per_skill:
                references.append({
                    "name": target_node.get("name") or target,
                    "path": target_node.get("path") or "",
                    "reason": edge.get("reason") or "",
                })
            continue

        if edge_type in relationship_rank and target in skill_ids:
            hints[source]["related"].append({
                "name": target,
                "type": edge_type,
                "confidence": float(edge.get("confidence") or 0),
                "reason": edge.get("reason") or "",
                "_rank": relationship_rank[edge_type],
            })

    for skill_hint in hints.values():
        skill_hint["related"] = [
            {key: value for key, value in related.items() if key != "_rank"}
            for related in sorted(
                skill_hint["related"],
                key=lambda item: (item["_rank"], -float(item.get("confidence") or 0), item["name"]),
            )[:max_related_per_skill]
        ]

    return {
        skill_name: hint
        for skill_name, hint in hints.items()
        if hint["references"] or hint["related"]
    }
