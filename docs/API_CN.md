# horbot API 文档

本文档介绍 horbot 的 Web API 端点和 WebSocket 事件。

## 📡 基础信息

- **基础 URL**: `http://localhost:8000`
- **API 前缀**: `/api`
- **数据格式**: JSON
- **流式响应**: Server-Sent Events (SSE)

---

## 🔌 API 端点

### 配置管理

#### 获取配置

```http
GET /api/config
```

**响应示例**:
```json
{
  "agents": {
    "defaults": {
      "workspace": ".horbot/agents/main/workspace",
      "models": {
        "main": {
          "provider": "openrouter",
          "model": "anthropic/claude-sonnet-4-20250514"
        },
        "planning": {
          "provider": "openrouter",
          "model": "anthropic/claude-sonnet-4-20250514"
        }
      }
    }
  },
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-xxx"
    }
  }
}
```

说明：

- `agents.defaults.models.main` 是默认主对话模型
- `agents.defaults.models.planning` 是内部规划场景模型
- 当前 Web Chat 已移除 `/plan` 命令，复杂任务会自动触发规划检测

#### 更新配置

```http
PUT /api/config
Content-Type: application/json

{
  "agents": {
    "defaults": {
      "workspace": ".horbot/agents/main/workspace",
      "models": {
        "main": {
          "provider": "openrouter",
          "model": "anthropic/claude-sonnet-4-20250514"
        }
      }
    }
  }
}
```

**响应示例**:
```json
{
  "status": "success",
  "message": "Configuration updated",
  "path": "./.horbot/config.json"
}
```

#### 更新联网搜索配置

```http
PATCH /api/config/web-search
Content-Type: application/json

{
  "enabled": true,
  "provider": "tavily",
  "tavilyEnabled": false,
  "langsearchEnabled": true,
  "maxResults": 5
}
```

说明：

- 可用于更新 Web 管理页中的联网搜索总开关 `enabled`、Provider、`tavilyEnabled` / `langsearchEnabled` 等 Provider 开关与最大结果数
- 当 `enabled=false` 时，即使当前 Provider 和 API Key 仍已配置，运行时也不会调用 web search 工具
- 当当前 Provider 对应开关被关闭时，即使 Provider 仍保持该选项，运行时也会回退到默认静默 HTTP 搜索；若继续失败，Agent 会建议改用浏览器 / CDP 路径
- 如需替换密钥，可同时传 `apiKey`；该密钥会按当前 Provider 分开保存，不再与其它搜索 Provider 共用

---

### Live Artifact 渲染

```http
POST /api/artifacts/render
GET /api/artifacts/runtime/{artifact_id}/index.html
DELETE /api/artifacts/runtime/expired
```

`POST /api/artifacts/render` 用结构化渲染规格生成临时 sandbox 页面。后端不会把 Agent 任意生成的 HTML 作为长期聊天历史保存；长期保留的是消息文本、渲染规格和数据，临时运行文件统一写入 `.horbot/runtime/rendered-artifacts`。

示例：

```http
POST /api/artifacts/render
Content-Type: application/json

{
  "ttl_seconds": 1800,
  "spec": {
    "title": "销售看板",
    "summary": "展示收入、增长率与区域信号。",
    "template": "dashboard",
    "items": [
      {"label": "收入", "value": "128 万"}
    ],
    "points": [
      {"label": "1 月", "value": 42}
    ]
  }
}
```

响应：

```json
{
  "artifact_id": "66256c9ce7af4ed89a6f6eb6abf85888",
  "title": "销售看板",
  "template": "dashboard",
  "render_url": "/api/artifacts/runtime/66256c9ce7af4ed89a6f6eb6abf85888/index.html",
  "expires_at": "2026-04-28T09:07:12.858170+00:00",
  "ttl_seconds": 1800
}
```

当前支持模板：`dashboard`、`chart-story`、`data-workbench`、`map-story`、`process-map`、`interactive-report`。

---

### 渠道实例与 Horbot 入站机器人

```http
GET /api/channels/catalog
GET /api/channels/endpoints
POST /api/channels/endpoints
PUT /api/channels/endpoints/{endpoint_id}
DELETE /api/channels/endpoints/{endpoint_id}
POST /api/channels/draft-test
POST /api/channels/endpoints/{endpoint_id}/test
POST /api/channels/inbound/{app_id}/messages
```

当通道类型选择 `horbot-inbound-bot` 时，Horbot 会为这个通道实例生成：

