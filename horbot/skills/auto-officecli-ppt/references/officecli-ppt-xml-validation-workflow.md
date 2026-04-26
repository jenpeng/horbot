# OfficeCLI PPT XML Validation Workflow

## When to use
- After bulk OfficeCLI edits to a `.pptx`, you need to verify formatting was applied correctly across many slides.
- GUI opening is slow or unavailable; you want a fast, scriptable way to confirm highlights, font sizes, or other OpenXML properties.
- You suspect OfficeCLI silently skipped or misapplied formatting on some slides.

## Steps

1. **Pick a temporary working directory**
   ```bash
   cd /tmp
   ```

2. **Inspect a single slide for a specific XML tag**
   ```bash
   unzip -p "path/to/file.pptx" ppt/slides/slide5.xml | grep "<a:highlight>"
   ```
   - Count matching lines to confirm the expected number of highlights.

3. **Check font sizes across a slide**
   ```bash
   unzip -p "path/to/file.pptx" ppt/slides/slide7.xml | grep -o 'sz="[0-9]*"' | sort | uniq -c
   ```
   - Verify title vs body sizes match the intended design (e.g., `4000` for 40pt, `2400` for 24pt, `2000` for 20pt).

4. **Batch-verify many slides**
   ```bash
   for i in $(seq 2 60); do
     echo "=== Slide $i ==="
     unzip -p "path/to/file.pptx" "ppt/slides/slide${i}.xml" | grep -o 'sz="[0-9]*"' | sort | uniq -c
   done
   ```
   - Scan for outliers (unexpected sizes or missing tags).

5. **Cross-check against the expected slide list**
   - Maintain a list of slides that should have a specific property (e.g., slides containing "词汇应用" need a highlight).
   - Run the grep per slide and assert the count is `> 0`.

## Pitfalls
- Slide numbering in filenames starts at `slide1.xml`, but presentation slide indices may differ if hidden slides exist.
- `grep` counts lines; if multiple highlights exist in one run, line count still equals run count, not highlight count. Use `grep -o` and count tokens if exact occurrence matters.
- Always quote the `.pptx` path to handle spaces.
- This reads XML directly; it will not catch rendering issues caused by theme/master inheritance. Complement with spot-checks in PowerPoint when possible.

## Example: verify highlights on targeted slides
```bash
for s in 2 3 5 6 8 9 11 12 14 15 17 18 20 21 23 24 26 27 29 30 32 33 35 36 38 39 41; do
  count=$(unzip -p "file.pptx" "ppt/slides/slide${s}.xml" | grep -c "<a:highlight>")
  echo "Slide $s: $count highlights"
done
```
