# Contributing

- [Project Home](../README.md)
- [Chinese Version](./CONTRIBUTING_CN.md)

## Setup

```bash
git clone https://github.com/jenpeng/horbot.git
cd horbot
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Frontend:

```bash
cd horbot/web/frontend
npm install
```

## Common Checks

```bash
python3 -m pytest
cd horbot/web/frontend && npm run test:run
cd horbot/web/frontend && npm run build
./horbot.sh smoke browser-e2e
```

## Contribution Expectations

- keep changes pragmatic and testable
- prefer targeted fixes over large speculative refactors
- preserve agent-scoped storage assumptions
- treat `.horbot/agents/<agent-id>/workspace/.horbot-agent/{memory,sessions,skills}` as the canonical agent runtime path
- update docs when user-facing behavior changes
- keep English and Chinese docs aligned when a change affects end users
- avoid reintroducing legacy `.horbot/context`, `.horbot/memory`, `.horbot/agents/<agent-id>/{memory,sessions,skills}`, or `workspace/skills` assumptions

## Skill Changes

When you change the skills system, keep these current rules aligned:

- auto-generated skills should prefer one broader family plus `references/*.md` over many narrow duplicates
- custom workspace skills live under the current agent runtime skill directory, not a generic global workspace folder
- if a change adds or removes Skills-page actions, update both the user docs and API docs in the same patch

## Docs And Screenshots

If a UI change affects README or documentation screenshots, capture them from the running local Web UI instead of using mockups.

English README screenshots can be refreshed with:

```bash
./.venv/bin/python scripts/capture_readme_screenshots.py --locale en --output-dir docs/assets/en
```