- `bot_app_id`
- `bot_token`
- `inbound_url_path`: `/api/channels/inbound/{app_id}/messages`

这个入口适合 WorkBuddy 或其他厂商/本地 Agent 平台像飞书、Discord 机器人一样把消息推送进 Horbot，再由通道实例绑定的内部 Agent 接手处理。

示例：

```http
POST /api/channels/inbound/hbot_ch_workbuddy_xxx/messages
Authorization: Bearer <bot_token>
Content-Type: application/json

{
  "content": "来自 WorkBuddy 的任务消息",
  "chat_id": "workbuddy-room-1",
  "sender_id": "workbuddy",
  "target_agent_id": "main",
  "message_id": "msg-001",
  "metadata": {
    "vendor": "workbuddy"
  }
}
```

边界说明：

- Channels 的 `horbot-inbound-bot` 负责“外部消息入口”和路由到内部 Agent
- External Agent 的 `inbound-bot` 负责“外部成员身份”，用于单聊或团队成员编排
- 如果只是给 WorkBuddy 一个 Horbot 机器人入口，让它推送消息进某个内部 Agent，优先在 Channels 创建 `horbot-inbound-bot`
- `horbot-inbound-bot` 可以固定绑定某个内部 Agent；如果不绑定，入站请求可以通过顶层 `target_agent_id` / `agent_id` 或 `metadata.target_agent_id` / `metadata.agent_id` 指定目标，后端会在当前运行实例的 Agent 配置中校验后再路由

---

### 多 Agent 管理与治理

#### 外部 Agent 列表

```http
GET /api/external-agents
```

**响应示例**:

```json
{
  "external_agents": [
    {
      "id": "workbuddy-agent",
      "name": "WorkBuddy Agent",
      "adapter": "inbound-bot",
      "transport": "http",
      "inbound": {
        "app_id": "hbot_workbuddy_xxx",
        "token": "generated-token",
        "url_path": "/api/external-agents/inbound/hbot_workbuddy_xxx/messages"
      },
      "dm_enabled": true,
      "team_enabled": true,
      "capabilities": ["research", "analysis"]
    }
  ],
  "count": 1
}
```

#### 创建或更新外部 Agent

```http
POST /api/external-agents
PUT /api/external-agents/{external_agent_id}
Content-Type: application/json

{
  "id": "workbuddy-agent",
  "name": "WorkBuddy Agent",
  "adapter": "inbound-bot",
  "endpoint": "",
  "transport": "http",
  "auth_type": "none",
  "auth_secret": "",
  "capabilities": ["research", "analysis"],
  "dm_enabled": true,
  "team_enabled": true,
  "mention_required": false,
  "adapter_config": {}
}
```

说明：

- 当前支持独立的外部 Agent CRUD 与连接探测，不需要把外部 Agent 混入内部 `agents.instances`
- `adapter` 是开放 slug；推荐主路径是 `inbound-bot`，旧配置不带 `adapter` 时会按 `generic-agent-api` 兼容处理
- `inbound-bot` 会由 Horbot 生成 `adapter_config.bot_app_id` 和 `adapter_config.bot_token`，并提供 `/api/external-agents/inbound/{app_id}/messages` 给 WorkBuddy 或其他平台推送消息
- `endpoint` 只对 `generic-agent-api` 与 `openai-compatible` 强制填写；`inbound-bot` 不需要外部 URL
- `adapter_config` 用于保存厂商或本地 Agent 协议的专属配置，例如 `openai-compatible` 的 `model`、`chat_completions_endpoint` 等
- 旧配置不带 `adapter` 时会自动按 `generic-agent-api` 兼容处理
- 如果更新后将 `team_enabled` 关闭，后端会自动清理相关 team member 引用

#### 测试外部 Agent 连接

```http
POST /api/external-agents/{external_agent_id}/test
```

该接口返回轻量探测结果，用于管理页中的 “Test Connection”。对 `inbound-bot`，该接口验证 Horbot 侧 App ID、Token 与入站 URL 是否已生成，不会主动调用外部平台。

#### 外部平台推送消息到 Horbot

```http
POST /api/external-agents/inbound/{app_id}/messages
Authorization: Bearer <bot_token>
Content-Type: application/json

{
  "content": "WorkBuddy 已完成任务",
  "chat_id": "dm_workbuddy-agent",
  "sender_id": "workbuddy",
  "message_id": "msg-001",
  "metadata": {
    "vendor": "workbuddy"
  }
}
```

