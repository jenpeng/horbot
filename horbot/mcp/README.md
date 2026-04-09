# MCP Servers

Model Context Protocol (MCP) Server 集合，为 AI 提供各种工具能力。

本项目核心代码借鉴自 [HKUDS/nanobot](https://github.com/HKUDS/nanobot) 仓库内容，并在此基础上扩展了 MCP 能力。

## 📦 可用 Servers

| Server | 功能 | 状态 |
|--------|------|------|
| [browser](./browser/) | 浏览器自动化操作 | ✅ 可用 |

## 🚀 快速开始

### 1. 安装依赖

每个 server 可能有不同的依赖，请查看各自的 README：

```bash
# 例如 browser server
pip install playwright
playwright install chromium
```

### 2. 配置

编辑 `config.json`，添加需要的 MCP Server：

```json
{
  "tools": {
    "mcp_servers": {
      "browser": {
        "command": "python",
        "args": ["-m", "horbot.mcp.browser.server"],
        "tool_timeout": 120
      }
    }
  }
}
```

### 3. 使用

启动 horbot 后，AI 会自动加载 MCP 工具，可以直接使用。

## 🛠️ 添加新 Server

### 方法 1: 使用内置模板

```bash
# 创建新的 MCP Server 目录
mkdir -p horbot/mcp/my-server

# 创建文件
touch horbot/mcp/my-server/server.py
touch horbot/mcp/my-server/README.md
```

### 方法 2: 使用外部 MCP Server

直接在 `config.json` 中配置：

```json
{
  "tools": {
    "mcp_servers": {
      "my-server": {
        "command": "node",
        "args": ["/path/to/my-server/index.js"],
        "env": {
          "API_KEY": "xxx"
        }
      }
    }
  }
}
```

## 📚 Server 规范

### 目录结构

```
horbot/mcp/<server-name>/
├── server.py          # MCP Server 实现
├── README.md          # 使用文档
├── requirements.txt   # Python 依赖（可选）
└── tests/             # 测试文件（可选）
```

### 命名规范

- 目录名：小写 + 连字符（如 `browser`, `file-system`）
- 模块名：Python 模块名（如 `horbot.mcp.browser.server`）
- 工具名：`<category>_<action>`（如 `browser_navigate`）

## 🔗 相关链接

- [MCP 官方文档](https://modelcontextprotocol.io/)
- [Python SDK](https://github.com/modelcontextprotocol/python-sdk)

## 🤝 贡献

欢迎贡献新的 MCP Server！请确保：

1. ✅ 遵循目录结构规范
2. ✅ 提供完整的 README
3. ✅ 包含错误处理和日志
4. ✅ 编写测试用例
