# User Manual

- [Project Home](../README.md)
- [Chinese Version](./USER_MANUAL_CN.md)

## Starting The Project

Recommended:

```bash
./horbot.sh install
./horbot.sh start
```

Default local URLs:

- Web UI: `http://127.0.0.1:3000`
- Backend API: `http://127.0.0.1:8000`

Useful commands:

```bash
./horbot.sh status
./horbot.sh restart
./horbot.sh stop
./horbot.sh logs backend
```

## Main Pages

- `Configuration`: providers, permissions, and global defaults
- `Teams`: agents, teams, workspaces, `SOUL.md`, `USER.md`, and bootstrap summaries
- `Chat`: direct chat, team relay chat, attachments, history, and interruptions
- `Skills`: create, edit, import, inspect compatibility, consolidate auto-generated skills, and promote custom skills to built-in
- `Channels`: endpoint configuration, missing-field diagnostics, and connectivity tests
- `Dashboard`: high-level operational overview
- `Status`: runtime diagnostics
- `Tokens`: token usage trends

## Interface Language

The current Web UI supports three locales:

- English
- Simplified Chinese
- Thai

The language switcher is available in the main navigation area and mobile drawer. The selected locale is persisted in browser storage, so refreshes and restarts keep the same UI language on the same browser.

Core admin pages such as Dashboard, Chat, Teams, Channels, Configuration, Status, and Tokens are covered by the current locale support.

## Attachments

Chat supports:

- image, audio, PDF, Office, and text uploads
- drag and drop
- paste upload
- inline history preview
- refresh and module-switch recovery that reloads the latest history window without browser cache reuse
- remote image links in assistant history are normalized into the same image-card attachment UI when possible
- compact assistant bubbles with tighter Markdown spacing for long replies
- a task workbench in the conversation overview that summarizes the latest request, files, execution steps, tools, relay count, and current stage from already loaded message metadata
- baton-aware team relay status so the UI shows who handed off to whom and whether the next turn is continuing discussion or returning to a final summary

Uploads are stored under `.horbot/data/uploads`.

When you refresh the Chat page or leave and return to it, Horbot reloads the latest conversation window with no-store requests and then scrolls back to the newest turn. If you are browsing older history, use the jump-to-latest control before sending a new message.

The task workbench is UI-derived and does not ask the model to generate extra status text. It reads existing messages, files, execution steps, tool names, and relay metadata, so it improves scanability without increasing prompt tokens. The overview stays compact by default; expand `Details` only when you need tool and execution-step breakdowns. Quick actions in the workbench only prefill the input box, so no model request is made until you explicitly send. These quick actions are state-aware: failures, attachments, long context, and team relay conversations can surface different suggested next steps. `Copy summary` copies the current workbench state for reuse in a new chat or handoff. `Use summary` fills that same summary into the message input for explicit continuation without sending automatically.

If a remote image link can be cached successfully, later history loads use a local attachment preview URL and preserve filename plus file size in the card. If caching fails, the chat still falls back to a remote image attachment instead of showing only a bare link.

### PPTX Preview

PPTX files use a LibreOffice-based high-fidelity preview path when `soffice` is available. Horbot converts the deck to an intermediate PDF with an isolated LibreOffice profile, then renders slide PNGs lazily as you open or navigate pages. This avoids browser-side PPTX reconstruction, which often loses layout, fonts, and positioning.

The preview iframe loads only the current slide and nearby slides. Closing or unloading the preview asks the backend to remove the intermediate PDF. Already rendered slide PNGs may remain in the upload preview cache for faster reopening, but the backend automatically removes slide image caches that have not been used for 3 days.

Install or verify the dependency with:

```bash
./horbot.sh install libreoffice
./horbot.sh check libreoffice
```

## Live Artifacts

Agents can include a structured `horbot-renderable` block when a reply is better as an interactive view instead of plain Markdown. The chat bubble then shows a Live Artifact card with a `Render` button.

Current supported templates include:

- `dashboard`
- `chart-story`
- `data-workbench`
- `map-story`
- `process-map`
- `interactive-report`

Horbot persists the reusable source as message text plus structured render spec/data. The generated HTML runtime is temporary: it is created only after clicking `Render`, displayed in a sandboxed iframe, and written under `.horbot/runtime/rendered-artifacts` with a TTL. Refreshing history shows the card again, and you can re-render from the saved spec.

The built-in `live-artifact-studio` skill guides agents to decide when Markdown is enough and when structured renderable output is appropriate.

## Configuration: Web Search And Remote Image Cache

The `Configuration` page now also exposes runtime web-search controls:

