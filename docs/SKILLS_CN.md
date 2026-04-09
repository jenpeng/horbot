# 技能系统

## 概述

horbot 的技能系统允许扩展 AI 的能力。每个技能是一个包含 `SKILL.md` 文件的目录，通过 Markdown 格式定义技能的行为和指令。

## 技能格式

### 目录结构

```
skills/
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
mkdir -p skills/my-skill
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
