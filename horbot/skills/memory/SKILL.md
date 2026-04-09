---
name: memory
description: Two-layer memory system with grep-based recall and hierarchical context management.
always: true
enabled: true
---

# Memory

## Structure

- `memory/MEMORY.md` — Long-term facts (preferences, project context, relationships). Always loaded into your context.
- `memory/HISTORY.md` — Append-only event log. NOT loaded into context. Search it with grep.

## Hierarchical Memory System

This skill is integrated with the hierarchical context management system:

- **L0 (Current Session)**: Active session memory, always loaded. Contains task progress, immediate decisions, and current context.
- **L1 (Recent)**: Recent session memories, loaded on demand. Contains important events and decisions from recent sessions.
- **L2 (Long-term)**: Consolidated long-term memories, search-based retrieval. Contains persistent knowledge and important patterns.

### Usage Scenarios

When saving memories, choose the appropriate level:

| Level | Use Case | Examples |
|-------|----------|----------|
| **L0** | Current session context | Task progress, active decisions, temporary state |
| **L1** | Recent important events | Recent bugs fixed, decisions made, lessons learned |
| **L2** | Long-term facts | User preferences, project architecture, persistent knowledge |

### Integration Details

The MemoryStore automatically syncs with hierarchical storage:

```python
# Long-term memory (MEMORY.md) syncs to L2
write_long_term(content)  # → L2 storage

# History entries sync to L1
append_history(entry)  # → L1 storage

# Session memory goes to L0
add_session_memory(content, session_key)  # → L0 storage
```

### Retrieving Hierarchical Context

Use `get_hierarchical_context()` to load layered context:

```python
# Load L0 and L1 context (default)
context = memory_store.get_hierarchical_context(session_key)

# Load specific levels
context = memory_store.get_hierarchical_context(
    session_key,
    levels=["L0", "L1", "L2"],
    max_tokens=8000
)
```

### Searching Across Layers

Search memories across all hierarchical levels:

```python
results = memory_store.search_memories(
    query="authentication",
    levels=["L1", "L2"],
    max_results=10
)
```

## Search Past Events

```bash
grep -i "keyword" memory/HISTORY.md
```

Use the `exec` tool to run grep. Combine patterns: `grep -iE "meeting|deadline" memory/HISTORY.md`

## When to Update MEMORY.md

Write important facts immediately using `edit_file` or `write_file`:
- User preferences ("I prefer dark mode")
- Project context ("The API uses OAuth2")
- Relationships ("Alice is the project lead")

## Auto-consolidation

Old conversations are automatically summarized and appended to HISTORY.md when the session grows large. Long-term facts are extracted to MEMORY.md. You don't need to manage this.

The consolidation process also respects the hierarchical levels:
- Session-specific context → L0
- Recent events and decisions → L1
- Persistent facts → L2
