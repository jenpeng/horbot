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

- 当某个 Agent 的会话历史同时存在于旧 `workspace/sessions` 与当前 `.horbot/agents/<agent-id>/sessions` 路径时，接口会自动合并、去重并按时间排序返回
- 返回结果中的附件与执行过程字段会尽量保留较完整的一份

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
```

说明：

- 当前接口默认使用 `inline` 返回，浏览器会优先尝试图片、音频、PDF、文本等内联预览
- 前端聊天历史会基于该接口打开统一预览弹窗

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
  "path": "/abs/path/skills/demo-skill/SKILL.md",
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

---

## 🔐 安全注意事项

1. **API Key 保护**: 不要在前端代码中暴露 API Key
2. **CORS 配置**: 生产环境应配置正确的 CORS 策略
3. **认证**: 生产环境建议添加认证层
4. **HTTPS**: 生产环境应使用 HTTPS
