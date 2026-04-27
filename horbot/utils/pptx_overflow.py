"""Structural PPTX text-overflow pre-screening.

This module does a fast OpenXML-based pass over `.pptx` slides to flag text
boxes that are likely to overflow. It is intentionally heuristic: the output
should be treated as a suspicious-slide list for later rendered/visual
verification, not as a final human-equivalent verdict.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any
import unicodedata
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZipFile

EMU_PER_POINT = 12700
DEFAULT_FONT_SIZE_PT = 18.0
DEFAULT_BODY_INSET_LEFT_RIGHT_EMU = 91440
DEFAULT_BODY_INSET_TOP_BOTTOM_EMU = 45720
EXCLUDED_PLACEHOLDER_TYPES = {"title", "ctrTitle", "subTitle", "dt", "sldNum", "ftr", "hdr"}
POWERPOINT_APP_PATH = Path("/Applications/Microsoft PowerPoint.app")
KEYNOTE_APP_PATH = Path("/Applications/Keynote.app")


def _tag_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _parse_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _office_archive_sort_key(name: str) -> tuple[int, str]:
    stem = Path(name).stem
    digits = "".join(ch for ch in stem if ch.isdigit())
    return (int(digits) if digits else 0, name)


def _emu_to_points(value: int | float) -> float:
    return float(value) / EMU_PER_POINT if value else 0.0


def _char_width_factor(ch: str) -> float:
    if not ch:
        return 0.0
    if ch.isspace():
        return 0.33
    east_asian = unicodedata.east_asian_width(ch)
    if east_asian in {"F", "W"}:
        return 0.95
    if ch.isdigit():
        return 0.56
    if ch.isalpha():
        return 0.58 if ch.isupper() else 0.52
    category = unicodedata.category(ch)
    if category.startswith("P"):
        return 0.34
    return 0.58


def _estimate_segment_lines(text: str, font_size_pt: float, available_width_pt: float) -> int:
    normalized = text.strip()
    if not normalized:
        return 1
    if available_width_pt <= 1:
        return max(1, len(normalized))

    estimated_width_pt = sum(_char_width_factor(ch) for ch in normalized) * font_size_pt
    line_count = int(math.ceil(estimated_width_pt / max(available_width_pt, 1.0)))
    return max(1, line_count)


def _first_matching_descendant(node: ET.Element, local_name: str) -> ET.Element | None:
    for child in node.iter():
        if _tag_name(getattr(child, "tag", "")) == local_name:
            return child
    return None


def _parse_shape_placeholder_type(shape: ET.Element) -> str:
    placeholder = _first_matching_descendant(shape, "ph")
    if placeholder is None:
        return ""
    return str(placeholder.attrib.get("type") or "").strip()


def _parse_shape_identity(shape: ET.Element, fallback_index: int) -> tuple[int, str]:
    c_nv_pr = _first_matching_descendant(shape, "cNvPr")
    if c_nv_pr is None:
        return fallback_index, f"Text Shape {fallback_index}"
    shape_id = _parse_int(c_nv_pr.attrib.get("id"), fallback_index)
    name = str(c_nv_pr.attrib.get("name") or "").strip() or f"Text Shape {shape_id}"
    return shape_id, name


def _parse_text_body_properties(tx_body: ET.Element) -> dict[str, Any]:
    body_pr = next((child for child in tx_body if _tag_name(getattr(child, "tag", "")) == "bodyPr"), None)
    if body_pr is None:
        return {
            "autofit": "unknown",
            "l_ins_emu": DEFAULT_BODY_INSET_LEFT_RIGHT_EMU,
            "r_ins_emu": DEFAULT_BODY_INSET_LEFT_RIGHT_EMU,
            "t_ins_emu": DEFAULT_BODY_INSET_TOP_BOTTOM_EMU,
            "b_ins_emu": DEFAULT_BODY_INSET_TOP_BOTTOM_EMU,
        }

    autofit = "unknown"
    for child in body_pr:
        tag = _tag_name(getattr(child, "tag", ""))
        if tag in {"noAutofit", "normAutofit", "spAutoFit"}:
            autofit = tag
            break

    return {
        "autofit": autofit,
        "l_ins_emu": _parse_int(body_pr.attrib.get("lIns"), DEFAULT_BODY_INSET_LEFT_RIGHT_EMU),
        "r_ins_emu": _parse_int(body_pr.attrib.get("rIns"), DEFAULT_BODY_INSET_LEFT_RIGHT_EMU),
        "t_ins_emu": _parse_int(body_pr.attrib.get("tIns"), DEFAULT_BODY_INSET_TOP_BOTTOM_EMU),
        "b_ins_emu": _parse_int(body_pr.attrib.get("bIns"), DEFAULT_BODY_INSET_TOP_BOTTOM_EMU),
    }


def _parse_shape_geometry(shape: ET.Element) -> dict[str, float]:
    xfrm = None
    sp_pr = next((child for child in shape if _tag_name(getattr(child, "tag", "")) == "spPr"), None)
    if sp_pr is not None:
        xfrm = next((child for child in sp_pr if _tag_name(getattr(child, "tag", "")) == "xfrm"), None)
    if xfrm is None:
        xfrm = _first_matching_descendant(shape, "xfrm")
    if xfrm is None:
        return {
            "x_pt": 0.0,
            "y_pt": 0.0,
            "width_pt": 0.0,
            "height_pt": 0.0,
        }

    off = next((child for child in xfrm if _tag_name(getattr(child, "tag", "")) == "off"), None)
    ext = next((child for child in xfrm if _tag_name(getattr(child, "tag", "")) == "ext"), None)
    return {
        "x_pt": _emu_to_points(_parse_int(off.attrib.get("x")) if off is not None else 0),
        "y_pt": _emu_to_points(_parse_int(off.attrib.get("y")) if off is not None else 0),
        "width_pt": _emu_to_points(_parse_int(ext.attrib.get("cx")) if ext is not None else 0),
        "height_pt": _emu_to_points(_parse_int(ext.attrib.get("cy")) if ext is not None else 0),
    }


def _parse_paragraph_metrics(paragraph: ET.Element, default_font_size_pt: float) -> dict[str, Any]:
    text_segments: list[str] = []
    current_segment: list[str] = []
    font_sizes: list[float] = []
    line_spacing_ratio: float | None = None
    line_spacing_points: float | None = None

    p_pr = next((child for child in paragraph if _tag_name(getattr(child, "tag", "")) == "pPr"), None)
    if p_pr is not None:
        ln_spc = next((child for child in p_pr if _tag_name(getattr(child, "tag", "")) == "lnSpc"), None)
        if ln_spc is not None:
            spc_pct = next((child for child in ln_spc if _tag_name(getattr(child, "tag", "")) == "spcPct"), None)
            spc_pts = next((child for child in ln_spc if _tag_name(getattr(child, "tag", "")) == "spcPts"), None)
            if spc_pct is not None:
                line_spacing_ratio = max(_parse_float(spc_pct.attrib.get("val")) / 100000.0, 0.8)
            elif spc_pts is not None:
                line_spacing_points = max(_parse_float(spc_pts.attrib.get("val")) / 100.0, 1.0)

    for child in paragraph:
        tag = _tag_name(getattr(child, "tag", ""))
        if tag == "r":
            text_node = next((node for node in child if _tag_name(getattr(node, "tag", "")) == "t"), None)
            if text_node is not None and text_node.text:
                current_segment.append(text_node.text)
            r_pr = next((node for node in child if _tag_name(getattr(node, "tag", "")) == "rPr"), None)
            if r_pr is not None:
                font_size_raw = _parse_int(r_pr.attrib.get("sz"))
                if font_size_raw > 0:
                    font_sizes.append(font_size_raw / 100.0)
            continue

        if tag == "fld":
            text_node = next((node for node in child.iter() if _tag_name(getattr(node, "tag", "")) == "t"), None)
            if text_node is not None and text_node.text:
                current_segment.append(text_node.text)
            continue

        if tag == "br":
            text_segments.append("".join(current_segment))
            current_segment = []
            continue

        if tag == "endParaRPr":
            font_size_raw = _parse_int(child.attrib.get("sz"))
            if font_size_raw > 0:
                font_sizes.append(font_size_raw / 100.0)

    text_segments.append("".join(current_segment))
    usable_segments = [segment for segment in text_segments if segment.strip()]
    paragraph_text = "\n".join(usable_segments).strip()
    paragraph_font_size = max(font_sizes) if font_sizes else default_font_size_pt

    return {
        "text": paragraph_text,
        "segments": usable_segments or [""],
        "font_size_pt": paragraph_font_size,
        "line_spacing_ratio": line_spacing_ratio,
        "line_spacing_points": line_spacing_points,
    }


def _estimate_shape_metrics(shape: ET.Element, slide_number: int, fallback_index: int) -> dict[str, Any] | None:
    tx_body = next((child for child in shape if _tag_name(getattr(child, "tag", "")) == "txBody"), None)
    if tx_body is None:
        return None

    placeholder_type = _parse_shape_placeholder_type(shape)
    if placeholder_type in EXCLUDED_PLACEHOLDER_TYPES:
        return None

    paragraphs = [
        _parse_paragraph_metrics(paragraph, DEFAULT_FONT_SIZE_PT)
        for paragraph in tx_body
        if _tag_name(getattr(paragraph, "tag", "")) == "p"
    ]
    paragraphs = [item for item in paragraphs if item["text"].strip()]
    if not paragraphs:
        return None

    shape_id, shape_name = _parse_shape_identity(shape, fallback_index)
    geometry = _parse_shape_geometry(shape)
    body_props = _parse_text_body_properties(tx_body)

    available_width_pt = max(
        geometry["width_pt"]
        - _emu_to_points(body_props["l_ins_emu"])
        - _emu_to_points(body_props["r_ins_emu"]),
        1.0,
    )
    available_height_pt = max(
        geometry["height_pt"]
        - _emu_to_points(body_props["t_ins_emu"])
        - _emu_to_points(body_props["b_ins_emu"]),
        1.0,
    )

    estimated_text_height_pt = 0.0
    font_sizes: list[float] = []
    explicit_line_breaks = 0
    paragraph_count = len(paragraphs)
    text_lines: list[str] = []

    for index, paragraph in enumerate(paragraphs):
        font_size_pt = float(paragraph["font_size_pt"] or DEFAULT_FONT_SIZE_PT)
        font_sizes.append(font_size_pt)
        segments = paragraph["segments"]
        explicit_line_breaks += max(0, len(segments) - 1)
        estimated_line_count = sum(
            _estimate_segment_lines(segment, font_size_pt, available_width_pt)
            for segment in segments
        )
        line_spacing_points = paragraph["line_spacing_points"]
        if line_spacing_points is not None:
            line_height_pt = max(line_spacing_points, font_size_pt * 1.0)
        else:
            spacing_ratio = paragraph["line_spacing_ratio"] if paragraph["line_spacing_ratio"] is not None else 1.18
            line_height_pt = max(font_size_pt * spacing_ratio, font_size_pt * 1.0)

        estimated_text_height_pt += estimated_line_count * line_height_pt
        if index > 0:
            estimated_text_height_pt += font_size_pt * 0.28
        text_lines.append(paragraph["text"])

    full_text = "\n".join(line for line in text_lines if line).strip()
    character_count = len(full_text.replace("\n", ""))
    average_font_size_pt = sum(font_sizes) / len(font_sizes) if font_sizes else DEFAULT_FONT_SIZE_PT
    occupancy_ratio = estimated_text_height_pt / max(available_height_pt, 1.0)

    reasons: list[str] = []
    risk_score = 0.0
    if occupancy_ratio >= 1.12:
        risk_score += 0.72
        reasons.append("estimated_text_height_exceeds_box")
    elif occupancy_ratio >= 1.0:
        risk_score += 0.58
        reasons.append("estimated_text_height_exceeds_box")
    elif occupancy_ratio >= 0.9:
        risk_score += 0.42
        reasons.append("estimated_text_near_box_limit")
    elif occupancy_ratio >= 0.8:
        risk_score += 0.24
        reasons.append("text_box_fill_ratio_high")

    autofit = str(body_props["autofit"] or "unknown")
    if autofit == "noAutofit":
        risk_score += 0.18 if occupancy_ratio >= 0.8 else 0.08
        reasons.append("no_autofit")
    elif autofit == "normAutofit" and occupancy_ratio >= 0.95:
        risk_score += 0.06
        reasons.append("autofit_may_not_be_enough")

    if paragraph_count >= 4 and geometry["height_pt"] <= 180:
        risk_score += 0.08
        reasons.append("dense_multi_paragraph_box")

    if average_font_size_pt >= 22 and character_count >= 120:
        risk_score += 0.08
        reasons.append("large_font_long_copy")

    if explicit_line_breaks >= 4:
        risk_score += 0.05
        reasons.append("many_explicit_line_breaks")

    risk_score = min(round(risk_score, 3), 1.0)
    severity = "low"
    if risk_score >= 0.8:
        severity = "critical"
    elif risk_score >= 0.6:
        severity = "high"
    elif risk_score >= 0.4:
        severity = "medium"

    return {
        "slide_number": slide_number,
        "shape_id": shape_id,
        "shape_name": shape_name,
        "placeholder_type": placeholder_type or "text",
        "autofit": autofit,
        "severity": severity,
        "risk_score": risk_score,
        "reasons": sorted(set(reasons)),
        "geometry": {
            "x_pt": round(geometry["x_pt"], 2),
            "y_pt": round(geometry["y_pt"], 2),
            "width_pt": round(geometry["width_pt"], 2),
            "height_pt": round(geometry["height_pt"], 2),
            "available_width_pt": round(available_width_pt, 2),
            "available_height_pt": round(available_height_pt, 2),
        },
        "text_stats": {
            "paragraph_count": paragraph_count,
            "character_count": character_count,
            "explicit_line_breaks": explicit_line_breaks,
            "average_font_size_pt": round(average_font_size_pt, 2),
            "estimated_text_height_pt": round(estimated_text_height_pt, 2),
            "occupancy_ratio": round(occupancy_ratio, 3),
        },
        "text_excerpt": full_text[:220],
    }


def analyze_pptx_text_overflow(
    file_path: str | Path,
    *,
    min_score: float = 0.55,
    include_all_shapes: bool = False,
) -> dict[str, Any]:
    """Analyze a PPTX and return a suspicious-slide report."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(path)

    try:
        with ZipFile(path) as archive:
            slide_paths = sorted(
                (
                    name
                    for name in archive.namelist()
                    if name.startswith("ppt/slides/slide") and name.endswith(".xml")
                ),
                key=_office_archive_sort_key,
            )

            slides: list[dict[str, Any]] = []
            suspicious_slides: list[dict[str, Any]] = []

            for slide_number, slide_path in enumerate(slide_paths, start=1):
                root = ET.fromstring(archive.read(slide_path))
                shape_reports: list[dict[str, Any]] = []
                for index, shape in enumerate(
                    node for node in root.iter() if _tag_name(getattr(node, "tag", "")) == "sp"
                ):
                    report = _estimate_shape_metrics(shape, slide_number, index + 1)
                    if report is not None:
                        shape_reports.append(report)

                shape_reports.sort(key=lambda item: item["risk_score"], reverse=True)
                suspicious_shapes = [item for item in shape_reports if item["risk_score"] >= min_score]
                max_risk_score = max((item["risk_score"] for item in shape_reports), default=0.0)

                slide_entry = {
                    "slide_number": slide_number,
                    "source_path": slide_path,
                    "shape_count": len(shape_reports),
                    "max_risk_score": round(max_risk_score, 3),
                    "status": "suspicious" if suspicious_shapes else "ok",
                    "shapes": shape_reports if include_all_shapes else suspicious_shapes,
                }
                slides.append(slide_entry)

                if suspicious_shapes:
                    suspicious_slides.append({
                        "slide_number": slide_number,
                        "max_risk_score": round(max_risk_score, 3),
                        "shape_count": len(suspicious_shapes),
                        "headline": (
                            f"Slide {slide_number}: {len(suspicious_shapes)} text box(es) need visual verification"
                        ),
                        "recommended_next_step": (
                            "Render this slide to PDF/image and confirm the suspicious text boxes visually."
                        ),
                        "shapes": suspicious_shapes,
                    })
    except BadZipFile as exc:
        raise ValueError(f"Invalid pptx archive: {path}") from exc

    suspicious_slides.sort(key=lambda item: item["max_risk_score"], reverse=True)
    return {
        "file": str(path),
        "analysis_mode": "structural-pre-screen",
        "slide_count": len(slides),
        "suspicious_slide_count": len(suspicious_slides),
        "minimum_risk_score": round(min_score, 3),
        "deck_summary": (
            "No suspicious slides crossed the threshold."
            if not suspicious_slides else
            f"{len(suspicious_slides)} slide(s) should be rendered for visual overflow verification."
        ),
        "recommended_next_step": (
            "Use rendered images/PDF plus OCR or visual inspection for final confirmation."
        ),
        "suspicious_slides": suspicious_slides,
        "slides": slides,
    }


