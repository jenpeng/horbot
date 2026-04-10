---
name: skillhub
description: Search and install agent skills from Tencent SkillHub, the Chinese skill registry optimized for local users.
homepage: https://skillhub.tencent.com
metadata: {"horbot":{"emoji":"🐧"}}
---

# SkillHub (Tencent)

腾讯 SkillHub - 专为中国用户优化的 Skills 社区。支持自然语言搜索（向量搜索）。

## When to use

Use this skill when the user asks any of:
- "从 SkillHub 找 skill"
- "搜索腾讯 SkillHub"
- "安装 skill"
- "有什么可用的 skill？"
- "更新我的 skills"
- "skillhub 上有什么"

## Search

```bash
npx --yes clawhub@latest search "关键词" --registry https://skillhub.tencent.com/api --limit 5
```

## Install

```bash
npx --yes clawhub@latest install <slug> --registry https://skillhub.tencent.com/api --workdir ~/.horbot/agents/main/workspace
```

Replace `<slug>` with the skill name from search results. This places the skill into `~/.horbot/agents/main/workspace/skills/`, where horbot loads workspace skills from. Always include `--workdir`.

## Update

```bash
npx --yes clawhub@latest update --all --registry https://skillhub.tencent.com/api --workdir ~/.horbot/agents/main/workspace
```

## List installed

```bash
npx --yes clawhub@latest list --workdir ~/.horbot/agents/main/workspace
```

## Notes

- Requires Node.js (`npx` comes with it).
- No API key needed for search and install.
- Login is only required for publishing.
- `--workdir ~/.horbot/agents/main/workspace` is critical — without it, skills install to the current directory instead of the horbot workspace.
- `--registry https://skillhub.tencent.com/api` points to Tencent SkillHub instead of default ClawHub.
- After install, remind the user to start a new session to load the skill.
- For Chinese users, SkillHub may provide better network performance and localized skills.

## Comparison with ClawHub

| Feature | ClawHub | SkillHub (Tencent) |
|---------|---------|-------------------|
| Homepage | clawhub.ai | skillhub.tencent.com |
| Registry URL | Default | https://skillhub.tencent.com/api |
| Optimization | Global | China-localized |
| Language | English | Chinese support |
