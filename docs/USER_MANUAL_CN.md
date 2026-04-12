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

## 1.1 聊天输入与附件使用方式

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

上传文件默认保存在：

```bash
.horbot/data/uploads
```

## 1.2 多 Agent 页面如何配置 Agent 档案

推荐在“团队管理 / 多 Agent 管理”里完成每个 Agent 的实例级配置。

每个 Agent 都有独立工作区，内部通常包含：

- `SOUL.md`：该 Agent 的身份、职责重点、沟通风格、边界约束
- `USER.md`：用户偏好、协作约定、特殊说明

页面里有两种调整方式：

1. 直接编辑 `SOUL.md` / `USER.md`
2. 编辑“配置摘要”

“配置摘要”适合日常快速调整。它按以下分类组织：

- 身份定位
- 职责重点
- 沟通风格
- 边界约束
- 用户偏好

每行填写一条，点击“保存摘要”后，会自动写回 `SOUL.md` / `USER.md` 对应章节。

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

## 2.3 WeCom 与 Mochat 的区别

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
- 新路径：`.horbot/agents/<agent-id>/sessions`

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
