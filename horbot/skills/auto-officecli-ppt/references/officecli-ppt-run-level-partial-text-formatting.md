# OfficeCLI PPT Run-Level Partial Text Formatting

## When to use
- You need to format only part of a text string inside a PowerPoint shape (e.g., highlight just the label "词汇应用" but leave surrounding text unchanged).
- OfficeCLI bulk or paragraph-level formatting is coloring/highlighting the entire shape or paragraph instead of the intended substring.
- You are editing OpenXML directly via a script to fix OfficeCLI-generated `.pptx` files.

## Core rule
**Always apply formatting at the `<a:r>` (run) level, never at the paragraph-level `<a:rPr>`.**

In OpenXML, a paragraph (`<a:p>`) contains one or more runs (`<a:r>`). Each run has its own run properties (`<a:rPr>`). Formatting placed in the paragraph-level `<a:rPr>` affects the entire paragraph. To target only part of the text, you must split the text into separate runs so the target substring is isolated in its own `<a:r>`.

## Steps

1. **Inspect the current XML**
   - Unzip the `.pptx` and locate the slide XML (`ppt/slides/slideN.xml`).
   - Find the target paragraph (`<a:p>`) and its runs (`<a:r>`).

2. **Check existing structure**
   - If the target text is already in its own `<a:r>`, add the formatting directly to that run's `<a:rPr>`.
   - If the target text shares a run with other text, split the run:
     - Duplicate the `<a:r>` node.
     - Put the text before the target in the first run, the target text in the second run, and the text after in the third run.
     - Preserve all existing `<a:rPr>` attributes (font, size, language) in each new run so formatting is not lost.

3. **Apply formatting to the isolated run**
   - Insert the formatting element inside the target run's `<a:rPr>`, for example:
     - Highlight: `<a:highlight><a:srgbClr val="FFFF00"/></a:highlight>`
     - Color: `<a:solidFill><a:srgbClr val="C00000"/></a:solidFill>`
     - Bold: `b="1"` attribute on `<a:rPr>`
   - Do **not** place these elements in the paragraph-level `<a:rPr>`.

4. **Validate**
   - Grep for the target text and confirm the formatting tag appears only inside the intended `<a:r>`.
   - Ensure no other runs in the same paragraph accidentally inherited the formatting.

5. **Repackage and test**
   - Zip the files back into `.pptx` and open in PowerPoint to visually confirm only the intended substring is formatted.

## Common pitfalls
- **Paragraph-level `<a:rPr>` trap**: Adding a highlight or color to the paragraph properties colors the entire paragraph. This is the most common mistake.
- **Run split without preserving properties**: When splitting a run, forgetting to copy the original `<a:rPr>` (font face, size, language) into the new runs causes formatting loss.
- **Wrong nesting order**: Some OpenXML elements are order-sensitive inside `<a:rPr>`. Keep the original element order when injecting new tags.
- **Not verifying surrounding runs**: After fixing one run, check adjacent runs to ensure they were not accidentally modified during the split.

## Example: before and after

### Before (incorrect — paragraph-level highlight)
```xml
<a:p>
  <a:pPr>...</a:pPr>
  <a:rPr>
    <a:highlight><a:srgbClr val="FFFF00"/></a:highlight>
  </a:rPr>
  <a:r><a:rPr .../><a:t>2.technology /tekˈnɒlədʒi/ 词汇应用 technology company</a:t></a:r>
</a:p>
```

### After (correct — run-level highlight on substring only)
```xml
<a:p>
  <a:pPr>...</a:pPr>
  <a:r><a:rPr .../><a:t>2.technology /tekˈnɒlədʒi/ </a:t></a:r>
  <a:r>
    <a:rPr ...>
      <a:highlight><a:srgbClr val="FFFF00"/></a:highlight>
    </a:rPr>
    <a:t>词汇应用</a:t>
  </a:r>
  <a:r><a:rPr .../><a:t> technology company</a:t></a:r>
</a:p>
```