也可以通过 `X-Horbot-Bot-Token` header 或 JSON body 里的 `token` 传入 Token。服务端会把消息保存到对应 Web 会话历史中。

#### 获取团队成员明细

```http
GET /api/teams/{team_id}/members
```

当前返回体已显式区分 internal / external：

```json
{
  "team_id": "team-a",
  "members": [
    {
      "id": "agent-a",
      "kind": "internal",
      "profile": {},
      "agent": { "id": "agent-a", "name": "Agent A" }
    },
    {
      "id": "partner-agent",
      "kind": "external",
      "profile": {},
      "external_agent": { "id": "partner-agent", "name": "Partner Agent" }
    }
  ],
  "internal_members": [
    {
      "id": "agent-a",
      "kind": "internal",
      "profile": {},
      "agent": { "id": "agent-a", "name": "Agent A" }
    }
  ],
  "external_members": [
    {
      "id": "partner-agent",
      "kind": "external",
      "profile": {},
      "external_agent": { "id": "partner-agent", "name": "Partner Agent" }
    }
  ],
  "member_order": [
    { "id": "agent-a", "kind": "internal" },
    { "id": "partner-agent", "kind": "external" }
  ],
  "count": 2,
  "counts": {
    "total": 2,
    "internal": 1,
    "external": 1
  }
}
```

#### 获取 Agent bootstrap 文件

```http
GET /api/agents/{agent_id}/bootstrap-files
```

说明：

- 当前 bootstrap 资产包含 `AGENTS.md`、`SOUL.md`、`USER.md`
- 返回体同时包含各文件内容、是否存在、摘要信息和 `workspace_path`

#### 更新 bootstrap 文件

```http
PUT /api/agents/{agent_id}/bootstrap-files/{file_kind}
Content-Type: application/json

{
  "content": "# AGENTS.md\n\n- 优先说明风险\n- 不直接泄露密钥"
}
```

`file_kind` 当前支持：

- `agents`
- `soul`
- `user`

#### 更新 bootstrap 摘要

```http
PUT /api/agents/{agent_id}/bootstrap-summary
Content-Type: application/json

{
  "identity": ["你是代码评审 Agent"],
  "role_focus": ["优先发现高风险回归"],
  "communication_style": ["先给结论，再给依据"],
  "boundaries": ["高风险操作先确认"],
  "user_preferences": ["回答保持简洁"]
}
```

#### 获取工具审计记录

```http
GET /api/memory/tool-audits?agent_id=main&session_key=web:dm_main&risk_kind=all&limit=20&summary_window_hours=24
```

**响应示例**:

```json
{
  "agent_id": "main",
  "session_key": "web:dm_main",
  "risk_kind": "all",
  "window_hours": 24,
  "limit": 20,
  "total_returned": 6,
  "total_matches": 6,
  "blocked_count": 1,
  "error_count": 1,
  "summary": {
    "window_hours": 24,
    "total_count": 6,
    "blocked_count": 1,
    "exec_count": 2,
    "outbound_count": 3,
    "error_count": 1
  },
  "items": []
}
```

说明：

- `risk_kind` 支持 `all`、`blocked`、`exec`、`outbound`、`error`
- `summary` 用于前端顶部风险摘要条
- `session_key` 可用于定位某一轮具体聊天会话中的工具调用

---

### 聊天功能

#### 发送消息

```http
POST /api/chat
Content-Type: application/json

{
  "content": "你好，请帮我分析这段代码",
  "session_key": "default"
}
```

**响应示例**:
```json
{
  "content": "好的，我来帮你分析这段代码..."
}
```

#### 流式聊天（SSE）

```http
POST /api/chat/stream
Content-Type: application/json

{
  "content": "请帮我写一个 Python 函数",
  "session_key": "default"
}
```

**响应格式**: Server-Sent Events

```
event: token
data: {"content": "好"}

event: token
data: {"content": "的"}

event: done
data: {"status": "complete"}
```

说明：

- 当前 SSE 流和相关历史消息都会携带 `request_id`
- 前端会用 `request_id` 做失败诊断、停止生成和超时后的历史回查
- 如果某次前端先超时、但后端随后已成功落盘，聊天页会按 `request_id` 自动尝试收敛这类假超时提示
- Web 单聊在进入模型前会按 token 预算自动压缩上下文；若模型返回 `finish_reason=length`，后端会自动继续请求并把后续内容拼接到同一条流式回复中
- 当前聊天页的流式 inactivity timeout 为 `240s`；这不是 provider 超时阈值，而是前端等待流事件的超时窗口

