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
- `Skills`: create, edit, import, and inspect compatibility
- `Channels`: endpoint configuration, missing-field diagnostics, and connectivity tests
- `Dashboard`: high-level operational overview
- `Status`: runtime diagnostics
- `Tokens`: token usage trends

## Attachments

Chat supports:

- image, audio, PDF, Office, and text uploads
- drag and drop
- paste upload
- inline history preview

Uploads are stored under `.horbot/data/uploads`.

## Agent Setup

Creating an agent now requires:

- agent id
- name
- provider
- model

After creation, you can refine the agent through chat or by editing workspace files.

## Skills And Compatibility

The Skills page accepts both `.skill` and `.zip` packages.

Before import, Horbot validates:

- package structure and safe paths
- required `SKILL.md`
- frontmatter plus `name` / `description`
- relative file references
- environment compatibility and missing requirements

Imported skills are written to the current agent skill directory, and compatibility results are shown immediately in the UI.

## External Channels

Horbot currently distinguishes two enterprise-WeChat-style paths:

- `WeCom`: the official AI Bot WebSocket gateway, with reply-mode streaming plus inbound/outbound media handling
- `Mochat`: a separate ecosystem integration for Mochat / Claw deployments

Treat them as different protocols with different credentials and operational assumptions.

## Smoke Tests

Useful smoke commands:

```bash
./horbot.sh smoke browser-e2e
./horbot.sh smoke agent-assets
./horbot.sh smoke dm-chat
./horbot.sh smoke team-chat
./horbot.sh smoke chat-error-retry
```
