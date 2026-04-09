# 分层上下文管理系统

## 概述

horbot 采用分层上下文管理系统 (Hierarchical Context Management)，通过 L0/L1/L2 三层架构实现从当前会话到长期历史的渐进式记忆管理。

## 架构设计

### 三层记忆架构

| 层级 | 名称 | 用途 | 加载策略 | Token 预算 |
|------|------|------|----------|-----------|
| **L0** | 核心记忆 | 当前会话的核心记忆，始终加载 | 按会话标识加载 | 60% |
| **L1** | 相关记忆 | 近期会话的相关记忆，按需加载 | 按修改时间排序 | 30% |
| **L2** | 历史记忆 | 长期历史记忆，检索加载 | 通过搜索查询检索 | 10% |

### 目录结构

```
.horbot/context/
├── memories/
│   ├── L0/                    # 核心记忆
│   │   ├── {session_key}.md   # 按会话标识命名
│   │   └── README.md
│   ├── L1/                    # 相关记忆
│   │   ├── memory_{timestamp}.md
│   │   └── README.md
│   └── L2/                    # 历史记忆
│       ├── memory_{timestamp}.md
│       └── README.md
├── executions/
│   ├── recent/                # 近期执行 (最多50条)
│   └── archived/              # 归档执行
└── resources/
    ├── files/
    ├── code/
    └── external/
```

## 使用场景

### L0 - 当前会话上下文
- 任务进度跟踪
- 活跃决策记录
- 临时状态管理

### L1 - 近期重要事件
- 最近修复的 Bug
- 近期做出的决策
- 学习到的经验教训

### L2 - 长期事实
- 用户偏好
- 项目架构知识
- 持久化最佳实践

## API 参考

### HierarchicalContextManager

```python
from horbot.agent.context_manager import HierarchicalContextManager

# 初始化
manager = HierarchicalContextManager(workspace=Path(".horbot/workspace"))

# 加载上下文
context = manager.load_context(
    session_key="web:session_123",
    levels=["L0", "L1"],
    max_tokens=8000
)

# 添加记忆
manager.add_memory(
    content="用户偏好使用深色主题",
    level="L1",
    metadata={"type": "preference"}
)

# 搜索上下文
results = manager.search_context(
    query="authentication",
    levels=["L1", "L2"],
    max_results=10
)

# 添加执行日志
manager.add_execution(
    execution_log={"task": "...", "result": "..."},
    session_key="web:session_123"
)
```

## 与 MemoryStore 集成

MemoryStore 自动与分层存储同步：

```python
# 长期记忆 (MEMORY.md) 同步到 L2
memory_store.write_long_term(content)

# 历史条目同步到 L1
memory_store.append_history(entry)

# 会话记忆存储到 L0
memory_store.add_session_memory(content, session_key)
```

## 配置选项

在 `config.json` 中配置：

```json
{
  "memory": {
    "hierarchical": true,
    "l0_token_budget": 0.60,
    "l1_token_budget": 0.30,
    "l2_token_budget": 0.10,
    "max_executions_recent": 50,
    "max_executions_archived_days": 30
  }
}
```
