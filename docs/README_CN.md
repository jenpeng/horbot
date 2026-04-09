<div align="center">
  <h1>horbot: 超轻量级个人 AI 助手</h1>
  <p>
    <a href="https://pypi.org/project/horbot-ai/"><img src="https://img.shields.io/pypi/v/horbot-ai" alt="PyPI"></a>
    <a href="https://pepy.tech/project/horbot-ai"><img src="https://static.pepy.tech/badge/horbot-ai" alt="Downloads"></a>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
    <a href="https://discord.gg/MnCvHqpUGB"><img src="https://img.shields.io/badge/Discord-Community-5865F2?style=flat&logo=discord&logoColor=white" alt="Discord"></a>
  </p>
  <p>
    <a href="./README_CN.md">简体中文</a> | <a href="../README.md">项目首页</a>
  </p>
</div>

---

🐎 **horbot** 是一个受 [OpenClaw](https://github.com/openclaw/openclaw) 启发的**超轻量级**个人 AI 助手。

⚡️ 仅用 **~4,000 行代码**实现核心 Agent 功能 — 相比重型代理框架更小、更容易理解和改造。

📏 实时代码行数：**3,966 行**（运行 `bash core_agent_lines.sh` 随时验证）

## 📢 最新动态

- **2026-02-24** 🚀 发布 **v0.1.4.post2** — 可靠性版本，重新设计心跳、提示缓存优化、提供商和渠道稳定性增强。
- **2026-02-21** 🎉 发布 **v0.1.4.post1** — 新增提供商、多渠道媒体支持、重大稳定性改进。
- **2026-02-17** 🎉 发布 **v0.1.4** — MCP 支持、进度流式传输、新提供商、多渠道改进。
- **2026-02-14** 🔌 horbot 已支持 MCP。详见 [MCP 章节](#mcp-model-context-protocol)。
- **2026-02-02** 🎉 horbot 正式发布！欢迎体验 🐎 horbot！

## 🔐 安全文档

- [安全指南](./SECURITY_CN.md)
- [用户手册](./USER_MANUAL_CN.md)
- [多 Agent 操作手册](./MULTI_AGENT_GUIDE_CN.md)

## 核心特性

| 特性 | 描述 |
|------|------|
| 🪶 **超轻量** | 仅 ~4,000 行核心代码，更适合理解、定制和快速迭代 |
| 🔬 **研究友好** | 清晰可读的代码，易于理解、修改和扩展 |
| ⚡️ **极速响应** | 最小化占用，更快的启动和更低的资源消耗 |
| 💎 **易于使用** | 一键部署，开箱即用 |
| 🔒 **安全可控** | 内置权限系统和审计日志，支持自主执行框架 |
| 🔥 **热加载** | 默认启用代码热加载，AI 修改代码后自动生效 |
| 📝 **Markdown 聊天** | Assistant 回复支持标题、列表、表格、引用、代码块与高亮 |
| 📎 **多模态附件** | 支持图片、音频、PDF、Word、Excel、PowerPoint、文本上传、拖拽与粘贴 |
| 👀 **历史预览** | 历史消息中的图片、音频、PDF、Office、文本附件可直接内联预览 |

## 🏗️ 架构

建议结合 [架构说明](./ARCHITECTURE_CN.md) 阅读。

## ✨ 功能展示

<table align="center">
  <tr align="center">
    <th><p align="center">📈 24/7 实时市场分析</p></th>
    <th><p align="center">🚀 全栈软件工程师</p></th>
    <th><p align="center">📅 智能日程管理</p></th>
    <th><p align="center">📚 个人知识助手</p></th>
  </tr>
  <tr>
    <td align="center"><p align="center"><img src="./assets/search.gif" width="180" height="400"></p></td>
    <td align="center"><p align="center"><img src="./assets/code.gif" width="180" height="400"></p></td>
    <td align="center"><p align="center"><img src="./assets/scedule.gif" width="180" height="400"></p></td>
    <td align="center"><p align="center"><img src="./assets/memory.gif" width="180" height="400"></p></td>
  </tr>
  <tr>
    <td align="center">发现 • 洞察 • 趋势</td>
    <td align="center">开发 • 部署 • 扩展</td>
    <td align="center">计划 • 自动化 • 组织</td>
    <td align="center">学习 • 记忆 • 推理</td>
  </tr>
</table>

## 📦 安装

**使用虚拟环境安装**（推荐，便于隔离和迁移）

```bash
git clone https://github.com/HKUDS/horbot.git
cd horbot
./install.sh        # macOS/Linux
# 或
.\install.ps1       # Windows PowerShell
```

这会创建一个 `.venv` 目录，所有依赖都在其中隔离。推荐使用项目脚本运行 horbot：

```bash
./horbot.sh start   # 启动前后端和 Gateway
./horbot.sh status  # 查看服务状态
./horbot.sh stop    # 停止所有服务
```

当前这轮聊天与附件能力落地没有新增第三方依赖，因此不需要额外修改 `package.json`、`pyproject.toml` 或部署 `yml`。

上传文件默认存放在：

```bash
.horbot/data/uploads
```

**Windows:**
```powershell
.\run.ps1 agent     # CLI 聊天模式
.\stop.ps1          # 停止所有服务
```

**从源码安装**（最新功能，推荐用于开发）

```bash
git clone https://github.com/HKUDS/horbot.git
cd horbot
pip install -e .
```

**使用 [uv](https://github.com/astral-sh/uv) 安装**（稳定、快速）

```bash
uv tool install horbot-ai
```

**从 PyPI 安装**（稳定版）

```bash
pip install horbot-ai
```

## 🚀 快速开始

> [!TIP]
> 在 `./.horbot/config.json` 中设置您的 API 密钥。
> 获取 API 密钥：[OpenRouter](https://openrouter.ai/keys)（全球）· [Brave Search](https://brave.com/search/api/)（可选，用于网页搜索）

**1. 初始化**

```bash
horbot onboard
```

**2. 配置** (`./.horbot/config.json`)

添加或合并以下**两部分**到您的配置中（其他选项使用默认值）。

*设置 API 密钥*（例如 OpenRouter，推荐全球用户使用）：
```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
    }
  }
}
```

*设置模型*（可选指定提供商 — 默认自动检测）：
```json
{
  "agents": {
    "defaults": {
      "models": {
        "main": {
          "provider": "openrouter",
          "model": "anthropic/claude-sonnet-4-20250514",
          "description": "主模型 - 通用对话"
        },
        "planning": {
          "provider": "openrouter",
          "model": "anthropic/claude-sonnet-4-20250514",
          "description": "计划模型 - 复杂任务规划"
        }
      }
    }
  }
}
```

> **注意**: 如果未配置模型，系统将使用默认模型 `openrouter/anthropic/claude-sonnet-4-20250514`。

**3. 开始聊天**

```bash
horbot agent
```

就是这么简单！2 分钟内您就拥有了一个可工作的 AI 助手。

## 🖥️ Web UI 命令

在 Web 界面输入框中，可以使用以下命令：

| 命令 | 说明 |
|------|------|
| `/plan` | 开启规划模式，用于复杂任务的规划和执行 |

**使用方式：**
1. 输入 `/` 显示命令列表
2. 按 `Tab` 或 `Space` 确认选择
3. 输入任务内容后发送

## 💬 聊天应用

将 horbot 连接到您喜欢的聊天平台。

| 平台 | 所需配置 |
|------|----------|
| **Telegram** | 来自 @BotFather 的 Bot Token |
| **Discord** | Bot Token + Message Content intent |
| **WhatsApp** | 扫描二维码 |
| **飞书** | App ID + App Secret |
| **ShareCRM** | App ID + App Secret |
| **Mochat** | Claw Token（支持自动设置） |
| **钉钉** | App Key + App Secret |
| **Slack** | Bot Token + App-Level Token |
| **Email** | IMAP/SMTP 凭据 |
| **QQ** | App ID + App Secret |

<details>
<summary><b>Telegram</b>（推荐）</summary>

**1. 创建 Bot**
- 打开 Telegram，搜索 `@BotFather`
- 发送 `/newbot`，按提示操作
- 复制 Token

**2. 配置**

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"]
    }
  }
}
```

> 您可以在 Telegram 设置中找到您的 **User ID**。显示为 `@yourUserId`。
> 复制此值**不带 `@` 符号**并粘贴到配置文件中。

**3. 运行**

```bash
horbot gateway
```

</details>

<details>
<summary><b>飞书</b></summary>

使用 **WebSocket** 长连接 — 无需公网 IP。

**1. 创建飞书机器人**
- 访问 [飞书开放平台](https://open.feishu.cn/app)
- 创建新应用 → 启用 **机器人** 能力
- **权限**：添加 `im:message`（发送消息）
- **事件**：添加 `im.message.receive_v1`（接收消息）
  - 选择 **长连接** 模式（需要先运行 horbot 建立连接）
- 从"凭证与基础信息"获取 **App ID** 和 **App Secret**
- 发布应用

**2. 配置**

```json
{
  "channels": {
    "feishu": {
      "enabled": true,
      "appId": "cli_xxx",
      "appSecret": "xxx",
      "encryptKey": "",
      "verificationToken": "",
      "allowFrom": [],
      "skipSslVerify": true
    }
  }
}
```

> `encryptKey` 和 `verificationToken` 在长连接模式下可选。
> `allowFrom`：留空允许所有用户，或添加 `["ou_xxx"]` 限制访问。
> `skipSslVerify`：跳过 SSL 验证，适用于代理/防火墙环境（默认 `true`）。

**3. 运行**

```bash
horbot gateway
```

> [!TIP]
> 飞书使用 WebSocket 接收消息 — 无需 webhook 或公网 IP！

</details>

<details>
<summary><b>ShareCRM（纷享销客）</b></summary>

使用 **SSE + REST** 通信 — 无需公网 IP。

**1. 创建 ShareCRM 机器人**
- 访问 [纷享销客开放平台](https://open.fxiaoke.com)
- 创建应用 → 启用 **企信机器人** 能力
- 从应用详情获取 **App ID** 和 **App Secret**

**2. 配置**

```json
{
  "channels": {
    "sharecrm": {
      "enabled": true,
      "gatewayBaseUrl": "https://open.fxiaoke.com",
      "appId": "your-app-id",
      "appSecret": "your-app-secret",
      "dmPolicy": "open",
      "allowFrom": [],
      "groupPolicy": "disabled",
      "groupAllowFrom": [],
      "textChunkLimit": 4000
    }
  }
}
```

**配置说明：**
| 字段 | 说明 |
|------|------|
| `gatewayBaseUrl` | IM Gateway 地址，默认 `https://open.fxiaoke.com` |
| `dmPolicy` | 私聊策略：`open`（开放）、`allowlist`（白名单）、`disabled`（禁用） |
| `allowFrom` | 私聊白名单用户 ID 列表 |
| `groupPolicy` | 群聊策略：`open`、`allowlist`、`disabled` |
| `groupAllowFrom` | 群聊白名单群组 ID 列表 |
| `textChunkLimit` | 消息分块大小限制，默认 4000 字符 |

**3. 运行**

```bash
horbot gateway
```

> [!TIP]
> ShareCRM 使用 SSE 接收消息 — 无需 webhook 或公网 IP！

</details>

<details>
<summary><b>Discord</b></summary>

**1. 创建 Bot**
- 访问 https://discord.com/developers/applications
- 创建应用 → Bot → Add Bot
- 复制 Bot Token

**2. 启用 Intents**
- 在 Bot 设置中，启用 **MESSAGE CONTENT INTENT**

**3. 获取您的 User ID**
- Discord 设置 → 高级 → 启用 **开发者模式**
- 右键点击您的头像 → **复制用户 ID**

**4. 配置**

```json
{
  "channels": {
    "discord": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"]
    }
  }
}
```

**5. 邀请 Bot**
- OAuth2 → URL Generator
- Scopes: `bot`
- Bot Permissions: `Send Messages`, `Read Message History`
- 打开生成的邀请链接并将 Bot 添加到您的服务器

**6. 运行**

```bash
horbot gateway
```

</details>

<details>
<summary><b>Slack</b></summary>

使用 **Socket Mode** — 无需公网 URL。

**1. 创建 Slack 应用**
- 访问 [Slack API](https://api.slack.com/apps) → **Create New App** → "From scratch"
- 选择名称和工作区

**2. 配置应用**
- **Socket Mode**：开启 → 生成 **App-Level Token**，添加 `connections:write` 作用域 → 复制 (`xapp-...`)
- **OAuth & Permissions**：添加 Bot 作用域：`chat:write`, `reactions:write`, `app_mentions:read`
- **Event Subscriptions**：开启 → 订阅 Bot 事件：`message.im`, `message.channels`, `app_mention`
- **App Home**：滚动到 **Show Tabs** → 启用 **Messages Tab**
- **Install App**：点击 **Install to Workspace** → 授权 → 复制 **Bot Token** (`xoxb-...`)

**3. 配置 horbot**

```json
{
  "channels": {
    "slack": {
      "enabled": true,
      "botToken": "xoxb-...",
      "appToken": "xapp-...",
      "groupPolicy": "mention"
    }
  }
}
```

**4. 运行**

```bash
horbot gateway
```

直接给 Bot 发私信或在频道中 @mention 它 — 它会响应！

</details>

## ⚙️ 配置

配置文件：`./.horbot/config.json`

### 提供商

| 提供商 | 用途 | 获取 API Key |
|--------|------|--------------|
| `custom` | 任何 OpenAI 兼容端点 | — |
| `openrouter` | LLM（推荐，访问所有模型） | [openrouter.ai](https://openrouter.ai) |
| `anthropic` | LLM（Claude 直连） | [console.anthropic.com](https://console.anthropic.com) |
| `openai` | LLM（GPT 直连） | [platform.openai.com](https://platform.openai.com) |
| `deepseek` | LLM（DeepSeek 直连） | [platform.deepseek.com](https://platform.deepseek.com) |
| `groq` | LLM + **语音转录**（Whisper） | [console.groq.com](https://console.groq.com) |
| `gemini` | LLM（Gemini 直连） | [aistudio.google.com](https://aistudio.google.com) |
| `minimax` | LLM（MiniMax 直连） | [platform.minimaxi.com](https://platform.minimaxi.com) |
| `siliconflow` | LLM（硅基流动） | [siliconflow.cn](https://siliconflow.cn) |
| `volcengine` | LLM（火山引擎） | [volcengine.com](https://www.volcengine.com) |
| `dashscope` | LLM（通义千问） | [dashscope.console.aliyun.com](https://dashscope.console.aliyun.com) |
| `moonshot` | LLM（Moonshot/Kimi） | [platform.moonshot.cn](https://platform.moonshot.cn) |
| `zhipu` | LLM（智谱 GLM） | [open.bigmodel.cn](https://open.bigmodel.cn) |
| `vllm` | LLM（本地，任何 OpenAI 兼容服务器） | — |

### MCP (Model Context Protocol)

> [!TIP]
> 配置格式与 Claude Desktop / Cursor 兼容。您可以直接从任何 MCP 服务器的 README 复制配置。

horbot 支持 [MCP](https://modelcontextprotocol.io/) — 连接外部工具服务器并将其作为原生 Agent 工具使用。

在 `config.json` 中添加 MCP 服务器：

```json
{
  "tools": {
    "mcpServers": {
      "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"]
      },
      "my-remote-mcp": {
        "url": "https://example.com/mcp/",
        "headers": {
          "Authorization": "Bearer xxxxx"
        }
      }
    }
  }
}
```

支持两种传输模式：

| 模式 | 配置 | 示例 |
|------|------|------|
| **Stdio** | `command` + `args` | 通过 `npx` / `uvx` 的本地进程 |
| **HTTP** | `url` + `headers`（可选） | 远程端点 (`https://mcp.example.com/sse`) |

### 安全

> [!TIP]
> 对于生产部署，在配置中设置 `"restrictToWorkspace": true` 以沙箱化 Agent。

| 选项 | 默认值 | 描述 |
|------|--------|------|
| `tools.restrictToWorkspace` | `false` | 为 `true` 时，限制**所有** Agent 工具（shell、文件读/写/编辑、列表）仅在工作区目录内操作 |
| `tools.exec.pathAppend` | `""` | 运行 shell 命令时要追加到 `PATH` 的额外目录 |
| `channels.*.allowFrom` | `[]`（允许所有） | 用户 ID 白名单。空 = 允许所有人；非空 = 仅列出的用户可交互 |

## CLI 参考

| 命令 | 描述 |
|------|------|
| `horbot onboard` | 初始化配置和工作区 |
| `horbot agent -m "..."` | 与 Agent 聊天 |
| `horbot agent` | 交互式聊天模式 |
| `horbot gateway` | 启动网关 |
| `horbot status` | 显示状态 |
| `horbot provider login openai-codex` | 提供商 OAuth 登录 |
| `horbot channels login` | 链接 WhatsApp（扫描二维码） |

交互模式退出：`exit`、`quit`、`/exit`、`/quit`、`:q` 或 `Ctrl+D`。

## 🐳 Docker

### Docker Compose

```bash
docker compose run --rm horbot-cli onboard   # 首次设置
vim ./.horbot/config.json                     # 添加 API 密钥
docker compose up -d horbot-gateway           # 启动网关
```

### Docker

```bash
# 构建镜像
docker build -t horbot .

# 初始化配置（仅首次）
docker run -v ./.horbot:/app/.horbot --rm horbot onboard

# 编辑主机上的配置以添加 API 密钥
vim ./.horbot/config.json

# 运行网关
docker run -v ./.horbot:/app/.horbot -p 18790:18790 horbot gateway

# 或运行单个命令
docker run -v ./.horbot:/app/.horbot --rm horbot agent -m "Hello!"
```

## 📁 项目结构

```
horbot/
├── agent/              # 🧠 核心 Agent 逻辑
│   ├── loop.py         #    Agent 循环（LLM ↔ 工具执行）
│   ├── context.py      #    提示构建器
│   ├── memory.py       #    持久化记忆
│   ├── planner.py      #    任务规划
│   ├── skills.py       #    技能加载器
│   ├── subagent.py     #    后台任务执行
│   ├── message_processor.py  # 消息处理（新增）
│   ├── tool_executor.py      # 工具执行（新增）
│   ├── executor/       #    执行检查点和状态
│   ├── planner/        #    计划生成器、验证器和策略
│   │   ├── generator.py
│   │   ├── validator.py
│   │   ├── analyzer.py
│   │   ├── errors.py   #    错误处理（新增）
│   │   └── strategy.py #    规划策略（新增）
│   ├── tools/          #    内置工具
│   │   ├── base.py     #    ToolMetadata, ToolError（增强）
│   │   ├── permission.py #  PermissionResult（增强）
│   │   ├── registry.py #    ExecutionResult（增强）
│   │   └── ...
│   └── workflow/       #    工作流解析器
├── skills/             # 🎯 内置技能（github, weather, tmux...）
├── channels/           # 📱 聊天渠道集成
│   ├── base.py         #    BaseChannel（增强）
│   ├── monitor.py      #    ChannelMonitor（新增）
│   └── ...
├── bus/                # 🚌 消息路由
├── cron/               # ⏰ 定时任务
├── heartbeat/          # 💓 主动唤醒
├── providers/          # 🤖 LLM 提供商
│   ├── base.py         #    BaseProvider（增强）
│   ├── selector.py     #    ProviderSelector（新增）
│   ├── monitor.py      #    ProviderMonitor（新增）
│   └── ...
├── session/            # 💬 会话管理
├── config/             # ⚙️ 配置
│   ├── validator.py    #    配置验证（新增）
│   ├── migrator.py     #    配置迁移（新增）
│   ├── watcher.py      #    热重载（新增）
│   └── ...
├── cli/                # 🖥️ 命令
├── web/                # 🌐 Web UI
└── utils/              # 🔧 工具函数
```

### 🆕 新功能 (v0.1.5+)

| 功能 | 描述 |
|------|------|
| **热重载** | 使用 `uvicorn --reload` 实现后端代码自动重载 |
| **HMR** | 使用 Vite 实现前端热模块替换 |
| **服务管理** | `./horbot.sh start/stop/restart/status` 命令 |
| **配置热重载** | 自动检测并应用配置变更 |
| **Provider 降级** | 自动重试并降级到备用提供商 |
| **渠道监控** | 渠道健康检查和自动重启 |

## 📂 工作区目录结构

工作区是 horbot 存储所有运行时数据的地方。通过配置中的 `agents.defaults.workspace` 设置：

```json
{
  "agents": {
    "defaults": {
      "workspace": ".horbot/workspace"
    }
  }
}
```

### 目录布局

```
workspace/
├── .audit/              # 📋 审计日志（工具执行跟踪）
├── .checkpoints/        # 💾 执行检查点（用于恢复）
├── .state/              # 📊 执行状态持久化
├── memory/              # 🧠 长期记忆
│   ├── MEMORY.md        #    关于用户的持久化事实
│   └── HISTORY.md       #    可搜索的事件日志
├── sessions/            # 💬 会话历史
├── skills/              # 🎯 自定义用户技能
├── cron/                # ⏰ 定时任务存储
├── logs/                # 📝 运行日志
├── AGENTS.md            # 📖 Agent 系统提示词
├── SOUL.md              # 🎭 Agent 人格
└── USER.md              # 👤 用户档案
```

### 路径解析

| 配置值 | 解析结果 |
|--------|----------|
| `.horbot/workspace`（默认） | `{project_root}/.horbot/workspace` |
| `~/.horbot/workspace` | `/home/user/.horbot/workspace` |
| `/custom/path` | `/custom/path` |

> **注意**：相对路径相对于项目根目录解析（通过 `.git`、`pyproject.toml` 或 `.horbot` 标记文件检测）。

---

## 🤖 自主执行框架

horbot 现已支持**自主规划和执行**，内置安全控制，灵感来自 Moltclaw/OpenClaw 但增强了安全性。

### 核心功能

| 功能 | 描述 |
|------|------|
| **任务分析** | 自动检测需要多步规划的复杂任务 |
| **计划生成** | LLM 驱动的 DAG 结构计划生成 |
| **安全执行** | 工具权限、路径保护、审计日志 |
| **错误恢复** | 自动重试和回滚机制 |
| **进度跟踪** | 实时进度更新和检查点 |

### 快速开始

1. **启用规划模式**：
```
/plan
```

2. **发送复杂任务**：
```
重构认证模块以使用 OAuth2 并更新所有测试
```

3. **审核并确认**生成的计划：
```
yes  # 执行
no   # 取消
```

### 权限配置文件

| 配置文件 | 描述 | 允许 | 拒绝 |
|----------|------|------|------|
| `minimal` | 最安全，只读 | - | runtime, automation |
| `balanced` | 默认，适合大多数任务 | fs, web | automation |
| `coding` | 用于开发工作 | fs, web, runtime | automation |
| `readonly` | 纯研究 | read, list_dir, web | write, edit, runtime |
| `full` | 所有工具启用 | 所有 | - |

### 配置

添加到 `./.horbot/config.json`：

```json
{
  "autonomous": {
    "enabled": true,
    "max_plan_steps": 10,
    "step_timeout": 300,
    "confirm_sensitive": true
  },
  "tools": {
    "permission": {
      "profile": "balanced",
      "allow": ["group:fs", "group:web"],
      "deny": ["group:automation"],
      "confirm": ["group:runtime"]
    }
  }
}
```

### 安全特性

- **工具权限**：白名单/黑名单控制工具访问
- **路径保护**：限制文件访问仅限工作区
- **敏感操作确认**：危险操作需要用户批准
- **审计日志**：完整记录所有工具执行
- **受保护路径**：核心配置文件和系统目录只读

### 与 Moltclaw/OpenClaw 对比

| 功能 | Moltclaw/OpenClaw | horbot |
|------|-------------------|---------|
| 自主规划 | ✅ 完全 | ✅ 可配置级别 |
| 工具访问 | ⚠️ 无限制（有风险） | ✅ 白名单/黑名单 |
| 文件修改 | ⚠️ 任何文件 | ✅ 路径隔离 + 核心保护 |
| 敏感操作 | ⚠️ 无确认 | ✅ 需要用户确认 |
| 审计日志 | ❌ 无 | ✅ 完整审计 |
| 错误恢复 | ❌ 有限 | ✅ 重试 + 回滚 |

---

## 🤝 贡献

PR 欢迎！代码库故意保持小巧和可读。🤗

**路线图** — 选择一项并 [提交 PR](https://github.com/HKUDS/horbot/pulls)！

- [x] **自主执行** — 自主规划和执行，带安全控制
- [ ] **多模态** — 看和听（图像、语音、视频）
- [ ] **长期记忆** — 永远不忘重要上下文
- [ ] **更好的推理** — 多步规划和反思
- [ ] **更多集成** — 日历等
- [ ] **自我改进** — 从反馈和错误中学习

## ⭐ Star 历史

<div align="center">
  <a href="https://star-history.com/#HKUDS/horbot&Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=HKUDS/horbot&type=Date&theme=dark" />
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=HKUDS/horbot&type=Date" />
      <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=HKUDS/horbot&type=Date" style="border-radius: 15px; box-shadow: 0 0 30px rgba(0, 217, 255, 0.3);" />
    </picture>
  </a>
</div>

<p align="center">
  <em>感谢访问 ✨ horbot！</em><br><br>
  <img src="https://visitor-badge.laobi.icu/badge?page_id=HKUDS.horbot&style=for-the-badge&color=00d4ff" alt="Views">
</p>

<p align="center">
  <sub>horbot 仅供教育、研究和技术交流目的</sub>
</p>
