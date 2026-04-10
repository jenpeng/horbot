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
