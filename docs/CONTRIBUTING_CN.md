# 贡献指南

感谢您有兴趣为 horbot 做贡献！本文档将帮助您了解如何参与项目开发。

## 📋 目录

- [行为准则](#行为准则)
- [如何贡献](#如何贡献)
- [开发环境设置](#开发环境设置)
- [新功能开发指南](#新功能开发指南)
- [技能开发流程](#技能开发流程)
- [文档更新指南](#文档更新指南)
- [代码风格](#代码风格)
- [提交规范](#提交规范)
- [Pull Request 流程](#pull-request-流程)

---

## 行为准则

本项目采用贡献者公约作为行为准则。参与本项目即表示您同意遵守其条款。

---

## 如何贡献

### 报告 Bug

如果您发现了 Bug，请通过 [GitHub Issues](https://github.com/jenpeng/horbot/issues) 提交报告。提交前请：

1. 搜索现有 Issues，确认该 Bug 尚未被报告
2. 使用 Bug 报告模板填写详细信息
3. 提供复现步骤、预期行为和实际行为

### 建议新功能

我们欢迎新功能建议！请：

1. 通过 [GitHub Discussions](https://github.com/jenpeng/horbot/discussions) 发起讨论
2. 详细描述功能需求和使用场景
3. 等待维护者反馈后再开始实现

### 提交代码

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

---

## 开发环境设置

### 前置要求

- Python 3.11+
- Node.js 18+ (用于 Web UI 开发)
- Git

### 设置步骤

```bash
# 1. 克隆仓库
git clone https://github.com/jenpeng/horbot.git
cd horbot

# 2. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# 或
.\.venv\Scripts\activate  # Windows

# 3. 安装开发依赖
pip install -e ".[dev]"

# 4. 安装 pre-commit hooks
pre-commit install

# 5. 运行测试
pytest

# 6. 启动开发服务器
horbot web
```

### Web UI 开发

```bash
cd horbot/web/frontend
npm install
npm run dev
```

### Web 后端路由开发

`horbot/web/api.py` 现在主要负责 router 组合、聊天核心兼容和旧导入 shim。新增功能端点时，应放入 `horbot/web/*_routes.py` 中最接近的功能模块，避免继续扩张 `api.py`。

修改聊天或会话历史路由时，需要保持以下契约：

- 历史接口响应必须包含 `Cache-Control: no-store`
- 前端历史请求应使用 `cache: 'no-store'`
- `after_id` 增量加载在锚点失效或本地缺失时，需要回退拉取最新窗口
- 除非有明确迁移文档和测试，否则 `horbot.web.api` 中的旧兼容导入点应继续可用

### 文档与截图同步

如果改动影响了 README 或文档截图，请基于当前本地运行中的真实 Web UI 重新抓图，不要使用设计稿或旧项目截图。

英文版 README 截图可使用：

```bash
./.venv/bin/python scripts/capture_readme_screenshots.py --locale en --output-dir docs/assets/en
```

---

## 新功能开发指南

### 分层上下文功能开发

开发与分层上下文相关的功能时，请遵循以下原则：

**层级选择**：
- **L0 (核心记忆)**: 当前会话活跃数据，如任务进度、临时状态
- **L1 (相关记忆)**: 近期重要事件，如最近修复的 Bug、近期决策
- **L2 (历史记忆)**: 长期持久化事实，如用户偏好、项目架构知识

**Token 预算**：
- L0: 60% 预算
- L1: 30% 预算
- L2: 10% 预算

**API 使用示例**：

```python
from horbot.agent.context_manager import HierarchicalContextManager
from pathlib import Path

# 初始化
manager = HierarchicalContextManager(workspace=Path(".horbot/agents/main/workspace"))

# 加载上下文
context = manager.load_context(
    session_key="web:session_123",
    levels=["L0", "L1"],
    max_tokens=8000
)

# 添加记忆
manager.add_memory(
    content="用户偏好使用深色主题",
    level="L1",
    metadata={"type": "preference"}
)

# 搜索上下文
results = manager.search_context(
    query="authentication",
    levels=["L1", "L2"],
    max_results=10
)
```

### 热加载功能开发

**配置热加载**：

```python
from horbot.config.watcher import ConfigWatcher
from pathlib import Path

# 创建配置监视器
watcher = ConfigWatcher(
    config_path=Path("./.horbot/config.json"),
    debounce_seconds=1.0
)

# 添加变更监听器
async def on_config_change(event):
    if event.error:
        print(f"配置加载失败: {event.error}")
        return
    print(f"配置已更新: {event.changed_keys}")

watcher.add_listener(on_config_change)

# 启动监视
await watcher.start()
```

**前端 HMR**: 确保 Vite 配置正确（已配置）
**后端热重载**: 使用 `uvicorn --reload` 启动

### Horbot 入站机器人开发

修改 `horbot-inbound-bot` 时，需要保持完整链路一致：

- `horbot/config/schema.py`：`HorbotInboundBotConfig` 保存通道级自动生成凭证
- `horbot/channels/endpoints.py`：维护 catalog 元数据、类型映射、runtime config 合并和 endpoint 投影
- `horbot/config/normalizer.py`：`_CHANNEL_TYPES` 必须包含 `horbot-inbound-bot`，否则保存的 endpoint 可能被规范化过程丢弃
- `horbot/channels/manager.py`：ChannelManager factory 必须能创建 `HorbotInboundBotChannel`
- `horbot/channels/horbot_inbound_bot.py`：保持轻量运行时；真正的 HTTP 入站处理在 Web API route 中，不在这里维护长连接
- `horbot/channels/diagnostics.py`：诊断需要确认 App ID 和 Token 已生成
- `horbot/web/api.py`：`/api/channels/inbound/{app_id}/messages` 负责 token 校验、sender allowlist、目标 Agent 校验，并调用 `get_agent_loop(target_agent_id).process_message(...)`
- `horbot/web/frontend/src/pages/ChannelsPage.tsx`：页面必须以可复制方式展示 App ID、Token 和 Inbound URL，并且该通道类型的 Agent 绑定是可选的

路由与安全规则：

- endpoint 上固定配置了 `agent_id` 时，优先路由到这个 Agent
- endpoint 未绑定 Agent 时，请求必须在顶层提供 `target_agent_id` / `agent_id`，或在 `metadata.target_agent_id` / `metadata.agent_id` 中提供
- 不允许把外部传入的任意 ID 直接当成目标执行，必须在当前运行实例的 `config.agents.instances` 中校验存在
- 未绑定 endpoint 不能静默回退到第一个默认 Agent；缺少或未知目标时应返回明确的 400
- token 可来自 `Authorization: Bearer`、`X-Horbot-Bot-Token` 或 JSON body 的 `token`，但比较必须继续使用 `secrets.compare_digest`

测试要求：

- 请求结构、路由规则、凭证生成或校验行为变化时，同步更新 `tests/test_channel_endpoints_api.py`
- 保持覆盖：凭证生成、固定 Agent 路由、请求指定 Agent 路由、未知 Agent 拒绝、错误 token 拒绝
- 推荐执行：`./.venv/bin/python -m unittest tests.test_channel_endpoints_api tests.test_config_normalizer tests.test_channel_diagnostics`

文档要求：

- 同步更新 `docs/API.md`、`docs/API_CN.md`、`docs/USER_MANUAL.md`、`docs/USER_MANUAL_CN.md`、`docs/ARCHITECTURE.md`、`docs/ARCHITECTURE_CN.md`
- 如果 UI 文案或提示变化，需要同步中英泰 locale 文件

---

## 技能开发流程

### 当前运行时目录约定

开发时请以以下 Agent 运行时目录为准：

- `.horbot/agents/<agent-id>/workspace/.horbot-agent/memory`
- `.horbot/agents/<agent-id>/workspace/.horbot-agent/sessions`
- `.horbot/agents/<agent-id>/workspace/.horbot-agent/skills`

不要再新增或依赖以下旧路径假设：

- `.horbot/context`
- `.horbot/memory`
- `.horbot/agents/<agent-id>/{memory,sessions,skills}`
- `workspace/skills`

### 创建新技能

1. **创建技能目录**：

```bash
mkdir -p .horbot/agents/main/workspace/.horbot-agent/skills/my-skill
```

2. **创建 SKILL.md 文件**：

```markdown
---
name: my-skill
description: 我的自定义技能
always: false
enabled: true
requires:
  bins: ["required-binary"]
  env: ["REQUIRED_ENV"]
---

# My Skill

## 功能说明

详细描述技能的功能和使用方法...

## 使用场景

- 场景1: 描述
- 场景2: 描述

## 示例

示例代码和用法...
```

3. **测试技能**：

```bash
# 重启服务或刷新技能列表
curl -X GET http://localhost:8000/api/skills
```

### 自动技能结构约定

如果改动涉及自动沉淀技能，请保持当前结构约定：

- 优先把同类技巧沉淀到一个更宽的技能家族
- `SKILL.md` 负责写清楚触发条件、用法和如何查阅资料
- 具体技巧、排障步骤、案例化说明放到 `references/*.md`
- 不要为同一类细小变体持续新增大量平铺的 `auto-*` 目录

### 技能最佳实践

1. **清晰的描述** - 让 AI 理解何时使用这个技能
2. **具体的指令** - 提供明确的操作步骤
3. **示例代码** - 展示如何使用技能
4. **依赖声明** - 明确需要的工具和环境变量

### 与分层上下文的集成

技能执行结果可以存储到分层记忆：

```python
# 存储到 L1 (近期记忆)
manager.add_memory(
    content="技能执行结果...",
    level="L1",
    metadata={"skill": "self-improvement", "type": "code-review"}
)

# 从分层上下文检索相关信息
results = manager.search_context(
    query="code review authentication",
    levels=["L1", "L2"],
    max_results=10
)
```

---

## 文档更新指南

### 文档结构

```
docs/
├── README_CN.md              # 中文 README
├── USER_MANUAL_CN.md         # 用户手册
├── MULTI_AGENT_GUIDE_CN.md   # 多 Agent 手册
├── ARCHITECTURE_CN.md        # 架构文档
├── API_CN.md                 # API 文档
├── SKILLS_CN.md              # 技能系统文档
├── SECURITY_CN.md            # 安全指南
└── CONTRIBUTING_CN.md        # 贡献指南
```

### 文档更新原则

1. **中英文同步**: 更新英文文档后，同步更新中文文档
2. **代码示例**: 所有代码示例应可运行
3. **链接有效**: 确保所有链接指向正确位置
4. **格式统一**: 遵循 Markdown 格式规范

### 文档更新检查清单

- [ ] 中英文文档内容一致
- [ ] 所有代码示例可运行
- [ ] 所有链接有效
- [ ] 文档格式统一
- [ ] 更新 CHANGELOG.md

---

## 代码风格

### Python

- 遵循 [PEP 8](https://peps.python.org/pep-0008/) 规范
- 使用 [ruff](https://github.com/astral-sh/ruff) 进行代码格式化和 linting
- 最大行长度：88 字符
- 使用类型注解

```bash
# 格式化代码
ruff format .

# 检查代码
ruff check .
```

### TypeScript/React

- 遵循 [Airbnb JavaScript Style Guide](https://github.com/airbnb/javascript)
- 使用 ESLint 和 Prettier
- 使用函数式组件和 Hooks

```bash
cd horbot/web/frontend
npm run lint
npm run format
```

### 提交信息

我们使用 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/) 规范：

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

**类型：**
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式（不影响功能）
- `refactor`: 代码重构
- `perf`: 性能优化
- `test`: 测试相关
- `chore`: 构建/工具相关

**示例：**
```
feat(provider): add support for new LLM provider

- Add provider configuration
- Implement API client
- Add unit tests

Closes #123
```

---

## Pull Request 流程

1. **确保测试通过**：运行 `pytest` 确保所有测试通过
2. **更新文档**：如有必要，更新 README 和其他文档
3. **添加测试**：为新功能添加单元测试
4. **填写 PR 模板**：描述更改内容和原因
5. **等待审核**：维护者会尽快审核您的 PR

### PR 检查清单

- [ ] 代码遵循项目风格指南
- [ ] 已添加必要的测试
- [ ] 所有测试通过
- [ ] 文档已更新
- [ ] 提交信息遵循规范

---

## 🙏 感谢

感谢所有贡献者的付出！您的贡献让 horbot 变得更好。

<a href="https://github.com/jenpeng/horbot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=jenpeng/horbot" />
</a>