#### 停止流式响应

```http
POST /api/chat/stream/{request_id}/stop
```

**响应示例**:
```json
{
  "status": "stopped"
}
```

---

### 会话管理

#### 获取聊天历史

```http
GET /api/chat/history?session_key=default
```

说明：

- 当某个 Agent 的会话历史同时存在于旧 `workspace/sessions` 与当前 `.horbot/agents/<agent-id>/workspace/.horbot-agent/sessions` 路径时，接口会自动合并、去重并按时间排序返回
- 返回结果中的附件与执行过程字段会尽量保留较完整的一份
- 该接口会返回 `Cache-Control: no-store`，前端也应使用 no-store 请求，避免刷新页面或切换模块后复用浏览器缓存中的旧历史窗口

**响应示例**:
```json
{
  "session_key": "default",
  "messages": [
    {
      "role": "user",
      "content": "你好",
      "timestamp": "2026-02-28T10:00:00"
    },
    {
      "role": "assistant",
      "content": "你好！有什么可以帮助你的吗？",
      "timestamp": "2026-02-28T10:00:05"
    }
  ]
}
```

#### 创建新会话

```http
POST /api/chat/sessions
```

**响应示例**:
```json
{
  "session_key": "session_4f0c6b0fd41f4c8bbf79d55d3d5421a8",
  "title": "新对话"
}
```

说明：

- 返回值中的 `session_key` 供前端和 Web API 直接使用
- 当前实现已改为 UUID 风格会话键，避免同秒创建时发生会话碰撞

#### 列出所有会话

```http
GET /api/chat/sessions
```

**响应示例**:
```json
{
  "sessions": [
    {
      "key": "web:session_4f0c6b0fd41f4c8bbf79d55d3d5421a8",
      "title": "代码分析",
      "created_at": "2026-04-12T11:05:12.120000",
      "message_count": 10
    }
  ]
}
```

#### 更新会话标题

```http
PUT /api/chat/sessions/{session_key}?title=新标题
```

**响应示例**:
```json
{
  "status": "success",
  "title": "新标题"
}
```

#### 删除会话

```http
DELETE /api/chat/sessions/{session_key}
```

**响应示例**:
```json
{
  "status": "success"
}
```

---

### 定时任务

---

### 文件上传与预览

#### 上传附件

```http
POST /api/upload
Content-Type: multipart/form-data
```

表单字段：

- `files`: 一个或多个文件

响应示例：

```json
{
  "files": [
    {
      "file_id": "2d43b693-8561-4735-9641-5ef4466c62b5",
      "filename": "2d43b693-8561-4735-9641-5ef4466c62b5.txt",
      "original_name": "demo.txt",
      "mime_type": "text/plain",
      "size": 22,
      "category": "document",
      "url": "/api/files/2d43b693-8561-4735-9641-5ef4466c62b5",
      "preview_url": null,
      "minimax_file_id": null,
      "extracted_text": "attachment smoke test\n"
    }
  ]
}
```

#### 获取附件原文件 / 内联预览

```http
GET /api/files/{file_id}
GET /api/files/{file_id}/preview
```

说明：

- 当前接口默认使用 `inline` 返回，浏览器会优先尝试图片、音频、PDF、文本等内联预览
- 前端聊天历史会基于该接口打开统一预览弹窗

#### PPTX 高保真预览能力

```http
GET /api/files/{file_id}/preview-capabilities
GET /api/files/{file_id}/preview/slides/{page}
POST /api/files/{file_id}/preview/cleanup
```

说明：

- PPTX 预览优先使用 LibreOffice：先把 PPTX 无头导出为中间 PDF，再用 PyMuPDF 按页渲染 PNG
- `preview-capabilities` 返回当前文件使用的 renderer、页数、已渲染页数和检测到的 `soffice` 路径
- `preview/slides/{page}` 只返回指定页 PNG；首次请求可能触发 LibreOffice 转 PDF，后续页面会复用 PDF 或 PNG 缓存
- `preview/cleanup` 删除该 PPTX 的中间 PDF；前端预览 iframe 卸载时会自动调用
- 已生成的 PNG 页缓存使用时会刷新时间戳，连续 3 天未使用后会被自动清理

响应示例：

