# Changelog

This changelog tracks notable product and documentation milestones for Horbot. For lower-level file changes, use Git history.

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