def detect_render_verification_capabilities() -> dict[str, Any]:
    """Describe which deck renderers are currently available."""
    osascript_path = shutil.which("osascript")
    soffice_path = shutil.which("soffice") or shutil.which("libreoffice")
    capabilities = {
        "powerpoint": {
            "available": bool(osascript_path and POWERPOINT_APP_PATH.exists()),
            "app_path": str(POWERPOINT_APP_PATH),
            "requires": ["osascript", "Microsoft PowerPoint.app"],
        },
        "keynote": {
            "available": bool(osascript_path and KEYNOTE_APP_PATH.exists()),
            "app_path": str(KEYNOTE_APP_PATH),
            "requires": ["osascript", "Keynote.app"],
        },
        "libreoffice": {
            "available": bool(soffice_path),
            "command": soffice_path or "",
            "requires": ["soffice or libreoffice"],
        },
    }
    available_renderers = [
        renderer
        for renderer in ("powerpoint", "keynote", "libreoffice")
        if capabilities[renderer]["available"]
    ]
    return {
        "available_renderers": available_renderers,
        "preferred_renderer": available_renderers[0] if available_renderers else "",
        "capabilities": capabilities,
    }


def _apple_script_quote(path: Path | str) -> str:
    return str(path).replace("\\", "\\\\").replace('"', '\\"')


