# Horbot - 轻量级个人 AI 助手

<div align="center">
  <h1>🐎 horbot: 轻量级个人 AI 助手</h1>
  <p>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>
</div>

**horbot** 是一个轻量级的个人 AI 助手框架，专注于简洁、高效和易用性。

项目核心代码借鉴自 [HKUDS/nanobot](https://github.com/HKUDS/nanobot) 仓库内容，并在此基础上持续演进。

## ✨ 特性

- 🪶 **轻量级**: 核心代码简洁，易于理解和扩展
- 🔧 **易于配置**: 使用项目目录下的 `.horbot` 目录存储配置和数据
- 🌐 **多渠道支持**: 支持 Telegram、Discord、飞书、钉钉等多种消息渠道
- 🤖 **多模型支持**: 支持 OpenAI、Anthropic、DeepSeek 等多种 LLM 提供者
- 🛠️ **MCP 支持**: 支持 Model Context Protocol，可扩展工具能力
- 🔄 **上下文压缩**: 智能压缩对话历史，支持长对话场景
- 📝 **聊天 Markdown 渲染**: Assistant 回复支持标题、列表、表格、代码块与高亮
- 📎 **多模态附件**: 支持图片、音频、PDF、Word、Excel、PowerPoint、文本上传、粘贴与拖拽
- 👀 **内联附件预览**: 聊天历史中的图片、音频、PDF、Office 与文本附件可直接预览
- 🌳 **工作树隔离**: 任务级别目录隔离，支持并行任务执行
- 🤝 **团队协议**: 规范化的代理间通信协议
- 🤖 **自主代理**: 支持代理自主扫描和认领任务

## 📦 安装

```bash
# 克隆项目
git clone https://github.com/jenpeng/horbot.git
cd horbot

# 使用项目管理脚本安装所有依赖
./horbot.sh install
```

## 🚀 快速开始

### 使用项目管理脚本

项目提供了 `horbot.sh` 脚本来管理所有操作：

```bash
# 查看帮助
./horbot.sh help

# 检查状态（依赖 + 服务）
./horbot.sh status

# 安装依赖
./horbot.sh install              # 安装所有依赖
./horbot.sh install backend      # 只安装后端依赖
./horbot.sh install frontend     # 只安装前端依赖

# 启动服务
./horbot.sh start                # 启动所有服务（后端 + 前端 + Gateway）
./horbot.sh start backend        # 只启动后端服务
./horbot.sh start frontend       # 只启动前端服务
./horbot.sh start gateway        # 只启动 Gateway 服务

# 停止服务
./horbot.sh stop                 # 停止所有服务
./horbot.sh stop backend         # 只停止后端服务
./horbot.sh stop frontend        # 只停止前端服务
./horbot.sh stop gateway         # 只停止 Gateway 服务

# 重启服务
./horbot.sh restart              # 重启所有服务
./horbot.sh restart backend      # 只重启后端服务
./horbot.sh restart frontend      # 只重启前端服务
./horbot.sh restart gateway      # 只重启 Gateway 服务

# 查看日志
./horbot.sh logs backend         # 查看后端日志
./horbot.sh logs frontend        # 查看前端日志
./horbot.sh logs gateway         # 查看 Gateway 日志

# 浏览器端到端回归
./horbot.sh smoke browser-e2e    # 真实浏览器回归：Configuration + Agent 资产 + Dashboard + Skills + Performance + 失败重试 + 接力中断 + 单聊 + 团队接力
./horbot.sh smoke config         # 只跑 Configuration 页面
./horbot.sh smoke agent-assets   # 只跑多 Agent / SOUL.md / USER.md / 配置摘要
./horbot.sh smoke dm-chat        # 只跑单聊
./horbot.sh smoke dm-team-dispatch  # 单聊指挥 agent 发到团队群并验证群内接力
./horbot.sh smoke team-chat      # 只跑团队接力
./horbot.sh smoke chat-interrupt # 只跑接力停止/打断
./horbot.sh smoke chat-error-retry  # 只跑失败态与重试
./horbot.sh smoke external-inbound-memory  # 校验 legacy:* 外部来源元数据是否写入 execution/memory
./horbot.sh smoke bound-channel-dispatch  # 校验单聊内指挥 agent 外发到绑定 endpoint 的路由是否正确

# 开发模式（带热重载）
./horbot.sh dev
```

浏览器烟测会优先使用当前系统主 Chrome，失败后回退到项目内 `.playwright-browsers` 下的 `Chrome for Testing`。
如果你希望直接使用项目内浏览器，可先执行：

```bash
PLAYWRIGHT_BROWSERS_PATH=.playwright-browsers ./.venv/bin/python -m playwright install chromium
```

当前 `browser-e2e` 已覆盖：

- 聊天 Markdown 依赖链加载
- 附件上传、重试、顺序调整
- PDF / DOCX / XLSX / PPTX 分析
- 图片 / 音频识别
- 粘贴上传与拖拽上传
- 历史附件预览

### 多 Agent 档案管理

在 Web UI 的“团队管理 / 多 Agent 管理”中，每个 Agent 都有自己的独立工作区，以及独立的 `SOUL.md` 与 `USER.md`。

- `SOUL.md` 用于定义该 Agent 的身份、职责、沟通风格和边界
- `USER.md` 用于记录用户偏好与该 Agent 的协作约定
- “配置摘要”支持按分类直接编辑，保存后会自动回写到 `SOUL.md` / `USER.md` 对应章节
- 首次私聊引导完成后，待配置标记会自动移除，后续可以继续通过私聊或文件编辑微调

如果你要验证这条链路，推荐直接运行：

```bash
./horbot.sh smoke agent-assets
```

### 聊天与附件体验

当前 Web Chat 已支持：

- Assistant 消息按 Markdown 渲染
- 输入框直接上传、拖拽或 `Cmd/Ctrl + V` 粘贴图片和文件
- 图片、音频、PDF、Word、Excel、PowerPoint、文本文件分析
- 历史消息附件内联预览，不再默认直接下载

上传文件默认保存到：

```bash
.horbot/data/uploads
```

### Skills 导入与兼容性

当前 Skills 页面支持：

- 新建 / 编辑 `SKILL.md`
- 导入 `.skill` 或 `.zip` 技能包

导入技能包时，Horbot 会先做规范校验，再决定是否允许写入工作区。当前会检查：

- 包内是否只有一个 skill 根目录
- 是否存在 `SKILL.md`
- `SKILL.md` frontmatter 是否包含合法的 `name` 与 `description`
- 技能命名是否符合规范
- 包内相对引用文件是否存在
- 压缩包路径是否安全

导入完成后，Skills 页面会显示兼容性状态：

- `compatible`: 当前环境可直接使用
- `Needs Setup`: 可导入，但存在 setup 警告
- `Incompatible`: 当前环境缺少依赖，或操作系统不匹配

这意味着即使 skill 来自 SkillHub / ClawHub，页面也会立即告诉你它与当前 Horbot 实例是否兼容，而不是等到运行时才暴露问题。

### 安全默认值

从当前版本开始：

- Web 后端默认监听 `127.0.0.1`
- 未配置管理员令牌时，远程 API / WebSocket 访问会被拒绝
- `tools.restrictToWorkspace` 默认开启
- Web UI 不再回显已保存的明文密钥

如果你需要远程访问，请在 `.horbot/config.json` 中配置：

```json
{
  "gateway": {
    "adminToken": "replace-with-a-long-random-token",
    "allowRemoteWithoutToken": false
  }
}
```

并在请求中携带：

- `Authorization: Bearer <token>`
- 或 `X-Horbot-Admin-Token: <token>`

详细说明见：

- [安全指南](./docs/SECURITY_CN.md)
- [用户手册](./docs/USER_MANUAL_CN.md)
- [多 Agent 操作手册](./docs/MULTI_AGENT_GUIDE_CN.md)

### 依赖说明

本轮聊天渲染与附件能力落地没有新增第三方依赖，因此当前无需额外修改：

- `horbot/web/frontend/package.json`
- `pyproject.toml`
- 部署用 `yml` / compose 文件

前端所需的 `react-markdown`、`remark-gfm`、`highlight.js` 已经存在于项目中。

### Web UI 命令

在 Web 界面输入框中，可以使用以下命令：

| 命令 | 说明 |
|------|------|
| `/plan` | 开启规划模式，用于复杂任务的规划和执行 |

**使用方式：**
1. 输入 `/` 显示命令列表
2. 按 `Tab` 或 `Space` 确认选择
3. 输入任务内容后发送

### 初始化配置

```bash
# 激活虚拟环境
source .venv/bin/activate

# 初始化配置
horbot onboard
```

### 配置 API Key

编辑 `.horbot/config.json`：

```json
{
  "providers": {
    "openrouter": {
      "apiKey": "your-api-key"
    }
  },
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

建议同时确认：

```json
{
  "tools": {
    "restrictToWorkspace": true
  }
}
```

> **注意**: 如果未配置模型，系统将使用默认模型 `openrouter/anthropic/claude-sonnet-4-20250514`。

### 开始使用

```bash
# CLI 交互模式
horbot agent

# 发送单条消息
horbot agent -m "你好！"

# 启动 Web 界面
horbot web

# 启动 Gateway（多渠道消息）
horbot gateway
```

## 📁 项目结构

```
.horbot/                 # 项目本地配置和数据目录
├── config.json          # 主配置文件
│
├── data/                # 持久化数据
│   ├── cron/            # 定时任务数据
│   │   └── jobs.json    # 定时任务存储
│   ├── plans/           # 计划数据
│   ├── sessions/        # 会话数据
│   │   ├── recent/      # 最近会话快照
│   │   └── archived/    # 归档会话
│   └── uploads/         # 文件上传目录
│
├── runtime/             # 运行时文件 (可 gitignore)
│   ├── logs/            # 日志文件
│   │   ├── backend.log  # 后端日志
│   │   ├── frontend.log # 前端日志
│   │   └── gateway.log  # Gateway 日志
│   └── pids/            # 进程 ID 文件
│
├── agents/
│   └── main/
│       └── workspace/   # Agent 工作空间示例
│           ├── scripts/
│           ├── skills/
│           ├── token_usage/
│           ├── SOUL.md
│           └── USER.md
└── teams/               # 团队共享工作区与数据

horbot/               # 源代码
├── agent/               # 核心代理逻辑
│   ├── audit/           # 审计日志
│   ├── executor/        # 执行器 (状态管理、检查点)
│   └── ...
├── channels/            # 多渠道支持
├── cli/                 # 命令行接口
├── config/              # 配置管理
├── providers/           # LLM 提供者
├── skills/              # 内置技能
├── templates/           # 模板文件
├── utils/               # 工具函数 (含路径管理)
│   └── paths.py         # 统一路径管理
└── web/                 # Web 界面
```

### 目录说明

| 目录 | 用途 | 是否追踪 |
|------|------|----------|
| `config.json` | 主配置文件 | ✅ 追踪 |
| `context/` | 分层上下文管理 (L0/L1/L2 记忆) | ✅ 追踪 |
| `data/` | 持久化数据 (cron、sessions、plans) | ✅ 追踪 |
| `runtime/` | 运行时文件 (日志、PID) | ❌ 忽略 |
| `workspace/` | 用户工作空间 (SOUL、USER、skills) | ✅ 追踪 |

### 目录职责说明

#### context/ - 上下文管理
分层记忆系统，支持 AI 助手在不同时间跨度内保持上下文：
- **L0 (核心记忆)**: 当前会话的核心信息，始终加载
- **L1 (相关记忆)**: 近期会话的相关信息，按需加载
- **L2 (历史记忆)**: 长期历史事实，检索加载

#### data/ - 持久化数据
存储需要持久化的业务数据：
- **cron/**: 定时任务配置和状态
- **sessions/**: 会话历史记录
- **plans/**: 任务计划数据

#### runtime/ - 运行时文件
存储运行时产生的临时文件，可安全删除：
- **logs/**: 各服务日志文件
- **pids/**: 进程 ID 文件，用于服务管理

#### workspace/ - 用户工作空间
用户可自定义的内容：
- **SOUL.md**: AI 人格配置，定义 AI 的个性和行为
- **USER.md**: 用户信息，帮助 AI 了解用户偏好
- **skills/**: 自定义技能扩展

### 路径管理 API

项目提供统一的路径管理模块：

```python
from horbot.utils.paths import (
    get_horbot_root,         # 当前数据根目录（.horbot）
    get_config_path,         # config.json 路径
    get_data_dir,            # data/ 目录
    get_cron_dir,            # data/cron/ 目录
    get_sessions_dir,        # data/sessions/ 目录
    get_uploads_dir,         # data/uploads/ 目录
    get_runtime_dir,         # runtime/ 目录
    get_logs_dir,            # runtime/logs/ 目录
    get_pids_dir,            # runtime/pids/ 目录
    get_workspace_dir,       # Agent workspace 目录
    get_skills_dir,          # workspace/skills/ 目录
    ensure_all_dirs,         # 确保所有目录存在
)
```

## ⚙️ 配置说明

### 配置文件位置

配置文件默认位于项目目录下的 `.horbot/config.json`，旧 `.horbot/config.json` 仍兼容。

### 环境变量

- `HORBOT_CONFIG_PATH`: 自定义配置文件路径
- `HORBOT_*`: 其他配置项的环境变量覆盖

## 🚀 高级功能

### 上下文压缩 (Context Compact)

当对话历史过长时，系统会自动压缩中间对话为摘要，保留关键信息：

```json
{
  "agents": {
    "defaults": {
      "context_compact": {
        "enabled": true,
        "max_tokens": 100000,
        "preserve_recent": 10,
        "compress_tool_results": true
      }
    }
  }
}
```

### 工作树隔离 (Worktree Isolation)

为并行任务提供独立的目录隔离：

```python
from horbot.agent.worktree import WorktreeManager

manager = WorktreeManager()
worktree = manager.create_worktree("task_123")
# 任务在独立目录中执行
manager.cleanup_worktree("task_123")
```

### 团队协议 (Team Protocols)

规范化的代理间通信：

```python
from horbot.agent.team_protocols import TeamCoordinator, TaskBoard

coordinator = TeamCoordinator()
mailbox = coordinator.register_agent("worker_1", {"file_ops", "shell"})

# 任务板操作
board = TaskBoard()
await board.add_task(task_id="task_001", title="Test Task", required_capabilities={"file_ops"})
await board.claim_task("task_001", "worker_1")
```

### 自主代理 (Autonomous Agents)

代理可自主扫描和认领任务：

```python
from horbot.agent.autonomous import AutonomousAgent, AutonomousAgentManager

async def task_executor(task):
    # 执行任务逻辑
    return {"status": "completed"}

agent = AutonomousAgent(
    agent_id="worker_1",
    capabilities={"file_ops", "shell"},
    task_executor=task_executor,
)
await agent.start()  # 开始自主循环
```

## 📚 文档

详细文档请参阅 `docs/` 目录：

- [中文 README](docs/README_CN.md)
- [API 文档](docs/API_CN.md)
- [架构说明](docs/ARCHITECTURE_CN.md)

## 📄 许可证

MIT License
