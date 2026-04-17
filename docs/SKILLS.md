# Skills

- [Project Home](../README.md)
- [Chinese Version](./SKILLS_CN.md)

## Skill Types

Horbot uses:

- built-in skills from `horbot/skills`
- user or auto-generated skills from the current agent skill directory

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

The current loop is:

1. task completes
2. background review checks reusability
3. reusable workflow becomes a skill
4. reflection and history memory are updated

## Storage

The active skill path is agent-scoped:

- `.horbot/agents/<agent-id>/skills`

Legacy `workspace/skills` assumptions no longer describe the current runtime.

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
