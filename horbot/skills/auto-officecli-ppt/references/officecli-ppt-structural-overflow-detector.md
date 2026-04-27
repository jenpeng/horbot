# OfficeCLI PPT Structural Overflow Detector

## When to use

Use this workflow when a `.pptx` may have body-text overflow, but you need a fast batchable pre-screen before doing rendered or human visual verification.

This detector is best for:

- OfficeCLI-generated decks that look dense or inconsistent
- identifying which slides should be rendered to PDF/images next
- repeated PPT quality checks where you need a suspicious-slide list first

## What it does

The detector reads slide XML and estimates whether each text box is at risk of overflow by combining:

- text box geometry
- text body insets
- font size
- paragraph count
- explicit line breaks
- autofit mode such as `noAutofit` or `normAutofit`
- estimated text height versus available text box height

It is a structural heuristic, not a visual verdict.

## Command

Run the detector from the repository root:

```bash
python scripts/pptx_overflow_detector.py path/to/deck.pptx
```

For JSON output that another agent step can parse:

```bash
python scripts/pptx_overflow_detector.py path/to/deck.pptx --json
```

If you want the detector to also export a rendered review PDF for the suspicious slides workflow:

```bash
python scripts/pptx_overflow_detector.py path/to/deck.pptx --json --verify-render
```

If you want a wider net:

```bash
python scripts/pptx_overflow_detector.py path/to/deck.pptx --json --min-score 0.45
```

## How to interpret the result

- `suspicious_slide_count` tells you how many slides should be checked visually next
- each suspicious shape contains:
  - `risk_score`
  - `reasons`
  - `autofit`
  - text-box geometry
  - estimated occupancy ratio
- `estimated_text_height_exceeds_box` is the strongest structural signal
- `no_autofit` raises the risk when the box is already dense

## Recommended follow-up

After the structural pass:

1. Render only the suspicious slides to PDF or images.
2. Verify whether the text really crosses the intended card/container boundary.
3. If overflow is confirmed, adjust one or more of:
   - font size
   - line spacing
   - text box height
   - text box width
   - autofit mode
4. Re-run the detector after edits.

That gives you a practical loop:

`detect -> render verify -> fix -> detect again`

## Pitfalls

- The detector does not know the real rendered background card boundary unless that matches the text-box geometry.
- Different renderers can still disagree. Treat Microsoft PowerPoint or your delivery renderer as final authority.
- Tables, SmartArt, and image-embedded text are outside this MVP and need separate handling.
