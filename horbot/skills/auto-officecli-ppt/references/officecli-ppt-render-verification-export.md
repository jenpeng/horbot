# OfficeCLI PPT Render Verification Export

## When to use

Use this after the structural overflow detector has already flagged suspicious slides and you need real rendered review material instead of only XML heuristics.

This workflow is for:

- exporting a review PDF through PowerPoint, Keynote, or LibreOffice
- handing suspicious slides to a human reviewer
- preparing a later OCR or vision-model stage

## Command

```bash
python scripts/pptx_overflow_detector.py path/to/deck.pptx --json --verify-render
```

If you want to force the renderer:

```bash
python scripts/pptx_overflow_detector.py path/to/deck.pptx --json --verify-render --renderer powerpoint
```

## Renderer priority

The current implementation prefers:

1. `powerpoint`
2. `keynote`
3. `libreoffice`

That order matches the practical goal of verifying against the delivery renderer when possible.

## What the export gives you

- a structural suspicious-slide list
- a rendered PDF path
- the slide numbers that still need visual confirmation
- capability details when the machine cannot render

## Recommended review loop

1. Run the detector with `--verify-render`.
2. Open the exported PDF.
3. Jump directly to the suspicious slide numbers from the JSON report.
4. Confirm whether text is clipped, escapes the intended card, or becomes too dense.
5. Apply the minimum fix.
6. Re-run the detector and export again if needed.

## Pitfalls

- This stage currently exports rendered review assets; it does not yet auto-decide overflow from pixels.
- PowerPoint or Keynote automation can be slower than XML inspection and may fail if the local app cannot be scripted.
- If no renderer is available, install or enable PowerPoint, Keynote, or LibreOffice and rerun.