def _run_export_command(command: list[str], *, timeout_sec: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )


def _export_pdf_via_libreoffice(
    pptx_path: Path,
    output_dir: Path,
    *,
    timeout_sec: int,
) -> dict[str, Any]:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError("LibreOffice is not available")

    command = [
        soffice,
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(output_dir),
        str(pptx_path),
    ]
    result = _run_export_command(command, timeout_sec=timeout_sec)
    pdf_path = output_dir / f"{pptx_path.stem}.pdf"
    if result.returncode != 0 or not pdf_path.exists():
        stderr = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(stderr or "LibreOffice PDF export failed")
    return {
        "renderer": "libreoffice",
        "pdf_path": str(pdf_path),
        "stdout": (result.stdout or "").strip(),
    }


def _export_pdf_via_powerpoint(
    pptx_path: Path,
    pdf_path: Path,
    *,
    timeout_sec: int,
) -> dict[str, Any]:
    if not shutil.which("osascript") or not POWERPOINT_APP_PATH.exists():
        raise RuntimeError("PowerPoint AppleScript rendering is not available")

    script_lines = [
        f'set inputFile to POSIX file "{_apple_script_quote(pptx_path)}" as alias',
        f'set outputPath to "{_apple_script_quote(pdf_path)}"',
        'tell application "Microsoft PowerPoint"',
        "open inputFile",
        "delay 1",
        "save active presentation in outputPath as save as PDF",
        "close active presentation saving no",
        "end tell",
    ]
    command = ["osascript"]
    for line in script_lines:
        command.extend(["-e", line])

    result = _run_export_command(command, timeout_sec=timeout_sec)
    if result.returncode != 0 or not pdf_path.exists():
        stderr = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(stderr or "PowerPoint PDF export failed")
    return {
        "renderer": "powerpoint",
        "pdf_path": str(pdf_path),
        "stdout": (result.stdout or "").strip(),
    }


