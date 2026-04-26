# OfficeCLI PPT highlight may live in `endParaRPr`

## When to use
Use this when PowerPoint text highlighting does not appear as expected after applying run-level formatting, or when a manually edited sample shows different XML than the generated output.

## Workflow
1. Inspect a manually corrected slide XML before assuming the highlight belongs in `<a:rPr>`.
2. Compare the paragraph containing the target text against the generated version.
3. Check whether the visible highlight is stored in `<a:endParaRPr>` instead of the text run's `<a:rPr>`.
4. If so, update the repair script or XML patch logic to reproduce the sample structure exactly.
5. After patching, ask the user to run the script if execution is blocked, then re-check the resulting XML on a few slides.

## Checks
- Verify the highlight tag is attached at the same XML level as the manual sample.
- Confirm the color value matches the expected highlight color.
- Spot-check multiple slides containing the target phrase, not just one sample slide.

## Pitfalls
- Do not assume all PPT highlights are run-level; some visible results may be driven by paragraph end properties.
- Do not generalize from OfficeCLI API behavior alone when direct XML evidence disagrees.
- Avoid bulk patching until a hand-edited reference slide has been inspected.
