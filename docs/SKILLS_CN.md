# 技能系统

## 概述

horbot 的技能系统允许扩展 AI 的能力。每个技能是一个包含 `SKILL.md` 文件的目录，通过 Markdown 格式定义技能的行为和指令。

当前 Skills 页面会把技能分成两类：

- `系统技能`：项目内置的 built-in skills
- `自定义技能`：当前 Agent 工作区下的手动技能和自动沉淀技能

## 技能格式

### 目录结构

```
.horbot/agents/<agent-id>/workspace/.horbot-agent/skills/
├── {skill_name}/
│   ├── SKILL.md          # 必需：技能定义文件
│   ├── agents/           # 可选：UI/Agent 元数据
│   │   └── openai.yaml
│   ├── scripts/          # 可选：脚本
│   ├── references/       # 可选：引用资料
│   └── assets/           # 可选：资源文件
```

### 技能包格式

Horbot 支持导入两种技能包：

- `.skill`
- `.zip`

`.skill` 本质上是 zip 包，只是扩展名不同。一个合法技能包应满足：

- 包内只包含一个 skill 根目录，或直接以该 skill 根目录作为压缩包根
- skill 根目录下必须存在 `SKILL.md`
- 标准顶层目录为 `agents/`、`scripts/`、`references/`、`assets/`
- 不允许包含路径穿越（如 `../`）或符号链接

### 导入校验规则

无论是通过 Web UI 导入，还是后续接 SkillHub / ClawHub，Horbot 当前都会执行统一校验：

1. 压缩包结构校验
2. `SKILL.md` frontmatter 校验
3. `name` / `description` 必填校验
4. 技能命名规范校验
5. 相对引用文件存在性校验
6. 运行环境兼容性分析

校验失败时，skill 不会被导入工作区。

## 自动沉淀与技能家族

Horbot 可以在工具驱动任务完成后，后台判断这次工作是否具有复用价值，并自动沉淀成技能。

当前自动技能优先采用“技能家族 + references 技巧库”的结构：

- `SKILL.md` 保持精简，主要负责说明触发条件和使用方式
- 具体技巧、排障手法、案例化步骤放到 `references/*.md`
- 同类 `auto-*` 技能会尽量合并到更宽的技能家族，而不是每个小变体单独保留一个目录

例如，一个 `auto-officecli-ppt` 家族下可以包含多份 `references/officecli-ppt-*.md` 技巧笔记。

当用户在聊天中明确要求 Agent “把刚才/之前的经验总结成技能”时，Agent 应使用受控的 `save_skill` 工具，而不是直接用 `write_file` 写技能目录。`save_skill` 只会写入当前 Agent 的规范技能目录，会校验生成的 `SKILL.md`，并把具体技巧放到 `references/` 下，因此不会因为 Agent 猜错路径而反馈“无权限写入技能路径”。

Skills 页面当前还提供两个手动入口：

- `整理自动技能`：把相关的自动技能手动收敛整理为技能家族
- `转为系统技能`：把当前工作区下的自定义技能转成项目内置系统技能
- `导出`：把系统技能或自定义技能下载为可再次导入的 `.skill` 包，包含 `references/` 等标准技能目录
- `图谱`：查看并重建当前 Agent 的技能图谱。MVP 阶段会记录技能节点、引用节点、`has_reference`、`similar_to`、`related_to` 等关系。

### SKILL.md 格式

```markdown
---
name: skill-name
description: 技能描述
always: false
enabled: true
requires:
  bins: ["git", "node"]
  env: ["API_KEY"]
---

# 技能名称

## 功能说明

详细描述技能的功能和使用方法...

## 使用场景

- 场景1
- 场景2

## 示例

示例代码和用法...
```

### Frontmatter 字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `name` | string | 是 | 技能名称 |
| `description` | string | 是 | 技能描述 |
| `always` | boolean | 否 | 是否始终加载（默认 false） |
| `enabled` | boolean | 否 | 是否启用（默认 true） |
| `requires.bins` | list | 否 | 依赖的二进制文件 |
| `requires.env` | list | 否 | 依赖的环境变量 |
| `metadata` | string(JSON) | 否 | Horbot / OpenClaw 兼容元数据 |

