# Bulk Paragraph Formatting for OfficeCLI PowerPoint Slides

## When to use
- You generate or copy many slides programmatically with OfficeCLI and discover that paragraph-level formatting (e.g., lineSpacing) is missing or inconsistent.
- Template/master placeholders do not propagate paragraph properties to newly created shapes, so explicit per-shape fixes are required.

## Steps

1. **Identify the gap**
   - Inspect a sample slide that looks correct and note its paragraph properties (lineSpacing, alignment, bullet style, spaceBefore/After).
   - Inspect a broken slide and confirm the same properties are missing or different.

2. **Plan the batch update**
   - Determine the slide range to fix (e.g., slides 4–60).
   - Determine the target shapes per slide (e.g., all textboxes, or specific shape IDs).
   - Choose the exact property values from the correct sample.

3. **Apply in batches**
   - Use OfficeCLI to update each target shape with the missing paragraph property.
   - Batch by slide range to avoid overly large single calls.
   - Example target property: `lineSpacing=1.5x`.

4. **Verify a sample**
   - Read back at least one fixed slide and one original sample slide.
   - Compare the relevant properties side-by-side to confirm parity.

5. **Validate the file**
   - Run OfficeCLI validation to ensure no corruption was introduced.

6. **Report clearly**
   - Summarize the scope (slide count, shape count, property changed).
   - Include a before/after comparison table for quick user confirmation.

## Common pitfalls
- **Master/template inheritance is limited**: paragraph-level settings like lineSpacing often do not inherit; always verify after generation.
- **Shape IDs can differ per slide**: if targeting specific shapes, confirm IDs are consistent or iterate by index/type.
- **Batch size**: very large single-batch updates may timeout or fail silently; split into smaller slide ranges.
- **Validation before delivery**: always run a file validation step before declaring the task complete.

## Checks
- [ ] Sample correct slide inspected and properties documented.
- [ ] Broken slide inspected and gap confirmed.
- [ ] Batch updates applied across full slide range.
- [ ] At least one fixed slide read back and compared to sample.
- [ ] OfficeCLI validation passes with no errors.
- [ ] Summary delivered with scope and comparison table.
