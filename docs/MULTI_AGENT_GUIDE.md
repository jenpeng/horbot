# Multi-Agent Guide

- [Project Home](../README.md)
- [Chinese Version](./MULTI_AGENT_GUIDE_CN.md)

## Agent Basics

Each agent has its own:

- workspace
- memory
- sessions
- skills
- provider and model settings

This means agent behavior is not only a prompt issue. Storage and runtime state are agent-scoped.

## Recommended Creation Flow

1. Create the agent with `provider` and `model`
2. Set a minimal role, permission profile, and optional capability tags
3. Open the first direct conversation
4. Refine `SOUL.md`, `USER.md`, and operating boundaries

## Team Basics

Teams define:

- ordered members
- lead agent
- role and responsibility per member
- shared workspace and shared memory

Team chat can relay between members while still preserving per-agent execution state.

Current relay behavior in the Web UI is ordered and baton-oriented:

- one teammate speaks at a time
- every baton appears as its own relay step in chat history
- pending turns can show who handed off the work plus a short task preview
- return-to-user summary turns are treated differently from normal teammate continuation turns

Agent-to-agent prompts are also biased toward shorter subtask replies so long relay chains remain readable in chat.

## Files You Will Touch Most Often

- `SOUL.md`
- `USER.md`
- current agent `skills/`
- current agent `memory/`

## Current Runtime Model

The active runtime layout is:

- `.horbot/agents/<agent-id>/workspace`
- `.horbot/agents/<agent-id>/memory`
- `.horbot/agents/<agent-id>/sessions`
- `.horbot/agents/<agent-id>/skills`

Legacy `.horbot/context` and `.horbot/memory` are not part of the current model.
