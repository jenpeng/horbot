# 变更记录

本记录用于概览 Horbot 的关键功能和文档演进。更细粒度的代码改动请直接查看 Git 历史。

## 2026-04-28

### Live Artifact 交互渲染

- 新增聊天气泡内的 Live Artifact 卡片，支持看板、图表故事、数据工作台、地图故事、流程视图和交互报告等结构化 Agent 输出
- 新增 `POST /api/artifacts/render`，临时运行文件统一写入 `.horbot/runtime/rendered-artifacts`
- 新增内置 `live-artifact-studio` 技能，指导 Agent 判断何时使用 Markdown，何时输出结构化可渲染数据
- 为 `auto-officecli-ppt` 技能家族补充 Live Artifact 到 PPT 预览/生成的参考技巧

### PPTX 高保真预览

- PPTX 预览从浏览器侧重建版式改为 LibreOffice 优先链路：PPTX -> PDF -> 按页懒加载 PNG
- 新增 `GET /api/files/{file_id}/preview-capabilities`、`GET /api/files/{file_id}/preview/slides/{page}`、`POST /api/files/{file_id}/preview/cleanup`
- `horbot.sh` 新增 `install libreoffice` 与 `check libreoffice`
- 新增 PyMuPDF 作为页面栅格化依赖，并补充 LibreOffice 导出缓存与清理相关测试

## 2026-04-27

### External Agent Adapter 架构

- External Agent 运行时已改为 adapter registry 分发，不再把旧 `endpoint + transport` 逻辑固化在单一 runtime 中
- 新增 `inbound-bot` 作为主接入模式：Horbot 生成 App ID、Token 和 Inbound URL，WorkBuddy 或其他厂商/本地平台像飞书/Discord 机器人一样把消息推送进 Horbot
- Channels 新增 `horbot-inbound-bot` 通道实例，由 Horbot 生成通道级 App ID、Token 和 Inbound URL，并将入站消息路由给固定绑定或请求指定的内部 Agent
- 新增 `generic-agent-api` 默认适配器，用于兼容原 HTTP / HTTP SSE / WebSocket 行为
- 新增 `openai-compatible` 适配器，用于接入 Chat Completions 风格的厂商或本地服务
- 外部 Agent 配置新增开放式 `adapter` slug 与 `adapter_config`，合法但尚未实现的未来厂商适配器可以先保存配置，运行时会给出明确 unsupported adapter 诊断
- Teams 页面外部 Agent 表单和详情页已展示 adapter 字段，并同步中英泰多语言文案

## 2026-04-15

### 浏览器联网回归 Playwright 默认模式

- Agent 默认联网路径已改回 `browser` / `web_search` / `web_fetch`
- `browser` MCP 默认直接使用 Playwright，不再优先依赖内置 `web-access` 代理
- `horbot.sh start|restart|status|logs` 不再把 `web-access` 作为常规托管服务的一部分
- 主 agent、subagent、提示词和工具筛选规则已同步去除默认 `web_access` 优先路径
- Web Chat 现在会把 Agent 通过 `message(..., media=...)` 发送的图片等媒体正确落盘并即时展示，而不再在 SSE / 前端层丢失

### 聊天图片卡片与远程图片缓存

- 聊天历史与会话消息接口现在会把 assistant 正文中的独立远程图片链接自动提升为 `files` 附件结构，前端恢复使用统一图片卡片，而不是退回裸链接或 Markdown 内联图
- Pollinations 等远程图片链接会尽量落盘到 `.horbot/data/uploads`，并生成本地 `preview_url`、文件名与文件大小，便于历史消息继续走图片卡片与预览弹窗
- Configuration 页面新增“远程图片缓存”状态区块，展示缓存文件数、累计大小与最近更新时间
- 新增远程图片缓存手动清理能力，可直接在配置页触发，也可通过 `GET/DELETE /api/files/cache/remote-images` 查询与清空缓存
- 聊天页在历史回刷和超时后补偿逻辑中，已支持“只有 files 没有正文”的 assistant 消息，不会再把成功图片消息误判为空响应

### 文档同步

- README、文档索引、MCP 文档和架构文档已同步更新为当前的 Playwright 默认运行模式

## 2026-04-14

### 多 Agent 管理与外部 Agent

