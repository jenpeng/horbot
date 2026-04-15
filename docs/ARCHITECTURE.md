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
- external chat channels such as WeCom, Feishu, ShareCRM, Telegram, Slack, Matrix, and Mochat

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
- native `web_access` is the preferred web/search entrypoint for agents
- `browser`, `web_search`, and `web_fetch` remain available as interactive or lightweight fallbacks
- permission profiles and workspace restrictions

### Built-In Browser Access Runtime

- `horbot.sh` now manages a built-in `web-access` proxy service as part of the normal local stack
- the proxy listens on `127.0.0.1:3456` and is started by `./horbot.sh start|restart`
- startup only performs a passive readiness check and no longer opens a visible browser window
- the first real browser-backed request can auto-launch a headless Chrome instance with remote debugging on `127.0.0.1:9222`
- the browser MCP server prefers this proxy first, then falls back to Playwright if needed

### Channel Runtime

- endpoint catalog and missing-config diagnostics
- long-lived connectors for official and ecosystem chat gateways
- reply-mode streaming and media handling for channels that support progressive edits

### Persistence Layer

- `.horbot/agents/<agent-id>/workspace`
- `.horbot/agents/<agent-id>/memory`
- `.horbot/agents/<agent-id>/sessions`
- `.horbot/agents/<agent-id>/skills`
- `.horbot/data/*` for uploads, plans, sessions, and cron data
- remote image cards can also be materialized into `.horbot/data/uploads` so later history loads still render as normal file attachments

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

This loop is aligned with the current agent-scoped memory layout rather than legacy global memory folders.

## Web Surface

The Web UI currently covers:

- configuration and providers
- agents and teams
- chat and relay conversations
- baton-aware relay navigation between direct chat and team chat during DM-initiated team dispatch flows
- richer attachment preview UX, including inline previews and a bottom thumbnail strip for multi-image preview modals
- assistant history normalization that upgrades standalone remote image URLs into image-card attachments when possible
- a Configuration-page remote-image cache panel with runtime stats and a manual clear action
- skills import/edit/compatibility
- channels and runtime status, including WeCom endpoint testing
- dashboard and token usage
