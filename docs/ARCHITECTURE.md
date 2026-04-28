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
- Horbot-issued inbound bot endpoints for vendor or local Agent platforms that need an App ID, Token, and push URL instead of a Horbot-calling-out URL

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
- `external_agents` adapter registry for adding vendor, local, OpenAI-compatible, or generic external agents as team members

### External Agent Runtime

- External Agent identity and team membership stay separate from internal `agents.instances`
- `ExternalAgentRuntime` only dispatches `complete()` and `probe()` through the adapter registry
- `inbound-bot` is the primary adapter for Feishu/Discord-style integrations: Horbot owns bot identity, token verification, and inbound message persistence while vendor/local platforms push messages in
- `generic-agent-api` preserves the previous HTTP, HTTP SSE, and WebSocket behavior as a compatibility adapter
- `openai-compatible` supports Chat Completions-style services through `adapter_config.model` and optional endpoint overrides
- Future integrations such as Dify, Coze, LangGraph, MCP Agent, web UI bridges, or channel-backed agents should add adapters instead of branching inside the runtime dispatcher

### Provider And Tool Layer

- provider registry and provider adapters
- local tools, browser tools, MCP tools, and file operations
- `browser`, `web_search`, and `web_fetch` are the standard web/search tools exposed to agents
- Playwright is the default interactive browser runtime
- permission profiles and workspace restrictions

### Built-In Browser Access Runtime

- the browser MCP server now defaults to Playwright for interactive browsing
- `horbot.sh` manages the normal local stack only: backend, frontend, and gateway
- browser-backed requests no longer depend on a built-in `web-access` proxy service

### Channel Runtime

- endpoint catalog and missing-config diagnostics
- long-lived connectors for official and ecosystem chat gateways
- `horbot-inbound-bot` endpoints are channel-owned inbound entrances: Horbot issues credentials, validates pushed messages, and routes them to a fixed bound Agent or to a request-specified Agent that exists in the current running instance
- reply-mode streaming and media handling for channels that support progressive edits

### Persistence Layer

- `.horbot/agents/<agent-id>/workspace`
- `.horbot/agents/<agent-id>/workspace/.horbot-agent/memory`
- `.horbot/agents/<agent-id>/workspace/.horbot-agent/sessions`
- `.horbot/agents/<agent-id>/workspace/.horbot-agent/skills`
- `.horbot/data/*` for uploads, plans, sessions, and cron data
- remote image cards can also be materialized into `.horbot/data/uploads` so later history loads still render as normal file attachments

The workspace root may also contain runtime-owned directories such as `.audit`, `.checkpoints`, and `.state`. These are active runtime artifacts, not duplicate legacy storage.

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

Auto-generated skills now prefer a family-oriented structure:

- one `SKILL.md` per family for shared trigger cues
- detailed techniques under `references/*.md`
- related `auto-*` skills can be consolidated into a broader family instead of multiplying near-duplicates

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
- skills import/edit/compatibility, custom-vs-system grouping, generated-skill consolidation, and promote-to-builtin actions
- channels and runtime status, including WeCom endpoint testing
- dashboard and token usage