```json
{
  "file_id": "6389fc95-22cc-491f-b051-95f4d2233ef5",
  "filename": "deck.pptx",
  "mime_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "supported": true,
  "renderer": "libreoffice-pdf-images",
  "preview_url": "/api/files/6389fc95-22cc-491f-b051-95f4d2233ef5/preview",
  "slide_count": 42,
  "visual_pages": 42,
  "rendered_pages": 3,
  "engines": [
    {"id": "libreoffice", "available": true, "command": "/opt/homebrew/bin/soffice"}
  ]
}
```

#### 远程图片缓存统计

```http
GET /api/files/cache/remote-images
```

响应示例：

```json
{
  "status": "success",
  "count": 3,
  "total_size_bytes": 216384,
  "newest_updated_at": "2026-04-15T15:44:23.521000"
}
```

说明：

- 该接口返回当前已落盘到上传目录的远程图片缓存统计
- Configuration 页面里的“远程图片缓存”区块会直接使用该接口

#### 清理远程图片缓存

```http
DELETE /api/files/cache/remote-images
```

响应示例：

```json
{
  "status": "success",
  "deleted_count": 3,
  "deleted_size_bytes": 216384
}
```

说明：

- 该接口只会删除自动缓存的远程图片文件，不会影响普通上传附件
- 可用于配置页中的手动“清理缓存”操作

#### 流式聊天携带附件

```http
POST /api/chat/stream
Content-Type: application/json

{
  "content": "请概括我上传的文件",
  "session_key": "web:dm_main",
  "agent_id": "main",
  "conversation_id": "dm_main",
  "conversation_type": "dm",
  "files": [
    {
      "file_id": "2d43b693-8561-4735-9641-5ef4466c62b5",
      "filename": "2d43b693-8561-4735-9641-5ef4466c62b5.txt",
      "original_name": "demo.txt",
      "mime_type": "text/plain",
      "size": 22,
      "category": "document",
      "url": "/api/files/2d43b693-8561-4735-9641-5ef4466c62b5",
      "preview_url": null,
      "minimax_file_id": null,
      "extracted_text": "attachment smoke test\n"
    }
  ]
}
```

支持的典型附件类型：

- 图片
- 音频
- PDF
- DOCX
- XLSX
- PPTX
- TXT / Markdown

历史消息补充说明：

- `GET /api/chat/history` 与 `GET /api/conversations/{conv_id}/messages` 会尽量把 assistant 正文中的独立远程图片链接提升为 `files` 附件
- `GET /api/conversations/{conv_id}/messages`、`GET /api/conversations/{conv_id}/search` 与 `GET /api/chat/history` 会明确返回 `Cache-Control: no-store`
- 会话消息分页支持最新窗口加载，以及 `before_id`、`after_id`、`around_id` 等锚点参数；如果 `after_id` 增量锚点已过期或本地不存在，客户端应回退重新拉取最新窗口
- 当远程图片缓存成功时，返回体中的 `preview_url` 会指向本地 `/api/files/{file_id}/preview`
- 当缓存失败时，仍会回退为远程 URL 形式的附件对象，前端继续按图片卡片渲染

#### 添加定时任务

```http
POST /api/cron
Content-Type: application/json

{
  "name": "每日提醒",
  "message": "早上好！今天有什么计划？",
  "cron": "0 9 * * *"
}
```

**响应示例**:
```json
{
  "id": "job_123",
  "name": "每日提醒",
  "cron": "0 9 * * *",
  "next_run": "2026-03-01T09:00:00"
}
```

#### 列出定时任务

```http
GET /api/cron
```

**响应示例**:
```json
{
  "jobs": [
    {
      "id": "job_123",
      "name": "每日提醒",
      "cron": "0 9 * * *",
      "next_run": "2026-03-01T09:00:00"
    }
  ]
}
```

#### 删除定时任务

```http
DELETE /api/cron/{job_id}
```

---

### 状态查询

#### 获取系统状态

```http
GET /api/status
```

**响应示例**:
```json
{
  "version": "0.1.4.post2",
  "provider": "openrouter",
  "model": "anthropic/claude-opus-4-5",
  "workspace": "./.horbot/agents/main/workspace",
  "channels": {
    "telegram": "connected",
    "discord": "disconnected"
  }
}
```

#### 获取渠道端点目录

```http
GET /api/channels/endpoints
```

说明：

- 返回所有渠道类型目录、当前已解析端点和缺失配置字段
- 当前目录已包含 `wecom`
- `wecom` 的必填字段为 `bot_id` 与 `secret`

