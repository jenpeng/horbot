# Skills

- [Project Home](../README.md)
- [Chinese Version](./SKILLS_CN.md)

## Skill Types

Horbot uses:

- built-in skills from `horbot/skills`
- user or auto-generated skills from the current agent skill directory

The Skills page also separates these into:

- `System`: built-in skills maintained with the project
- `Custom`: workspace-local skills, including manual and auto-generated entries

## Package Formats

Supported imports:

- `.skill`
- `.zip`

Validation covers:

- package root structure
- required `SKILL.md`
- frontmatter validity
- `name` and `description`
- relative references inside the package
- compatibility hints and missing requirements

## Compatibility

Imported skills are checked against the current environment for:

- operating system
- required CLI binaries
- required environment variables
- legacy metadata normalization

## Automatic Skill Distillation

Horbot can quietly review completed tool-backed work and create or update reusable skills when the workflow is repeatable.

Auto-generated skills now prefer a family layout instead of one folder per tiny variation:

- `SKILL.md` stays lean and describes the shared trigger cues
- detailed techniques live under `references/*.md`
- related auto-skills can be merged into one broader family such as `auto-officecli-ppt`

The current loop is:

1. task completes
2. background review checks reusability
3. reusable workflow becomes a skill family or updates an existing family
4. reflection and history memory are updated

When a user explicitly asks an agent to summarize prior experience into a skill, the agent should use the managed `save_skill` tool. This tool writes only to the current agent skill store, validates the generated `SKILL.md`, and keeps detailed techniques under `references/`. Agents should not use raw `write_file` calls for skill persistence.

The Web UI also exposes:

- `Consolidate Generated`: manually merge related `auto-*` skills into broader families
- `Promote to Builtin`: turn a custom workspace skill into a built-in system skill
- `Export`: download a system or custom skill as a re-importable `.skill` package, including `references/` and other standard skill files

## Storage

The active skill path is agent-scoped:

- `.horbot/agents/<agent-id>/workspace/.horbot-agent/skills`

Legacy `.horbot/agents/<agent-id>/skills` and `workspace/skills` assumptions no longer describe the current runtime.

## Selected Built-In Skills

### `officecli` - Office document operations

Use this when OfficeCLI MCP is available and the task involves Word, Excel, PowerPoint, or OpenXML-aware document edits.

Rules:

- inspect document structure with `view` / `get` / `query` before mutating content
- prefer high-level Office operations over raw XML or XPath
- if the server exposes a single generic tool such as `mcp_officecli_officecli`, pass the concrete `command` argument directly
- for `.xlsx`, use real OfficeCLI property names such as `font.color`, `font.size`, `fill`, and `alignment.horizontal`
- for `.pptx`, run `validate` after structural edits and prefer recreating a deck at a fresh path if validation starts failing
- if OfficeCLI is unavailable, do not claim native Office edits succeeded
