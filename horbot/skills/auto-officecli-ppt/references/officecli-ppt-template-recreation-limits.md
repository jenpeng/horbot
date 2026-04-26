# PowerPoint template recreation limits with OfficeCLI

## When to use
Use when editing or generating `.pptx` files with OfficeCLI and the task expects slides to match an existing template closely, especially when adding new slides based on sample/template pages.

## Workflow
1. Inspect the template/sample slides first to identify the visible structure: title, body text, lines/connectors, shapes, and approximate positions.
2. Recreate the slide using supported OfficeCLI objects instead of assuming template placeholders or master-layout behavior will carry over to newly added slides.
3. Validate object types and API-specific values before retrying failed insertions. For example, connector creation may require a preset like `straight` even if readback labels appear as `line`.
4. After making a sample set of recreated slides, run a structural check to confirm the expected visible elements are present.
5. Before bulk generation, clearly tell the user whether the output is:
   - true template/page duplication, or
   - high-fidelity visual recreation only.
6. If master placeholders are not preserved on new slides, pause and get confirmation before continuing large-scale generation.

## Checks
- Confirm whether new slides inherit master/layout placeholders automatically.
- Compare a recreated sample slide against the source for element count and visible hierarchy.
- Verify tool error messages for allowed enum values instead of reusing display names from read output.
- State the current limitation and resulting quality level before scaling up.

## Pitfalls
- Do not promise binary-identical or master-preserving template copies unless the tool actually supports slide duplication.
- Do not assume readback object names are valid write-time parameter values.
- Avoid bulk-producing many slides before the user accepts any fidelity limitations.