`wecom` 典型配置字段包括：

- `websocket_url`
- `bot_id`
- `secret`
- `dm_policy`
- `group_policy`
- `stream_replies`
- `stream_edit_interval_ms`
- `stream_buffer_threshold`
- `stream_cursor`
- `download_media`

#### 测试渠道连通性

```http
POST /api/channels/endpoints/{endpoint_id}/test
```

说明：

- 可用于校验渠道配置是否完整以及当前链路是否可连通
- `wecom` 测试会检查 WeCom AI Bot WebSocket 网关配置

---

### 执行计划 API

#### 列出所有计划

```http
GET /api/plans?session_key=default
```

**响应示例**:
```json
{
  "plans": [
    {
      "id": "plan_123",
      "title": "实现用户认证功能",
      "status": "pending",
      "created_at": "2026-03-05T10:00:00",
      "session_key": "default"
    }
  ]
}
```

#### 获取计划详情

```http
GET /api/plan/{plan_id}
```

**响应示例**:
```json
{
  "id": "plan_123",
  "title": "实现用户认证功能",
  "description": "实现完整的用户认证系统",
  "status": "pending",
  "subtasks": [
    {
      "id": "task_1",
      "title": "创建用户模型",
      "status": "pending"
    }
  ]
}
```

#### 确认并执行计划

```http
POST /api/plan/{plan_id}/confirm
Content-Type: application/json

{
  "session_key": "default"
}
```

**响应**: SSE 流，包含子任务执行进度

#### 取消计划

```http
POST /api/plan/{plan_id}/cancel
```

**响应示例**:
```json
{
  "status": "cancelled",
  "plan_id": "plan_123"
}
```

#### 停止计划执行

```http
POST /api/plan/{plan_id}/stop
```

#### 获取计划执行日志

```http
GET /api/plan/{plan_id}/logs
```

---

### 技能管理 API

#### 列出所有技能

```http
GET /api/skills
```

**响应示例**:
```json
{
  "skills": [
    {
      "name": "memory",
      "source": "builtin",
      "description": "记忆管理技能",
      "enabled": true,
      "always": false
    }
  ]
}
```

#### 获取技能详情

```http
GET /api/skills/{skill_name}
```

#### 创建技能

```http
POST /api/skills
Content-Type: application/json

{
  "name": "my-skill",
  "content": "---\nname: my-skill\n---\n# My Skill"
}
```

#### 更新技能

```http
PUT /api/skills/{skill_name}
Content-Type: application/json

{
  "content": "---\nname: my-skill\n---\n# Updated Content"
}
```

#### 删除技能

```http
DELETE /api/skills/{skill_name}
```

#### 切换技能状态

```http
PATCH /api/skills/{skill_name}/toggle
```

---

### 子 Agent API

#### 列出所有子 Agent

```http
GET /api/subagents?session_key=default
```

**响应示例**:
```json
{
  "subagents": [
    {
      "task_id": "task_123",
      "label": "代码审查",
      "status": "running",
      "created_at": "2026-03-05T10:00:00"
    }
  ],
  "count": 1
}
```

#### 获取子 Agent 详情

```http
GET /api/subagents/{task_id}
```

#### 取消子 Agent

```http
POST /api/subagents/{task_id}/cancel
```

#### 取消所有子 Agent

```http
POST /api/subagents/cancel-all?session_key=default
```

---

### SSE 事件类型

流式响应支持以下事件类型：

#### 聊天事件

| 事件 | 描述 | 数据格式 |
|------|------|----------|
| `progress` | 进度更新 | `{"content": "..."}` |
| `tool_start` | 工具开始执行 | `{"tool_name": "...", "arguments": {}}` |
| `tool_result` | 工具执行结果 | `{"tool_name": "...", "result": "..."}` |
| `status` | 状态消息 | `{"message": "..."}` |
| `thinking` | 思考过程 | `{"content": "..."}` |
| `content` | 最终内容 | `{"content": "..."}` |
| `agent_start` | 某个 Agent 开始接棒 | `{"agent_id": "...", "agent_name": "...", "turn_id": "...", "message_id": "..."}` |
| `agent_mentioned` | 某个 Agent 被点名进入等待队列 | `{"agent_id": "...", "agent_name": "...", "mentioned_by": "...", "mentioned_by_name": "...", "handoff_mode": "relay|continue|summary", "handoff_preview": "..."}` |
| `agent_done` | 某个 Agent 完成这一棒 | `{"agent_id": "...", "content": "...", "turn_id": "...", "message_id": "..."}` |
| `done` | 完成 | `{}` |
| `stopped` | 已停止 | `{"content": "..."}` |
| `error` | 错误 | `{"content": "..."}` |

