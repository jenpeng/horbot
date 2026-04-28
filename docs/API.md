# Horbot API

- [Project Home](../README.md)
- [Chinese Version](./API_CN.md)

## Base

- Base URL: `http://127.0.0.1:8000`
- Prefix: `/api`
- Formats: JSON and Server-Sent Events

## Main Areas

### Configuration

- `GET /api/config`
- `PUT /api/config`
- `GET /api/config/validate`
- `PATCH /api/config/web-search`

### Chat

- `POST /api/chat`
- `POST /api/chat/stream`
- `GET /api/chat/history`
- `POST /api/chat/sessions`
- `GET /api/chat/sessions`
- `PUT /api/chat/sessions/{session_key}`
- `DELETE /api/chat/sessions/{session_key}`

### Conversations

- `GET /api/conversations`
- `GET /api/conversations/{conv_id}`
- `GET /api/conversations/{conv_id}/messages`

### Files And Cache

- `POST /api/upload`
- `GET /api/files/{file_id}`
- `GET /api/files/{file_id}/preview`
- `GET /api/files/cache/remote-images`
- `DELETE /api/files/cache/remote-images`

### Agents And Teams

- `GET /api/agents`
- `POST /api/agents`
- `PUT /api/agents/{agent_id}`
- `DELETE /api/agents/{agent_id}`
- `GET /api/external-agents`
- `POST /api/external-agents`
- `PUT /api/external-agents/{external_agent_id}`
- `DELETE /api/external-agents/{external_agent_id}`
- `POST /api/external-agents/{external_agent_id}/test`
- `POST /api/external-agents/inbound/{app_id}/messages`
- `GET /api/teams`
- `POST /api/teams`
- `PUT /api/teams/{team_id}`
- `DELETE /api/teams/{team_id}`

### Skills

- `GET /api/skills`
- `GET /api/skills/{skill_name}`
- `POST /api/skills`
- `PUT /api/skills/{skill_name}`
- `DELETE /api/skills/{skill_name}`
- `PATCH /api/skills/{skill_name}/toggle`
- `POST /api/skills/import`
- `POST /api/skills/consolidate-generated`
- `POST /api/skills/{skill_name}/promote`

### Runtime And Status

- `GET /api/status`
- `GET /api/providers`
- `GET /api/channels/catalog`
- `GET /api/channels/endpoints`
- `POST /api/channels/endpoints`
- `PUT /api/channels/endpoints/{endpoint_id}`
- `DELETE /api/channels/endpoints/{endpoint_id}`
- `POST /api/channels/draft-test`
- `GET /api/channels/endpoints/{endpoint_id}/events`
- `POST /api/channels/endpoints/{endpoint_id}/test`
- `POST /api/channels/inbound/{app_id}/messages`
- `GET /api/tasks`
- `GET /api/token-usage/stats`

## Channel Endpoint Inbound Bot

`horbot-inbound-bot` is a Channels endpoint type for Feishu/Discord-style inbound integrations. Horbot owns the bot identity and gives the external platform an App ID, Token, and push URL.

Create or draft-test a channel endpoint with:

```json
{
  "id": "workbuddy-inbound",
  "type": "horbot-inbound-bot",
  "name": "WorkBuddy Inbound",
  "agent_id": "",
  "enabled": true,
  "allow_from": [],
  "config": {}
}
```

Horbot fills these fields under `endpoint.config`:

- `bot_app_id`
- `bot_token`
- `inbound_url_path`: `/api/channels/inbound/{app_id}/messages`

External platforms then push messages with:

```http
POST /api/channels/inbound/hbot_ch_workbuddy_xxx/messages
Authorization: Bearer <bot_token>
Content-Type: application/json

{
  "content": "Message from WorkBuddy",
  "chat_id": "workbuddy-room-1",
  "sender_id": "workbuddy",
  "target_agent_id": "main",
  "message_id": "msg-001",
  "metadata": {
    "vendor": "workbuddy"
  }
}
```

Token can be supplied as `Authorization: Bearer <token>`, `X-Horbot-Bot-Token`, or JSON body `token`.

