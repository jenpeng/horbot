# Live Artifact To PPT

Use this note when a PPT workflow benefits from a chat-side interactive preview before generating or revising the final deck.

## When To Use
- The user needs to inspect chart/story/dashboard structure before committing to slides.
- The deck requires data-driven pages such as KPI dashboards, map stories, comparison tables, or executive reports.
- The slide design is uncertain and should be validated visually in chat first.

## Workflow
1. Generate a concise Markdown explanation plus a `horbot-renderable` block using the `live-artifact-studio` contract.
2. Ask the user to render and inspect the temporary view when design approval is needed.
3. Convert the approved structure into PPT pages:
   - KPI cards become summary slides or dashboard strips.
   - Chart points become editable chart data or OfficeCLI shapes.
   - Narrative sections become speaker notes, callouts, or section divider copy.
   - Rows become appendix tables or detailed evidence slides.
4. Run the existing OfficeCLI PPT overflow checks after generating the deck.

## Constraints
- Do not paste raw generated HTML into the PPT workflow.
- Treat the renderable JSON as the source of truth.
- Keep `template` as a string from the supported Horbot whitelist: `dashboard`, `chart-story`, `data-workbench`, `map-story`, `process-map`, or `interactive-report`.
- Do not place HTML, CSS, JavaScript, or a custom template object inside the renderable spec. Use `items`, `points`, `sections`, and `rows` as the reusable data contract.
- If the user wants the live view preserved, export it separately or recreate it from the JSON spec; otherwise runtime HTML is temporary.