#### 计划事件

| 事件 | 描述 | 数据格式 |
|------|------|----------|
| `plan_generating` | 计划生成中 | `{}` |
| `plan_created` | 计划已创建 | `{"plan": {...}}` |
| `plan_skipped` | 计划已跳过 | `{}` |
| `subtask_start` | 子任务开始 | `{"plan_id": "...", "subtask_id": "..."}` |
| `subtask_complete` | 子任务完成 | `{"plan_id": "...", "status": "..."}` |
| `plan_complete` | 计划完成 | `{"content": "..."}` |

#### 确认事件

| 事件 | 描述 | 数据格式 |
|------|------|----------|
| `confirmation_required` | 需要确认 | `{"confirmation_id": "...", "tool_name": "..."}` |
| `step_start` | 步骤开始 | `{"step_id": "..."}` |
| `step_complete` | 步骤完成 | `{"step_id": "...", "status": "..."}` |

补充说明：

- `handoff_mode=relay` 表示普通转派
- `handoff_mode=continue` 表示发起 Agent 要求下一棒继续深入讨论
- `handoff_mode=summary` 表示这一棒准备回到最终面向用户的总结

---

## 🔄 WebSocket 事件

### 连接

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
```

### 客户端事件

#### 发送消息

```json
{
  "type": "chat",
  "content": "你好",
  "session_key": "default"
}
```

#### 停止生成

```json
{
  "type": "stop",
  "request_id": "req_123"
}
```

### 服务端事件

#### 流式 Token

```json
{
  "type": "token",
  "content": "好",
  "request_id": "req_123"
}
```

#### 完成响应

```json
{
  "type": "done",
  "request_id": "req_123",
  "full_content": "好的，我来帮你..."
}
```

#### 错误

```json
{
  "type": "error",
  "message": "API key not configured",
  "code": "CONFIG_ERROR"
}
```

---

## 🚨 错误响应

所有错误响应遵循统一格式：

```json
{
  "detail": "错误描述信息"
}
```

### 常见错误码

| 状态码 | 描述 |
|--------|------|
| 400 | 请求参数无效 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

---

## 📝 请求示例

### cURL

```bash
# 获取配置
curl http://localhost:8000/api/config

# 发送消息
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"content": "你好", "session_key": "default"}'

# 创建会话
curl -X POST http://localhost:8000/api/chat/sessions
```

### JavaScript (fetch)

```javascript
// 发送消息
const response = await fetch('/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    content: '你好',
    session_key: 'default'
  })
});
const data = await response.json();
console.log(data.content);
```

### Python (requests)

```python
import requests

