# OfficeCLI PPT: Run Fill vs. Shape Fill Trap

## When to use

You are using OfficeCLI to highlight or color specific text (a `run`) inside a PowerPoint slide, but the color ends up applied to the entire text box (`shape`) instead of just the intended words.

## The trap

- OfficeCLI's `fill` property on a `run` may be interpreted at the shape level, causing the whole text box to take that background color.
- OfficeCLI does **not** expose a `highlight` property for true text-background highlighting.
- If a shape contains multiple paragraphs/runs, setting `fill` on any run can paint the entire shape.

## Steps to diagnose

1. **Target the run precisely** — use the full run path, e.g. `/slide[5]/shape[@id=10004]/paragraph[1]/run[1]`.
2. **Apply the color** — set `fill` to the desired hex (e.g., `FFFF00`).
3. **Verify immediately** — inspect the shape (not just the run) to see whether the `fill` leaked to the whole shape.
4. **Check child runs** — confirm whether other runs in the same shape also show the background color.

## Safe workarounds (in order of preference)

1. **Accept shape-wide fill** — If the visual result is acceptable (e.g., the whole block is a callout/highlight section), document this behavior and proceed.
2. **Split into separate shapes** — Move the target text into its own text box so shape fill equals run fill. Update layout coordinates to preserve alignment.
3. **Use XML manipulation** — If OfficeCLI cannot achieve run-level highlighting, fallback to direct OpenXML editing on the `.pptx` (unzip, edit `ppt/slides/slideN.xml`, adjust `<a:rPr><a:highlight>` for the run, rezip).
4. **Propose to the user** — Present the trade-off (accept broad fill vs. complex split/XML fix) and let the user decide before making large structural changes.

## Pitfalls

- Do **not** assume `run.fill` is scoped to the run text only.
- Do **not** perform bulk edits across many slides before validating one sample slide.
- Do **not** split shapes without checking layout/template dependencies; placeholders and master layouts may break.

## Related skills

- `auto-officecli-ppt-slide-fidelity-debug` — for comparing generated vs. template slide structure.
- `auto-officecli-ppt-master-background-inheritance` — for XML-level fixes when OfficeCLI limits are hit.