### 命名规范

技能名必须满足以下规则：

- 只允许小写字母、数字、`-`、`_`
- 长度 2 到 64 个字符
- 必须以字母或数字开头

例如：

- `github`
- `excel-xlsx`
- `my_skill`

不推荐：

- `MySkill`
- `skill hub`
- `技能A`

## 内置技能

### memory - 记忆管理

分层记忆系统，支持 L0/L1/L2 三层上下文管理。

**特性**：
- 长期记忆存储 (MEMORY.md)
- 历史日志记录 (HISTORY.md)
- 与分层上下文集成

### self-improvement - 自我改进

AI 自主改进能力，包括代码审查、能力评估、错误分析。

**特性**：
- 代码审查与优化
- 能力评估
- 错误分析
- 学习建议生成

**模板**：
- `templates/code-review.md` - 代码审查模板
- `templates/capability-assessment.md` - 能力评估模板
- `templates/learning-plan.md` - 学习计划模板

### autonomous - 自主执行

复杂任务的自主规划和执行。

**特性**：
- 任务复杂度分析
- 计划生成
- 安全执行
- 错误恢复

### github - GitHub 集成

通过 `gh` CLI 与 GitHub 交互。

### officecli - Office 文档操作

在已接入 OfficeCLI MCP 时，用于处理 Word / Excel / PowerPoint / OpenXML 文档。

**适用场景**：
- `.docx` / `.xlsx` / `.pptx`
- 需要保留 Office 原生结构、样式、公式或版式
- 需要比普通文件读写更可靠的 Office 文档编辑能力

**规则**：
- 优先用 `view` / `get` / `query` 类工具先读结构，再做写入
- 优先使用高层 Office 操作，只有必要时才退到 raw XML / XPath
- 如果 MCP 只暴露一个通用工具，例如 `mcp_officecli_officecli`，直接传 `command=create|view|set|add|validate|batch` 等参数使用即可
- 处理 `.xlsx` 样式或属性时，优先使用 OfficeCLI 的真实属性名，例如 `font.color`、`font.size`、`fill`、`alignment.horizontal`
- 处理 `.pptx` 结构性改动后要执行 `validate`；如果反复编辑后校验失败，优先改用新的输出文件重建，而不是继续在坏文件上叠改
- OfficeCLI 不可用时，不要伪造 Office 原生编辑结果

### weather - 天气查询

获取天气信息，支持 wttr.in 和 Open-Meteo。

### summarize - 内容摘要

摘要 URLs、文件和 YouTube 视频。

### tmux - 远程控制

远程控制 tmux 会话。

### clawhub - 技能市场

从 ClawHub 搜索和安装技能。

### skill-creator - 技能创建

创建新技能的辅助工具。

### cron - 定时任务

管理定时任务。

## 技能开发指南

### 创建新技能

1. 创建技能目录：
```bash
mkdir -p .horbot/agents/main/workspace/.horbot-agent/skills/my-skill
```

2. 创建 SKILL.md 文件：
```markdown
---
name: my-skill
description: 我的自定义技能
always: false
enabled: true
---

# My Skill

## 功能

这个技能做什么...

## 使用方法

如何使用这个技能...
```

3. 重启服务或使用 API 刷新技能列表。

### 从技能包导入

现在可以直接在 Skills 页面点击 `Import Skill`，导入 `.skill` 或 `.zip` 文件。

导入成功后，页面会立即展示兼容性状态：

- `compatible`: 当前环境可直接使用
- `Needs Setup`: skill 可导入，但存在 setup 警告
- `Incompatible`: 当前环境缺少依赖，或操作系统不匹配

兼容性检查目前主要覆盖：

- 操作系统 (`metadata.horbot.os`)
- CLI 依赖 (`requires.bins`)
- 环境变量依赖 (`requires.env`)
- 旧版 metadata 是否被兼容层转换

