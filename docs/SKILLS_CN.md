# 技能系统

## 概述

horbot 的技能系统允许扩展 AI 的能力。每个技能是一个包含 `SKILL.md` 文件的目录，通过 Markdown 格式定义技能的行为和指令。

## 技能格式

### 目录结构

```
skills/
├── {skill_name}/
│   ├── SKILL.md          # 必需：技能定义文件
│   └── templates/        # 可选：模板文件
│       └── template.md
```

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
