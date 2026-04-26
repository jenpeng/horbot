#!/usr/bin/env python3
"""Audit legacy .horbot storage layout and optionally archive safe duplicates."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class DirComparison:
    source: Path
    target: Path
    source_files: int
    target_files: int
    source_bytes: int
    target_bytes: int
    only_source: list[str]
    only_target: list[str]
    differing: list[str]

    @property
    def is_source_empty(self) -> bool:
        return self.source_files == 0

    @property
    def is_exact_duplicate(self) -> bool:
        return not self.only_source and not self.only_target and not self.differing and self.source_files > 0

    @property
    def is_absorbed_subset(self) -> bool:
        return not self.only_source and not self.differing and self.source_files > 0 and bool(self.only_target)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("horbot_root", type=Path, help="Path to .horbot root")
    parser.add_argument(
        "--archive-safe-duplicates",
        action="store_true",
        help="Move safe legacy directories into .horbot/archives/path-cleanup-<timestamp>/",
    )
    return parser.parse_args()


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_directory(path: Path) -> tuple[dict[str, str], int]:
    files: dict[str, str] = {}
    total_bytes = 0
    if not path.exists():
        return files, total_bytes
    for file_path in sorted(p for p in path.rglob("*") if p.is_file()):
        rel = str(file_path.relative_to(path))
        files[rel] = file_digest(file_path)
        total_bytes += file_path.stat().st_size
    return files, total_bytes


def compare_dirs(source: Path, target: Path) -> DirComparison:
    source_files, source_bytes = snapshot_directory(source)
    target_files, target_bytes = snapshot_directory(target)
    only_source = sorted(set(source_files) - set(target_files))
    only_target = sorted(set(target_files) - set(source_files))
    differing = sorted(
        rel for rel in set(source_files) & set(target_files) if source_files[rel] != target_files[rel]
    )
    return DirComparison(
        source=source,
        target=target,
        source_files=len(source_files),
        target_files=len(target_files),
        source_bytes=source_bytes,
        target_bytes=target_bytes,
        only_source=only_source,
        only_target=only_target,
        differing=differing,
    )


def classify_agent(agent_dir: Path) -> dict[str, list[DirComparison]]:
    workspace_dir = agent_dir / "workspace"
    metadata_root = workspace_dir / ".horbot-agent"
    comparisons = {
        "exact_duplicates": [],
        "absorbed_subsets": [],
        "empty_legacy_dirs": [],
        "conflicts": [],
    }
    pairs = [
        (agent_dir / "memory", metadata_root / "memory"),
        (agent_dir / "sessions", metadata_root / "sessions"),
        (agent_dir / "skills", metadata_root / "skills"),
        (workspace_dir / "sessions", metadata_root / "sessions"),
        (workspace_dir / "skills", metadata_root / "skills"),
    ]
    for source, target in pairs:
        if not source.exists():
            continue
        result = compare_dirs(source, target)
        if result.is_source_empty:
            comparisons["empty_legacy_dirs"].append(result)
        elif result.is_exact_duplicate:
            comparisons["exact_duplicates"].append(result)
        elif result.is_absorbed_subset:
            comparisons["absorbed_subsets"].append(result)
        else:
            comparisons["conflicts"].append(result)
    return comparisons


def find_safe_legacy_paths(agent_dir: Path) -> list[Path]:
    """Return safe one-time migration leftovers that can be archived."""
    workspace_dir = agent_dir / "workspace"
    candidates = [
        workspace_dir / ".main-workspace-migration.json",
        workspace_dir / ".migration-backups",
    ]
    return [path for path in candidates if path.exists()]


def archive_paths(horbot_root: Path, paths: list[Path]) -> Path:
    archive_root = horbot_root / "archives" / f"path-cleanup-{datetime.now().strftime('%Y%m%dT%H%M%SZ')}"
    archive_root.mkdir(parents=True, exist_ok=True)
    for source in paths:
        rel = source.relative_to(horbot_root)
        target = archive_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
    return archive_root


def main() -> int:
    args = parse_args()
    horbot_root = args.horbot_root.expanduser().resolve()
    agents_root = horbot_root / "agents"
    report: dict[str, dict[str, list[dict[str, object]]]] = {}
    safe_archive_paths: list[Path] = []

    for agent_dir in sorted(p for p in agents_root.iterdir() if p.is_dir()):
        classified = classify_agent(agent_dir)
        agent_report: dict[str, list[dict[str, object]]] = {}
        for key, items in classified.items():
            serialized: list[dict[str, object]] = []
            for item in items:
                serialized.append(
                    {
                        "source": str(item.source),
                        "target": str(item.target),
                        "source_files": item.source_files,
                        "target_files": item.target_files,
                        "source_bytes": item.source_bytes,
                        "target_bytes": item.target_bytes,
                        "only_source": item.only_source,
                        "only_target": item.only_target,
                        "differing": item.differing,
                    }
                )
                if key in {"exact_duplicates", "absorbed_subsets", "empty_legacy_dirs"}:
                    safe_archive_paths.append(item.source)
            if serialized:
                agent_report[key] = serialized
        legacy_paths = find_safe_legacy_paths(agent_dir)
        if legacy_paths:
            agent_report["migration_leftovers"] = [
                {
                    "path": str(path),
                    "kind": "directory" if path.is_dir() else "file",
                }
                for path in legacy_paths
            ]
            safe_archive_paths.extend(legacy_paths)
        if agent_report:
            report[agent_dir.name] = agent_report

    archive_root = None
    if args.archive_safe_duplicates and safe_archive_paths:
        unique_paths = sorted(set(safe_archive_paths))
        archive_root = archive_paths(horbot_root, unique_paths)

    output = {
        "horbot_root": str(horbot_root),
        "agents": report,
        "safe_archive_count": len(set(safe_archive_paths)),
        "archive_root": str(archive_root) if archive_root else None,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
