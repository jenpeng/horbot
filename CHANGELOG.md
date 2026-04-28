# Changelog

This file summarizes notable Horbot product and documentation changes. For fine-grained code history, use Git directly.

## 2026-04-27

### External Agent Adapter Runtime

- Replaced the old monolithic External Agent runtime with an adapter registry dispatcher
- Added `inbound-bot` as the primary Feishu/Discord-style integration mode: Horbot issues App ID, Token, and Inbound URL, and vendor/local platforms push messages into Horbot
- Added Channels-managed `horbot-inbound-bot` endpoints so vendor/local platforms can push messages into a bound internal Agent or a request-specified Agent without being modeled as team members
- Moved the previous HTTP, HTTP SSE, and WebSocket behavior into the `generic-agent-api` compatibility adapter
- Added an `openai-compatible` adapter for Chat Completions-style vendor or local services
- Added open `adapter` slugs and `adapter_config` to External Agent configuration, so future vendor/local protocols can be configured without schema enum changes
- Updated the Teams UI to display and submit adapter fields with English, Simplified Chinese, and Thai labels

## 2026-04-15

### Native Web Access Runtime

- Added a native `web_access` tool as the unified entrypoint for web search, fetch, navigation, page interaction, screenshots, and page inspection
- Updated agent guidance and tool-selection heuristics so web work prefers `web_access` first, with `browser`, `web_search`, and `web_fetch` as fallbacks
- Replaced the temporary external `web-access` clone approach with an in-repo built-in proxy service
- Extended `./horbot.sh start|restart|stop|status|logs` to manage the built-in `web-access` service on `127.0.0.1:3456`
- The built-in proxy now tries to auto-launch a Chrome instance with remote debugging on `127.0.0.1:9222`
- Fixed Web Chat media handling so images emitted by agents through `message(..., media=...)` are persisted and rendered in chat instead of being dropped in the session/SSE/frontend path

### Docs

- Synced the homepage, docs index, MCP docs, and architecture docs with the current native `web_access` runtime model

## 2026-04-13

### Localization And Docs

- Added browser-persisted Web UI locale switching across English, Simplified Chinese, and Thai for the current core admin pages
- Updated README, documentation index, user manuals, and contributing notes to document the current multilingual UI behavior
- Refreshed English README/doc screenshots from the live local Horbot Web UI instead of reusing older assets

### Chat And Team Relay

- Web Chat now auto-switches from direct chat into the target team conversation when a DM agent dispatches work through the `message` tool
- Once the team relay finishes and the mirrored final summary returns to the originating direct chat, the UI automatically switches back there
- A short-lived baton navigation banner now appears at the top of chat for both transitions so users can see why the view changed and optionally jump back
- Short-round baton guidance is now injected into both kickoff and relay handoff prompts, not only follow-up turns
- Team relay bubbles now keep a compact baton/status strip visible while streaming content is already arriving, so the current handoff does not feel like a sudden final-only jump
- When a relay stream emits the final `done` event, the current turn is now hard-reconciled against persisted history so stale pending/streaming rows are flushed without requiring a page refresh

## 2026-04-12

### Chat, Channels, And Docs

- Tightened assistant bubble density and Markdown spacing in chat
- Added clearer baton status for relay conversations, including handoff direction and summary-return states
- Added WeCom AI Bot support with reply-mode streaming plus media upload and inbound media handling
- Synced README, documentation index, API notes, and user docs with the current provider/model, skills, and channel behavior

## 2026-04-10

### Product Positioning And Runtime Layout

- Reworked the repository homepage around the current Horbot architecture and linked English/Chinese docs more clearly
- Documented inspiration from `HKUDS/nanobot`, `NousResearch/hermes-agent`, `volcengine/OpenViking`, and `OpenClaw`
- Updated docs to reflect the current agent-scoped runtime layout and removed outdated references to legacy `.horbot/context`, `.horbot/memory`, and manual `/plan` command flow
