#!/bin/bash

# 重置所有 Agent 和 Team 的记忆、聊天记录和历史记录
# Reset all agent and team memories, chat history and records

HORBOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HORBOT_DATA="$HORBOT_DIR/.horbot"

echo "=== Horbot 数据重置脚本 ==="
echo "工作目录: $HORBOT_DIR"
echo "数据目录: $HORBOT_DATA"
echo ""

# 确认操作
read -p "确定要重置所有记忆和聊天记录吗？这将删除所有历史数据！(y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "操作已取消"
    exit 0
fi

echo ""
echo "开始重置..."

# 1. 清除会话文件 (聊天记录)
echo "1. 清除会话文件..."
SESSIONS_DIRS=(
    "$HORBOT_DATA/workspace/sessions"
    "$HORBOT_DATA/sessions"
    "$HORBOT_DATA/data/sessions/active"
)

for dir in "${SESSIONS_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        rm -f "$dir"/*.jsonl 2>/dev/null
        echo "   - 已清除: $dir"
    fi
done

# 清除团队会话
if [ -d "$HORBOT_DATA/teams" ]; then
    find "$HORBOT_DATA/teams" -name "*.jsonl" -type f -delete 2>/dev/null
    echo "   - 已清除团队会话"
fi

# 2. 清除记忆文件
echo "2. 清除记忆文件..."
MEMORY_DIRS=(
    "$HORBOT_DATA/context/memories/memories"
    "$HORBOT_DATA/context/memories/executions/recent"
    "$HORBOT_DATA/data/memories"
    "$HORBOT_DATA/agents/main/memory"
)

for dir in "${MEMORY_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        rm -rf "$dir"/* 2>/dev/null
        echo "   - 已清除: $dir"
    fi
done

# 3. 清除上下文缓存
echo "3. 清除上下文缓存..."
if [ -d "$HORBOT_DATA/context/cache" ]; then
    rm -rf "$HORBOT_DATA/context/cache"/* 2>/dev/null
    echo "   - 已清除上下文缓存"
fi

# 4. 清除任务记录
echo "4. 清除任务记录..."
if [ -d "$HORBOT_DATA/tasks" ]; then
    rm -rf "$HORBOT_DATA/tasks"/* 2>/dev/null
    echo "   - 已清除任务记录"
fi

# 5. 清除技能执行记录
echo "5. 清除技能执行记录..."
if [ -d "$HORBOT_DATA/skills" ]; then
    find "$HORBOT_DATA/skills" -name "*.log" -type f -delete 2>/dev/null
    echo "   - 已清除技能日志"
fi

# 6. 清除临时文件
echo "6. 清除临时文件..."
if [ -d "$HORBOT_DATA/tmp" ]; then
    rm -rf "$HORBOT_DATA/tmp"/* 2>/dev/null
    echo "   - 已清除临时文件"
fi

echo ""
echo "=== 重置完成 ==="
echo ""
echo "注意: 如果后端服务正在运行，请重启服务以清除内存中的缓存。"
echo "      可以通过以下方式重启："
echo "      1. 在终端按 Ctrl+C 停止服务"
echo "      2. 重新运行: ./horbot.sh restart"
echo ""
echo "或者在浏览器中刷新页面（硬刷新: Cmd+Shift+R）"
