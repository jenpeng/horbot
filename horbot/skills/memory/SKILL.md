---
name: memory
description: Agent-scoped memory system with long-term memory, grep-friendly history, reflection notes, and hierarchical recall. Use when you need to save durable facts, search past work, or record reusable strategies.
always: true
enabled: true
---

# Memory

## What Exists

Horbot's memory is agent-scoped, not conversation-scoped. The important files are usually under:

- `.horbot/agents/<agent-id>/memory/L2/MEMORY.md` for durable facts and stable context
- `.horbot/agents/<agent-id>/memory/L1/HISTORY.md` for append-only recent events
- `.horbot/agents/<agent-id>/memory/L1/REFLECTION.md` for reusable strategies, stable observations, and corrected assumptions

When team shared memory is enabled, additional shared context may live under:

- `.horbot/teams/<team-id>/shared_memory/`

## How To Use Each Layer

### `MEMORY.md`

Store information that should remain true across future sessions:

- durable user preferences
- stable project architecture facts
- long-lived decisions and boundaries
- identities, roles, and persistent collaboration rules

Do not dump transient task chatter here.

### `HISTORY.md`

Use for grep-friendly session summaries:

- what changed
- what was decided
- what was tested
- what failed and how it was fixed

Prefer concrete nouns, file names, feature names, and dates so future search works well.

### `REFLECTION.md`

Use for lessons that improve future behavior:

- reusable debugging strategies
- stable observations about the repo or workflow
- previously-held assumptions that are now invalid

This is the best place for compact operational learnings.

## Hierarchical Recall Model

Horbot's runtime recall uses layered memory:

- `L0`: session-specific working memory
- `L1`: recent history and reflection
- `L2`: durable long-term memory

In practice:

- save durable facts into `MEMORY.md`
- save recent progress into `HISTORY.md`
- save reusable tactics into `REFLECTION.md`

The system will pull from these layers when building later context.

## Search Strategy

When you need past context, search `HISTORY.md` first:

```bash
grep -i "keyword" /abs/path/to/HISTORY.md
grep -iE "meeting|deadline|auth" /abs/path/to/HISTORY.md
```

If you need durable facts or reusable tactics, read `MEMORY.md` or `REFLECTION.md`.

## What To Save

Save immediately when the information is likely to matter later:

- user says a stable preference
- project establishes a durable rule
- a bug fix reveals a reusable checklist
- an old assumption is invalidated
- a team handoff needs to survive the current turn

## What Not To Save

Do not store:

- secrets or raw tokens unless explicitly required and safely handled
- one-off chatter
- duplicate paragraphs already present in memory
- temporary guesses that are not yet verified
