# OfficeCLI PowerPoint cross-file slide-copy limitation

## When to use
Use when a user asks to copy or import slides from one PowerPoint file into another using OfficeCLI.

## Workflow
1. Verify the available OfficeCLI operations before promising slide transfer.
2. Check whether the tool supports cross-file slide duplication, import, or external-node references.
3. If OfficeCLI only operates within the currently opened file, state clearly that cross-file slide copy is not supported.
4. Explain the limitation in tool terms, not as user error.
5. Offer practical alternatives:
   - continue generating slides inside the existing template file,
   - recreate the layout manually in a new file if acceptable,
   - ask the user which fallback they prefer before doing bulk work.

## Checks
- Confirm there is no operation equivalent to external slide import or copy.
- Distinguish same-file slide operations from cross-file operations.
- Keep the explanation concise and decision-oriented.

## Pitfalls
- Do not imply the tool can copy slides across files when it cannot.
- Do not start large-scale manual recreation without confirming the fallback path.
- Do not present template inheritance and manual reconstruction as equivalent-quality outcomes.
