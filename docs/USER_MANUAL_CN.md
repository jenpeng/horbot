# 用户手册

本文档面向日常使用者，重点说明升级后的启动方式、安全访问方式和常见操作。

## 1. 启动项目

推荐使用项目脚本：

```bash
./horbot.sh start
```

默认访问地址：

- Web UI: [http://127.0.0.1:3000](http://127.0.0.1:3000)
- Backend API: [http://127.0.0.1:8000](http://127.0.0.1:8000)

常用命令：

```bash
./horbot.sh status
./horbot.sh logs backend
./horbot.sh restart
./horbot.sh stop
```

如果要做真实浏览器回归测试，可直接运行：

```bash
./horbot.sh smoke browser-e2e
```

它会顺序验证：

- Configuration 页面加载、重新加载与保存回归
- 多 Agent 页面中的 `SOUL.md`、`USER.md` 与“配置摘要”保存/刷新回归
- Dashboard、Skills 与关键页面性能采样
- 聊天失败态与重试
- 团队接力停止/打断
- 单聊消息发送与返回
- `@agent` 团队接力

如需单独执行某一项：

```bash
./horbot.sh smoke config
./horbot.sh smoke agent-assets
./horbot.sh smoke dm-chat
./horbot.sh smoke dm-team-dispatch
./horbot.sh smoke team-chat
./horbot.sh smoke chat-interrupt
./horbot.sh smoke chat-error-retry
./horbot.sh smoke external-inbound-memory
./horbot.sh smoke bound-channel-dispatch
```

聊天与附件相关回归目前覆盖：

- Assistant Markdown 渲染依赖链
- 历史聊天加载与引用详情
- 附件上传、失败重试、顺序调整
- 图片 / 音频识别
- PDF / Word / Excel / PowerPoint 阅读
- 粘贴上传与拖拽上传
- 多 agent 接力顺序与交棒可视化回归

## 1.1 聊天输入与附件使用方式

## 1.0 界面语言切换

当前 Web UI 支持三种界面语言：

- English
- 简体中文
- ไทย

语言切换入口位于主导航区域和移动端抽屉中。所选语言会持久化保存在浏览器本地存储中，因此同一浏览器下刷新页面或重启服务后仍会保持当前语言。

当前已覆盖的核心页面包括：

- Dashboard / 控制台
- Chat / 对话
- Teams / 团队管理
- Channels / 渠道
- Configuration / 配置
- Status / 状态
- Tokens / Token 使用统计

聊天输入框支持以下交互：

- 直接发送文本消息
- 上传图片、音频、PDF、DOCX、XLSX、PPTX、TXT、Markdown
- `Cmd/Ctrl + V` 直接粘贴图片或文件
- 将文件拖进输入框区域上传
- 浏览器支持时可直接语音输入

当前限制：

- 单个附件最大 `50 MB`
- 单次对话最多保留 `10` 个附件

上传完成后，附件会先停留在输入框上方的待发送区，你可以：

- 调整附件顺序
- 删除单个附件
- 对失败附件直接重试
- 仅发送附件，系统会自动补一条默认分析请求

历史消息中的附件现在默认走内联预览：

- 图片会直接弹出图片预览
- 音频会提供播放器
- PDF 会在弹窗中直接打开
- Word / Excel / PowerPoint / 文本会展示可读预览或原文件入口
- 对于 assistant 正文里独立出现的远程图片链接，后端会尽量自动提升成统一图片卡片，而不是只显示裸链接

聊天区当前还有两项默认交互：

- Assistant 消息泡和 Markdown 排版更紧凑，长回复不会再留出过多空白
- 团队接力等待态会直接显示交棒来源、目标以及“继续讨论 / 返回总结”的状态

## Skills 页面当前可做什么

Skills 页面现在不只是查看和导入技能，还支持以下操作：

- 区分 `系统技能` 与 `自定义技能`
- 查看某个自定义技能是 `手动添加` 还是 `Agent 自动沉淀`
- 创建、编辑、启用/禁用、删除自定义技能
- 导入 `.skill` / `.zip` 并立即查看兼容性结果
- 手动点击 `整理自动技能`，把相关的 `auto-*` 技能收敛成更宽的技能家族
- 手动点击 `转为系统技能`，把当前工作区中的自定义技能转成项目内置系统技能

当前自动沉淀技能优先采用“技能家族 + references 技巧库”的结构：

- `SKILL.md` 负责写清楚这个技能家族的触发条件、适用场景和如何查阅资料
- 具体技巧、排障步骤、案例化方法放到 `references/*.md`

当前 Agent 的运行时技能目录位于：

```bash
.horbot/agents/<agent-id>/workspace/.horbot-agent/skills
```

补充说明：

- 手动创建/导入的自定义技能写入当前 Agent 的上述目录
- 自动沉淀技能也写入同一目录，只是通常以 `auto-*` 开头命名
- 旧的 `.horbot/agents/<agent-id>/skills` 与 `workspace/skills` 只作为兼容迁移来源，不应再作为新的写入位置

## 1.1.1 团队接力当前的运行方式

当前团队接力仍然是“有序串行”而不是并行乱序：

- 一次只会有一个 Agent 处于当前处理态
- 每一棒都会在聊天区保留独立消息组
- 如果某个 Agent 被点名但还没开始输出，会先显示等待接棒卡片
- 回到发起 Agent 做最终总结时，界面会明确标识这是“返回总结”而不是继续向下转派

为了让体感更像真实接力，Agent-to-Agent 回合现在默认被约束为更短回复，优先一小段或最多 3 条要点。

上传文件默认保存在：

```bash
.horbot/data/uploads
```

补充说明：

- 如果远程图片链接能成功缓存，历史回刷后会继续显示本地图片卡片，并保留文件名、大小与统一预览弹窗
- 如果远程图片暂时无法缓存，前端也会回退为远程图片附件卡片，而不是只剩下正文里的 URL

## 1.1.2 Configuration 页中的联网搜索与远程图片缓存

Configuration 页面当前除基础 Provider / 模型配置外，还支持：

- 全局开启或关闭联网搜索
- 切换联网搜索 Provider
- 单独开启或关闭已支持的 API Provider，例如 Tavily / LangSearch
- 按 Provider 分开保存各自的 API Key，避免切换供应商时沿用上一家的密钥状态
- 调整默认最大搜索结果数
- 查看“远程图片缓存”的文件数、累计大小与最近更新时间
- 手动清理远程图片缓存

其中：

- 当联网搜索总开关被关闭后，即使 Provider 和 API Key 已配置，运行时也不会调用 web search 工具
- 当当前 Provider 对应的 API 开关被关闭后，即使 Provider 仍停留在该项，运行时也会回退到默认静默 HTTP 搜索
- “远程图片缓存”只清理自动从远程图片链接落盘的缓存文件，不会删除普通上传附件

## 1.2 多 Agent 页面如何配置 Agent 档案

推荐在“团队管理 / 多 Agent 管理”里完成每个 Agent 的实例级配置。

每个 Agent 都有独立工作区，内部通常包含：

- `AGENTS.md`：运行治理、协作规则、执行边界与约束优先级
- `SOUL.md`：该 Agent 的身份、职责重点、沟通风格、边界约束
- `USER.md`：用户偏好、协作约定、特殊说明

页面里有两种调整方式：

1. 直接编辑 `AGENTS.md` / `SOUL.md` / `USER.md`
2. 编辑“配置摘要”

“配置摘要”适合日常快速调整。它按以下分类组织：

- 身份定位
- 职责重点
- 沟通风格
- 边界约束
- 用户偏好

每行填写一条，点击“保存摘要”后，会自动写回 `SOUL.md` / `USER.md` 对应章节。

其中：

- `AGENTS.md` 适合放运行规则、工具使用边界、协作约束、接力规范
- “配置摘要”更适合放日常会调整的人设、职责、风格和用户偏好

当前管理页还会对 bootstrap 内容做更严格的安全收口：

- 不建议把 token、密码、Bearer 凭证直接写进这些文件
- 明显的提示词覆盖、密钥泄露、命令载荷内容会在运行时守卫中被识别

如果某个 Agent 还处于首次引导阶段：

- 可以先进入私聊，让 AI 通过对话引导你补全信息
- 也可以直接在多 Agent 页面手动补全
- 一旦正式内容写入并移除待配置标记，该 Agent 就不会再强制进入首次引导

## 2. 首次配置

编辑 `.horbot/config.json`，至少配置一个模型提供商：

```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
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

如果你需要为复杂任务单独指定内部规划模型，也可以继续配置：

```json
{
  "agents": {
    "defaults": {
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
  }
}
```

这里的 `planning` 表示内部规划场景模型，不对应 Web Chat 中的 `/plan` 命令。当前前端已经移除该命令入口，复杂任务会自动触发规划检测。

## 2.1 创建 Agent 时的模型配置

当前“团队管理 / 多 Agent 管理”里的“创建 Agent”弹窗已经支持直接填写：

- provider
- model
- 权限档位
- 协作画像

因此不再需要先创建、再进入编辑页补模型。`provider` 与 `model` 需要在创建时直接填写完成。

## 2.2 Skills 导入与兼容性

Skills 页面当前支持导入 `.skill` 与 `.zip`。

导入前系统会统一执行：

- 压缩包结构校验
- `SKILL.md` 存在性校验
- frontmatter 与 `name` / `description` 校验
- 相对引用文件校验
- 当前环境兼容性与缺依赖分析

导入完成后，页面会直接展示兼容性结果与缺失依赖提示，而不是等到运行失败后才暴露问题。

## 2.3 外部 Agent 接入

“团队管理 / 多 Agent 管理”现在支持接入外部 Agent。

如果你的目标只是给 WorkBuddy 或其他平台一个 Horbot 机器人入口，让它把消息推送给某个内部 Agent，应该优先去 `Channels / 渠道` 页面创建 `Horbot 入站机器人` 通道实例，而不是在 External Agent 里填写外部 endpoint。

Channels 入站机器人的典型流程：

1. 进入 `Channels / 渠道`
2. 新建通道实例，类型选择 `Horbot 入站机器人`
3. 可选择固定绑定目标内部 Agent；如果不绑定，外部请求需要传 `target_agent_id` 或 `agent_id`
4. 执行草稿测试，保存后复制 Horbot 生成的 App ID、Token 和 Inbound URL
5. 将这些值配置到 WorkBuddy 或其他厂商/本地 Agent 平台

边界很明确：Channels 管外部消息入口和路由，External Agent 管外部成员身份和团队/单聊编排。

不固定绑定时，Horbot 不会信任外部任意字符串直接执行，而是只允许路由到当前运行实例 `.horbot/config.json` 中实际存在的 Agent。这样不同用户独立运行本项目、各自创建自己的 Agent 时，同一个接入模式仍然能按各自实例里的 Agent ID 工作。

典型流程：

1. 进入 `Connect External Agent`
2. 优先选择 `inbound-bot`，复制 Horbot 生成的 App ID、Token 和 Inbound URL 到 WorkBuddy 或其他厂商/本地 Agent 平台
3. 选择 capability tags
4. 决定是否允许单聊、团队接力、是否必须显式 `@`
5. 点击“测试连接”做轻量探测

当前表单里最重要的两个连接字段是：

- `Adapter`：决定接入模式；推荐 `inbound-bot`，由 Horbot 提供机器人凭证和入站 URL，外部平台负责推送消息进来
- `Endpoint`：只对需要 URL 的适配器强制填写，例如兼容旧模式的 `generic-agent-api` 和 `openai-compatible`
- `Transport`：仅在通用适配器下显示，表示 HTTP、SSE 或 WebSocket 底层连接方式

`generic-agent-api` 仅用于兼容旧设计，也就是 Horbot 主动调用外部 HTTP / SSE / WebSocket URL；新接 WorkBuddy 或类似平台时不应优先使用这个模式。

`openai-compatible` 适配器适合接入 Chat Completions 风格的服务，通常需要在 `adapter_config` 中提供 `model`，并可选提供 `chat_completions_endpoint`。

能力标签不再建议纯手填。当前界面支持：

- 快捷预设
- 智能推荐
- 常用标签点选
- 折叠式手动补充自定义标签

如果某个外部 Agent 允许加入团队，那么团队详情和成员接口会显式把它标记为 external member。

## 2.4 工具审计怎么看

Agent Detail 的 Activity 面板现在有独立的“工具审计”区域。

你可以直接看：

- 最近 24h 风险摘要
- 被拦截次数
- `exec` 次数
- 外联次数
- 错误次数
- 指定 `session_key` 下的工具记录

如果审计记录很多，优先先按风险类型或 `session_key` 过滤，再展开单条明细。

## 2.5 WeCom 与 Mochat 的区别

如果你在企业微信生态内接入 Horbot，需要区分两条链路：

- `WeCom`：企业微信官方 AI Bot WebSocket 网关，支持 reply-mode 流式回复、媒体上传、入站媒体下载与解密
- `Mochat`：Mochat / Claw 生态接入方式，更偏向托管账号场景

二者不能共用同一套 token / 配置字段，也不应按同一种协议理解。

## 3. Web UI 中密钥为什么看不到原文

这是新版本的安全改动。

现在页面只显示：

- 是否已配置
- 掩码预览

不会再把已保存的明文 API Key、token、secret 回传给浏览器。

如果你想更新 Provider：

1. 打开对应 Provider
2. 在 `API Key` 中输入新的值
3. 留空表示保持现有值不变
4. 点击保存

如果你想更新 MCP 的环境变量：

1. 打开 MCP 编辑器
2. 重新填写完整 JSON
3. 保存后覆盖旧值

## 4. 远程访问

默认只建议本机访问。

如果你确实需要远程访问，请先在 `.horbot/config.json` 中配置：

```json
{
  "gateway": {
    "adminToken": "replace-with-a-long-random-token",
    "allowRemoteWithoutToken": false
  }
}
```

然后远程请求必须携带：

```http
Authorization: Bearer replace-with-a-long-random-token
```

或：

```http
X-Horbot-Admin-Token: replace-with-a-long-random-token
```

如果你用浏览器直接打开远程 UI，可在控制台设置：

```js
localStorage.setItem('horbotAdminToken', 'replace-with-a-long-random-token')
```

刷新后生效。

## 5. 常见问题

### 5.0 为什么历史聊天会突然少一段

当前版本已经补了兼容读取逻辑。

如果某个 Agent 历史曾同时写入旧路径和新路径，页面现在会自动合并读取：

- 旧路径：`workspace/sessions`
- 新路径：`.horbot/agents/<agent-id>/workspace/.horbot-agent/sessions`

如果你刷新后仍发现历史缺失，建议先执行：

```bash
./horbot.sh restart backend
```

### 5.1 页面打开了，但提示 401 或 403

原因通常是：

- 你在远程访问
- 后端已启用安全校验
- 浏览器没有带管理员令牌

处理方式：

- 本机访问请使用 `127.0.0.1`
- 远程访问请设置 `localStorage.horbotAdminToken`

### 5.2 为什么 AI 不能随便读写整个磁盘了

因为默认开启了工作区限制。

这是故意的安全收紧。AI 工具默认只应在工作区内操作。如果确实需要更宽权限，应明确修改配置并知晓风险。

### 5.3 为什么编辑 MCP 时环境变量看起来像被隐藏了

因为敏感值不会再回显。若要修改，请重新填写完整 JSON。

### 5.4 为什么现在聊天回复看起来像富文本

因为 Assistant 消息已经默认按 Markdown 渲染。

这意味着以下内容会自动格式化：

- 标题
- 列表
- 表格
- 引用
- 代码块与语法高亮

### 5.5 为什么顶部黄条里会显示一个 request_id

这是为了排查聊天失败、provider 超时和前端假超时。

当前失败诊断信息会出现在两个位置：

- 输入框上方的顶部状态条
- 对应 turn 头部的 badge

这样即使你不展开具体错误消息，也能直接拿 `request_id` 去查后端日志、网关日志或会话历史。

### 5.6 为什么明明工具还有输出，前端却提示“模型服务响应超时”

当前版本已经对一类前端假超时做了修复。

之前可能出现这种情况：

- 前端等待超时
- 后端稍后继续完成请求
- 成功结果已经写入历史
- 但前端仍先弹出 timeout 提示

现在修复分成两层：

- 前端会在超时后按 `request_id` 回查历史消息；如果发现该请求其实已经成功落盘，就会自动收敛这条错误提示
- 后端会对超长 Web 单聊上下文自动压缩；如果模型因为回复过长被截断，还会自动续答并继续往同一条回复里输出

补充说明：

- 当前聊天页的前端流式等待窗口是 `240s`
- 这不等于 provider 超时；它只表示前端在多长时间内没有收到新的流事件就判定本次流中断
- 如果你怀疑某次仍是误报，优先看顶部或 turn 头部的 `request_id`，然后对照后端日志和会话历史确认

## 6. 推荐做法

- 日常开发只用 `127.0.0.1`
- 不要把 `.horbot/config.json` 提交到公开仓库
- 不要把 `.horbot/runtime/logs/` 暴露给其他人
- 若曾经把密钥暴露到旧日志中，建议轮换相关密钥

## 7. 相关文档

- [安全指南](./SECURITY_CN.md)
- [API 文档](./API_CN.md)
- [架构说明](./ARCHITECTURE_CN.md)
- [多 Agent 操作手册](./MULTI_AGENT_GUIDE_CN.md)

## 8. 依赖是否需要额外更新

这轮聊天 Markdown、附件预览、粘贴拖拽上传能力没有新增第三方依赖。

因此当前不需要额外修改：

- `package.json`
- `pyproject.toml`
- `docker-compose.yml` 或其他部署 `yml`

如果后续要补更强的 Office 渲染或音频转码，再单独评估是否新增依赖。