def _export_pdf_via_keynote(
    pptx_path: Path,
    pdf_path: Path,
    *,
    timeout_sec: int,
) -> dict[str, Any]:
    if not shutil.which("osascript") or not KEYNOTE_APP_PATH.exists():
        raise RuntimeError("Keynote AppleScript rendering is not available")

    script_lines = [
        f'set inputFile to POSIX file "{_apple_script_quote(pptx_path)}" as alias',
        f'set outputFile to POSIX file "{_apple_script_quote(pdf_path)}"',
        'tell application "Keynote"',
        "open inputFile",
        "delay 1",
        "set docRef to front document",
        "export docRef to outputFile as PDF",
        "close docRef saving no",
        "end tell",
    ]
    command = ["osascript"]
    for line in script_lines:
        command.extend(["-e", line])

    result = _run_export_command(command, timeout_sec=timeout_sec)
    if result.returncode != 0 or not pdf_path.exists():
        stderr = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(stderr or "Keynote PDF export failed")
    return {
        "renderer": "keynote",
        "pdf_path": str(pdf_path),
        "stdout": (result.stdout or "").strip(),
    }


def export_render_verification_assets(
    pptx_path: str | Path,
    *,
    output_dir: str | Path | None = None,
    renderer: str = "auto",
    timeout_sec: int = 90,
) -> dict[str, Any]:
    """Export rendered review assets for a deck, preferring real slide renderers."""
    pptx_file = Path(pptx_path)
    if not pptx_file.exists():
        raise FileNotFoundError(pptx_file)

    capabilities = detect_render_verification_capabilities()
    selected_renderer = renderer.strip().lower() or "auto"
    if selected_renderer == "auto":
        renderer_order = list(capabilities["available_renderers"])
    else:
        renderer_order = [selected_renderer]
    if not renderer_order:
        raise RuntimeError("No supported PPT renderers are available")

    if output_dir is None:
        target_dir = Path(tempfile.mkdtemp(prefix="horbot-pptx-render-"))
    else:
        target_dir = Path(output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    payload: dict[str, Any] | None = None
    for candidate in renderer_order:
        pdf_path = target_dir / f"{pptx_file.stem}.verification.pdf"
        try:
            if candidate == "libreoffice":
                payload = _export_pdf_via_libreoffice(pptx_file, target_dir, timeout_sec=timeout_sec)
            elif candidate == "powerpoint":
                payload = _export_pdf_via_powerpoint(pptx_file, pdf_path, timeout_sec=timeout_sec)
            elif candidate == "keynote":
                payload = _export_pdf_via_keynote(pptx_file, pdf_path, timeout_sec=timeout_sec)
            else:
                raise ValueError(f"Unsupported renderer: {candidate}")
            break
        except Exception as exc:
            errors.append(f"{candidate}: {exc}")
    if payload is None:
        raise RuntimeError("; ".join(errors) if errors else "No renderer export succeeded")

    payload.update(
        {
            "status": "rendered_pdf",
            "output_dir": str(target_dir),
            "capabilities": capabilities,
            "attempted_renderers": renderer_order,
        }
    )
    return payload


def attach_render_verification(
    report: dict[str, Any],
    *,
    renderer: str = "auto",
    output_dir: str | Path | None = None,
    timeout_sec: int = 90,
) -> dict[str, Any]:
    """Attach rendered review assets to a structural report when possible."""
    enriched = dict(report)
    suspicious_slides = list(report.get("suspicious_slides") or [])
    if not suspicious_slides:
        enriched["render_verification"] = {
            "status": "skipped",
            "reason": "no_suspicious_slides",
            "capabilities": detect_render_verification_capabilities(),
        }
        return enriched

    capabilities = detect_render_verification_capabilities()
    try:
        export_result = export_render_verification_assets(
            report["file"],
            output_dir=output_dir,
            renderer=renderer,
            timeout_sec=timeout_sec,
        )
        enriched["render_verification"] = {
            **export_result,
            "review_slide_numbers": [slide["slide_number"] for slide in suspicious_slides],
            "review_summary": (
                "Open the exported PDF and manually verify the suspicious slides, "
                "or pass the PDF/images to a later OCR/vision stage."
            ),
        }
    except Exception as exc:
        enriched["render_verification"] = {
            "status": "unavailable",
            "reason": str(exc),
            "capabilities": capabilities,
            "review_slide_numbers": [slide["slide_number"] for slide in suspicious_slides],
            "review_summary": (
                "No renderer could export a review PDF. Install or enable PowerPoint, Keynote, or LibreOffice, "
                "then rerun with --verify-render."
            ),
        }
    return enriched


def format_overflow_report(report: dict[str, Any]) -> str:
    """Render a compact text report for terminal use."""
    lines = [
        f"File: {report['file']}",
        (
            f"Slides: {report['slide_count']} | "
            f"Suspicious: {report['suspicious_slide_count']} | "
            f"Threshold: {report['minimum_risk_score']:.2f}"
        ),
    ]
    suspicious_slides = list(report.get("suspicious_slides") or [])
    if not suspicious_slides:
        lines.append("No suspicious slides crossed the threshold.")
        return "\n".join(lines)

    for slide in suspicious_slides:
        lines.append(
            f"- Slide {slide['slide_number']} | max risk {slide['max_risk_score']:.2f} | "
            f"{slide['shape_count']} shape(s)"
        )
        for shape in slide.get("shapes") or []:
            excerpt = str(shape.get("text_excerpt") or "").replace("\n", " ").strip()
            if len(excerpt) > 96:
                excerpt = excerpt[:93] + "..."
            lines.append(
                "  "
                + (
                    f"* {shape['shape_name']} [{shape['autofit']}] "
                    f"score={shape['risk_score']:.2f} "
                    f"fill={shape['text_stats']['occupancy_ratio']:.2f} "
                    f"reasons={','.join(shape['reasons']) or 'none'} "
                    f"text={excerpt or '(empty)'}"
                )
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Structurally pre-screen a PPTX for likely text overflow.",
    )
    parser.add_argument("pptx", help="Path to the .pptx file to inspect")
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.55,
        help="Only flag shapes at or above this risk score threshold",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of the compact text report",
    )
    parser.add_argument(
        "--all-shapes",
        action="store_true",
        help="Include low-risk shapes in the per-slide output",
    )
    parser.add_argument(
        "--verify-render",
        action="store_true",
        help="After structural pre-screening, try exporting a rendered PDF for manual or later visual verification",
    )
    parser.add_argument(
        "--renderer",
        default="auto",
        choices=["auto", "powerpoint", "keynote", "libreoffice"],
        help="Which real renderer to use for the verification export",
    )
    parser.add_argument(
        "--render-dir",
        default="",
        help="Directory where verification assets such as exported PDFs should be written",
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=90,
        help="Timeout for the renderer export step when --verify-render is enabled",
    )
    args = parser.parse_args(argv)

    report = analyze_pptx_text_overflow(
        args.pptx,
        min_score=args.min_score,
        include_all_shapes=args.all_shapes,
    )
    if args.verify_render:
        report = attach_render_verification(
            report,
            renderer=args.renderer,
            output_dir=args.render_dir or None,
            timeout_sec=args.timeout_sec,
        )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        output = format_overflow_report(report)
        render_verification = report.get("render_verification")
        if isinstance(render_verification, dict):
            output += "\n\nRender Verification:\n"
            status = str(render_verification.get("status") or "unknown")
            output += f"  status={status}\n"
            renderer_name = str(render_verification.get("renderer") or "").strip()
            if renderer_name:
                output += f"  renderer={renderer_name}\n"
            pdf_path = str(render_verification.get("pdf_path") or "").strip()
            if pdf_path:
                output += f"  pdf={pdf_path}\n"
            summary = str(render_verification.get("review_summary") or "").strip()
            if summary:
                output += f"  note={summary}\n"
            reason = str(render_verification.get("reason") or "").strip()
            if reason:
                output += f"  reason={reason}\n"
        print(output.rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
