# Security

- [Project Home](../README.md)
- [Chinese Version](./SECURITY_CN.md)

## Defaults

- Web services are intended for local access by default
- remote access should be protected with an admin token
- tool execution should remain workspace-restricted unless you explicitly change it

## Remote Access

When enabling remote access, configure:

- `gateway.adminToken`
- `gateway.allowRemoteWithoutToken = false`

Clients should send:

- `Authorization: Bearer <token>`
- or `X-Horbot-Admin-Token: <token>`

## Sensitive Data

The UI and normal API flows avoid echoing raw secrets such as:

- provider API keys
- channel secrets and passwords
- sensitive MCP env/header values

## Operational Advice

- keep the Web UI behind localhost, VPN, or a reverse proxy with authentication
- do not commit `.horbot/config.json` with real secrets
- keep permission profiles tight for production-like environments
