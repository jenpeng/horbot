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

## Web Backend Route Changes

`horbot/web/api.py` is now a router composition, chat-core compatibility, and legacy shim module. Add new feature endpoints to the closest focused route module under `horbot/web/*_routes.py` instead of expanding `api.py`.

When changing chat or conversation history routes, preserve these behavior contracts:

- history responses must include `Cache-Control: no-store`
- frontend history fetches should use `cache: 'no-store'`
- incremental `after_id` loads should fall back to the latest window when the anchor is stale or missing
- compatibility imports from `horbot.web.api` should keep working unless a migration is documented and tested

## Skill Changes

When you change the skills system, keep these current rules aligned:

- auto-generated skills should prefer one broader family plus `references/*.md` over many narrow duplicates
- custom workspace skills live under the current agent runtime skill directory, not a generic global workspace folder
- if a change adds or removes Skills-page actions, update both the user docs and API docs in the same patch

## Channel Inbound Bot Development

When changing `horbot-inbound-bot`, keep the full implementation chain aligned:

- `horbot/config/schema.py`: `HorbotInboundBotConfig` stores channel-scoped generated credentials.
- `horbot/channels/endpoints.py`: catalog metadata, typed config mapping, runtime config merge, and endpoint projection.
- `horbot/config/normalizer.py`: `_CHANNEL_TYPES` must include `horbot-inbound-bot`, otherwise saved endpoints can be dropped by normalization.
- `horbot/channels/manager.py`: the ChannelManager factory must create `HorbotInboundBotChannel`.
- `horbot/channels/horbot_inbound_bot.py`: keep this runtime lightweight. The actual inbound HTTP handling lives in the Web API route, not in a long-running vendor socket.
- `horbot/channels/diagnostics.py`: diagnostics should validate that generated App ID and Token exist.
- `horbot/web/api.py`: `/api/channels/inbound/{app_id}/messages` validates token, sender allowlist, target Agent, and then dispatches through `get_agent_loop(target_agent_id).process_message(...)`.
- `horbot/web/frontend/src/pages/ChannelsPage.tsx`: the UI must show generated App ID, Token, and Inbound URL in a copyable form and make Agent binding optional for this channel type.

Routing and security rules:

- A fixed `agent_id` on the endpoint takes precedence over request payload routing.
- If the endpoint is unbound, the request must provide `target_agent_id` or `agent_id`, either at the top level or under `metadata`.
- Never route to arbitrary external IDs. Validate the target against `config.agents.instances` in the current running Horbot instance.
- Do not silently fall back to the first/default Agent for unbound inbound-bot endpoints. Missing or unknown targets should fail with a clear 400 response.
- Tokens may be accepted from `Authorization: Bearer`, `X-Horbot-Bot-Token`, or JSON body `token`, but comparison must stay constant-time with `secrets.compare_digest`.

Testing expectations:

- Update `tests/test_channel_endpoints_api.py` when request shape, routing rules, credential generation, or validation behavior changes.
- Keep coverage for credential generation, fixed-Agent routing, dynamic request-Agent routing, unknown-Agent rejection, and token rejection.
- Run `./.venv/bin/python -m unittest tests.test_channel_endpoints_api tests.test_config_normalizer tests.test_channel_diagnostics`.

Documentation expectations:

- Keep `docs/API.md`, `docs/API_CN.md`, `docs/USER_MANUAL.md`, `docs/USER_MANUAL_CN.md`, `docs/ARCHITECTURE.md`, and `docs/ARCHITECTURE_CN.md` aligned.
- If the UI labels or helper text change, update English, Simplified Chinese, and Thai locale files in the same patch.

## Docs And Screenshots

If a UI change affects README or documentation screenshots, capture them from the running local Web UI instead of using mockups.

English README screenshots can be refreshed with:

```bash
./.venv/bin/python scripts/capture_readme_screenshots.py --locale en --output-dir docs/assets/en
```
