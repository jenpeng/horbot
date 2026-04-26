---
name: auto-officecli-ppt
description: Reusable techniques, troubleshooting workflows, and reference notes for officecli ppt tasks, including across, after, alignment.
generated_by: skill-evolution
generated_at: 2026-04-26T03:34:58.899219+00:00
metadata: {"horbot":{"enabled":true}}
---

# Officecli Ppt

Reusable techniques, troubleshooting workflows, and reference notes for officecli ppt tasks, including across, after, alignment.

## When To Use
- Use this skill family when the task matches one of the trigger cues below and you need a proven reusable workflow.
- Read the relevant reference note before executing or advising on the detailed steps.

## Trigger Cues
- A repeated task or failure pattern matches this skill family.
- The user asks for a reusable checklist, playbook, or troubleshooting workflow.
- You need detailed steps from one of the reference notes before acting.

## How To Navigate
1. Scan the reference list below to find the closest technique.
2. Open the matching file under `references/`.
3. Apply or adapt that technique, and avoid mixing unrelated references.

## Reference Library
- [Bulk Paragraph Formatting for OfficeCLI PowerPoint Slides](references/officecli-ppt-bulk-paragraph-formatting.md) - - You generate or copy many slides programmatically with OfficeCLI and discover that paragraph-level formatting (e.g., lineSpacing) is missing or inconsistent.
- [OfficeCLI PowerPoint cross-file slide-copy limitation](references/officecli-ppt-cross-file-copy-limits.md) - Use when a user asks to copy or import slides from one PowerPoint file into another using OfficeCLI.
- [OfficeCLI PPT highlight may live in `endParaRPr`](references/officecli-ppt-endpararpr-highlight-debug.md) - Use this when PowerPoint text highlighting does not appear as expected after applying run-level formatting, or when a manually edited sample shows different XML than the generated 
- [OfficeCLI PPT XML Repair Script Delivery (Exec Blocked)](references/officecli-ppt-exec-blocked-xml-repair-script.md) - - You need to fix PowerPoint XML (highlights, fonts, backgrounds, autofit, etc.) but `exec` is blocked by confirmation gates.
- [OfficeCLI PowerPoint Highlight XML Debug](references/officecli-ppt-highlight-xml-debug.md) - When to use: PowerPoint text highlighting (yellow highlight) is not displaying correctly in OfficeCLI-generated or modified slides.
- [Auto-OfficeCLI PPT Master Slide Background Fix](references/officecli-ppt-master-background-inheritance.md) - When using OfficeCLI to generate PowerPoint slides that look correct in isolation but miss master slide formatting (background color, theme colors) after insertion — especially whe
- [OfficeCLI PPT: Run Fill vs. Shape Fill Trap](references/officecli-ppt-run-fill-vs-shape-fill-trap.md) - You are using OfficeCLI to highlight or color specific text (a `run`) inside a PowerPoint slide, but the color ends up applied to the entire text box (`shape`) instead of just the 
- [OfficeCLI PPT Run-Level Partial Text Formatting](references/officecli-ppt-run-level-partial-text-formatting.md) - - You need to format only part of a text string inside a PowerPoint shape (e.g., highlight just the label "词汇应用" but leave surrounding text unchanged).
- [OfficeCLI PPT Slide Fidelity Debugging](references/officecli-ppt-slide-fidelity-debug.md) - Use when OfficeCLI-generated slides look wrong, deviate from a template sample, or have formatting/layout issues (wrong fonts, missing highlights, overflow, etc.).
- [PowerPoint template recreation limits with OfficeCLI](references/officecli-ppt-template-recreation-limits.md) - Use when editing or generating `.pptx` files with OfficeCLI and the task expects slides to match an existing template closely, especially when adding new slides based on sample/tem
- [OfficeCLI PPT Text Overflow Debugging](references/officecli-ppt-text-overflow-debug.md) - - Generated PowerPoint slides still show text overflow after increasing text box height/width.
- [Generate PPTX XML Patch Script for Precise Run-Level Formatting](references/officecli-ppt-xml-patch-script-generation.md) - - OfficeCLI's high-level API cannot apply formatting to a specific substring (e.g., highlighting only "词汇应用" but not surrounding text).
- [OfficeCLI PPT XML Validation Workflow](references/officecli-ppt-xml-validation-workflow.md) - - After bulk OfficeCLI edits to a `.pptx`, you need to verify formatting was applied correctly across many slides.
