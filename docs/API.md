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

### Agents And Teams

- `GET /api/agents`
- `POST /api/agents`
- `PUT /api/agents/{agent_id}`
- `DELETE /api/agents/{agent_id}`
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

### Runtime And Status

- `GET /api/status`
- `GET /api/providers`
- `GET /api/channels/endpoints`
- `GET /api/tasks`
- `GET /api/token-usage/stats`

## Notes

- Agent creation requires explicit `provider` and `model`.
- Team history and direct-message history automatically merge legacy and current session storage when possible.
- Skills APIs resolve to the current agent skill directory, not a generic legacy workspace path.

For detailed request and response examples, use the Chinese reference: [API_CN.md](./API_CN.md).