Routing rules:

- If the endpoint has `agent_id`, all inbound messages route to that fixed internal Agent.
- If the endpoint has no `agent_id`, the request must provide `target_agent_id` or `agent_id` at the top level, or `metadata.target_agent_id` / `metadata.agent_id`.
- Horbot validates the requested Agent ID against the current running instance before routing. It does not route across users, projects, or another Horbot instance.
- `allow_from` restricts accepted `sender_id` values when configured.

Use this endpoint when you are defining an external message entrance. Use External Agent `inbound-bot` when you are defining an external member that can appear in DMs or teams.

## Notes

- Agent creation requires explicit `provider` and `model`.
- External Agent creation accepts an open `adapter` slug plus `adapter_config`; missing legacy adapters default to `generic-agent-api`.
- `inbound-bot` is the preferred Feishu/Discord-style adapter. Horbot generates `adapter_config.bot_app_id` and `adapter_config.bot_token`, then exposes `/api/external-agents/inbound/{app_id}/messages` for WorkBuddy or another platform to push messages into Horbot.
- `generic-agent-api` is only the compatibility adapter for the older model where Horbot calls HTTP, HTTP SSE, or WebSocket endpoints. `openai-compatible` is for Chat Completions-style services and expects `adapter_config.model`.
- `endpoint` is required only for `generic-agent-api` and `openai-compatible`; `inbound-bot` does not require an external URL.
- Channels also support `horbot-inbound-bot` endpoint instances. Horbot generates channel-scoped `bot_app_id`, `bot_token`, and `/api/channels/inbound/{app_id}/messages` so WorkBuddy or another platform can push traffic into an internal Agent.
- A `horbot-inbound-bot` endpoint can be fixed to one bound Agent. If it is left unbound, the inbound request may provide `target_agent_id` or `agent_id`; Horbot validates that ID against the current running instance before routing.
- Use `horbot-inbound-bot` in Channels when you are defining an external message entrance. Use External Agent `inbound-bot` when you are defining an external member that can appear in DMs or teams.
- Team history and direct-message history automatically merge legacy and current session storage when possible.
- Skills APIs resolve to the current agent skill directory, not a generic legacy workspace path.
- The current agent skill directory is `.horbot/agents/<agent-id>/workspace/.horbot-agent/skills`.
- `GET /api/skills` and `GET /api/skills/{skill_name}` also return skill source metadata such as `source_group`, `source_origin_kind`, and `source_origin_agent_id` so the UI can distinguish built-in, manual, and agent-generated skills.
- `PATCH /api/config/web-search` can update the global web-search `enabled` flag, the active search provider, provider-specific toggles such as `tavilyEnabled` and `langsearchEnabled`, provider-scoped search API keys, plus other runtime search defaults used by the Configuration page.
- `POST /api/chat/sessions` returns UUID-based session keys such as `session_4f0c...`, avoiding timestamp collisions.
- `GET /api/chat/history` and `GET /api/conversations/{conv_id}/messages` now normalize standalone remote image URLs in assistant messages into `files` attachments when possible, so the chat UI can render the standard image card experience.
- `GET /api/files/cache/remote-images` and `DELETE /api/files/cache/remote-images` expose the runtime-managed remote image cache used for those promoted image cards.
- Channel endpoint metadata now includes WeCom, including required fields for `bot_id` and `secret`.
- `POST /api/skills/import` validates `.skill` and `.zip` packages before writing them into the active agent skill directory.
- `POST /api/skills/consolidate-generated` manually merges related `auto-*` skills into broader families and preserves detailed notes under `references/`.
- `POST /api/skills/{skill_name}/promote` moves a custom workspace skill into the built-in skill set.
- Team relay SSE flows include relay-oriented events such as `agent_start`, `agent_mentioned`, and `agent_done`.
- `agent_mentioned` may also include `mentioned_by_name`, `handoff_mode` (`relay` / `continue` / `summary`), and `handoff_preview` so the frontend can show clearer baton status.

For detailed request and response examples, use the Chinese reference: [API_CN.md](./API_CN.md).
