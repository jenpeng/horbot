# 变更记录

本记录用于概览 Horbot 的关键功能和文档演进。更细粒度的代码改动请直接查看 Git 历史。

## 2026-04-10

### 文档与项目定位

- 将 GitHub 首页 README 重写为英文优先，并补齐中英文跳转
- 在项目说明中明确标注 `HKUDS/nanobot`、`NousResearch/hermes-agent`、`volcengine/OpenViking` 与 `OpenClaw` 的借鉴来源
- 补齐架构、API、用户手册、技能、安全、贡献、多 Agent 指南等英文版文档
- 清理文档中关于旧 `.horbot/context`、`.horbot/memory` 和 `/plan` 命令模型的过时描述

### Web UI 与产品流程

- 创建 Agent 时改为必须直接填写 `provider` 和 `model`，不再要求创建后再编辑一次
- 持续拆分和整理 dashboard、status、teams 页面中的共享逻辑与 hook
- 调整 Token 使用统计布局，并移除预估成本展示
- 将错误态重试从整页刷新改为 hook 内部刷新，减少界面抖动

### 技能与记忆

- 新增 `.skill` 与 `.zip` 技能包导入校验
- 在 Skills 页面直接展示兼容性与缺失依赖修复提示
- 将 memory、自我改进和后台技能沉淀闭环对齐到当前 agent-scoped memory 结构
- 修复子 Agent 被取消后又被错误标记为 completed 的状态覆盖问题

### 运行目录

- 当前运行时目录统一为 `.horbot/agents/<agent-id>/...`
- 将本地旧 `.horbot/context` 和 `.horbot/memory` 从默认使用路径中移除

## 2026-04-09

### Skills

- 落地技能包导入与结构校验
- 明确展示下载技能与当前 Horbot 环境的兼容性和缺依赖状态

### 前端稳定性

- 改善前端 stale chunk reload 后的恢复行为
- 继续拆分 dashboard 与 teams 大页面，减轻单文件复杂度

## 2026-02-24

### 发布 `v0.1.4.post2`

- 可靠性版本，重点调整心跳、提示缓存以及 Provider / Channel 稳定性

## 2026-02-21

### 发布 `v0.1.4.post1`

- 新增更多提供商、多渠道媒体支持和稳定性改进

## 2026-02-17

### 发布 `v0.1.4`

- 新增 MCP、进度流式传输、新提供商与多渠道能力增强
