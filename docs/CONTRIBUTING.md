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
- update docs when user-facing behavior changes
- keep English and Chinese docs aligned when a change affects end users
- avoid reintroducing legacy `.horbot/context` or `.horbot/memory` assumptions

## Docs And Screenshots

If a UI change affects README or documentation screenshots, capture them from the running local Web UI instead of using mockups.

English README screenshots can be refreshed with:

```bash
./.venv/bin/python scripts/capture_readme_screenshots.py --locale en --output-dir docs/assets/en
```
