# OfficeCLI PowerPoint Highlight XML Debug

When to use: PowerPoint text highlighting (yellow highlight) is not displaying correctly in OfficeCLI-generated or modified slides.

## Diagnostic Steps

1. Extract and inspect the slide XML:
   ```bash
   unzip -p yourfile.pptx ppt/slides/slideN.xml | grep -i highlight
   ```

2. Verify the highlight tag is nested inside `<a:rPr>` (run properties):
   ```xml   <a:r>
     <a:rPr>
       <a:highlight>
         <a:srgbClr val="FFFF00"/>
       </a:highlight>     </a:rPr>
     <a:t>text</a:t>
   </a:r>
   ```

## Common Fix: Add Alpha Transparency

If highlights render but appear invisible or wrong, the PowerPoint version may require explicit alpha in the color value. Add `<a:alpha val="100000"/>` (100% opaque) inside the `<a:srgbClr>`:

```xml
<a:highlight>
  <a:srgbClr val="FFFF00">
    <a:alpha val="100000"/>
  </a:srgbClr>
</a:highlight>
```

## Fallback: Text Box Background Color

If highlight tags continue to fail, apply yellow background to the parent shape's `<a:solidFill>` instead of using text highlight tags.

## Validation

After patching, repack the PPTX and verify with `unzip -p` that the XML is well-formed. Open the file in PowerPoint to confirm display.