- enable or disable web search globally
- switch the preferred web-search provider
- enable or disable supported API providers such as Tavily or LangSearch without changing the stored provider selection
- keep API keys isolated per search provider so switching providers does not reuse the previous provider's key state
- adjust the default max-results limit
- inspect and manually clear the remote image cache used for promoted image cards

If global web search is disabled, runtime requests will not call web-search tools even when a provider and API key are already configured.

The remote image cache panel shows:

- cached file count
- total cached size
- newest update timestamp

Manual clear only removes runtime-generated remote-image cache entries. It does not delete ordinary user-uploaded files.

## Agent Setup

Creating an agent now requires:

- agent id
- name
- provider
- model

After creation, you can refine the agent through chat or by editing workspace files.

## Skills And Compatibility

The Skills page accepts both `.skill` and `.zip` packages.

Current organization in the page:

- `System`: project built-ins
- `Custom`: skills from the current agent workspace, including manual and auto-generated skills

Custom skills also show whether they came from:

- a manual workspace-local skill
- automatic agent-generated distillation

Before import, Horbot validates:

- package structure and safe paths
- required `SKILL.md`
- frontmatter plus `name` / `description`
- relative file references
- environment compatibility and missing requirements

Imported skills are written to the current agent skill directory, and compatibility results are shown immediately in the UI.

The current agent runtime skill directory is:

- `.horbot/agents/<agent-id>/workspace/.horbot-agent/skills`

Auto-generated skills now prefer a family layout:

- a lean `SKILL.md` for trigger cues and routing
- one or more detailed technique notes under `references/*.md`

The Skills page also includes two manual management actions:

- `Consolidate Generated`: merge related `auto-*` skills into broader families
- `Promote to Builtin`: move a custom workspace skill into the built-in system skill set

### Skill Graph

The `Graph` tab shows an agent-scoped graph built from the current skill set.

It includes:

- skill nodes from system and custom skills
- reference nodes for files under `references/`
- `has_reference`, `similar_to`, and `related_to` edges
- summary cards for node and edge counts
- a focused one-hop graph view so dense relationships do not collapse into an unreadable cluster

Horbot automatically refreshes the persisted graph after managed skill changes such as create, update, import, delete, enable/disable, generated-skill consolidation, promotion to builtin, and automatic skill evolution writes. Use `Rebuild Graph` when files were changed outside the UI or when the graph needs to be regenerated immediately.

The persisted graph is stored under the current agent workspace as `.horbot-agent/skill_graph.json`. The agent runtime also reads it as compact skill-summary hints, so related skills and nearby `references/` files can be suggested without loading full reference content into every request.

## Team Relay Behavior

Current team relay behavior is intentionally ordered, not parallel:

- one agent responds at a time
- the UI keeps showing each baton as a separate relay group
- waiting cards can display who handed the turn off and a short preview of the subtask
- summary-return turns are treated differently from normal teammate handoffs

Agent-to-agent turns are also guided to stay shorter by default so relay chains feel more incremental in the chat UI.

## External Channels

Horbot currently distinguishes two enterprise-WeChat-style paths:

- `WeCom`: the official AI Bot WebSocket gateway, with reply-mode streaming plus inbound/outbound media handling
- `Mochat`: a separate ecosystem integration for Mochat / Claw deployments

Treat them as different protocols with different credentials and operational assumptions.

## External Agents

The Teams page can connect third-party or local agents as external members.

Use `Adapter` to choose the integration mode. Prefer `inbound-bot`: Horbot creates a bot identity and shows App ID, Token, and Inbound URL. Copy those values into WorkBuddy or another vendor/local agent platform so it can push messages into Horbot.

`generic-agent-api` is now a compatibility mode for the older design where Horbot actively calls an external HTTP, SSE, or WebSocket URL. `Transport` is only shown for that generic adapter. `Endpoint` is required for `generic-agent-api` and `openai-compatible`, but not for `inbound-bot`.

For `openai-compatible`, provide a Chat Completions-style endpoint and set `adapter_config.model`.

## Channels Inbound Bot

Use the Channels page when you need a message entrance that routes into an internal Agent. Create a `Horbot inbound bot` channel instance, optionally bind it to a target Agent, run the draft test, and save it.

After the test/save step, Horbot shows the generated App ID, Token, and Inbound URL. Configure those values in WorkBuddy or another vendor/local platform so it can push messages into Horbot. If the endpoint is not fixed to one Agent, the inbound request must include `target_agent_id` or `agent_id`; Horbot validates the ID against the current running instance before routing. This is separate from External Agent membership: Channels owns entrances, External Agents own team/DM member identity.

## Smoke Tests

Useful smoke commands:

```bash
./horbot.sh smoke browser-e2e
./horbot.sh smoke agent-assets
./horbot.sh smoke dm-chat
./horbot.sh smoke team-chat
./horbot.sh smoke chat-error-retry
```
