# OfficeCLI PPT Render Verification Export

## When to use

Use this after the structural overflow detector has already flagged suspicious slides and you need real rendered review material instead of only XML heuristics.

This workflow is for:

- exporting a review PDF through LibreOffice
- handing suspicious slides to a human reviewer
- preparing a later OCR or vision-model stage

## Command

```bash
python scripts/pptx_overflow_detector.py path/to/deck.pptx --json --verify-render
```

Force LibreOffice for the current Horbot workflow:

```bash
python scripts/pptx_overflow_detector.py path/to/deck.pptx --json --verify-render --renderer libreoffice
```

## Renderer policy

Horbot's Web PPTX preview uses LibreOffice only: PPTX is converted to PDF, then pages are rendered to PNG lazily.

If an older local detector still exposes other renderer options, do not use them for the Horbot preview path. Prefer `--renderer libreoffice` so review output matches the Web UI pipeline.

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
- LibreOffice conversion is slower than XML inspection, especially for very large decks.
- If no renderer is available, run `./horbot.sh install libreoffice` or install LibreOffice manually, then rerun.
