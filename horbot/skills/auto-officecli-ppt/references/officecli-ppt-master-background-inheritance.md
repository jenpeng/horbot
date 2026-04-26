# Auto-OfficeCLI PPT Master Slide Background Fix

## When to use

When using OfficeCLI to generate PowerPoint slides that look correct in isolation but miss master slide formatting (background color, theme colors) after insertion — especially when slides are created as plain text boxes rather than inheriting from the template.

## Steps

1. **Identify the gap**: Generate one or two test slides and render to SVG. Compare with the template/example slide. Look for missing background color (`<rect fill="...">`), font styles, or placeholder behaviors.

2. **Inspect the working slide's XML**: Use `exec` to unzip the `.pptx` and examine the XML of a correctly formatted slide (e.g., slide 1). Locate the background color definition — it may be in `slideMasters/slideMaster1.xml` rather than the slide itself.

3. **Identify the background source**:
   - If the background comes from the slide **master**, slides won't inherit it unless they use master placeholders.
   - Check both `ppt/slides/` (individual slide XML) and `ppt/slideMasters/` (master definitions).

4. **Inject the background into all slides**: For each slide XML, add a `<p:bg>` element referencing the correct fill color. Example for orange-red `#F26B43`:
   ```xml
   <p:bg>
     <p:bgPr>
       <a:solidFill>
         <a:srgbClr val="F26B43"/>
       </a:solidFill>
       <a:effectLst/>
     </p:bgPr>
   </p:bg>
   ```
   Insert this right after `<p:cSld>` opening tag, before `<p:spTree>`.

5. **Batch-apply to all slides**: Use `exec` with a Python one-liner or shell loop to inject the background element into every slide XML in `ppt/slides/`.

6. **Re-zip and validate**: Re-pack the `.pptx`, then render a few slides to SVG to confirm the background color is present. Check slides 1, middle, and last.

## Pitfalls

- **Slides look fine in code but render wrong**: Always render to SVG and visually compare with the template — text-only inspection misses background and theme effects.
- **Master slide vs. slide-level background**: A slide that *should* inherit from the master but doesn't may have no `<p:bg>` element at all. Adding it fixes the inheritance gap.
- **Other master properties may also be missing**: After fixing the background, verify fonts (should be 微软雅黑) and line spacing (should be 150%) are also present. Inject those at the `<a:pPr>` level if needed.
- **Do not hardcode file paths**: Use the working directory or temp paths. Do not reference absolute paths like `/Users/...`.
