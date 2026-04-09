# Security Guide

本文档说明当前项目的默认安全边界、远程访问要求以及升级后的敏感信息处理策略。

## 默认安全策略

- Web API 与 WebSocket 现在默认只建议本机访问。
- `horbot.sh` 与 `horbot web` 默认监听 `127.0.0.1`。
- 即使进程被改成监听 `0.0.0.0`，远程客户端在未配置管理员令牌时也会被后端拒绝。
- 工具执行默认开启 `tools.restrictToWorkspace = true`，降低误操作到宿主机其他路径的风险。

## 远程访问

如果确实需要从局域网、反向代理或公网访问，请在 `.horbot/config.json` 中显式配置管理员令牌：

```json
{
  "gateway": {
    "host": "127.0.0.1",
    "port": 18790,
    "adminToken": "replace-with-a-long-random-token",
    "allowRemoteWithoutToken": false
  }
}
```

远程请求必须携带以下任一请求头：

- `Authorization: Bearer <token>`
- `X-Horbot-Admin-Token: <token>`

示例：

```bash
curl http://your-host:8000/api/status \
  -H 'Authorization: Bearer replace-with-a-long-random-token'
```

## 浏览器访问远程 Web UI

前端会自动读取以下来源的管理员令牌：

- 浏览器 `localStorage["horbotAdminToken"]`

如果你通过浏览器直接访问远程 UI，可以在控制台设置：

```js
localStorage.setItem('horbotAdminToken', 'replace-with-a-long-random-token')
```

刷新页面后，前端请求会自动附带该令牌。

## 敏感信息脱敏

以下数据不再以明文形式回显到 Web UI 或普通 API 响应：

- Provider API Key
- 各渠道 token / secret / password
- MCP `env` / `headers` 中的敏感值

页面会显示：

- 是否已配置
- 掩码预览
- 需要重新填写时的提示

这意味着编辑 Provider 或 MCP 时：

- 已保存的敏感值不会回显
- 若要覆盖旧值，需要重新输入新的完整值

## 日志策略

后端现在会对 JSON 请求体中的常见敏感字段做脱敏再写日志，包括：

- `apiKey` / `api_key`
- `token`
- `secret`
- `password`
- `authorization`

仍然建议：

- 不要把 `.horbot/runtime/logs/` 暴露到共享目录
- 不要把完整配置文件提交到公共仓库
- 定期轮换外部服务密钥

## 部署建议

- 本地开发：保持默认 `127.0.0.1`
- 局域网访问：配置强随机 `adminToken`
- 反向代理：在代理层继续做 IP 白名单或 Basic Auth
- 公网暴露：不建议裸露部署，至少同时启用代理鉴权和 `adminToken`

## 已知边界

当前项目仍然是偏单用户、可信操作者模型，不是强多租户隔离系统。

这意味着：

- 拿到管理员访问能力的人，本质上仍拥有高权限
- `exec` 仍属于高风险工具，只是默认范围更受限
- MCP 插件仍应视为受信扩展，不应把不受信任的服务直接接入
