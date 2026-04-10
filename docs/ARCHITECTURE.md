# horbot 架构设计文档

## 核心理念

### The Model IS the Agent

**Agent 是什么？**

Agent 是一个神经网络 —— 一个经过训练的模型，能够感知环境、推理目标并采取行动。

```
Agent = Trained Model + Harness (感知 + 行动)
```

**Agent 不是什么？**

- Agent 不是框架代码
- Agent 不是 prompt 链
- Agent 不是拖拽工作流

**Harness 是什么？**

Harness 是给模型提供感知和行动能力的代码：

```
Harness = Tools + Knowledge + Observation + Action + Permissions
```

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        User Request                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Agent Loop                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  while True:                                         │   │
│  │      response = LLM(messages, tools)                │   │
│  │      if stop_reason != "tool_use": return           │   │
│  │      execute_tools()                                 │   │
│  │      append_results()                                │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
    ┌──────────┐        ┌──────────┐        ┌──────────┐
    │  Tools   │        │  Skills  │        │  Memory  │
    │ Registry │        │  Loader  │        │  Store   │
    └──────────┘        └──────────┘        └──────────┘
```

## 核心模块

### 1. Agent Loop (s01)

**问题**: 如何让模型持续工作直到任务完成？

**解决方案**: 一个简单的 while 循环。

```python
def agent_loop(messages):
    while True:
        response = llm.chat(messages, tools=tools)
        
        if response.stop_reason != "tool_use":
            return response.content
        
        for tool_call in response.tool_calls:
            result = execute_tool(tool_call)
            messages.append(tool_result(result))
```

**关键点**:
- 模型决定何时停止
- 代码只执行模型请求的工具
- 循环属于模型，不属于代码

### 2. Tool Use (s02)

**问题**: 如何扩展 Agent 的能力？

**解决方案**: 添加一个工具注册表。

```python
TOOLS = {
    "read_file": read_file_handler,
    "write_file": write_file_handler,
    "exec": exec_handler,
}

def execute_tool(tool_call):
    handler = TOOLS[tool_call.name]
    return handler(**tool_call.arguments)
```

**关键点**:
- 添加工具 = 添加处理函数
- 循环保持不变
- 统一的调度接口

### 3. Context Compact (s06)

**问题**: 对话历史会填满上下文窗口。

**解决方案**: 3 层压缩策略。

```
┌─────────────────────────────────────────┐
│ Layer 1: Preserve (保留层)              │
│   - System messages                     │
│   - Recent N messages                   │
├─────────────────────────────────────────┤
│ Layer 2: Compress (压缩层)              │
│   - Middle conversation → Summary       │
│   - Tool calls → Key info only          │
├─────────────────────────────────────────┤
│ Layer 3: Discard (丢弃层)               │
│   - Redundant information               │
└─────────────────────────────────────────┘
```

### 4. Subagents (s04)

**问题**: 大任务会污染主对话上下文。

**解决方案**: 每个子任务有独立的 messages[]。

```python
def spawn_subagent(task):
    # 全新的消息历史
    messages = [
        {"role": "system", "content": subagent_prompt},
        {"role": "user", "content": task},
    ]
    return run_agent_loop(messages)  # 完全独立
```

**关键点**:
- 子代理不继承主代理的对话历史
- 结果通过通知返回
- 主代理上下文保持干净

### 5. Task Graph (s07)

**问题**: 任务之间有依赖关系。

**解决方案**: 依赖图 + 拓扑排序。

```
     task_1
       │
       ├──► task_2
       │       │
       │       └──► task_3
       │
       └──► task_4

执行顺序: [task_1] → [task_2, task_4] → [task_3]
```

### 6. Background Tasks (s08)

**问题**: 慢操作会阻塞 Agent。

**解决方案**: 后台执行 + 异步通知。

```python
async def run_background(task_id, coro):
    asyncio.create_task(coro)
    # Agent 继续工作
    # 完成后发送通知
    await notify_queue.put((task_id, result))
```

### 7. Team Protocols (s10)

**问题**: 多个 Agent 如何协作？

**解决方案**: 标准化的消息协议。

```python
message = {
    "sender": "agent_a",
    "receiver": "agent_b",
    "action": "task_assign",
    "payload": {...},
    "timestamp": "2024-01-01T00:00:00Z",
}
```

### 8. Autonomous Agents (s11)

**问题**: Agent 如何自主工作？

**解决方案**: 空闲循环 + 任务认领。

```python
async def autonomous_loop():
    while True:
        if current_task is None:
            tasks = scan_task_board()
            for task in tasks:
                if can_handle(task):
                    claim_task(task)
                    execute_task(task)
                    break
        await sleep(idle_interval)
```

## 文件结构

```
horbot/agent/
├── loop.py              # Agent Loop (s01)
├── tools/
│   ├── registry.py      # Tool Registry (s02)
│   └── spawn.py         # Subagent Spawner (s04)
├── context_compact.py   # Context Compression (s06)
├── subagent.py          # Subagent Manager (s04)
├── team_protocols.py    # Team Protocols (s10) + TaskGraph (s07)
├── autonomous.py        # Autonomous Agents (s11)
├── background.py        # Background Tasks (s08)
├── worktree.py          # Worktree Isolation (s12)
└── skill_loader.py      # On-demand Skill Loading (s05)
```

## 设计原则

### 1. 简洁至上

- Bash is all you need
- 最小化抽象层
- 代码即文档

### 2. 信任模型

- 模型决定何时调用工具
- 模型决定何时停止
- Harness 不应该"聪明"

### 3. 渐进式复杂度

- 从简单的 loop 开始
- 按需添加功能
- 每个模块独立可测试

## 当前运行时说明

- 复杂任务的规划链路由系统自动判断并触发，不依赖 Web Chat 中的 `/plan` 命令
- `agents.defaults.models.planning` 代表内部规划场景模型，如果未单独配置则回退到 `main`
- Agent 在完成任务后可异步复盘，并将可复用流程沉淀为工作区 Skills

## 使用示例

### 基础 Agent Loop

```python
from horbot.agent.loop import AgentLoop
from horbot.providers.litellm_provider import LiteLLMProvider

provider = LiteLLMProvider(default_model="anthropic/claude-sonnet-4-5")
agent = AgentLoop(provider=provider)

result = await agent.run([{"role": "user", "content": "Hello!"}])
```

### 使用 Context Compact

```python
from horbot.agent.context_compact import compact_context

messages = [...]  # 长对话历史
compressed = compact_context(messages, max_tokens=100000)
```

### 使用 Task Graph

```python
from horbot.agent.team_protocols import TaskGraph

graph = TaskGraph()
graph.add_task("task_1")
graph.add_task("task_2", dependencies=["task_1"])

ready = graph.get_ready_tasks()  # ["task_1"]
```

### 使用 Background Notifier

```python
from horbot.agent.background import BackgroundNotifier

notifier = BackgroundNotifier()
task_id = await notifier.run_in_background("my_task", slow_coro())
notification = await notifier.wait_for_notification(timeout=60)
```

## 参考资料

- [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) - Claude Code 架构学习
- [Anthropic API](https://docs.anthropic.com/) - Claude API 文档
