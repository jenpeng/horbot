# Changelog

This changelog tracks notable product and documentation milestones for Horbot. For lower-level file changes, use Git history.

## 2026-04-12

### Chat And Team Relay

- Tightened assistant message spacing and Markdown layout in the chat UI to reduce excessive whitespace
- Added clearer baton-oriented team relay state in chat, including who handed off the turn and whether the next baton is continuation or final summary
- Added a local multi-agent relay SSE regression covering a longer ordered handoff chain

### Channels

- Added `WeCom` channel support for the official enterprise WeChat AI Bot WebSocket gateway
- Implemented reply-mode streaming with progressive edits and final stream completion handling
- Added inbound media download/decryption plus outbound media upload/send support for WeCom conversations

### Documentation

- Removed the stale `## Notes` section from the repository homepage README
- Synced README, documentation index, API, user manual, and architecture docs with current channel, skill import, and agent creation behavior
- Updated API examples to reflect UUID-based chat session keys and the current channel endpoint catalog

## 2026-04-10

### Documentation And Project Positioning

- Reworked the GitHub homepage into an English-first README with bilingual navigation
- Clarified that Horbot borrows ideas from `HKUDS/nanobot`, `NousResearch/hermes-agent`, `volcengine/OpenViking`, and `OpenClaw`
- Added English documentation counterparts for architecture, API, user manual, skills, security, contribution, and multi-agent guides
- Removed stale documentation references to legacy `.horbot/context`, `.horbot/memory`, and the old `/plan` command model

### Web UI And Product Flow

- Required `provider` and `model` when creating agents instead of forcing a second edit pass
- Refined dashboard, status, and teams pages by extracting shared hooks and reducing repeated UI logic
- Simplified token usage presentation and removed estimated cost from the usage view
- Improved error recovery so retry flows refresh data inside hooks instead of reloading whole pages

### Skills And Memory

- Added skill package import validation for `.skill` and `.zip` bundles
- Surfaced compatibility and missing dependency guidance directly in the Skills UI
- Aligned memory, self-improvement, and background skill distillation with the current agent-scoped memory layout
- Preserved cancelled subagent state instead of incorrectly marking cancelled work as completed

### Runtime Layout

- Standardized active runtime storage around `.horbot/agents/<agent-id>/...`
- Removed legacy local `.horbot/context` and `.horbot/memory` directories from the active setup guidance

## 2026-04-09

### Skills

- Implemented validated skill import flows and documented compatibility expectations for downloaded skills
- Improved missing dependency surfacing so operators can tell whether a skill needs setup before use

### Frontend Reliability

- Recovered more gracefully from stale frontend chunks after reload
- Continued splitting large dashboard and teams page logic into smaller components and hooks

## 2026-02-24

### Release `v0.1.4.post2`

- Reliability-focused release with heartbeat redesign, prompt cache improvements, and provider/channel stability work

## 2026-02-21

### Release `v0.1.4.post1`

- Added more providers, broader channel media support, and significant stability improvements

## 2026-02-17

### Release `v0.1.4`

- Added MCP support, progress streaming, new providers, and multi-channel improvements
