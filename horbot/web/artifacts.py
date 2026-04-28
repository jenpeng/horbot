"""Ephemeral live artifact rendering for chat messages."""

from __future__ import annotations

import html
import json
import re
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from horbot.config.loader import get_cached_config


MAX_RENDERABLE_JSON_BYTES = 512 * 1024
DEFAULT_TTL_SECONDS = 30 * 60
ALLOWED_TEMPLATES = {
    "dashboard",
    "chart-story",
    "data-workbench",
    "map-story",
    "process-map",
    "interactive-report",
}
ALLOWED_TEMPLATES_LABEL = ", ".join(sorted(ALLOWED_TEMPLATES))


class ArtifactValidationError(ValueError):
    """Raised when a renderable spec is not safe or not supported."""


def get_runtime_artifacts_root() -> Path:
    """Return the runtime directory for temporary rendered artifacts."""
    workspace = Path(get_cached_config().workspace_path).expanduser().resolve()
    horbot_root = next((parent for parent in (workspace, *workspace.parents) if parent.name == ".horbot"), None)
    root = (horbot_root or (Path.cwd() / ".horbot")) / "runtime" / "rendered-artifacts"
    root.mkdir(parents=True, exist_ok=True)
    return root


def cleanup_expired_artifacts(now: float | None = None) -> int:
    root = get_runtime_artifacts_root()
    current = now or time.time()
    removed = 0
    for item in root.iterdir():
        if not item.is_dir():
            continue
        manifest_path = item / "manifest.json"
        expires_at = 0.0
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            expires_at = float(manifest.get("expires_at_epoch") or 0)
        except Exception:
            expires_at = item.stat().st_mtime + DEFAULT_TTL_SECONDS
        if expires_at and expires_at < current:
            shutil.rmtree(item, ignore_errors=True)
            removed += 1
    return removed


