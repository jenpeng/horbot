# OfficeCLI PPT Text Overflow Debugging

## When to use
- Generated PowerPoint slides still show text overflow after increasing text box height/width.
- Font sizes appear unexpectedly small (e.g., 18pt–23pt) on slides with long content.
- `normAutofit` is enabled and overriding manual dimension adjustments.

## Steps

1. **Identify overflow slides**
   - Inspect each slide's text box font size.
   - Flag slides where the font size is smaller than the intended/target size (common threshold: < 24pt).

2. **Confirm root cause**
   - Verify that `normAutofit` is active on the text body properties.
   - Recognize that PowerPoint autofit reduces font size to fit the text box; increasing box dimensions alone may not help if the content volume is too large.

3. **Choose a fix strategy**
   - **Reduce content volume**: Shorten text, remove less critical lines, or trim examples.
   - **Split content**: Distribute long text across multiple text boxes on the same slide, or split into multiple slides.
   - **Disable normAutofit** (if design allows): Switch to `noAutofit` so the font stays fixed, then manually ensure the box is large enough.
   - **Decrease target font size globally** (last resort): If the design permits, lower the base font size so more content fits naturally.

4. **Validate after fix**
   - Re-inspect the flagged slides and confirm font sizes are at or above the target threshold.
   - Check that no text is visually clipped or overlapping.

## Pitfalls
- Increasing text box height without reducing content or disabling autofit often has no effect because `normAutofit` will still shrink the font.
- Do not assume overflow is only a width issue; long vertical content triggers the same autofit behavior.
- Always verify on a slide-by-slide basis—some slides may look fine while others silently overflow.

## Checks
- [ ] List of overflow slides identified with actual vs. target font sizes.
- [ ] Root cause confirmed as autofit behavior, not just insufficient box size.
- [ ] Fix applied (content reduction, split, or autofit disabled).
- [ ] Post-fix validation shows font sizes restored and no clipping.
