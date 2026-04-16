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

### 2. Prefer semantic operations over raw XML

- Use high-level document operations first.
- Only drop to raw XML or XPath when the higher-level OfficeCLI tools cannot express the change.
- If you use raw XML, keep the edit small and targeted.

### 3. Preserve document integrity

- Avoid flattening Office documents into plain text unless the user explicitly wants conversion.
- Keep sheet names, slide order, headings, styles, and document structure intact unless the user asked to change them.
- If the edit is large or risky, save to a new output path first.

### 4. Keep edits auditable

- Summarize what part of the document was changed.
- Mention the file path and the affected sheet/slide/section when relevant.
- If a change could affect formulas, references, or layout, call that out clearly.

## Failure Handling

If OfficeCLI tools are not available:

- say that OfficeCLI MCP is not configured or not reachable
- fall back to `mcp_excel_*` only for simple Excel tasks when appropriate
- otherwise stop and ask for OfficeCLI MCP configuration instead of faking Office-native edits
