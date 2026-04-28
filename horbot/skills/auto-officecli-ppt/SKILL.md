---
name: auto-officecli-ppt
description: "Reusable OfficeCLI/OpenXML workflows for PowerPoint generation, layout debugging, text overflow triage, and XML-level PPT troubleshooting."
generated_by: skill-evolution
generated_at: 2026-04-26T03:34:58.899219+00:00
metadata: {"horbot":{"enabled":true}}
---

# Officecli Ppt

Reusable OfficeCLI/OpenXML workflows for PowerPoint generation, layout debugging, text overflow triage, and XML-level PPT troubleshooting.

## When To Use
- Use this skill family when OfficeCLI-generated `.pptx` files look crowded, text may be clipped, or slide XML needs targeted PowerPoint debugging.
- Read the relevant reference note before executing the detailed steps.

## Trigger Cues
- The user says a PowerPoint slide may have text overflow, clipping, or truncated body copy.
- A generated deck validates structurally but still looks too dense or visually wrong.
- You need a repeatable PPT debugging workflow instead of ad hoc XML edits.

## How To Navigate
1. Scan the reference list below to find the closest technique.
2. Open the matching file under `references/`.
3. Apply or adapt that technique, and avoid mixing unrelated references.

## Reference Library
- [OfficeCLI PPT Structural Overflow Detector](references/officecli-ppt-structural-overflow-detector.md) - Run a structural pre-screen on `.pptx` slides to flag likely overflow before visual verification.
- [OfficeCLI PPT Render Verification Export](references/officecli-ppt-render-verification-export.md) - Export a rendered review PDF through PowerPoint, Keynote, or LibreOffice after the structural pass flags suspicious slides.
- [OfficeCLI PPT Text Overflow Debug](references/officecli-ppt-text-overflow-debug.md) - Diagnose persistent overflow in OfficeCLI-generated decks by checking text boxes, autofit behavior, and slide XML.
- [Live Artifact To PPT](references/live-artifact-to-ppt.md) - Use chat-side renderable previews to validate data dashboards, chart stories, map stories, or report layouts before producing the final PPT.
