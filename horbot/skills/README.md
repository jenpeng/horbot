# horbot Skills

This directory contains built-in skills that extend horbot's capabilities.

The project's core code borrows from the [HKUDS/nanobot](https://github.com/HKUDS/nanobot) repository and continues to evolve on top of that foundation.

## Skill Format

Each skill is a directory containing a `SKILL.md` file with:
- YAML frontmatter (name, description, metadata)
- Markdown instructions for the agent

## Attribution

These skills are adapted from [OpenClaw](https://github.com/openclaw/openclaw)'s skill system.
Horbot keeps runtime compatibility with OpenClaw skill metadata through a dedicated adapter layer.

## Metadata Compatibility

Horbot uses `horbot` as the canonical skill metadata schema.
The loader also accepts `openclaw` metadata and normalizes it into Horbot's internal shape.

Recommended authoring format:
- `metadata: {"horbot": {...}}`

Compatible legacy format:
- `metadata: {"openclaw": {...}}`

The normalized result records compatibility details such as:
- `source_schema`
- `source_schema_version`
- `canonical_schema`
- `canonical_schema_version`
- `normalized_from_legacy`

## Available Skills

| Skill | Description |
|-------|-------------|
| `autonomous` | Autonomous execution of complex tasks |
| `clawhub` | Search and install skills from ClawHub registry |
| `cron` | Manage scheduled tasks |
| `github` | Interact with GitHub using the `gh` CLI |
| `memory` | Memory management with hierarchical context (L0/L1/L2) |
| `self-improvement` | AI self-improvement capabilities: code review, capability assessment, error analysis |
| `skill-creator` | Create new skills |
| `summarize` | Summarize URLs, files, and YouTube videos |
| `tmux` | Remote-control tmux sessions |
| `weather` | Get weather info using wttr.in and Open-Meteo |

## Self-Improvement Skill

The `self-improvement` skill enables AI to autonomously improve its capabilities:

**Features**:
- Code review and optimization
- Capability assessment
- Error analysis
- Learning suggestion generation

**Templates**:
- `templates/code-review.md` - Code review template
- `templates/capability-assessment.md` - Capability assessment template
- `templates/learning-plan.md` - Learning plan template

**Integration with Hierarchical Context**:
- L0: Active improvement tasks and ongoing reviews
- L1: Recent improvements and lessons learned
- L2: Integrated improvement patterns and best practices
