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
- avoid reintroducing legacy `.horbot/context` or `.horbot/memory` assumptions
