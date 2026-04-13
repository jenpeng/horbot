# Changelog

This file summarizes notable Horbot product and documentation changes. For fine-grained code history, use Git directly.

## 2026-04-13

### Chat And Team Relay

- Web Chat now auto-switches from direct chat into the target team conversation when a DM agent dispatches work through the `message` tool
- Once the team relay finishes and the mirrored final summary returns to the originating direct chat, the UI automatically switches back there
- A short-lived baton navigation banner now appears at the top of chat for both transitions so users can see why the view changed and optionally jump back
- Short-round baton guidance is now injected into both kickoff and relay handoff prompts, not only follow-up turns

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