### SkillHub / ClawHub 兼容性说明

SkillHub / ClawHub 解决的是“发现和下载 skill”，但不能天然保证 skill 与当前 Horbot 实例完全兼容。

当前 Horbot 的策略是：

1. 允许导入
2. 静态分析兼容性
3. 在 Skills 页面显式展示问题

因此从 SkillHub / ClawHub 获取 skill 后，建议立即检查：

- 是否被标记为 `Incompatible`
- 是否缺少本机 CLI 依赖
- 是否需要补充环境变量
- 是否仍在使用 legacy metadata

如果后续要做更强的“下载前兼容性判定”，需要 skill registry 提供更完整的 manifest，例如 provider、model capability、项目类型和工具组约束。

## 存储路径

当前 Agent 运行时技能目录位于：

- `.horbot/agents/<agent-id>/workspace/.horbot-agent/skills`
- `.horbot/agents/<agent-id>/workspace/.horbot-agent/skill_graph.json`

其中：

- 手动创建或导入的自定义技能写入当前 Agent 的上述目录
- 自动沉淀技能也写入同一目录，只是通常以 `auto-*` 形式命名
- 旧的 `.horbot/agents/<agent-id>/skills` 和 `workspace/skills` 只作为兼容迁移来源，不应再作为新的运行时写入位置
- 当前技能图谱会作为 Agent 运行时技能摘要里的轻量召回提示使用，只提示相关技能和 `references/` 文件位置，不直接把引用内容塞进上下文；Agent 会按当前任务再读取需要的本地文件。
- `GET /api/skills/graph` 会检查持久化图谱里的文件指纹；如果技能或引用文件已经变化，会先自动重建并重新持久化，避免页面刷新后继续展示旧图谱。
- Horbot 会在受管技能发生变更后自动刷新持久化图谱，包括新建、编辑、导入、删除、启停、整理自动技能、转为系统技能，以及 Agent 通过 `save_skill` 或自动沉淀写入技能。图谱刷新失败只记录 warning，不回滚技能操作。

### 技能最佳实践

1. **清晰的描述** - 让 AI 理解何时使用这个技能
2. **具体的指令** - 提供明确的操作步骤
3. **示例代码** - 展示如何使用技能
4. **依赖声明** - 明确需要的工具和环境变量

## 与分层上下文的集成

技能系统与分层上下文管理系统深度集成：

### 记忆存储

技能执行结果可以存储到分层记忆：

```python
# 存储到 L1 (近期记忆)
manager.add_memory(
    content="技能执行结果...",
    level="L1",
    metadata={"skill": "self-improvement", "type": "code-review"}
)
```

### 上下文检索

技能可以从分层上下文检索相关信息：

```python
# 搜索过去的改进记录
results = manager.search_context(
    query="code review authentication",
    levels=["L1", "L2"],
    max_results=10
)
```

## API 管理

### 列出技能

```http
GET /api/skills
```

### 获取技能详情

```http
GET /api/skills/{skill_name}
```

### 创建技能

```http
POST /api/skills
Content-Type: application/json

{
  "name": "my-skill",
  "content": "---\nname: my-skill\n..."
}
```

### 更新技能

```http
PUT /api/skills/{skill_name}
Content-Type: application/json

{
  "content": "---\nname: my-skill\n..."
}
```

### 删除技能

```http
DELETE /api/skills/{skill_name}
```

### 切换技能状态

```http
PATCH /api/skills/{skill_name}/toggle
```

### 导入技能包

```http
POST /api/skills/import
Content-Type: multipart/form-data
```

表单字段：

- `file`: `.skill` 或 `.zip`
- `replace_existing`: 可选，是否覆盖同名 skill

### 导出技能包

```http
GET /api/skills/{skill_name}/export
```

返回标准 `.skill` 包。目录型技能会包含完整的 `SKILL.md`、`references/`、`scripts/`、`assets/`、`agents/` 等文件；旧的单文件技能会被整理成标准技能包结构后导出。
