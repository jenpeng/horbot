# OfficeCLI PPT Slide Fidelity Debugging

## When to use

Use when OfficeCLI-generated slides look wrong, deviate from a template sample, or have formatting/layout issues (wrong fonts, missing highlights, overflow, etc.).

## Steps

1. **Identify the reference sample**
   - Locate the "correct" slides (e.g., slides 1–3) that match the intended template.
   - Note the slide layout name used by the sample.

2. **Inspect shape types**
   - For each key shape (title, body/content), check whether it is a **placeholder** (e.g., `Title`, `Content`) or a plain `Text Box`.
   - Generated slides must use the same placeholder types as the sample; plain text boxes break master inheritance.

3. **Check autofit settings**
   - Compare `normAutofit` vs `none` on text frames.
   - If the sample uses `normAutofit`, generated slides must too; otherwise long content overflows or shrinks unexpectedly.

4. **Compare explicit formatting**
   - Highlight / background color (e.g., `FFFF00` yellow)
   - Separator lines / shapes
   - Bullet styles and indentation
   - Paragraph spacing and alignment

5. **Detect font-size deviations**
   - If generated slides use smaller font sizes (e.g., 18 pt instead of 24 pt), it usually means content overflow or missing autofit.
   - List any slides where the body font size differs from the sample.

6. **Summarize findings in a table**

   | Element | Sample | Generated | Issue |
   |---------|--------|-----------|-------|
   | Title type | `Title` placeholder | `Text Box` | Should use master placeholder |
   | Body type | `Content` placeholder | `Text Box` | Should use content placeholder |
   | Autofit | `normAutofit` | `none` | Content overflows |
   | Highlight | `FFFF00` present | Missing | Add yellow highlight |
   | Separator | Present | Missing | Add separator line |

7. **Prioritize fixes**
   - Fix placeholder types first (structural).
   - Then autofit.
   - Then cosmetic formatting (highlights, separators).

## Pitfalls

- Do not assume `Text Box` is acceptable for titles or body content if the sample uses placeholders; master inheritance will be lost.
- Font-size reduction is a symptom, not the root cause. Always trace back to autofit or placeholder type.
- When content is very long, `normAutofit` may still shrink text. Consider splitting content or increasing placeholder size rather than disabling autofit.
