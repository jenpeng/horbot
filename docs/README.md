# Horbot Documentation

This is the English documentation hub for Horbot.

- [Project Home](../README.md)
- [简体中文](./README_CN.md)

## Overview

Horbot is a lightweight multi-agent assistant stack with:

- per-agent workspace, memory, sessions, and skills
- Web UI for operations and configuration
- browser-persisted UI locale switching for English, Simplified Chinese, and Thai
- chat, attachments, and relay-style team conversations
- compact chat layout plus baton-aware relay status in team conversations
- automatic DM -> team -> DM baton navigation in Web Chat, with a temporary top banner so relay-driven view changes are explicit
- promoted remote image links that render as normal image-card attachments, plus a manual remote-image cache clear entry in Configuration
- MCP and external channel integration
- Playwright-backed browser tooling with `browser`, `web_search`, and `web_fetch` as the standard web tool path
- background skill distillation from reusable work
- validated `.skill` / `.zip` imports with compatibility checks
- WeCom AI Bot channel support with reply streaming and media handling

## Interface Preview

The images below are captured from the current Horbot Web UI with the interface language set to English.

| Dashboard | Chat |
| --- | --- |
| ![Dashboard](./assets/en/preview-dashboard.png) | ![Chat](./assets/en/preview-chat.png) |

| Skills | Teams |
| --- | --- |
| ![Skills](./assets/en/preview-skills.png) | ![Teams](./assets/en/preview-teams.png) |

## Guides

- [Architecture](./ARCHITECTURE.md)
- [API](./API.md)
- [User Manual](./USER_MANUAL.md)
- [Multi-Agent Guide](./MULTI_AGENT_GUIDE.md)
- [Skills](./SKILLS.md)
- [Security](./SECURITY.md)
- [Contributing](./CONTRIBUTING.md)
- [Changelog](../CHANGELOG.md)

## Runtime Notes

The active runtime model is agent-scoped:

- `.horbot/agents/<agent-id>/workspace`
- `.horbot/agents/<agent-id>/memory`
- `.horbot/agents/<agent-id>/sessions`
- `.horbot/agents/<agent-id>/skills`

Legacy `.horbot/context` and `.horbot/memory` directories are no longer used by the current memory pipeline.

Creating an agent in the current UI requires choosing both `provider` and `model` up front.

Recent chat updates also tightened assistant message spacing, improved Markdown density, and surfaced clearer relay baton state for multi-agent team discussions.

Current web runtime notes:

- `browser` MCP now defaults to Playwright instead of a built-in `web-access` proxy
- `./horbot.sh start` only starts the normal Horbot services: backend, frontend, and gateway
- the agent now uses `browser`, `web_search`, and `web_fetch` as the standard web/search tools
- Configuration now exposes a remote-image cache status panel and manual clear action for chat image-card materialization