- 新增 `external_agents` 配置与运行时模块，支持外部 Agent 的列表、详情、创建、更新、删除与连接探测
- “Connect External Agent” 界面补齐更友好的能力标签交互，支持快捷预设、智能推荐、常用标签点选与折叠式手动补充，而不再只依赖手填
- 团队成员接口 `GET /api/teams/{team_id}/members` 的返回体显式区分 `internal_members` / `external_members`，并补充 `member_order` 与分类统计，便于前端稳定渲染 mixed team
- Teams 页面同步支持外部 Agent 目录、团队成员展示、团队选择与相关表单/校验回归

### Agent Bootstrap、安全与审计

- Agent 实例级 bootstrap 文件扩展为 `AGENTS.md`、`SOUL.md`、`USER.md` 三类可编辑资产，Web 管理端支持直接读取、保存与摘要回写
- 新增 `horbot/security/runtime_guard.py`，集中提供用户输入 intent guard、tool result 检查/脱敏、bootstrap 内容检查等运行时安全守卫
- 工具执行审计接口 `GET /api/memory/tool-audits` 支持按 `agent_id`、`session_key`、风险类型和时间窗口查询，并返回最近窗口的聚合摘要
- Agent Activity 面板新增工具审计视图，支持按风险和会话过滤，并在顶部展示最近 24h 的拦截 / exec / 外联 / 错误摘要

### 聊天诊断与失败恢复

- 聊天错误消息卡片新增 provider 诊断字段展示，包括 `request_id`、`error_code`、`error_kind`、provider、model 与 status code
- 前端流式 inactivity timeout 已提高到 `240s`，并在超时后按 `request_id` 回查历史消息，避免后端已成功落盘但前端误报“模型服务响应超时”
- 会话顶部黄条与 turn 级 badge 现在都会直接展示失败请求的 `request_id`，无需展开具体错误消息再查诊断线索
- Web 单聊上下文压缩改为预算驱动：先压缩旧话题，再在必要时继续裁剪最近的大段 assistant/tool 内容，避免超长 recent context 把首轮响应拖到假超时
- 当模型返回 `finish_reason=length` 时，AgentLoop 会自动续答并把后续片段拼接到同一条流式回复和最终落盘消息中，而不是把半截回答直接暴露给前端

## 2026-04-13

### 多语言与文档

- 当前核心 Web 管理页面新增并整理为支持英文、简体中文、泰语三种界面语言切换，且浏览器会持久化保存所选语言
- 将多语言能力同步更新到 README、文档索引、用户手册与贡献指南
- 英文版 README / 文档首页截图改为从本地真实运行中的 Horbot Web UI 重新抓取，不再复用旧图

### 聊天与团队接力

- 单聊中的 Agent 使用 `message` 工具把任务派发到团队接力时，Web Chat 会自动切到目标团队会话
- 团队接力完成后，如果最终结果会镜像回原单聊，界面会自动切回发起该接力的单聊
- 顶部新增短暂的接力导航提示，明确说明当前是“切去团队接力”还是“返回单聊查看汇报”，并提供反向跳转入口
- 将更短回合的 baton 提示词同时下沉到团队首棒 kickoff 和后续 relay handoff，减少第一棒长时间闷头输出的体感
- 团队接力在正文已经开始流式输出时，仍会保留一条紧凑的接棒状态条，避免用户误以为只有最终结果才出现
- 团队接力收到最终 `done` 事件后，会对当前 turn 做更强的本地收口与历史回刷，尽量清掉残留的等待态/流式态而无需手动刷新

## 2026-04-12

### 聊天与团队接力

- 收紧聊天界面中的 Assistant 消息泡与 Markdown 排版，减少长回复中的空白占位
- 团队接力在聊天区新增更明确的交棒状态，能直接看见“谁交给谁”以及是继续讨论还是返回总结
- 新增本地多 agent 接力 SSE 回归，覆盖更长的有序交棒链路

### 渠道能力

- 新增 `WeCom` 渠道，接入企业微信官方 AI Bot WebSocket 网关
- 支持 reply-mode 流式回复、渐进式编辑和最终完成收口
- 支持 WeCom 入站媒体下载/解密，以及出站媒体上传/发送

### 文档同步

- 移除仓库首页 README 末尾不符合现状的 `## Notes`
- 将 WeCom、技能包导入校验、Agent 创建必填 `provider/model` 等现状同步到 README、文档索引、API、用户手册和架构文档
- 将聊天会话 API 示例更新为当前 UUID 风格会话键，并补充渠道端点目录说明

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
