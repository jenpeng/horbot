# OfficeCLI PPT XML Repair Script Delivery (Exec Blocked)

## When to use
- You need to fix PowerPoint XML (highlights, fonts, backgrounds, autofit, etc.) but `exec` is blocked by confirmation gates.
- OfficeCLI operations failed or are insufficient, and direct Python XML manipulation is required.
- You must hand off a repair script to the user for manual execution.

## Steps

1. **Assess the damage**
   - Identify which slides and XML elements need changing (e.g., `<a:rPr>`, `<a:bodyPr>`, `<p:spPr>`).
   - Note the target .pptx path and any backup requirements.

2. **Build a standalone Python script**
   - Use only the standard library (`zipfile`, `os`, `shutil`, `xml.etree.ElementTree` or `lxml` if available).
   - Make the script:
     - Accept the .pptx path as an argument or hardcode it clearly at the top.
     - Create a backup (`*.pptx.backup`) before modifying.
     - Unzip the .pptx to a temp directory.
     - Parse and mutate the relevant `ppt/slides/slide*.xml` files.
     - Rezip with correct compression and `.pptx` extension.
     - Print a clear success/failure summary.
   - Include error handling for missing files or parse errors.

3. **Deliver via `write_file`**
   - Save the script to a user-accessible location (e.g., Desktop).
   - Do not include secrets, tokens, or absolute paths that won’t exist on the user’s machine.

4. **Provide exact manual instructions**
   - Give the precise terminal command, including quoted paths if spaces exist.
   - Ask the user to share the output so you can verify the fix.

5. **Post-execution validation plan**
   - Once the user runs the script, ask them to confirm the output.
   - If possible, guide them to verify visually in PowerPoint or by re-inspecting the XML.

## Pitfalls
- **Path assumptions**: Avoid hardcoding home-directory paths; prefer `~/Desktop` or instruct the user to update the path variable at the top of the script.
- **Rezip structure**: Ensure the final archive keeps the same top-level structure (`[Content_Types].xml` at root, `ppt/` folder, etc.). `zipfile.write` with `arcname` helps preserve layout.
- **XML namespaces**: When editing OpenXML, register or preserve namespaces so ElementTree does not inject redundant `ns0:` prefixes.
- **Backup first**: Always create a `.backup` copy; a bad rezip can corrupt the presentation.
- **Don’t hallucinate execution**: Since `exec` is blocked, never claim the script was run by you. Explicitly state the user must run it.

## Example snippet structure
```python
import zipfile, shutil, os, tempfile
from xml.etree import ElementTree as ET

pptx_path = "/path/to/file.pptx"
backup_path = pptx_path + ".backup"
shutil.copy2(pptx_path, backup_path)

tmp = tempfile.mkdtemp()
with zipfile.ZipFile(pptx_path, 'r') as z:
    z.extractall(tmp)

# ... edit ppt/slides/slide1.xml ...

with zipfile.ZipFile(pptx_path, 'w', zipfile.ZIP_DEFLATED) as zout:
    for root, dirs, files in os.walk(tmp):
        for f in files:
            full = os.path.join(root, f)
            arc = os.path.relpath(full, tmp)
            zout.write(full, arc)

print("Done. Backup:", backup_path)
```
