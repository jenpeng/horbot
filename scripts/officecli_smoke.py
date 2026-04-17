#!/usr/bin/env python3
"""Smoke test for direct OfficeCLI document operations."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def load_officecli_helper():
    """Load the OfficeCLI helper without importing horbot.config package side effects."""
    helper_path = PROJECT_ROOT / "horbot" / "config" / "officecli.py"
    spec = importlib.util.spec_from_file_location("horbot_config_officecli_helper", helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load OfficeCLI helper from {helper_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    return module


detect_officecli_command = load_officecli_helper().detect_officecli_command


@dataclass
class StepResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def combined_output(self) -> str:
        parts = [self.stdout.strip(), self.stderr.strip()]
        return "\n".join(part for part in parts if part)


def _coerce_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


@dataclass
class ScenarioResult:
    name: str
    ok: bool = False
    file_path: str = ""
    steps: list[StepResult] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def run_command(args: Sequence[str]) -> StepResult:
    try:
        completed = subprocess.run(
            list(args),
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        return StepResult(
            command=list(args),
            returncode=completed.returncode,
            stdout=_coerce_text(completed.stdout),
            stderr=_coerce_text(completed.stderr),
        )
    except subprocess.TimeoutExpired as exc:
        return StepResult(
            command=list(args),
            returncode=124,
            stdout=_coerce_text(exc.stdout),
            stderr=_coerce_text(exc.stderr) + "\nCommand timed out after 30s.",
        )


def record_step(
    result: ScenarioResult,
    step: StepResult,
    *,
    allow_timeout_if_contains: str | None = None,
) -> str:
    result.steps.append(step)
    output = step.combined_output
    timeout_is_acceptable = (
        step.returncode == 124
        and allow_timeout_if_contains is not None
        and allow_timeout_if_contains in output
    )
    if step.returncode != 0 and not timeout_is_acceptable:
        result.errors.append(f"command failed: {' '.join(step.command)}")
        if output:
            result.errors.append(output)
    return output


def require_contains(result: ScenarioResult, key: str, haystack: str, needle: str) -> None:
    matched = needle in haystack
    result.checks[key] = matched
    if not matched:
        result.errors.append(f"missing expected output for {key}: {needle}")


def smoke_docx(officecli: str, root: Path) -> ScenarioResult:
    result = ScenarioResult(name="docx")
    file_path = root / "officecli_smoke.docx"
    result.file_path = str(file_path)

    create = run_command([officecli, "create", str(file_path)])
    create_output = record_step(
        result,
        create,
        allow_timeout_if_contains=f"Created: {file_path}",
    )
    require_contains(result, "create", create_output, f"Created: {file_path}")

    add_paragraph = run_command([officecli, "add", str(file_path), "/body", "--type", "paragraph", "--index", "0"])
    add_paragraph_output = record_step(result, add_paragraph)
    require_contains(result, "add_paragraph", add_paragraph_output, "Added paragraph")

    add_run = run_command(
        [officecli, "add", str(file_path), "/body/p[1]", "--type", "run", "--prop", "text=OfficeCLI Smoke", "--prop", "bold=true"]
    )
    add_run_output = record_step(result, add_run)
    require_contains(result, "add_run", add_run_output, "Added run")

    view = run_command([officecli, "view", str(file_path), "outline"])
    view_output = record_step(result, view)
    require_contains(result, "view_outline", view_output, "1 paragraphs")

    validate = run_command([officecli, "validate", str(file_path)])
    validate_output = record_step(result, validate)
    require_contains(result, "validate", validate_output, "Validation passed")

    result.ok = not result.errors and file_path.exists()
    return result


def smoke_xlsx(officecli: str, root: Path) -> ScenarioResult:
    result = ScenarioResult(name="xlsx")
    file_path = root / "officecli_smoke.xlsx"
    result.file_path = str(file_path)

    create = run_command([officecli, "create", str(file_path)])
    create_output = record_step(
        result,
        create,
        allow_timeout_if_contains=f"Created: {file_path}",
    )
    require_contains(result, "create", create_output, f"Created: {file_path}")

    add_sheet = run_command([officecli, "add", str(file_path), "/workbook", "--type", "sheet", "--prop", "name=Validation"])
    add_sheet_output = record_step(result, add_sheet)
    require_contains(result, "add_sheet", add_sheet_output, "Added sheet")

    set_a1 = run_command(
        [officecli, "set", str(file_path), "/Validation/A1", "--prop", "value=OfficeCLI Smoke", "--prop", "font.color=FF0000"]
    )
    set_a1_output = record_step(result, set_a1)
    require_contains(result, "set_a1", set_a1_output, "Updated /Validation/A1")

    set_a2 = run_command([officecli, "set", str(file_path), "/Validation/A2", "--prop", "value=Spreadsheet smoke row"])
    set_a2_output = record_step(result, set_a2)
    require_contains(result, "set_a2", set_a2_output, "Updated /Validation/A2")

    view = run_command([officecli, "view", str(file_path), "text", "--max-lines", "10"])
    view_output = record_step(result, view)
    require_contains(result, "view_text_a1", view_output, "OfficeCLI Smoke")
    require_contains(result, "view_text_a2", view_output, "Spreadsheet smoke row")

    validate = run_command([officecli, "validate", str(file_path)])
    validate_output = record_step(result, validate)
    require_contains(result, "validate", validate_output, "Validation passed")

    result.ok = not result.errors and file_path.exists()
    return result


def smoke_pptx(officecli: str, root: Path) -> ScenarioResult:
    result = ScenarioResult(name="pptx")
    file_path = root / "officecli_smoke.pptx"
    result.file_path = str(file_path)

    create = run_command([officecli, "create", str(file_path)])
    create_output = record_step(
        result,
        create,
        allow_timeout_if_contains=f"Created: {file_path}",
    )
    require_contains(result, "create", create_output, f"Created: {file_path}")

    add_slide = run_command([officecli, "add", str(file_path), "/", "--type", "slide"])
    add_slide_output = record_step(result, add_slide)
    require_contains(result, "add_slide", add_slide_output, "Added slide")

    add_title = run_command(
        [
            officecli,
            "add",
            str(file_path),
            "/slide[1]",
            "--type",
            "textbox",
            "--prop",
            "text=OfficeCLI Smoke",
            "--prop",
            "x=1cm",
            "--prop",
            "y=1cm",
            "--prop",
            "width=10cm",
            "--prop",
            "height=2cm",
            "--prop",
            "size=28pt",
            "--prop",
            "bold=true",
        ]
    )
    add_title_output = record_step(result, add_title)
    require_contains(result, "add_title", add_title_output, "Added textbox")

    add_body = run_command(
        [
            officecli,
            "add",
            str(file_path),
            "/slide[1]",
            "--type",
            "textbox",
            "--prop",
            "text=PowerPoint smoke body",
            "--prop",
            "x=1cm",
            "--prop",
            "y=4cm",
            "--prop",
            "width=16cm",
            "--prop",
            "height=3cm",
            "--prop",
            "size=18pt",
        ]
    )
    add_body_output = record_step(result, add_body)
    require_contains(result, "add_body", add_body_output, "Added textbox")

    view = run_command([officecli, "view", str(file_path), "outline"])
    view_output = record_step(result, view)
    require_contains(result, "view_outline_slides", view_output, "1 slides")
    require_contains(result, "view_outline_shapes", view_output, "2 text box(es)")

    validate = run_command([officecli, "validate", str(file_path)])
    validate_output = record_step(result, validate)
    require_contains(result, "validate", validate_output, "Validation passed")

    result.ok = not result.errors and file_path.exists()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run direct OfficeCLI smoke tests.")
    parser.add_argument("--json", action="store_true", help="Print JSON summary.")
    parser.add_argument("--keep-temp", action="store_true", help="Keep temporary smoke files.")
    args = parser.parse_args()

    officecli = detect_officecli_command()
    if not officecli or not shutil.which(officecli):
        print("OfficeCLI executable not found. Run ./horbot.sh install officecli first.", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="officecli-smoke-") as tempdir:
        root = Path(tempdir)
        results = [
            smoke_docx(officecli, root),
            smoke_xlsx(officecli, root),
            smoke_pptx(officecli, root),
        ]

        if args.keep_temp:
            kept_root = Path.cwd() / ".tmp" / "officecli-smoke"
            if kept_root.exists():
                shutil.rmtree(kept_root)
            shutil.copytree(root, kept_root)

    payload = {
        "ok": all(item.ok for item in results),
        "officecli": officecli,
        "scenarios": [
            {
                **asdict(item),
                "steps": [
                    {
                        "command": step.command,
                        "returncode": step.returncode,
                        "stdout": step.stdout,
                        "stderr": step.stderr,
                    }
                    for step in item.steps
                ],
            }
            for item in results
        ],
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for item in results:
            status = "PASS" if item.ok else "FAIL"
            print(f"[{status}] {item.name}: {item.file_path}")
            for key, passed in item.checks.items():
                print(f"  - {key}: {'ok' if passed else 'failed'}")
            for error in item.errors:
                print(f"  - error: {error}")

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
