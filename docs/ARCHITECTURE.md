# Horbot Architecture

- [Project Home](../README.md)
- [Chinese Version](./ARCHITECTURE_CN.md)

## Core Idea

Horbot keeps the runtime intentionally small:

- the model remains the decision-maker
- the harness provides tools, permissions, memory, and persistence
- the Web layer exposes operations without turning the stack into a heavy framework

## Main Layers

### Interface Layer

- Web UI
- CLI
- external chat channels

### Core Runtime

- `AgentLoop` for iterative model-tool execution
- `ContextBuilder` for assembling runtime context
- `SessionManager` for conversation persistence
- `MemoryStore` for agent-scoped memory
- `SkillsLoader` for built-in and user skills

### Multi-Agent Layer

- `AgentManager` for per-agent configuration and lifecycle
- `TeamManager` and team workspaces
- relay-style team chat and ordered agent participation

### Provider And Tool Layer

- provider registry and provider adapters
- local tools, browser tools, MCP tools, and file operations
- permission profiles and workspace restrictions

### Persistence Layer

- `.horbot/agents/<agent-id>/workspace`
- `.horbot/agents/<agent-id>/memory`
- `.horbot/agents/<agent-id>/sessions`
- `.horbot/agents/<agent-id>/skills`
- `.horbot/data/*` for uploads, plans, sessions, and cron data

## Memory Model

The active memory model is agent-scoped:

- `L2/MEMORY.md` for durable facts
- `L1/HISTORY.md` for recent summaries
- `L1/REFLECTION.md` for reusable strategies and corrected assumptions

Team shared memory is stored separately under `.horbot/teams/<team-id>/shared_memory`.

Legacy `.horbot/context` and `.horbot/memory` are not part of the current runtime path.

## Skill Loop

Horbot supports two skill paths:

1. Built-in skills from `horbot/skills`
2. User or auto-generated skills from the current agent skill directory

Completed tool-backed work can be reviewed in the background and, when reusable, distilled into agent skills and reflection memory.

## Web Surface

The Web UI currently covers:

- configuration and providers
- agents and teams
- chat and relay conversations
- skills import/edit/compatibility
- channels and runtime status
- dashboard and token usage
