# OfficeCLI PPT Text Overflow Debug

## When to use

Use this workflow when a `.pptx` already shows overflow symptoms and you need to debug why the text box is failing, not just detect that it is risky.

This is most useful after the structural detector has already flagged suspicious slides.

## Debug sequence

1. Inspect the target slide structure first.
2. Confirm which shape actually owns the overflowing body text.
3. Check the text box geometry and body insets.
4. Check the text runs and paragraph settings.
5. Check the autofit mode.
6. Make one minimal change at a time and re-check.

## What to inspect

- the body text shape rather than the title placeholder
- `a:bodyPr` settings and whether `noAutofit`, `normAutofit`, or `spAutoFit` is present
- run font sizes in `a:rPr`
- paragraph line spacing and explicit line breaks
- whether the generated content is too long for the intended layout
- whether the text should actually be split across multiple slides

## Practical pattern

Start with the structural detector:

```bash
python scripts/pptx_overflow_detector.py path/to/deck.pptx --json
```

Then focus your XML or OfficeCLI inspection on the highest-risk slide and text box only.

## Fix options

- reduce body font size slightly
- reduce line spacing
- enlarge the body text box
- switch away from `noAutofit` when that matches the desired layout behavior
- shorten or split copy across multiple slides

## Pitfalls

- a deck can be XML-valid and still overflow visually
- repeated blind edits to a damaged deck can make the XML harder to reason about
- if validation starts failing repeatedly after many mutations, rebuild the problematic slide or deck from a fresh output path
