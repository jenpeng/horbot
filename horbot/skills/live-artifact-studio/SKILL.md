---
name: live-artifact-studio
description: Use when a reply should include an interactive visual artifact such as dashboards, charts, maps, process views, data workbenches, or report-like layouts. Guides the agent to choose Markdown vs structured renderable output and to persist data/spec rather than raw HTML or JavaScript.
always: true
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

Hard requirements:
- `template` must be a string, never an object.
- `template` must be exactly one of: `dashboard`, `chart-story`, `data-workbench`, `map-story`, `process-map`, `interactive-report`.
- Do not invent template names such as `dashboard.sales-funnel.realtime.v1`, `html-dashboard`, `sales-funnel`, or `raw-html`.
- Do not put HTML, CSS, JSX, JavaScript, or remote asset URLs in `template`, `html`, `css`, `script`, or similar fields.
- Use simple data fields the renderer understands: `items` with `label`/`value`/`note`, `points` with `label`/`value`, `sections` with `title`/`body`, and optional `rows` as flat objects.

## Templates
- `dashboard`: KPI cards, trend chart, narrative sections, and table.
- `chart-story`: one primary chart plus explanation and supporting table.
- `data-workbench`: KPI cards plus sortable/searchable data intent; provide `rows`.
- `map-story`: location points and narrative. Use user-provided or explicitly stated coordinates only.
- `process-map`: stages, status, owners, risks, and next actions.
- `interactive-report`: sectioned report with metrics, narrative, and evidence rows.

## Safety Rules
- Do not emit raw `<script>`, arbitrary HTML apps, remote scripts, or credentials.
- If you want a custom layout, express it as structured data and choose the closest supported template. Do not encode a layout DSL inside `template`.
- Do not browse, search, or open JSON Schema documentation just to validate this output contract. The contract in this skill is sufficient for local Live Artifact generation.
- Only use web/browser tools when the user explicitly asks for external facts, latest/current information, a specific URL, a public document, or real web page interaction.
- Persist the reusable truth as JSON data and render spec. Treat generated HTML as temporary runtime output.
- If exact coordinates or data are missing, state the assumption in the summary and include approximate or placeholder data only when the user accepts that framing.
- Keep JSON under 512 KB. For large datasets, summarize rows and attach or reference the full file instead.

## Invalid Examples
Do not output this:

```json
{
  "template": {
    "type": "html-dashboard",
    "html": "<div>...</div>",
    "css": ".card{...}"
  }
}
```

Do this instead:

```horbot-renderable
{
  "title": "Sales Funnel Dashboard",
  "summary": "Lead, opportunity, quote, and close signals.",
  "template": "dashboard",
  "items": [
    {"label": "Leads", "value": "1,284", "note": "+18.6%"}
  ],
  "points": [
    {"label": "09:00", "value": 18}
  ],
  "sections": [
    {"title": "Insight", "body": "Quote-to-close conversion needs attention."}
  ]
}
```

## Design Rules
- Give every artifact a clear title, short summary, and meaningful labels.
- Prefer 3-8 metrics, 5-20 chart points, and concise narrative sections.
- Use `theme.colorway` intentionally: `ocean`, `earth`, `graphite`, or `sunrise`.
- Keep interaction useful, not decorative: comparison, drill-in, map context, filtering, or scannable layout.
