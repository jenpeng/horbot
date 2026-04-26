# Generate PPTX XML Patch Script for Precise Run-Level Formatting

## When to use
- OfficeCLI's high-level API cannot apply formatting to a specific substring (e.g., highlighting only "词汇应用" but not surrounding text).
- You need to inject or modify `<a:rPr>` properties (highlight, color, bold, font size) at the run level inside slide XML.
- Direct XML manipulation is safer than repeated failed OfficeCLI attempts.

## Steps
1. **Identify the target slides and text patterns**  
   Determine which slides contain the text that needs formatting and the exact substring to match.

2. **Write a standalone Python script** that:
   - Creates a `.backup_real` copy of the original `.pptx`.
   - Unzips the `.pptx` to a temp directory.
   - Iterates over `ppt/slides/slide*.xml`.
   - Parses or regex-searches for `<a:r>` runs containing the target text.
   - Inserts the desired property (e.g., `<a:highlight><a:srgbClr val="FFFF00"/></a:highlight>`) inside the corresponding `<a:rPr>`, creating `<a:rPr>` if absent.
   - Rezips the directory back into a `.pptx`.

3. **Run the script via `exec`**  
   If `exec` is blocked, fall back to delivering the script with exact manual execution instructions (see `auto-exec-blocked-script-delivery-fallback`).

4. **Validate with XML inspection**  
   Unzip the repaired `.pptx` and `grep` for the inserted tags to confirm they appear only in the intended runs.

## Key checks
- Ensure the modification targets `<a:rPr>` at the **run level**, not the paragraph level, to avoid coloring the entire shape.
- Verify that adjacent runs sharing the same paragraph are not accidentally modified.
- Confirm the backup copy exists before overwriting.

## Pitfalls
- Modifying `<a:pPr>` instead of `<a:rPr>` will apply formatting to the whole paragraph/shape.
- Regex replacements must be careful not to break XML nesting or duplicate tags.
- Always rezip with the correct internal structure; macOS `zip` may add extra metadata that corrupts the `.pptx`.
