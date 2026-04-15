# 浏览器自动化 MCP Server

让 AI 可以通过 MCP 工具控制浏览器，实现可视化自动化操作。

当前实现默认优先接入项目内置的 `web-access` CDP 代理能力；代理不可用、选择器语法不兼容或动作未实现时，再自动回退到内置 Playwright 浏览器。

本项目核心代码借鉴自 [HKUDS/nanobot](https://github.com/HKUDS/nanobot) 仓库内容，并在此基础上扩展了浏览器 MCP 能力。

## 📦 安装依赖

```bash
# 项目会在 ./horbot.sh start|restart 时自动启动内置 web-access 服务
# 服务默认监听 127.0.0.1:3456，并会自动尝试拉起支持 remote debugging 的 Chrome

# 安装 Playwright
pip install playwright

# 安装浏览器驱动
playwright install chromium
```

## ⚙️ 配置

默认情况下，无需再单独 clone 或手工启动外部 `web-access` 仓库。

编辑 `config.json`，添加 MCP Server 配置：

```json
{
  "tools": {
    "mcp_servers": {
      "browser": {
        "command": "python",
        "args": ["-m", "horbot.mcp.browser.server"],
        "env": {
          "WEB_ACCESS_PREFER_PROXY": "1",
          "WEB_ACCESS_PROXY_URL": "http://127.0.0.1:3456",
          "WEB_ACCESS_PROXY_TIMEOUT": "30"
        },
        "tool_timeout": 120
      }
    }
  }
}
```

## 🛠️ 可用工具

启动后，AI 可以使用以下工具：

### 页面导航

| 工具 | 说明 | 参数 |
|------|------|------|
| `browser_navigate` | 打开指定 URL | `url`: 网址 |
| `browser_get_url` | 获取当前 URL | - |
| `browser_get_title` | 获取页面标题 | - |
| `browser_goto_back` | 后退 | - |
| `browser_goto_forward` | 前进 | - |
| `browser_reload` | 刷新页面 | - |

### 元素操作

| 工具 | 说明 | 参数 |
|------|------|------|
| `browser_click` | 点击元素 | `selector`: CSS选择器 |
| `browser_type` | 输入文本 | `selector`, `text`, `delay`(可选) |
| `browser_hover` | 鼠标悬停 | `selector` |
| `browser_press_key` | 按键 | `key`: 按键名 |
| `browser_find_elements` | 查找元素 | `selector` |

### 页面交互

| 工具 | 说明 | 参数 |
|------|------|------|
| `browser_scroll` | 滚动页面 | `direction`: up/down, `distance` |
| `browser_wait_for` | 等待元素 | `selector`, `timeout` |
| `browser_evaluate` | 执行 JavaScript | `script` |

### 信息获取

| 工具 | 说明 | 参数 |
|------|------|------|
| `browser_get_text` | 获取文本 | `selector`(可选) |
| `browser_get_html` | 获取 HTML | `selector`(可选) |
| `browser_screenshot` | 截图 | `path`(可选) |

### 其他

| 工具 | 说明 | 参数 |
|------|------|------|
| `browser_new_tab` | 打开新标签 | `url`(可选) |
| `browser_close` | 关闭浏览器 | - |

## 📝 使用示例

### 示例 1: 访问财经网站并查看新闻

```
用户: 帮我打开新浪财经，看看有什么新闻

AI 会调用:
1. browser_navigate(url="https://finance.sina.com.cn")
2. browser_screenshot()
3. browser_get_text(selector=".news-list")
```

### 示例 2: 搜索信息

```
用户: 帮我在百度搜索"人工智能最新进展"

AI 会调用:
1. browser_navigate(url="https://www.baidu.com")
2. browser_type(selector="#kw", text="人工智能最新进展")
3. browser_click(selector="#su")
4. browser_screenshot()
```

### 示例 3: 自动填表

```
用户: 帮我填写这个表单，姓名填"张三"，邮箱填"test@example.com"

AI 会调用:
1. browser_type(selector="#name", text="张三")
2. browser_type(selector="#email", text="test@example.com")
3. browser_click(selector="button[type='submit']")
```

## 🎯 CSS 选择器参考

常用选择器语法：

```css
#id          /* ID 选择器 */
.class       /* 类选择器 */
tag          /* 标签选择器 */
[attr=val]   /* 属性选择器 */

/* Playwright 特殊选择器 */
text=登录     /* 文本选择器 */
button:has-text("提交")  /* 包含文本 */
input:visible  /* 可见元素 */
```

## ⚠️ 注意事项

1. **默认代理优先** - 配置了 `WEB_ACCESS_PREFER_PROXY=1` 时，会优先走 web-access 代理。
2. **内置服务托管** - `./horbot.sh start|restart|status|logs` 已纳入 `web-access` 管理。
3. **自动拉起 Chrome** - 代理会尝试自动启动带 `--remote-debugging-port=9222` 的 Chrome；可通过 `WEB_ACCESS_AUTO_LAUNCH_CHROME=0` 关闭。
4. **自动回退** - 代理不可达、接口未实现或使用了 Playwright 专属选择器时，会自动回退到 Playwright。
5. **浏览器窗口可见** - Playwright 回退模式下，你可以看到 AI 的每一步操作。
6. **超时控制** - MCP 工具超时默认 120 秒，代理 HTTP 超时默认 30 秒。
7. **安全性** - 浏览器关闭后需要重新启动，代理目标页关闭后会自动清理当前 target。

## 🔧 高级配置

### 调整工具超时

```json
{
  "tools": {
    "mcp_servers": {
      "browser": {
        "command": "python",
        "args": ["-m", "horbot.mcp.browser.server"],
        "tool_timeout": 300  // 5分钟
      }
    }
  }
}
```

### 无头模式（后台运行）

设置环境变量 `BROWSER_HEADLESS=1`

### 关闭代理优先模式

设置环境变量 `WEB_ACCESS_PREFER_PROXY=0`

## 🐛 故障排查

### 问题：浏览器未启动

```bash
# 检查 Playwright 是否安装
pip show playwright

# 重新安装浏览器驱动
playwright install chromium
```

### 问题：找不到元素

- 使用 `browser_find_elements` 查看页面有哪些元素
- 使用 `browser_screenshot` 查看当前页面状态
- 检查选择器语法是否正确

### 问题：操作超时

- 增加 `tool_timeout` 配置值
- 使用 `browser_wait_for` 等待元素加载

### 问题：web-access 没有生效

- 检查 `./horbot.sh status` 是否显示 `web-access`
- 检查 `WEB_ACCESS_PROXY_URL` 指向的代理是否可访问，且 `/health` 返回成功
- 检查 `web-access.log` 中是否已自动拉起 Chrome remote debugging
- 检查代理是否支持 `/new`、`/click`、`/eval`、`/screenshot`、`/close` 等基础接口
- 如果只是临时不可用，系统会自动回退到 Playwright

## 📚 相关文档

- [Playwright 文档](https://playwright.dev/python/)
- [CSS 选择器参考](https://developer.mozilla.org/zh-CN/docs/Web/CSS/CSS_Selectors)
- [MCP 协议规范](https://modelcontextprotocol.io/)
