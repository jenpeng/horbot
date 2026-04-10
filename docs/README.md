# Horbot Documentation

This is the English documentation hub for Horbot.

- [Project Home](../README.md)
- [简体中文](./README_CN.md)

## Overview

Horbot is a lightweight multi-agent assistant stack with:

- per-agent workspace, memory, sessions, and skills
- Web UI for operations and configuration
- chat, attachments, and relay-style team conversations
- MCP and external channel integration
- background skill distillation from reusable work

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
