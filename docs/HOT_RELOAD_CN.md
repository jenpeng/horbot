# 热加载机制

## 概述

horbot 支持多种热加载机制，包括前端 HMR、后端热重载和配置文件热加载，大大提升开发体验。

## 前端 HMR (Hot Module Replacement)

### 配置说明

前端使用 Vite 实现 HMR，配置位于 `horbot/web/frontend/vite.config.ts`：

```typescript
export default defineConfig({
  server: {
    port: 3000,
    host: true,
    hmr: {
      overlay: true,
    },
    watch: {
      usePolling: true,
      interval: 100,
    },
  },
})
```

### 使用方式

```bash
# 启动前端开发服务器
cd horbot/web/frontend
npm run dev
```

修改前端代码后，浏览器会自动刷新并应用更改，无需手动刷新。

## 后端热重载

### 配置说明

后端使用 uvicorn 的 `--reload` 参数实现热重载：

```bash
uvicorn horbot.web.main:app --reload --host 127.0.0.1 --port 8000
```

### 启动脚本

推荐使用 `horbot.sh` 脚本管理服务：

```bash
./horbot.sh start
./horbot.sh stop
./horbot.sh restart
./horbot.sh status
./horbot.sh dev
```

其中：

- `./horbot.sh dev` 适合前端联调与热更新
- `./horbot.sh restart` 适合验证配置和服务重载

### 注意事项

- 后端热重载会重新加载 Python 模块
- 某些状态可能丢失（如内存中的缓存）
- 生产环境建议关闭热重载

## 配置文件热加载

### ConfigWatcher 实现

配置文件热加载通过 `ConfigWatcher` 类实现，位于 `horbot/config/watcher.py`：

```python
from horbot.config.watcher import ConfigWatcher, ConfigManager

# 创建配置监视器
watcher = ConfigWatcher(
    config_path=Path("./.horbot/config.json"),
    debounce_seconds=1.0
)

# 添加变更监听器
watcher.add_listener(on_config_change)

# 启动监视
await watcher.start()
```

### 配置变更处理

当配置文件变更时，系统会：

1. 检测文件变化（使用 watchfiles 库）
2. 防抖处理（默认 1 秒）
3. 重新加载配置
4. 通知所有注册的回调函数

### 自动应用的配置项

以下配置项变更会自动生效：

- `agents.defaults.max_iterations`
- `agents.defaults.temperature`
- `agents.defaults.max_tokens`
- `tools.permission.*`
- `tools.mcpServers.*`

### 使用示例

```python
async def on_config_change(event: ConfigChangeEvent):
    if event.error:
        logger.error(f"配置加载失败: {event.error}")
        return
    
    print(f"配置已更新: {event.changed_keys}")
    # 应用新配置...

# 使用 ConfigManager
manager = ConfigManager(auto_reload=True)
manager.subscribe(lambda old, new: print("配置已更新"))
await manager.start()
```

## 完整热加载架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        开发环境                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  前端 (Vite HMR)          后端 (uvicorn --reload)              │
│  ├── 代码变更检测          ├── Python 文件监控                  │
│  ├── 模块热替换            ├── 模块重新加载                     │
│  └── 浏览器自动刷新        └── 服务自动重启                     │
│                                                                 │
│                    配置文件热加载                                │
│                    ├── watchfiles 监控                          │
│                    ├── 防抖处理                                 │
│                    └── 回调通知                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 故障排除

### 前端 HMR 不工作

1. 检查 Vite 配置中的 `hmr` 设置
2. 确保没有代理或防火墙阻止 WebSocket 连接
3. 尝试清除浏览器缓存

### 后端热重载不工作

1. 确保使用 `--reload` 参数启动
2. 检查文件是否在监控范围内
3. 查看 uvicorn 日志是否有错误

### 配置热加载不工作

1. 确保 watchfiles 包已安装：`pip install watchfiles`
2. 检查配置文件路径是否正确
3. 查看日志中的热加载相关消息