def normalize_renderable_spec(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ArtifactValidationError("Renderable spec must be a JSON object.")

    raw = json.dumps(value, ensure_ascii=False)
    if len(raw.encode("utf-8")) > MAX_RENDERABLE_JSON_BYTES:
        raise ArtifactValidationError("Renderable spec is too large.")

    spec = dict(value)
    if isinstance(spec.get("artifact"), dict):
        merged = dict(spec["artifact"])
        for key in ("response_mode", "reason"):
            if key in spec and key not in merged:
                merged[key] = spec[key]
        spec = merged

    raw_template = spec.get("template") or "dashboard"
    if not isinstance(raw_template, str):
        raise ArtifactValidationError(
            "Renderable template must be a string from the supported whitelist "
            f"({ALLOWED_TEMPLATES_LABEL}). Do not use a template object, raw HTML, or CSS."
        )

    template = raw_template.strip().lower()
    if template not in ALLOWED_TEMPLATES:
        raise ArtifactValidationError(
            f"Unsupported renderable template: {template}. Supported templates: {ALLOWED_TEMPLATES_LABEL}."
        )

    title = _clean_text(spec.get("title") or spec.get("name") or "Live Artifact", 120)
    summary = _clean_text(spec.get("summary") or spec.get("description") or "", 600)
    theme = spec.get("theme") if isinstance(spec.get("theme"), dict) else {}
    data = spec.get("data") if isinstance(spec.get("data"), dict | list) else {}

    return {
        **spec,
        "title": title,
        "summary": summary,
        "template": template,
        "theme": theme,
        "data": data,
    }


def render_artifact(spec: dict[str, Any], ttl_seconds: int = DEFAULT_TTL_SECONDS) -> dict[str, Any]:
    cleanup_expired_artifacts()
    normalized = normalize_renderable_spec(spec)
    artifact_id = uuid.uuid4().hex
    created_at = time.time()
    ttl = max(60, min(int(ttl_seconds or DEFAULT_TTL_SECONDS), 24 * 60 * 60))
    expires_at = created_at + ttl

    artifact_dir = get_runtime_artifacts_root() / artifact_id
    artifact_dir.mkdir(parents=True, exist_ok=False)
    (artifact_dir / "spec.json").write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (artifact_dir / "index.html").write_text(_render_html_document(normalized), encoding="utf-8")
    (artifact_dir / "manifest.json").write_text(
        json.dumps(
            {
                "artifact_id": artifact_id,
                "title": normalized["title"],
                "template": normalized["template"],
                "created_at": datetime.fromtimestamp(created_at, timezone.utc).isoformat(),
                "expires_at": datetime.fromtimestamp(expires_at, timezone.utc).isoformat(),
                "expires_at_epoch": expires_at,
                "pinned": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "artifact_id": artifact_id,
        "title": normalized["title"],
        "template": normalized["template"],
        "render_url": f"/api/artifacts/runtime/{artifact_id}/index.html",
        "expires_at": datetime.fromtimestamp(expires_at, timezone.utc).isoformat(),
        "ttl_seconds": ttl,
    }


def resolve_runtime_artifact_file(artifact_id: str, filename: str) -> Path:
    safe_id = re.sub(r"[^a-f0-9]", "", artifact_id.lower())
    if safe_id != artifact_id or len(safe_id) != 32:
        raise ArtifactValidationError("Invalid artifact id.")
    if filename != "index.html":
        raise ArtifactValidationError("Only index.html can be served.")
    path = (get_runtime_artifacts_root() / safe_id / filename).resolve()
    root = get_runtime_artifacts_root().resolve()
    if root not in path.parents:
        raise ArtifactValidationError("Invalid artifact path.")
    if not path.exists():
        raise FileNotFoundError(filename)
    return path


def _clean_text(value: Any, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def _theme(spec: dict[str, Any]) -> dict[str, str]:
    raw = spec.get("theme") if isinstance(spec.get("theme"), dict) else {}
    colorway = str(raw.get("colorway") or "ocean").lower()
    palettes = {
        "earth": ("#5b4b35", "#d97706", "#f4e7d0", "#fffaf0"),
        "graphite": ("#111827", "#475569", "#e2e8f0", "#f8fafc"),
        "sunrise": ("#7c2d12", "#f97316", "#fed7aa", "#fff7ed"),
        "ocean": ("#123047", "#0891b2", "#cffafe", "#f0fdfa"),
    }
    ink, accent, soft, paper = palettes.get(colorway, palettes["ocean"])
    return {
        "ink": ink,
        "accent": accent,
        "soft": soft,
        "paper": paper,
        "tone": str(raw.get("tone") or "executive"),
        "density": str(raw.get("density") or "comfortable"),
    }


def _extract_items(spec: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [
        spec.get("items"),
        spec.get("cards"),
        spec.get("metrics"),
        (spec.get("data") or {}).get("items") if isinstance(spec.get("data"), dict) else None,
        (spec.get("data") or {}).get("metrics") if isinstance(spec.get("data"), dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)][:24]
    return []


def _extract_rows(spec: dict[str, Any]) -> list[dict[str, Any]]:
    table = spec.get("table") if isinstance(spec.get("table"), dict) else {}
    data = spec.get("data") if isinstance(spec.get("data"), dict) else {}
    for candidate in (table.get("rows"), data.get("rows"), spec.get("rows")):
        if isinstance(candidate, list):
            return [row for row in candidate if isinstance(row, dict)][:200]
    return []


def _extract_chart_points(spec: dict[str, Any]) -> list[dict[str, Any]]:
    chart = spec.get("chart") if isinstance(spec.get("chart"), dict) else {}
    data = spec.get("data") if isinstance(spec.get("data"), dict) else {}
    for candidate in (chart.get("points"), chart.get("series"), data.get("points"), spec.get("points")):
        if isinstance(candidate, list):
            return [point for point in candidate if isinstance(point, dict)][:80]
    return []


def _render_html_document(spec: dict[str, Any]) -> str:
    theme = _theme(spec)
    title = html.escape(spec["title"])
    summary = html.escape(spec.get("summary") or "")
    payload = {
        "template": spec["template"],
        "title": spec["title"],
        "summary": spec.get("summary") or "",
        "items": _extract_items(spec),
        "rows": _extract_rows(spec),
        "points": _extract_chart_points(spec),
        "sections": [item for item in spec.get("sections", []) if isinstance(item, dict)][:12]
        if isinstance(spec.get("sections"), list)
        else [],
    }
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    :root {{
      --ink: {theme["ink"]};
      --accent: {theme["accent"]};
      --soft: {theme["soft"]};
      --paper: {theme["paper"]};
      --line: rgba(15, 23, 42, .12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at 12% 12%, rgba(255,255,255,.95), transparent 28rem),
        linear-gradient(135deg, var(--paper), var(--soft));
    }}
    .shell {{ width: min(1180px, calc(100vw - 32px)); margin: 0 auto; padding: 28px 0 34px; }}
    .hero {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 18px;
      align-items: end;
      margin-bottom: 18px;
    }}
    h1 {{ margin: 0; font-size: clamp(28px, 4vw, 52px); letter-spacing: -.045em; line-height: .95; }}
    .summary {{ margin: 10px 0 0; max-width: 760px; color: rgba(15,23,42,.68); font-size: 15px; line-height: 1.55; }}
    .badge {{ border: 1px solid var(--line); border-radius: 999px; padding: 8px 12px; background: rgba(255,255,255,.62); font-size: 12px; }}
    .grid {{ display: grid; grid-template-columns: repeat(12, 1fr); gap: 14px; }}
    .card {{
      border: 1px solid var(--line);
      border-radius: 26px;
      background: rgba(255,255,255,.72);
      box-shadow: 0 20px 45px rgba(15, 23, 42, .08);
      backdrop-filter: blur(12px);
      padding: 18px;
    }}
    .metric {{ grid-column: span 3; min-height: 132px; }}
    .metric .label {{ color: rgba(15,23,42,.58); font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; }}
    .metric .value {{ margin-top: 16px; font-size: 34px; font-weight: 850; letter-spacing: -.04em; }}
    .metric .note {{ margin-top: 8px; color: rgba(15,23,42,.58); font-size: 13px; }}
    .wide {{ grid-column: span 8; }}
    .side {{ grid-column: span 4; }}
    .full {{ grid-column: span 12; }}
    .chart {{ height: 310px; display: flex; align-items: end; gap: 10px; padding-top: 20px; }}
    .bar {{ flex: 1; min-width: 18px; border-radius: 14px 14px 6px 6px; background: linear-gradient(180deg, var(--accent), var(--ink)); position: relative; }}
    .bar span {{ position: absolute; left: 50%; bottom: -24px; transform: translateX(-50%); font-size: 11px; color: rgba(15,23,42,.58); white-space: nowrap; }}
    .list {{ display: grid; gap: 10px; }}
    .list-item {{ display: flex; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--line); padding: 10px 0; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 12px 10px; text-align: left; vertical-align: top; }}
    th {{ color: rgba(15,23,42,.58); font-size: 11px; text-transform: uppercase; letter-spacing: .08em; }}
    .section {{ margin-bottom: 12px; }}
    .section h2 {{ margin: 0 0 8px; font-size: 20px; letter-spacing: -.02em; }}
    .section p {{ margin: 0; color: rgba(15,23,42,.66); line-height: 1.55; }}
    .map {{
      min-height: 360px;
      border-radius: 26px;
      background:
        linear-gradient(90deg, rgba(15,23,42,.08) 1px, transparent 1px),
        linear-gradient(0deg, rgba(15,23,42,.08) 1px, transparent 1px),
        linear-gradient(135deg, rgba(255,255,255,.82), rgba(255,255,255,.35));
      background-size: 42px 42px, 42px 42px, auto;
      position: relative;
      overflow: hidden;
    }}
    .pin {{ position: absolute; transform: translate(-50%, -50%); padding: 8px 10px; border-radius: 999px; background: var(--ink); color: white; font-size: 12px; box-shadow: 0 10px 26px rgba(15,23,42,.22); }}
    .empty {{ color: rgba(15,23,42,.58); border: 1px dashed var(--line); border-radius: 20px; padding: 18px; }}
    @media (max-width: 820px) {{
      .hero {{ grid-template-columns: 1fr; }}
      .metric, .wide, .side, .full {{ grid-column: span 12; }}
      .chart {{ overflow-x: auto; }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <header class="hero">
      <div>
        <h1>{title}</h1>
        <p class="summary">{summary}</p>
      </div>
      <div class="badge">Horbot Live Artifact · {html.escape(spec["template"])}</div>
    </header>
    <section id="app" class="grid"></section>
  </main>
  <script type="application/json" id="payload">{_safe_json(payload)}</script>
  <script>
    const data = JSON.parse(document.getElementById('payload').textContent);
    const app = document.getElementById('app');
    const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
    const num = (v) => Number.isFinite(Number(v)) ? Number(v) : 0;
    function metricCards() {{
      return (data.items || []).slice(0, 8).map((item) => `
        <article class="card metric">
          <div class="label">${{esc(item.label || item.name || 'Metric')}}</div>
          <div class="value">${{esc(item.value ?? item.amount ?? '-')}}</div>
          <div class="note">${{esc(item.note || item.change || item.description || '')}}</div>
        </article>
      `).join('');
    }}
    function chartCard(cls = 'wide') {{
      const points = data.points || [];
      if (!points.length) return `<article class="card ${{cls}}"><div class="empty">No chart points provided.</div></article>`;
      const max = Math.max(...points.map((p) => Math.abs(num(p.value ?? p.y ?? p.amount))), 1);
      return `<article class="card ${{cls}}"><div class="section"><h2>${{esc(data.chartTitle || 'Trend')}}</h2><p>${{esc(data.summary || '')}}</p></div><div class="chart">${{points.map((p) => {{
        const value = Math.abs(num(p.value ?? p.y ?? p.amount));
        return `<div class="bar" title="${{esc(p.label || p.x || '')}}: ${{esc(value)}}" style="height:${{Math.max(8, value / max * 100)}}%"><span>${{esc(p.label || p.x || '')}}</span></div>`;
      }}).join('')}}</div></article>`;
    }}
    function rowsCard(cls = 'full') {{
      const rows = data.rows || [];
      if (!rows.length) return `<article class="card ${{cls}}"><div class="empty">No table rows provided.</div></article>`;
      const columns = Object.keys(rows[0] || {{}}).slice(0, 8);
      return `<article class="card ${{cls}}"><table><thead><tr>${{columns.map((c) => `<th>${{esc(c)}}</th>`).join('')}}</tr></thead><tbody>${{rows.slice(0, 80).map((row) => `<tr>${{columns.map((c) => `<td>${{esc(row[c])}}</td>`).join('')}}</tr>`).join('')}}</tbody></table></article>`;
    }}
    function sectionsCard(cls = 'side') {{
      const sections = data.sections || [];
      if (!sections.length) return `<article class="card ${{cls}}"><div class="empty">No narrative sections provided.</div></article>`;
      return `<article class="card ${{cls}}">${{sections.map((section) => `<div class="section"><h2>${{esc(section.title || 'Insight')}}</h2><p>${{esc(section.body || section.content || '')}}</p></div>`).join('')}}</article>`;
    }}
    function mapCard() {{
      const points = (data.points || data.items || []).slice(0, 24);
      return `<article class="card full"><div class="map">${{points.map((p, index) => {{
        const left = Math.min(92, Math.max(8, num(p.lng ?? p.x ?? (20 + index * 17)) % 100));
        const top = Math.min(88, Math.max(12, num(p.lat ?? p.y ?? (24 + index * 13)) % 100));
        return `<span class="pin" style="left:${{left}}%;top:${{top}}%">${{esc(p.label || p.name || ('Point ' + (index + 1)))}}</span>`;
      }}).join('')}}</div></article>`;
    }}
    if (data.template === 'data-workbench') app.innerHTML = metricCards() + rowsCard();
    else if (data.template === 'map-story') app.innerHTML = mapCard() + sectionsCard('full');
    else if (data.template === 'process-map' || data.template === 'interactive-report') app.innerHTML = metricCards() + sectionsCard('full') + rowsCard();
    else if (data.template === 'chart-story') app.innerHTML = chartCard('wide') + sectionsCard('side') + rowsCard();
    else app.innerHTML = metricCards() + chartCard('wide') + sectionsCard('side') + rowsCard();
  </script>
</body>
</html>
"""
