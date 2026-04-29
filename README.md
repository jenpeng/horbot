# Horbot

<div align="center">
  <h1>Horbot: A Lightweight Personal Multi-Agent Assistant</h1>
  <p>
    <img src="https://img.shields.io/badge/python-%E2%89%A53.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
    <img src="https://visitor-badge.laobi.icu/badge?page_id=jenpeng.horbot&style=for-the-badge&color=00d4ff" alt="Views">
  </p>
  <p>
    <a href="./README.md">English</a> |
    <a href="./docs/README_CN.md">简体中文</a>
  </p>
</div>

Horbot is a lightweight AI assistant stack focused on practical multi-agent orchestration, agent-specific workspaces, browser-based operations, chat channels, and persistent memory.

The project borrows and adapts ideas from several excellent open-source systems:

- Core lightweight agent patterns and implementation structure from [HKUDS/nanobot](https://github.com/HKUDS/nanobot)
- Autonomous agent and self-improvement ideas from [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- Three-layer memory ideas inspired by [volcengine/OpenViking](https://github.com/volcengine/OpenViking)
- Earlier skill-system inspiration from [OpenClaw](https://github.com/openclaw/openclaw)

Horbot does not attempt to be a giant framework. The emphasis is:

- a readable agent loop
- practical Web UI operations
- agent-scoped workspace, memory, sessions, and skills
- compatibility with real operational workflows
- browser-persisted Web UI language switching for English, Simplified Chinese, and Thai

## Interface Preview

The screenshots below were captured from the current Horbot Web UI with the locale set to English.

<table align="center">
  <tr align="center">
    <th>Dashboard</th>
    <th>Chat</th>
  </tr>
  <tr>
    <td align="center"><img src="./docs/assets/en/preview-dashboard.png" width="420" alt="Horbot dashboard"></td>
    <td align="center"><img src="./docs/assets/en/preview-chat.png" width="420" alt="Horbot chat page"></td>
  </tr>
  <tr align="center">
    <th>Skills</th>
    <th>Teams</th>
  </tr>
  <tr>
    <td align="center"><img src="./docs/assets/en/preview-skills.png" width="420" alt="Horbot skills page"></td>
    <td align="center"><img src="./docs/assets/en/preview-teams.png" width="420" alt="Horbot teams page"></td>
  </tr>
</table>

## What Horbot Can Do

### Multi-Agent Operations

- Create multiple agents with independent `provider`, `model`, permission profile, workspace, memory, and skills
- Build teams with ordered members, responsibilities, and lead assignment
- Support direct chat and team relay conversations in the same UI
- Let agents silently review completed work and distill reusable workflows into skill families with reference notes

### Workspace And Memory

- Maintain per-agent `SOUL.md` and `USER.md`
- Persist agent-scoped runtime metadata under `.horbot/agents/<agent-id>/workspace/.horbot-agent/`
- Separate long-term memory, recent history, and reflection notes
- Keep team shared memory separate from private agent memory

### Chat And Attachments

- Markdown rendering for assistant messages
- Live Artifact cards for structured agent output such as dashboards, chart stories, map stories, process views, and interactive reports
- Denser chat bubbles and tighter Markdown spacing to reduce blank space in long conversations
- Conversation history loads use no-store responses and incremental fallback recovery so refreshes or module switches do not reuse stale latest-message windows
- Inline preview for image, audio, PDF, Office, and text attachments
- High-fidelity PPTX preview through LibreOffice PDF export plus lazy per-slide PNG rendering
- Office document operations via OfficeCLI MCP, including structure-aware create/edit/view/validate flows for `.docx`, `.xlsx`, and `.pptx`
- Standalone remote image URLs in assistant history are promoted into normal image-card attachments when possible, instead of degrading to bare links
- Multi-image preview modals now include a bottom thumbnail strip for faster visual switching
- Drag-and-drop, paste upload, and retry flows
- Group chat history merge and recovery across legacy and current session paths
- Team relay timeline now shows clearer baton status such as who handed work to whom and whether the next turn is a continuation or a final summary
- When a direct-message agent dispatches work into a team relay, the Web UI now auto-switches into the team chat and then returns to the original direct chat once the final mirrored summary is ready, with a short-lived baton navigation banner at the top

### Providers, Tools, And Channels

- Multiple provider backends
- MCP integration
- Automatic OfficeCLI MCP wiring during local setup so agents can use Word, Excel, PowerPoint, and OpenXML-aware document tools without extra manual configuration
- `browser`, `web_search`, and `web_fetch` as the standard browser/search toolset, with Playwright as the default browser runtime
- External Agent inbound-bot runtime for Feishu/Discord-style vendor or local agent platforms, plus compatibility adapters for OpenAI-compatible and generic HTTP/SSE/WebSocket agents
- Channels can also create Horbot inbound bot endpoints that issue App ID, Token, and an Inbound URL for platforms such as WorkBuddy to push messages into a fixed or request-specified internal Agent
- External channels such as WeCom, Feishu, ShareCRM, Telegram, Discord, Slack, Matrix, Email, Mochat, and others
- WeCom AI Bot support with reply-mode streaming, media upload, and inbound media download/decryption

### Operational Tooling

- Web admin UI for configuration, agents, teams, status, skills, channels, tasks, and token usage
- Skills UI support for custom vs system grouping, auto-skill consolidation, and promoting custom skills into built-in system skills
- Configuration now exposes remote-image cache stats and a manual clear action for runtime-generated image-card cache files
- Built-in UI locale switcher for English, Simplified Chinese, and Thai, with the selection persisted in browser storage
- Smoke scripts for browser, chat, configuration, and agent asset flows
- Security defaults for local-only access and admin-token-gated remote access

### Development Notes

- Web API endpoints are now split into focused route modules under `horbot/web/*_routes.py`; keep `horbot/web/api.py` as the composition, chat-core, and compatibility layer instead of adding unrelated feature routes back into it.
- The Chat page keeps history parsing, file metadata, stream errors, execution-step mapping, and turn virtualization in focused modules under `horbot/web/frontend/src/pages/chat/`.

## Quick Start

```bash
git clone https://github.com/jenpeng/horbot.git
cd horbot
./horbot.sh install
./horbot.sh start
```

`./horbot.sh install` now also installs `OfficeCLI` and checks LibreOffice. OfficeCLI is wired into `./.horbot/config.json` for document operations; LibreOffice is used by the Web UI for high-fidelity PPTX preview.

To validate the Office document toolchain end to end, run `./horbot.sh smoke officecli`. It directly checks `.docx`, `.xlsx`, and `.pptx` create/edit/view/validate flows with the locally installed `officecli`.

Default local URLs:

- Web UI: [http://127.0.0.1:3000](http://127.0.0.1:3000)
- Backend API: [http://127.0.0.1:8000](http://127.0.0.1:8000)

Common commands:

```bash
./horbot.sh status
./horbot.sh restart
./horbot.sh install officecli
./horbot.sh install libreoffice
./horbot.sh check libreoffice
./horbot.sh smoke officecli
./horbot.sh logs backend
./horbot.sh smoke browser-e2e
```

## Documentation

### English

- [Documentation Index](./docs/README.md)
- [Architecture](./docs/ARCHITECTURE.md)
- [API](./docs/API.md)
- [User Manual](./docs/USER_MANUAL.md)
- [Multi-Agent Guide](./docs/MULTI_AGENT_GUIDE.md)
- [Skills](./docs/SKILLS.md)
- [Security](./docs/SECURITY.md)
- [Contributing](./docs/CONTRIBUTING.md)
- [Changelog](./CHANGELOG.md)

### Chinese

- [中文文档首页](./docs/README_CN.md)
- [架构说明](./docs/ARCHITECTURE_CN.md)
- [API 文档](./docs/API_CN.md)
- [用户手册](./docs/USER_MANUAL_CN.md)
- [多 Agent 操作手册](./docs/MULTI_AGENT_GUIDE_CN.md)
- [技能系统](./docs/SKILLS_CN.md)
- [安全指南](./docs/SECURITY_CN.md)
- [贡献指南](./docs/CONTRIBUTING_CN.md)
- [变更记录](./docs/CHANGELOG_CN.md)

## Current Runtime Layout

The current runtime model is agent-scoped:

```text
.horbot/
├── agents/
│   └── <agent-id>/
│       └── workspace/
│           ├── SOUL.md
│           ├── USER.md
│           ├── .audit/
│           ├── .checkpoints/
│           ├── .state/
│           └── .horbot-agent/
│               ├── memory/
│               ├── sessions/
│               └── skills/
├── teams/
│   └── <team-id>/
│       ├── workspace/
│       ├── shared_memory/
│       └── taskboard/
├── data/
│   ├── uploads/
│   ├── sessions/
│   ├── plans/
│   └── cron/
└── runtime/
    ├── logs/
    └── pids/
```

Legacy `.horbot/context` and `.horbot/memory` directories are no longer part of the active memory model and can be removed from existing local environments.

Legacy agent paths such as `.horbot/agents/<agent-id>/{memory,sessions,skills}` and `workspace/{memory,skills}` are treated as migration inputs only. Current builds merge forward from those paths but do not recreate them.

## License

Horbot is released under the [MIT License](./LICENSE).

This license allows commercial use, modification, distribution, private deployment, and resale, provided that the original copyright notice and license text are retained.

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=jenpeng/horbot&type=Date)](https://star-history.com/#jenpeng/horbot&Date)
