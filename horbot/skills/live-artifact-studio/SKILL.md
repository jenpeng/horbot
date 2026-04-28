---
name: live-artifact-studio
description: Use when a reply should include an interactive visual artifact such as dashboards, charts, maps, process views, data workbenches, or report-like layouts. Guides the agent to choose Markdown vs structured renderable output and to persist data/spec rather than raw HTML or JavaScript.
metadata: {"horbot":{"enabled":true,"origin":"system"}}
---

# Live Artifact Studio

Use this skill when the user asks for an interactive visual result, chart, map, dashboard, data table, report, or UI-like preview inside chat.

## Output Choice
- Use normal Markdown for explanations, steps, decisions, plain tables, and code snippets.
- Use a renderable artifact when the answer benefits from visual scanning, filtering, chart comparison, map positioning, process navigation, or a polished report layout.
- Use file artifacts for PPTX, XLSX, PDF, images, or other durable files.

## Renderable Contract
When a renderable view is useful, include a short textual summary first, then a fenced `horbot-renderable` JSON block:

```horbot-renderable
{
  "title": "Sales Performance Dashboard",
  "summary": "Revenue, growth, and regional signals for the selected period.",
  "template": "dashboard",
  "theme": {
    "tone": "executive",
    "colorway": "ocean",
    "density": "comfortable"
  },
  "items": [
    {"label": "Revenue", "value": "$1.28M", "note": "+12.4% vs last month"}
  ],
  "points": [
    {"label": "Jan", "value": 42},
    {"label": "Feb", "value": 58}
  ],
  "sections": [
    {"title": "Key insight", "body": "Growth is concentrated in enterprise renewals."}
  ],
  "rows": [
    {"region": "East", "revenue": 420000, "growth": "11%"}
  ]
}
```

## Templates
- `dashboard`: KPI cards, trend chart, narrative sections, and table.
- `chart-story`: one primary chart plus explanation and supporting table.
- `data-workbench`: KPI cards plus sortable/searchable data intent; provide `rows`.
- `map-story`: location points and narrative. Use user-provided or explicitly stated coordinates only.
- `process-map`: stages, status, owners, risks, and next actions.
- `interactive-report`: sectioned report with metrics, narrative, and evidence rows.

## Safety Rules
- Do not emit raw `<script>`, arbitrary HTML apps, remote scripts, or credentials.
- Persist the reusable truth as JSON data and render spec. Treat generated HTML as temporary runtime output.
- If exact coordinates or data are missing, state the assumption in the summary and include approximate or placeholder data only when the user accepts that framing.
- Keep JSON under 512 KB. For large datasets, summarize rows and attach or reference the full file instead.

## Design Rules
- Give every artifact a clear title, short summary, and meaningful labels.
- Prefer 3-8 metrics, 5-20 chart points, and concise narrative sections.
- Use `theme.colorway` intentionally: `ocean`, `earth`, `graphite`, or `sunrise`.
- Keep interaction useful, not decorative: comparison, drill-in, map context, filtering, or scannable layout.
