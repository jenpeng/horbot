---
name: officecli
description: "Use OfficeCLI-backed MCP tools to inspect and edit Word, Excel, and PowerPoint files with OpenXML-aware operations. Prefer these tools for .docx/.xlsx/.pptx work when they are available."
metadata: {"horbot":{"emoji":"🧾"}}
---

# OfficeCLI Skill

Use this skill when the task is about Microsoft Office files, especially:

- `.docx`, `.xlsx`, `.pptx`
- Word, Excel, PowerPoint
- OpenXML structure, document parts, or raw XML edits
- preserving Office-native structure instead of exporting to plain text

## Tool Preference

When OfficeCLI MCP tools are available, prefer them in this order:

1. `mcp_officecli_view*` / `mcp_officecli_get*` / `mcp_officecli_query*`
2. `mcp_officecli_set*` / `mcp_officecli_add*` / `mcp_officecli_remove*`
3. raw XML or XPath style tools only when high-level tools are not enough

If the MCP server exposes a single generic tool such as `mcp_officecli_officecli`, use that tool directly and set its `command` argument (`create`, `view`, `get`, `query`, `set`, `add`, `remove`, `move`, `swap`, `validate`, `batch`, `raw`, `help`) instead of looking for split sub-tools.

If the server is split by document type, the following names are also expected:

- `mcp_office-word_*`
- `mcp_office-excel_*`
- `mcp_office-powerpoint_*`

For simple spreadsheet table writes, `mcp_excel_*` is still acceptable. Prefer OfficeCLI when workbook structure, formulas, formatting fidelity, or OpenXML correctness matter.

## Working Rules

### 1. Inspect before editing

- Start with a read-only operation first.
- For Word or PowerPoint, inspect the document structure before inserting or removing content.
- For Excel, inspect sheets, ranges, and workbook structure before changing formulas or styles.
- For non-trivial `.xlsx` or `.pptx` edits, call `help` for that format first if you do not already know the exact property names.

### 2. Prefer semantic operations over raw XML

- Use high-level document operations first.
- Only drop to raw XML or XPath when the higher-level OfficeCLI tools cannot express the change.
- If you use raw XML, keep the edit small and targeted.

### 3. Preserve document integrity

- Avoid flattening Office documents into plain text unless the user explicitly wants conversion.
- Keep sheet names, slide order, headings, styles, and document structure intact unless the user asked to change them.
- If the edit is large or risky, save to a new output path first.
- For newly created `.pptx`, prefer a fresh output path. If a generated deck starts failing validation, recreate from scratch instead of repeatedly mutating the same broken file.

### 4. Keep edits auditable

- Summarize what part of the document was changed.
- Mention the file path and the affected sheet/slide/section when relevant.
- If a change could affect formulas, references, or layout, call that out clearly.

## Format-Specific Rules

### Word (`.docx`)

- A safe creation flow is: `create` -> `add paragraph` -> `add run` -> optional `view` or `validate`.
- For title/body content, prefer adding semantic paragraphs and runs instead of replacing the whole document body with raw XML.

### Excel (`.xlsx`)

- For direct `set` / `add` calls, `props` is usually a list of `key=value` strings.
- For `batch`, each nested command should use a JSON object for `props`, not a string list.
- Use OfficeCLI's actual Excel property names such as `font.color`, `font.size`, `font.name`, `fill`, `alignment.horizontal`.
- Do not guess aliases like `fontColor` or `fillColor`; if unsure, call `help xlsx` first.
- For simple sheet creation, use `add` on `/workbook` with sheet props, then `set` cell paths like `/Sheet1/A1`.

### PowerPoint (`.pptx`)

- Do not assume layout aliases like `titleAndContent` will be accepted. Use the exact layout names returned by OfficeCLI/template inspection, or omit the layout and add a blank slide.
- A robust creation flow is: `create` -> `add slide` -> `add textbox` -> `add textbox` -> `view outline`.
- After structural `.pptx` edits, run `validate`. If validation reports schema errors, do not claim the presentation is fully correct.
- If `validate` fails after multiple edits, prefer recreating the deck from a fresh file path and reapplying the content.

## Failure Handling

If OfficeCLI tools are not available:

- say that OfficeCLI MCP is not configured or not reachable
- fall back to `mcp_excel_*` only for simple Excel tasks when appropriate
- otherwise stop and ask for OfficeCLI MCP configuration instead of faking Office-native edits