# 发送消息
response = requests.post(
    'http://localhost:8000/api/chat',
    json={
        'content': '你好',
        'session_key': 'default'
    }
)
print(response.json()['content'])
```

---

## Skills API

### 获取技能列表

```http
GET /api/skills
```

每个 skill 现在包含以下兼容性相关字段：

- `missing_requirements`: 缺失的 CLI / ENV 依赖列表
- `install`: 可选安装建议
- `compatibility`: 兼容性报告
- `source_group`: `system` 或 `custom`
- `source_origin_kind`: `builtin`、`manual`、`agent`
- `source_origin_agent_id`: 当 skill 来自自动沉淀时，对应生成它的 Agent ID

`compatibility` 结构示例：

```json
{
  "status": "incompatible",
  "issues": ["Missing CLI dependency: gh"],
  "warnings": ["This skill uses legacy metadata and was normalized to the horbot schema."]
}
```

### 获取技能详情

```http
GET /api/skills/{skill_name}
```

详情接口同样返回 `missing_requirements`、`install` 和 `compatibility`。

### 获取技能图谱

```http
GET /api/skills/graph
```

返回当前 Agent 的技能图谱。若尚未持久化图谱，后端会基于当前技能目录即时构建内存图谱。

### 重建技能图谱

```http
POST /api/skills/graph/rebuild
```

重新扫描当前 Agent 技能目录，生成技能节点、引用节点、`has_reference`、`similar_to`、`related_to` 等关系，并写入 `.horbot-agent/skill_graph.json`。

持久化后的技能图谱也会被 Agent 运行时读取为技能摘要里的轻量提示，用于提示相邻技能和相关 `references/` 文件位置。

受管技能变更接口会在成功写入后尝试自动刷新持久化图谱，并可能返回 `skill_graph_refreshed`。图谱刷新失败不影响技能接口主流程。

### 导出技能包

```http
GET /api/skills/{skill_name}/export
```

返回标准 `.skill` 包，`Content-Disposition` 文件名为 `{skill_name}.skill`。目录型技能会包含完整的 `SKILL.md`、`references/`、`scripts/`、`assets/`、`agents/` 等文件；旧的单文件技能会被整理成标准技能包结构后导出。

### 创建技能

```http
POST /api/skills
Content-Type: application/json
```

请求体示例：

```json
{
  "name": "my-skill",
  "content": "---\nname: my-skill\ndescription: Describe when this skill should be used.\n---\n\n# My Skill"
}
```

创建时会执行 skill 规范校验；若 `SKILL.md` 缺少 frontmatter、`name/description`、或命名不合规，会返回 `400`。

### 更新技能

```http
PUT /api/skills/{skill_name}
Content-Type: application/json
```

请求体示例：

```json
{
  "content": "---\nname: my-skill\ndescription: Updated description.\n---\n\n# My Skill"
}
```

更新同样会经过 skill 校验。

### 导入技能包

```http
POST /api/skills/import
Content-Type: multipart/form-data
```

表单字段：

- `file`: 必填，`.skill` 或 `.zip`
- `replace_existing`: 可选，`true/false`

示例：

```bash
curl -X POST http://localhost:8000/api/skills/import \
  -F "file=@demo-skill.skill" \
  -F "replace_existing=false"
```

说明：

- 后端统一支持 `.skill` 与 `.zip`
- 导入前会验证标准 skill 目录结构、`SKILL.md`、frontmatter、`name/description`、相对引用文件以及兼容性信息
- 非法技能包会直接返回 `400`

导入时会校验：

- 压缩包结构是否合法
- 是否存在唯一 skill 根目录
- 是否存在 `SKILL.md`
- frontmatter / 命名规范是否正确
- 包内引用文件是否存在
- 路径是否安全

成功响应示例：

```json
{
  "name": "demo-skill",
  "path": "/abs/path/.horbot/agents/main/workspace/.horbot-agent/skills/demo-skill/SKILL.md",
  "message": "Skill 'demo-skill' imported successfully",
  "files": ["SKILL.md", "references/guide.md"],
  "description": "Demo packaged skill",
  "warnings": [],
  "compatibility": {
    "status": "incompatible",
    "issues": ["Missing CLI dependency: demo-cli"],
    "warnings": []
  }
}
```

### 手动整理自动技能

```http
POST /api/skills/consolidate-generated
```

说明：

- 手动把相关的 `auto-*` 技能合并成更宽的技能家族
- 合并后保留一个精简 `SKILL.md`，并把具体技巧整理到 `references/*.md`

成功响应示例：

```json
{
  "family_count_before": 3,
  "family_count_after": 1,
  "merged_skill_count": 3,
  "updated_families": [
    {
      "skill_name": "auto-officecli-ppt",
      "merged_skills": [
        "auto-officecli-ppt-highlight-xml-debug",
        "auto-officecli-ppt-text-overflow-debug"
      ]
    }
  ],
  "message": "Consolidated 3 generated skills across 1 skill families."
}
```

### 转为系统技能

```http
POST /api/skills/{skill_name}/promote
```

说明：

- 把当前工作区中的自定义 skill 提升为项目内置系统技能
- 内置后会从当前 Agent 工作区移出，写入项目 `horbot/skills/`

成功响应示例：

```json
{
  "name": "demo-skill",
  "path": "/abs/path/horbot/skills/demo-skill/SKILL.md",
  "source": "builtin",
  "message": "Skill 'demo-skill' promoted to builtin successfully"
}
```

Agent 侧还提供受控的 `save_skill` 工具，用于处理用户在聊天中明确提出的“把经验总结/沉淀为技能”请求。它不是公开 HTTP API，但会写入同一个当前 Agent 技能目录，并沿用自动沉淀的“技能家族 + references 技巧库”结构。

---

## 🔐 安全注意事项

1. **API Key 保护**: 不要在前端代码中暴露 API Key
2. **CORS 配置**: 生产环境应配置正确的 CORS 策略
3. **认证**: 生产环境建议添加认证层
4. **HTTPS**: 生产环境应使用 HTTPS
