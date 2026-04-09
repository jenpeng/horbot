#!/bin/bash

# Horbot 项目管理脚本
# 支持依赖检查、安装、服务启动和管理

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 项目根目录（处理路径中的空格）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
FRONTEND_DIR="$PROJECT_ROOT/horbot/web/frontend"
VENV_DIR="$PROJECT_ROOT/.venv"
HORBOT_DATA_ROOT="$PROJECT_ROOT/.horbot"
DATA_ROOT="$HORBOT_DATA_ROOT"
MAIN_WORKSPACE_DIR="$DATA_ROOT/agents/main/workspace"
PID_DIR="$DATA_ROOT/runtime/pids"
LOG_DIR="$DATA_ROOT/runtime/logs"
BACKEND_FINGERPRINT_FILE="$DATA_ROOT/runtime/backend.codehash"

# Logo
LOGO="🐎"

print_logo() {
    echo -e "${CYAN}$LOGO Horbot 项目管理${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

display_data_root_rel() {
    echo ".horbot"
}

display_config_file_rel() {
    echo "$(display_data_root_rel)/config.json"
}

# 确保目录存在
ensure_dirs() {
    mkdir -p "$PID_DIR"
    mkdir -p "$LOG_DIR"
    mkdir -p "$DATA_ROOT/data/sessions"
    mkdir -p "$DATA_ROOT/data/memories"
    mkdir -p "$DATA_ROOT/data/cron"
    mkdir -p "$DATA_ROOT/data/plans"
    mkdir -p "$MAIN_WORKSPACE_DIR/skills"
    mkdir -p "$MAIN_WORKSPACE_DIR/scripts"
}

# 检查后端依赖
check_backend() {
    print_info "检查后端依赖..."
    
    if [ -d "$VENV_DIR" ]; then
        source "$VENV_DIR/bin/activate" 2>/dev/null || true
    fi
    
    if python -c "import horbot" 2>/dev/null; then
        print_success "后端依赖已安装"
        return 0
    else
        print_warning "后端依赖未安装"
        return 1
    fi
}

# 检查前端依赖
check_frontend() {
    print_info "检查前端依赖..."
    
    if [ -d "$FRONTEND_DIR/node_modules" ]; then
        print_success "前端依赖已安装"
        return 0
    else
        print_warning "前端依赖未安装"
        return 1
    fi
}

# 安装后端依赖
install_backend() {
    print_info "安装后端依赖..."
    
    if [ ! -d "$VENV_DIR" ]; then
        print_info "创建虚拟环境..."
        python3 -m venv "$VENV_DIR"
    fi
    
    source "$VENV_DIR/bin/activate"
    
    print_info "安装 Python 依赖..."
    pip install -e "$PROJECT_ROOT"
    
    print_success "后端依赖安装完成"
}

# 安装前端依赖
install_frontend() {
    print_info "安装前端依赖..."
    
    cd "$FRONTEND_DIR"
    
    if command -v npm &> /dev/null; then
        npm install
    elif command -v yarn &> /dev/null; then
        yarn install
    elif command -v pnpm &> /dev/null; then
        pnpm install
    else
        print_error "未找到 npm、yarn 或 pnpm"
        cd "$PROJECT_ROOT"
        return 1
    fi
    
    cd "$PROJECT_ROOT"
    print_success "前端依赖安装完成"
}

# 安装所有依赖
install_all() {
    install_backend
    install_frontend
    create_default_config
    print_success "所有依赖安装完成"
}

# 创建默认配置文件
create_default_config() {
    local config_file="$DATA_ROOT/config.json"
    
    if [ -f "$config_file" ]; then
        print_info "配置文件已存在，跳过创建"
        return 0
    fi
    
    print_info "创建默认配置文件..."
    
    mkdir -p "$DATA_ROOT"
    
    cat > "$config_file" << 'EOF'
{
  "agents": {
    "defaults": {
      "workspace": ".horbot/agents/main/workspace",
      "maxTokens": 4096,
      "temperature": 0.7,
      "maxToolIterations": 20,
      "memoryWindow": 20,
      "models": {
        "main": {
          "provider": "openrouter",
          "model": "anthropic/claude-sonnet-4-20250514",
          "description": "主模型 - 通用对话",
          "capabilities": []
        },
        "planning": {
          "provider": "openrouter",
          "model": "anthropic/claude-sonnet-4-20250514",
          "description": "计划模型 - 复杂任务规划",
          "capabilities": []
        },
        "file": {
          "provider": "openrouter",
          "model": "anthropic/claude-sonnet-4-20250514",
          "description": "文件处理模型",
          "capabilities": []
        },
        "image": {
          "provider": "openrouter",
          "model": "anthropic/claude-sonnet-4-20250514",
          "description": "图片处理模型",
          "capabilities": ["vision"]
        },
        "audio": {
          "provider": "openrouter",
          "model": "anthropic/claude-sonnet-4-20250514",
          "description": "音频处理模型",
          "capabilities": ["audio"]
        },
        "video": {
          "provider": "openrouter",
          "model": "anthropic/claude-sonnet-4-20250514",
          "description": "视频处理模型",
          "capabilities": ["vision"]
        }
      },
      "context_compact": {
        "enabled": true,
        "max_tokens": 100000,
        "preserve_recent": 10,
        "compress_tool_results": true
      }
    }
  },
  "channels": {
    "sendProgress": false,
    "sendToolHints": false,
    "whatsapp": {
      "enabled": false,
      "bridgeUrl": "ws://localhost:3001",
      "bridgeToken": "",
      "allowFrom": []
    },
    "telegram": {
      "enabled": false,
      "token": "",
      "allowFrom": [],
      "proxy": null,
      "replyToMessage": false
    },
    "discord": {
      "enabled": false,
      "token": "",
      "allowFrom": [],
      "gatewayUrl": "wss://gateway.discord.gg/?v=10&encoding=json",
      "intents": 37377
    },
    "feishu": {
      "enabled": false,
      "appId": "",
      "appSecret": "",
      "encryptKey": "",
      "verificationToken": "",
      "allowFrom": [],
      "skipSslVerify": false
    },
    "dingtalk": {
      "enabled": false,
      "clientId": "",
      "clientSecret": "",
      "allowFrom": []
    },
    "mochat": {
      "enabled": false,
      "baseUrl": "https://mochat.io",
      "socketUrl": "",
      "socketPath": "/socket.io",
      "socketDisableMsgpack": false,
      "socketReconnectDelayMs": 1000,
      "socketMaxReconnectDelayMs": 10000,
      "socketConnectTimeoutMs": 10000,
      "refreshIntervalMs": 30000,
      "watchTimeoutMs": 25000,
      "watchLimit": 100,
      "retryDelayMs": 500,
      "maxRetryAttempts": 0,
      "clawToken": "",
      "agentUserId": "",
      "sessions": [],
      "panels": [],
      "allowFrom": [],
      "mention": {
        "requireInGroups": false
      },
      "groups": {},
      "replyDelayMode": "non-mention",
      "replyDelayMs": 120000
    },
    "email": {
      "enabled": false,
      "consentGranted": false,
      "imapHost": "",
      "imapPort": 993,
      "imapUsername": "",
      "imapPassword": "",
      "imapMailbox": "INBOX",
      "imapUseSsl": true,
      "smtpHost": "",
      "smtpPort": 587,
      "smtpUsername": "",
      "smtpPassword": "",
      "smtpUseTls": true,
      "smtpUseSsl": false,
      "fromAddress": "",
      "autoReplyEnabled": true,
      "pollIntervalSeconds": 30,
      "markSeen": true,
      "maxBodyChars": 12000,
      "subjectPrefix": "Re: ",
      "allowFrom": []
    },
    "slack": {
      "enabled": false,
      "mode": "socket",
      "webhookPath": "/slack/events",
      "botToken": "",
      "appToken": "",
      "userTokenReadOnly": true,
      "replyInThread": true,
      "reactEmoji": "eyes",
      "groupPolicy": "mention",
      "groupAllowFrom": [],
      "dm": {
        "enabled": true,
        "policy": "open",
        "allowFrom": []
      }
    },
    "qq": {
      "enabled": false,
      "appId": "",
      "secret": "",
      "allowFrom": []
    },
    "matrix": {
      "enabled": false,
      "homeserver": "https://matrix.org",
      "accessToken": "",
      "userId": "",
      "deviceId": "",
      "e2EeEnabled": true,
      "syncStopGraceSeconds": 2,
      "maxMediaBytes": 20971520,
      "allowFrom": [],
      "groupPolicy": "open",
      "groupAllowFrom": [],
      "allowRoomMentions": false
    },
    "sharecrm": {
      "enabled": false,
      "gatewayBaseUrl": "https://open.fxiaoke.com",
      "appId": "",
      "appSecret": "",
      "dmPolicy": "open",
      "allowFrom": [],
      "groupPolicy": "disabled",
      "groupAllowFrom": [],
      "textChunkLimit": 4000
    }
  },
  "providers": {
    "custom": {
      "apiKey": "",
      "apiBase": null,
      "extraHeaders": null
    },
    "anthropic": {
      "apiKey": "",
      "apiBase": null,
      "extraHeaders": null
    },
    "openai": {
      "apiKey": "",
      "apiBase": null,
      "extraHeaders": null
    },
    "openrouter": {
      "apiKey": "",
      "apiBase": null,
      "extraHeaders": null
    },
    "deepseek": {
      "apiKey": "",
      "apiBase": "https://api.deepseek.com",
      "extraHeaders": null
    },
    "groq": {
      "apiKey": "",
      "apiBase": null,
      "extraHeaders": null
    },
    "zhipu": {
      "apiKey": "",
      "apiBase": null,
      "extraHeaders": null
    },
    "dashscope": {
      "apiKey": "",
      "apiBase": null,
      "extraHeaders": null
    },
    "vllm": {
      "apiKey": "",
      "apiBase": null,
      "extraHeaders": null
    },
    "gemini": {
      "apiKey": "",
      "apiBase": null,
      "extraHeaders": null
    },
    "moonshot": {
      "apiKey": "",
      "apiBase": null,
      "extraHeaders": null
    },
    "minimax": {
      "apiKey": "",
      "apiBase": "https://api.minimaxi.com/v1",
      "extraHeaders": null
    },
    "aihubmix": {
      "apiKey": "",
      "apiBase": null,
      "extraHeaders": null
    },
    "siliconflow": {
      "apiKey": "",
      "apiBase": null,
      "extraHeaders": null
    },
    "volcengine": {
      "apiKey": "",
      "apiBase": null,
      "extraHeaders": null
    },
    "openaiCodex": {
      "apiKey": "",
      "apiBase": null,
      "extraHeaders": null
    },
    "githubCopilot": {
      "apiKey": "",
      "apiBase": null,
      "extraHeaders": null
    }
  },
  "gateway": {
    "host": "127.0.0.1",
    "port": 18790,
    "adminToken": "",
    "allowRemoteWithoutToken": false,
    "heartbeat": {
      "enabled": false,
      "intervalS": 1800
    }
  },
  "tools": {
    "web": {
      "search": {
        "provider": "duckduckgo",
        "api_key": "",
        "max_results": 5
      }
    },
    "exec": {
      "timeout": 60,
      "pathAppend": ""
    },
    "restrictToWorkspace": true,
    "mcpServers": {},
    "permission": {
      "profile": "full",
      "allow": [],
      "deny": [],
      "confirm": []
    }
  },
  "autonomous": {
    "enabled": false,
    "maxPlanSteps": 10,
    "stepTimeout": 300,
    "totalTimeout": 3600,
    "retryCount": 3,
    "retryDelay": 5,
    "confirmSensitive": true,
    "sensitiveOperations": [
      "write_file",
      "edit_file",
      "exec",
      "spawn",
      "cron"
    ],
    "protectedPaths": [
      "~/.ssh",
      "~/.env",
      "**/.env"
    ]
  }
}
EOF
    
    print_success "默认配置文件已创建: $config_file"
    
    # 创建 workspace 目录
    mkdir -p "$MAIN_WORKSPACE_DIR"
    
    # 创建 SOUL.md 文件
    local soul_file="$MAIN_WORKSPACE_DIR/SOUL.md"
    if [ ! -f "$soul_file" ]; then
        cat > "$soul_file" << 'SOUL_EOF'
# 灵魂

我是 horbot 🐎，你的个人 AI 助手。

## 个性

- 热情友好，乐于助人
- 简洁明了，直击要点
- 好奇求知，持续学习

## 价值观

- 准确优先于速度
- 用户隐私与安全至上
- 行为透明，可解释

## 沟通风格

- 清晰直接
- 适时解释推理过程
- 需要时主动询问澄清

## 核心能力

- 代码编写与调试
- 文件操作与管理
- 网络搜索与信息获取
- 任务规划与执行

---

*你可以编辑此文件来自定义 AI 的个性。*
SOUL_EOF
        print_success "SOUL.md 文件已创建"
    fi
    
    # 创建 USER.md 文件
    local user_file="$MAIN_WORKSPACE_DIR/USER.md"
    if [ ! -f "$user_file" ]; then
        cat > "$user_file" << 'USER_EOF'
# 用户档案

用户信息，帮助个性化交互体验。

## 基本信息

- **姓名**：（你的名字）
- **时区**：（你的时区，如：UTC+8）
- **语言**：（首选语言，如：中文）

## 偏好设置

### 沟通风格

- [ ] 轻松随意
- [ ] 专业正式
- [ ] 技术导向

### 回复长度

- [ ] 简洁明了
- [ ] 详细解释
- [ ] 根据问题自适应

### 技术水平

- [ ] 初学者
- [ ] 中级
- [ ] 专家

## 工作背景

- **主要角色**：（你的角色，如：开发者、研究员、产品经理）
- **当前项目**：（你正在进行的项目）
- **常用工具**：（IDE、编程语言、框架等）

## 兴趣主题

- 
- 
- 

## 特别说明

（对助手行为的特殊要求或说明）

---

*编辑此文件来自定义 horbot 的行为，使其更符合你的需求。*
USER_EOF
        print_success "USER.md 文件已创建"
    fi
    
    print_warning "请编辑配置文件添加 API Key"
}

# 检查所有依赖
check_all() {
    local backend_ok=true
    local frontend_ok=true
    
    check_backend || backend_ok=false
    check_frontend || frontend_ok=false
    
    echo ""
    if $backend_ok && $frontend_ok; then
        print_success "所有依赖已就绪"
        return 0
    else
        print_warning "部分依赖缺失，请运行: $0 install"
        return 1
    fi
}

# 读取 PID（安全处理）
read_pid() {
    local pid_file="$1"
    if [ -f "$pid_file" ]; then
        cat "$pid_file"
    else
        echo ""
    fi
}

# 检查进程是否运行
is_running() {
    local pid="$1"
    [ -n "$pid" ] || return 1
    ps -p "$pid" >/dev/null 2>&1
}

# 获取 PID 对应命令
get_pid_command() {
    local pid="$1"
    if [ -z "$pid" ]; then
        return 1
    fi
    ps -p "$pid" -o command= 2>/dev/null
}

pid_listens_on_port() {
    local pid="$1"
    local port="$2"
    [ -z "$pid" ] || [ -z "$port" ] && return 1
    lsof -nP -a -p "$pid" -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

# 递归获取子进程
collect_child_pids() {
    local pid="$1"
    if [ -z "$pid" ] || ! command -v pgrep >/dev/null 2>&1; then
        return 0
    fi

    local child
    while IFS= read -r child; do
        [ -z "$child" ] && continue
        collect_child_pids "$child"
        echo "$child"
    done < <(pgrep -P "$pid" 2>/dev/null || true)
}

# 终止进程及其子进程
terminate_pid_tree() {
    local pid="$1"
    [ -z "$pid" ] && return 0

    local child
    while IFS= read -r child; do
        [ -z "$child" ] && continue
        terminate_pid_tree "$child"
    done < <(collect_child_pids "$pid")

    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
    fi
}

# 获取监听指定端口的 PID
list_port_pids() {
    local port="$1"
    lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | sort -u
}

# 判断 PID 是否为指定服务
is_expected_service_pid() {
    local pid="$1"
    local service="$2"
    local command

    command="$(get_pid_command "$pid")"

    case "$service" in
        backend)
            if [ -n "$command" ]; then
                [[ "$command" == *"uvicorn horbot.web.main:app"* ]] || [[ "$command" == *"python -m uvicorn horbot.web.main:app"* ]]
            else
                pid_listens_on_port "$pid" 8000
            fi
            ;;
        frontend)
            if [ -n "$command" ]; then
                [[ "$command" == *"vite"* ]]
            else
                pid_listens_on_port "$pid" 3000
            fi
            ;;
        gateway)
            if [ -n "$command" ]; then
                [[ "$command" == *"horbot gateway"* ]]
            else
                local recorded_pid
                recorded_pid="$(read_pid "$PID_DIR/gateway.pid")"
                [ -n "$recorded_pid" ] && [ "$recorded_pid" = "$pid" ]
            fi
            ;;
        *)
            return 1
            ;;
    esac
}

# 检查端口是否被占用
is_port_in_use() {
    local port="$1"
    list_port_pids "$port" | head -1
}

# 获取占用端口的 PID
get_port_pid() {
    local port="$1"
    list_port_pids "$port" | head -1
}

# 根据服务类型查找匹配的进程 PID
list_service_pids() {
    local service="$1"
    local pid
    local command_line

    while IFS= read -r line; do
        [ -z "$line" ] && continue
        pid="${line%% *}"
        command_line="${line#"$pid"}"
        command_line="${command_line#"${command_line%%[![:space:]]*}"}"

        case "$service" in
            backend)
                [[ "$command_line" == *"uvicorn horbot.web.main:app"* ]] || [[ "$command_line" == *"python -m uvicorn horbot.web.main:app"* ]] || continue
                ;;
            frontend)
                [[ "$command_line" == *"vite"* ]] || continue
                ;;
            gateway)
                [[ "$command_line" == *"horbot gateway"* ]] || continue
                ;;
            *)
                return 1
                ;;
        esac

        if is_expected_service_pid "$pid" "$service"; then
            echo "$pid"
        fi
    done < <(ps -axo pid=,command= 2>/dev/null)
}

get_service_pid() {
    local service="$1"
    list_service_pids "$service" | head -1
}

# 清理端口占用（杀死占用端口的进程）
cleanup_port() {
    local port="$1"
    local pids
    pids="$(list_port_pids "$port")"
    if [ -n "$pids" ]; then
        for pid in $pids; do
            if kill -0 "$pid" 2>/dev/null; then
                print_warning "发现端口 $port 被进程 $pid 占用，正在清理..."
                terminate_pid_tree "$pid"
            fi
        done
        sleep 2
        local remaining_pids
        remaining_pids="$(list_port_pids "$port")"
        if [ -n "$remaining_pids" ]; then
            for pid in $remaining_pids; do
                print_warning "进程 $pid 未响应，强制终止..."
                kill -9 "$pid" 2>/dev/null || true
            done
            sleep 1
        fi
        if [ -n "$(list_port_pids "$port")" ]; then
            print_error "端口 $port 仍被占用，请手动处理"
            return 1
        fi
    fi
    return 0
}

# 以独立会话启动后台进程，避免在调用脚本退出后被回收
spawn_detached() {
    local working_dir="$1"
    local log_file="$2"
    shift 2

    python3 - "$working_dir" "$log_file" "$@" <<'PY'
import os
import subprocess
import sys

working_dir = sys.argv[1]
log_file = sys.argv[2]
command = sys.argv[3:]

with open(log_file, "ab", buffering=0) as log_fp:
    proc = subprocess.Popen(
        command,
        cwd=working_dir,
        stdin=subprocess.DEVNULL,
        stdout=log_fp,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
        env=os.environ.copy(),
    )

print(proc.pid)
PY
}

# 等待服务端口真正就绪
wait_for_port() {
    local port="$1"
    local expected_service="$2"
    local pid_file="$3"
    local timeout="${4:-15}"
    local elapsed=0

    while [ "$elapsed" -lt "$timeout" ]; do
        local port_pid
        port_pid="$(get_port_pid "$port")"
        if [ -n "$port_pid" ] && is_expected_service_pid "$port_pid" "$expected_service"; then
            echo "$port_pid" > "$pid_file"
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done

    return 1
}

# 等待服务进程稳定存活，不依赖端口监听
wait_for_process() {
    local service="$1"
    local pid_file="$2"
    local timeout="${3:-15}"
    local elapsed=0

    while [ "$elapsed" -lt "$timeout" ]; do
        local resolved_pid
        resolved_pid="$(resolve_service_pid "$service" "$pid_file" "" 2>/dev/null || true)"
        if [ -n "$resolved_pid" ] && is_running "$resolved_pid"; then
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done

    return 1
}

compute_backend_source_fingerprint() {
    python3 - "$PROJECT_ROOT" <<'PY'
from pathlib import Path
import hashlib
import sys

project_root = Path(sys.argv[1])
targets = [
    project_root / "horbot",
    project_root / "pyproject.toml",
]

hash_obj = hashlib.sha256()

for target in targets:
    if target.is_dir():
        files = sorted(path for path in target.rglob("*.py") if path.is_file())
    elif target.is_file():
        files = [target]
    else:
        files = []

    for path in files:
        relative = path.relative_to(project_root)
        stat = path.stat()
        hash_obj.update(str(relative).encode("utf-8"))
        hash_obj.update(b"\0")
        hash_obj.update(str(stat.st_mtime_ns).encode("utf-8"))
        hash_obj.update(b"\0")
        hash_obj.update(str(stat.st_size).encode("utf-8"))
        hash_obj.update(b"\0")

print(hash_obj.hexdigest())
PY
}

backend_code_matches_runtime() {
    local current_fingerprint
    current_fingerprint="$(compute_backend_source_fingerprint)"

    if [ ! -f "$BACKEND_FINGERPRINT_FILE" ]; then
        return 1
    fi

    local stored_fingerprint
    stored_fingerprint="$(cat "$BACKEND_FINGERPRINT_FILE" 2>/dev/null | tr -d '[:space:]')"
    [ -n "$stored_fingerprint" ] && [ "$stored_fingerprint" = "$current_fingerprint" ]
}

persist_backend_runtime_fingerprint() {
    compute_backend_source_fingerprint > "$BACKEND_FINGERPRINT_FILE"
}

ensure_browser_services_ready() {
    start_backend
    start_frontend
}

# 优先使用真实存活的 PID，并在必要时通过端口恢复 PID 文件
resolve_service_pid() {
    local service="$1"
    local pid_file="$2"
    local port="$3"

    local pid
    pid="$(read_pid "$pid_file")"
    if is_running "$pid"; then
        echo "$pid"
        return 0
    fi

    if [ -n "$port" ]; then
        local port_pid
        port_pid="$(get_port_pid "$port")"
        if [ -n "$port_pid" ] && is_expected_service_pid "$port_pid" "$service"; then
            echo "$port_pid" > "$pid_file"
            echo "$port_pid"
            return 0
        fi
    fi

    local service_pid
    service_pid="$(get_service_pid "$service")"
    if [ -n "$service_pid" ]; then
        echo "$service_pid" > "$pid_file"
        echo "$service_pid"
        return 0
    fi

    rm -f "$pid_file"
    echo ""
    return 1
}

# 启动后端服务
start_backend() {
    ensure_dirs
    
    local pid_file="$PID_DIR/backend.pid"
    local port=8000
    local current_pid=$(read_pid "$pid_file")
    
    if is_running "$current_pid"; then
        if backend_code_matches_runtime; then
            print_warning "后端服务已在运行 (PID: $current_pid)"
            return 0
        fi
        print_warning "检测到后端代码已更新，自动重启后端服务..."
        stop_service backend
        current_pid=""
    fi
    
    local port_pid=$(get_port_pid "$port")
    if [ -n "$port_pid" ]; then
        if is_expected_service_pid "$port_pid" backend; then
            if backend_code_matches_runtime; then
                print_warning "检测到后端服务已在端口 $port 运行，恢复 PID 文件 (PID: $port_pid)"
                echo "$port_pid" > "$pid_file"
                return 0
            fi
            print_warning "检测到端口 $port 上运行的是旧版后端实例，正在自动重启..."
            cleanup_port "$port" || return 1
        fi
        if [ -n "$(get_port_pid "$port")" ]; then
            print_warning "端口 $port 被进程 $port_pid 占用"
            cleanup_port "$port" || return 1
        fi
    fi
    
    print_info "启动后端服务..."
    
    local python_cmd="python3"
    if [ -x "$VENV_DIR/bin/python" ]; then
        python_cmd="$VENV_DIR/bin/python"
    fi

    local new_pid
    new_pid="$(spawn_detached "$PROJECT_ROOT" "$LOG_DIR/backend.log" \
        "$python_cmd" -m uvicorn horbot.web.main:app --host 127.0.0.1 --port 8000)"
    echo "$new_pid" > "$pid_file"

    if wait_for_port "$port" backend "$pid_file" 15; then
        local actual_pid
        actual_pid="$(read_pid "$pid_file")"
        persist_backend_runtime_fingerprint
        print_success "后端服务已启动 (PID: $actual_pid)"
        print_info "访问地址: http://localhost:8000"
    else
        print_error "后端服务启动失败"
        rm -f "$pid_file"
        rm -f "$BACKEND_FINGERPRINT_FILE"
        cat "$LOG_DIR/backend.log"
        return 1
    fi
}

# 启动前端服务
start_frontend() {
    ensure_dirs
    
    local pid_file="$PID_DIR/frontend.pid"
    local port=3000
    local current_pid=$(read_pid "$pid_file")
    
    if is_running "$current_pid"; then
        print_warning "前端服务已在运行 (PID: $current_pid)"
        return 0
    fi
    
    local port_pid=$(get_port_pid "$port")
    if [ -n "$port_pid" ]; then
        if is_expected_service_pid "$port_pid" frontend; then
            print_warning "检测到前端服务已在端口 $port 运行，恢复 PID 文件 (PID: $port_pid)"
            echo "$port_pid" > "$pid_file"
            return 0
        fi
        print_warning "端口 $port 被进程 $port_pid 占用"
        cleanup_port "$port" || return 1
    fi
    
    print_info "启动前端服务..."
    
    cd "$FRONTEND_DIR"
    
    if [ ! -d "node_modules" ]; then
        print_error "前端依赖未安装，请先运行: $0 install frontend"
        cd "$PROJECT_ROOT"
        return 1
    fi
    
    local new_pid
    new_pid="$(spawn_detached "$FRONTEND_DIR" "$LOG_DIR/frontend.log" npm run dev -- --host 127.0.0.1)"
    echo "$new_pid" > "$pid_file"
    
    cd "$PROJECT_ROOT"
    
    if wait_for_port "$port" frontend "$pid_file" 20; then
        local actual_pid
        actual_pid="$(read_pid "$pid_file")"
        print_success "前端服务已启动 (PID: $actual_pid)"
        print_info "访问地址: http://localhost:3000"
    else
        print_error "前端服务启动失败"
        rm -f "$pid_file"
        cat "$LOG_DIR/frontend.log"
        return 1
    fi
}

# 启动 Gateway 服务
start_gateway() {
    ensure_dirs
    
    local pid_file="$PID_DIR/gateway.pid"
    local port
    port="$(get_gateway_port)"
    local current_pid
    current_pid="$(resolve_service_pid gateway "$pid_file" "$port" || true)"
    
    if is_running "$current_pid"; then
        print_warning "Gateway 服务已在运行 (PID: $current_pid)"
        return 0
    fi
    
    print_info "启动 Gateway 服务..."
    
    local gateway_cmd="horbot"
    if [ -x "$VENV_DIR/bin/horbot" ]; then
        gateway_cmd="$VENV_DIR/bin/horbot"
    fi

    local new_pid
    new_pid="$(spawn_detached "$PROJECT_ROOT" "$LOG_DIR/gateway.log" "$gateway_cmd" gateway --port "$port")"
    echo "$new_pid" > "$pid_file"

    if wait_for_port "$port" gateway "$pid_file" 15; then
        local actual_pid
        actual_pid="$(read_pid "$pid_file")"
        print_success "Gateway 服务已启动 (PID: $actual_pid)"
        print_info "Gateway HTTP 入口: http://localhost:$port"
    else
        print_error "Gateway 服务启动失败"
        rm -f "$pid_file"
        cat "$LOG_DIR/gateway.log"
        return 1
    fi
}

# 获取本机IP地址
get_local_ip() {
    local ip=""
    if command -v ipconfig &> /dev/null; then
        ip=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "")
    elif command -v hostname &> /dev/null; then
        ip=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "")
    fi
    echo "$ip"
}

get_gateway_port() {
    local config_file="$DATA_ROOT/config.json"
    local default_port="18790"

    if [ ! -f "$config_file" ]; then
        echo "$default_port"
        return 0
    fi

    python3 - "$config_file" "$default_port" <<'PY'
import json
import sys

config_file = sys.argv[1]
default_port = sys.argv[2]

try:
    with open(config_file, encoding="utf-8") as f:
        data = json.load(f)
    gateway = data.get("gateway") or {}
    port = gateway.get("port") or default_port
    print(int(port))
except Exception:
    print(default_port)
PY
}

# 启动所有服务
start_all() {
    start_backend
    start_frontend
    start_gateway
    echo ""
    print_success "所有服务已启动"
    echo ""
    local local_ip=$(get_local_ip)
    local gateway_port
    gateway_port="$(get_gateway_port)"
    print_info "Web UI: http://localhost:3000"
    print_info "后端API: http://localhost:8000"
    print_info "Gateway: http://localhost:$gateway_port"
    if [ -n "$local_ip" ]; then
        echo ""
        echo -e "${CYAN}局域网访问(需管理员令牌):${NC}"
        echo -e "  Web UI:   http://$local_ip:3000"
        echo -e "  Backend:  http://$local_ip:8000"
        echo ""
        echo -e "${YELLOW}远程访问提示:${NC}"
        echo -e "  默认仅本机直连；远程访问前请先在 $(display_config_file_rel) 中配置 gateway.adminToken"
        echo -e "  浏览器远程访问还需在 localStorage.horbotAdminToken 中写入同一令牌"
    fi
}

# 停止服务
stop_service() {
    local service=$1
    local pid_file="$PID_DIR/${service}.pid"
    local port=""
    
    case "$service" in
        backend)  port=8000 ;;
        frontend) port=3000 ;;
        gateway)  port=18790 ;;
    esac
    
    local pid=""
    if [ -f "$pid_file" ]; then
        pid="$(cat "$pid_file")"
    else
        pid="$(get_service_pid "$service")"
    fi

    if [ -n "$pid" ] && is_running "$pid"; then
        terminate_pid_tree "$pid"
        print_success "${service} 服务已停止"
    else
        print_warning "${service} 服务未运行"
    fi
    rm -f "$pid_file"
    if [ "$service" = "backend" ]; then
        rm -f "$BACKEND_FINGERPRINT_FILE"
    fi

    local extra_pids
    extra_pids="$(list_service_pids "$service")"
    if [ -n "$extra_pids" ]; then
        for p in $extra_pids; do
            if kill -0 "$p" 2>/dev/null; then
                print_warning "清理 ${service} 服务残留进程 $p"
                terminate_pid_tree "$p"
                sleep 1
                if kill -0 "$p" 2>/dev/null; then
                    kill -9 "$p" 2>/dev/null || true
                fi
            fi
        done
    fi
    
    if [ -n "$port" ]; then
        local port_pids
        port_pids="$(list_port_pids "$port")"
        if [ -n "$port_pids" ]; then
            for p in $port_pids; do
                print_warning "清理端口 $port 上的残留进程 $p"
                terminate_pid_tree "$p"
                sleep 1
                if kill -0 "$p" 2>/dev/null; then
                    kill -9 "$p" 2>/dev/null || true
                fi
            done
        fi
    fi
}

# 停止所有服务
stop_all() {
    stop_service backend
    stop_service frontend
    stop_service gateway
    print_success "所有服务已停止"
}

# 查看服务状态
status() {
    ensure_dirs
    
    echo ""
    print_logo
    
    # 检查是否有服务在运行
    local backend_pid
    backend_pid="$(resolve_service_pid backend "$PID_DIR/backend.pid" 8000 || true)"
    local frontend_pid
    frontend_pid="$(resolve_service_pid frontend "$PID_DIR/frontend.pid" 3000 || true)"
    local gateway_pid
    local gateway_port
    gateway_port="$(get_gateway_port)"
    gateway_pid="$(resolve_service_pid gateway "$PID_DIR/gateway.pid" "$gateway_port" || true)"
    
    local any_running=false
    if [ -n "$backend_pid" ] || [ -n "$frontend_pid" ] || [ -n "$gateway_pid" ]; then
        any_running=true
    fi
    
    if [ "$any_running" = false ]; then
        echo -e "${RED}● 服务未运行${NC}"
        echo ""
        echo -e "使用 '${GREEN}./horbot.sh start${NC}' 启动服务"
        echo ""
        return 0
    fi
    
    echo -e "${GREEN}● 服务运行中${NC}"
    echo ""
    echo -e "${CYAN}进程状态:${NC}"
    
    # 后端状态
    if [ -n "$backend_pid" ]; then
        local backend_mem=$(ps -o rss= -p "$backend_pid" 2>/dev/null | awk '{printf "%.1f MB", $1/1024}')
        local backend_cpu=$(ps -o %cpu= -p "$backend_pid" 2>/dev/null | awk '{printf "%.1f%%", $1}')
        if [ -n "$backend_mem" ] && [ -n "$backend_cpu" ]; then
            echo -e "  ${GREEN}Backend${NC}  PID: $backend_pid  CPU: $backend_cpu  Memory: $backend_mem  Port: 8000"
        else
            echo -e "  ${GREEN}Backend${NC}  PID: $backend_pid  Port: 8000"
        fi
    else
        echo -e "  ${RED}Backend${NC}  已停止"
    fi
    
    # 前端状态
    if [ -n "$frontend_pid" ]; then
        local frontend_mem=$(ps -o rss= -p "$frontend_pid" 2>/dev/null | awk '{printf "%.1f MB", $1/1024}')
        local frontend_cpu=$(ps -o %cpu= -p "$frontend_pid" 2>/dev/null | awk '{printf "%.1f%%", $1}')
        if [ -n "$frontend_mem" ] && [ -n "$frontend_cpu" ]; then
            echo -e "  ${GREEN}Frontend${NC} PID: $frontend_pid  CPU: $frontend_cpu  Memory: $frontend_mem  Port: 3000"
        else
            echo -e "  ${GREEN}Frontend${NC} PID: $frontend_pid  Port: 3000"
        fi
    else
        echo -e "  ${RED}Frontend${NC} 已停止"
    fi
    
    # Gateway 状态
    if [ -n "$gateway_pid" ]; then
        local gateway_mem=$(ps -o rss= -p "$gateway_pid" 2>/dev/null | awk '{printf "%.1f MB", $1/1024}')
        local gateway_cpu=$(ps -o %cpu= -p "$gateway_pid" 2>/dev/null | awk '{printf "%.1f%%", $1}')
        if [ -n "$gateway_mem" ] && [ -n "$gateway_cpu" ]; then
            echo -e "  ${GREEN}Gateway${NC}  PID: $gateway_pid  CPU: $gateway_cpu  Memory: $gateway_mem  Port: $gateway_port"
        else
            echo -e "  ${GREEN}Gateway${NC}  PID: $gateway_pid  Port: $gateway_port"
        fi
    else
        echo -e "  ${RED}Gateway${NC}  已停止"
    fi
    
    echo ""
    echo -e "${CYAN}访问地址:${NC}"
    echo -e "  Web UI:   http://localhost:3000"
    echo -e "  Backend:  http://localhost:8000"
    echo -e "  Gateway:  http://localhost:$gateway_port"
    local local_ip=$(get_local_ip)
    if [ -n "$local_ip" ]; then
        echo ""
        echo -e "${CYAN}局域网访问(需管理员令牌):${NC}"
        echo -e "  Web UI:   http://$local_ip:3000"
        echo -e "  Backend:  http://$local_ip:8000"
        echo ""
        echo -e "${YELLOW}远程访问提示:${NC}"
        echo -e "  默认仅本机直连；远程访问前请先在 $(display_config_file_rel) 中配置 gateway.adminToken"
        echo -e "  浏览器远程访问还需在 localStorage.horbotAdminToken 中写入同一令牌"
    fi
    echo ""
    echo -e "${CYAN}日志文件:${NC}"
    echo -e "  Frontend: $LOG_DIR/frontend.log"
    echo -e "  Backend:  $LOG_DIR/backend.log"
    echo -e "  Gateway:  $LOG_DIR/gateway.log"
    echo ""
    echo -e "${CYAN}常用命令:${NC}"
    echo -e "  ${RED}./horbot.sh stop${NC}      停止服务"
    echo -e "  ${YELLOW}./horbot.sh restart${NC}   重启服务"
    echo -e "  ${BLUE}./horbot.sh logs backend${NC}  查看后端日志"
    echo ""
    echo -e "${CYAN}配置文件:${NC}"
    echo -e "  配置文件: $(display_config_file_rel)"
    echo ""
}

# 查看日志
logs() {
    local service=$1
    local log_file="$LOG_DIR/${service}.log"
    
    if [ -f "$log_file" ]; then
        tail -f "$log_file"
    else
        print_error "日志文件不存在: $log_file"
    fi
}

# 重启服务
restart() {
    local service=$1
    
    case $service in
        backend)
            stop_service backend
            start_backend
            ;;
        frontend)
            stop_service frontend
            start_frontend
            ;;
        gateway)
            stop_service gateway
            start_gateway
            ;;
        all)
            stop_all
            echo ""
            start_all
            ;;
        *)
            print_error "未知服务: $service"
            return 1
            ;;
    esac
}

# 运行烟雾测试
smoke_chat_ui() {
    ensure_dirs

    local script="$PROJECT_ROOT/scripts/chat_ui_smoke.py"
    if [ ! -f "$script" ]; then
        print_error "烟测脚本不存在: $script"
        return 1
    fi

    local python_cmd="python3"
    if [ -x "$VENV_DIR/bin/python" ]; then
        python_cmd="$VENV_DIR/bin/python"
    fi

    local browser_path="$PROJECT_ROOT/.playwright-browsers"

    ensure_browser_services_ready

    print_info "运行聊天页面烟雾测试..."
    PLAYWRIGHT_BROWSERS_PATH="$browser_path" "$python_cmd" "$script" --scenario team "$@"
}

smoke_dm_chat() {
    ensure_dirs

    local script="$PROJECT_ROOT/scripts/chat_ui_smoke.py"
    if [ ! -f "$script" ]; then
        print_error "烟测脚本不存在: $script"
        return 1
    fi

    local python_cmd="python3"
    if [ -x "$VENV_DIR/bin/python" ]; then
        python_cmd="$VENV_DIR/bin/python"
    fi

    local browser_path="$PROJECT_ROOT/.playwright-browsers"

    ensure_browser_services_ready

    print_info "运行单聊页面烟雾测试..."
    PLAYWRIGHT_BROWSERS_PATH="$browser_path" "$python_cmd" "$script" --scenario dm "$@"
}

smoke_dm_team_dispatch() {
    ensure_dirs

    local script="$PROJECT_ROOT/scripts/chat_ui_smoke.py"
    if [ ! -f "$script" ]; then
        print_error "私聊触发团队群聊烟测脚本不存在: $script"
        return 1
    fi

    local python_cmd="python3"
    if [ -x "$VENV_DIR/bin/python" ]; then
        python_cmd="$VENV_DIR/bin/python"
    fi

    local browser_path="$PROJECT_ROOT/.playwright-browsers"

    ensure_browser_services_ready

    print_info "运行私聊触发团队群聊烟雾测试..."
    PLAYWRIGHT_BROWSERS_PATH="$browser_path" "$python_cmd" "$script" --scenario dm-team-dispatch "$@"
}

smoke_team_chat() {
    smoke_chat_ui "$@"
}

smoke_chat_attachments() {
    ensure_dirs

    local script="$PROJECT_ROOT/scripts/chat_ui_smoke.py"
    if [ ! -f "$script" ]; then
        print_error "附件聊天烟测脚本不存在: $script"
        return 1
    fi

    local python_cmd="python3"
    if [ -x "$VENV_DIR/bin/python" ]; then
        python_cmd="$VENV_DIR/bin/python"
    fi

    local browser_path="$PROJECT_ROOT/.playwright-browsers"

    ensure_browser_services_ready

    print_info "运行聊天附件烟雾测试..."
    PLAYWRIGHT_BROWSERS_PATH="$browser_path" "$python_cmd" "$script" --scenario attachments "$@"
}

smoke_chat_office_attachments() {
    ensure_dirs

    local script="$PROJECT_ROOT/scripts/chat_ui_smoke.py"
    if [ ! -f "$script" ]; then
        print_error "办公附件聊天烟测脚本不存在: $script"
        return 1
    fi

    local python_cmd="python3"
    if [ -x "$VENV_DIR/bin/python" ]; then
        python_cmd="$VENV_DIR/bin/python"
    fi

    local browser_path="$PROJECT_ROOT/.playwright-browsers"

    ensure_browser_services_ready

    print_info "运行办公附件烟雾测试..."
    PLAYWRIGHT_BROWSERS_PATH="$browser_path" "$python_cmd" "$script" --scenario office-attachments "$@"
}

smoke_chat_media_attachments() {
    ensure_dirs

    local script="$PROJECT_ROOT/scripts/chat_ui_smoke.py"
    if [ ! -f "$script" ]; then
        print_error "媒体附件聊天烟测脚本不存在: $script"
        return 1
    fi

    local python_cmd="python3"
    if [ -x "$VENV_DIR/bin/python" ]; then
        python_cmd="$VENV_DIR/bin/python"
    fi

    local browser_path="$PROJECT_ROOT/.playwright-browsers"

    ensure_browser_services_ready

    print_info "运行图片与音频识别烟雾测试..."
    PLAYWRIGHT_BROWSERS_PATH="$browser_path" "$python_cmd" "$script" --scenario media-attachments "$@"
}

smoke_chat_paste_attachments() {
    ensure_dirs

    local script="$PROJECT_ROOT/scripts/chat_ui_smoke.py"
    if [ ! -f "$script" ]; then
        print_error "粘贴附件聊天烟测脚本不存在: $script"
        return 1
    fi

    local python_cmd="python3"
    if [ -x "$VENV_DIR/bin/python" ]; then
        python_cmd="$VENV_DIR/bin/python"
    fi

    local browser_path="$PROJECT_ROOT/.playwright-browsers"

    ensure_browser_services_ready

    print_info "运行粘贴图片/文件烟雾测试..."
    PLAYWRIGHT_BROWSERS_PATH="$browser_path" "$python_cmd" "$script" --scenario paste-attachments "$@"
}

smoke_chat_drag_attachments() {
    ensure_dirs

    local script="$PROJECT_ROOT/scripts/chat_ui_smoke.py"
    if [ ! -f "$script" ]; then
        print_error "拖拽附件聊天烟测脚本不存在: $script"
        return 1
    fi

    local python_cmd="python3"
    if [ -x "$VENV_DIR/bin/python" ]; then
        python_cmd="$VENV_DIR/bin/python"
    fi

    local browser_path="$PROJECT_ROOT/.playwright-browsers"

    ensure_browser_services_ready

    print_info "运行拖拽上传附件烟雾测试..."
    PLAYWRIGHT_BROWSERS_PATH="$browser_path" "$python_cmd" "$script" --scenario drag-attachments "$@"
}

smoke_chat_retry_attachments() {
    ensure_dirs

    local script="$PROJECT_ROOT/scripts/chat_ui_smoke.py"
    if [ ! -f "$script" ]; then
        print_error "附件失败重试烟测脚本不存在: $script"
        return 1
    fi

    local python_cmd="python3"
    if [ -x "$VENV_DIR/bin/python" ]; then
        python_cmd="$VENV_DIR/bin/python"
    fi

    local browser_path="$PROJECT_ROOT/.playwright-browsers"

    ensure_browser_services_ready

    print_info "运行附件失败后重试烟雾测试..."
    PLAYWRIGHT_BROWSERS_PATH="$browser_path" "$python_cmd" "$script" --scenario retry-attachments "$@"
}

smoke_chat_order_attachments() {
    ensure_dirs

    local script="$PROJECT_ROOT/scripts/chat_ui_smoke.py"
    if [ ! -f "$script" ]; then
        print_error "附件顺序烟测脚本不存在: $script"
        return 1
    fi

    local python_cmd="python3"
    if [ -x "$VENV_DIR/bin/python" ]; then
        python_cmd="$VENV_DIR/bin/python"
    fi

    local browser_path="$PROJECT_ROOT/.playwright-browsers"

    ensure_browser_services_ready

    print_info "运行附件重排顺序烟雾测试..."
    PLAYWRIGHT_BROWSERS_PATH="$browser_path" "$python_cmd" "$script" --scenario order-attachments "$@"
}

smoke_chat_interrupt() {
    ensure_dirs

    local script="$PROJECT_ROOT/scripts/chat_ui_interrupt_smoke.py"
    if [ ! -f "$script" ]; then
        print_error "接力中断烟测脚本不存在: $script"
        return 1
    fi

    local python_cmd="python3"
    if [ -x "$VENV_DIR/bin/python" ]; then
        python_cmd="$VENV_DIR/bin/python"
    fi

    local browser_path="$PROJECT_ROOT/.playwright-browsers"

    ensure_browser_services_ready

    print_info "运行团队接力中断烟雾测试..."
    PLAYWRIGHT_BROWSERS_PATH="$browser_path" "$python_cmd" "$script" "$@"
}

smoke_chat_error_retry() {
    ensure_dirs

    local script="$PROJECT_ROOT/scripts/chat_ui_error_retry_smoke.py"
    if [ ! -f "$script" ]; then
        print_error "错误重试烟测脚本不存在: $script"
        return 1
    fi

    local python_cmd="python3"
    if [ -x "$VENV_DIR/bin/python" ]; then
        python_cmd="$VENV_DIR/bin/python"
    fi

    local browser_path="$PROJECT_ROOT/.playwright-browsers"

    ensure_browser_services_ready

    print_info "运行聊天错误重试烟雾测试..."
    PLAYWRIGHT_BROWSERS_PATH="$browser_path" "$python_cmd" "$script" "$@"
}

smoke_chat_memory_trace() {
    ensure_dirs

    local script="$PROJECT_ROOT/scripts/chat_ui_memory_trace_smoke.py"
    if [ ! -f "$script" ]; then
        print_error "记忆引用烟测脚本不存在: $script"
        return 1
    fi

    local python_cmd="python3"
    if [ -x "$VENV_DIR/bin/python" ]; then
        python_cmd="$VENV_DIR/bin/python"
    fi

    local browser_path="$PROJECT_ROOT/.playwright-browsers"

    ensure_browser_services_ready

    print_info "运行聊天记忆引用详情烟雾测试..."
    PLAYWRIGHT_BROWSERS_PATH="$browser_path" "$python_cmd" "$script" "$@"
}

smoke_mock_relay() {
    ensure_dirs

    local script="$PROJECT_ROOT/scripts/chat_relay_mock_e2e.py"
    if [ ! -f "$script" ]; then
        print_error "Mock relay 烟测脚本不存在: $script"
        return 1
    fi

    local python_cmd="python3"
    if [ -x "$VENV_DIR/bin/python" ]; then
        python_cmd="$VENV_DIR/bin/python"
    fi

    print_info "运行本地 mock relay SSE 回归..."
    "$python_cmd" "$script"
}

smoke_external_inbound_memory() {
    ensure_dirs

    local script="$PROJECT_ROOT/scripts/external_inbound_memory_smoke.py"
    if [ ! -f "$script" ]; then
        print_error "外部入站来源记忆烟测脚本不存在: $script"
        return 1
    fi

    local python_cmd="python3"
    if [ -x "$VENV_DIR/bin/python" ]; then
        python_cmd="$VENV_DIR/bin/python"
    fi

    print_info "运行外部入站 -> 执行 -> 来源记忆元数据烟雾测试..."
    "$python_cmd" "$script" "$@"
}

smoke_bound_channel_dispatch() {
    ensure_dirs

    local script="$PROJECT_ROOT/scripts/bound_channel_dispatch_smoke.py"
    if [ ! -f "$script" ]; then
        print_error "绑定外部渠道路由烟测脚本不存在: $script"
        return 1
    fi

    local python_cmd="python3"
    if [ -x "$VENV_DIR/bin/python" ]; then
        python_cmd="$VENV_DIR/bin/python"
    fi

    print_info "运行单聊 -> Agent 工具调用 -> 绑定外部渠道路由烟雾测试..."
    "$python_cmd" "$script" "$@"
}

smoke_dashboard() {
    ensure_dirs

    local script="$PROJECT_ROOT/scripts/dashboard_smoke.py"
    if [ ! -f "$script" ]; then
        print_error "Dashboard 烟测脚本不存在: $script"
        return 1
    fi

    local python_cmd="python3"
    if [ -x "$VENV_DIR/bin/python" ]; then
        python_cmd="$VENV_DIR/bin/python"
    fi

    local browser_path="$PROJECT_ROOT/.playwright-browsers"
    mkdir -p "$browser_path"

    ensure_browser_services_ready
    print_info "运行 Dashboard 烟雾测试..."
    PLAYWRIGHT_BROWSERS_PATH="$browser_path" "$python_cmd" "$script" "$@"
}

smoke_config() {
    ensure_dirs

    local script="$PROJECT_ROOT/scripts/config_smoke.py"
    if [ ! -f "$script" ]; then
        print_error "Configuration 烟测脚本不存在: $script"
        return 1
    fi

    local python_cmd="python3"
    if [ -x "$VENV_DIR/bin/python" ]; then
        python_cmd="$VENV_DIR/bin/python"
    fi

    local browser_path="$PROJECT_ROOT/.playwright-browsers"
    mkdir -p "$browser_path"

    ensure_browser_services_ready
    print_info "运行 Configuration 烟雾测试..."
    PLAYWRIGHT_BROWSERS_PATH="$browser_path" "$python_cmd" "$script" "$@"
}

smoke_agent_assets() {
    ensure_dirs

    local script="$PROJECT_ROOT/scripts/agent_assets_smoke.py"
    if [ ! -f "$script" ]; then
        print_error "Agent 资产烟测脚本不存在: $script"
        return 1
    fi

    local python_cmd="python3"
    if [ -x "$VENV_DIR/bin/python" ]; then
        python_cmd="$VENV_DIR/bin/python"
    fi

    local browser_path="$PROJECT_ROOT/.playwright-browsers"
    mkdir -p "$browser_path"

    ensure_browser_services_ready
    print_info "运行 Agent 资产管理烟雾测试..."
    PLAYWRIGHT_BROWSERS_PATH="$browser_path" "$python_cmd" "$script" "$@"
}

smoke_skills() {
    ensure_dirs

    local script="$PROJECT_ROOT/scripts/skills_smoke.py"
    if [ ! -f "$script" ]; then
        print_error "Skills 烟测脚本不存在: $script"
        return 1
    fi

    local python_cmd="python3"
    if [ -x "$VENV_DIR/bin/python" ]; then
        python_cmd="$VENV_DIR/bin/python"
    fi

    local browser_path="$PROJECT_ROOT/.playwright-browsers"
    mkdir -p "$browser_path"

    ensure_browser_services_ready
    print_info "运行 Skills 烟雾测试..."
    PLAYWRIGHT_BROWSERS_PATH="$browser_path" "$python_cmd" "$script" "$@"
}

smoke_performance() {
    ensure_dirs

    local script="$PROJECT_ROOT/scripts/performance_smoke.py"
    if [ ! -f "$script" ]; then
        print_error "Performance 烟测脚本不存在: $script"
        return 1
    fi

    local python_cmd="python3"
    if [ -x "$VENV_DIR/bin/python" ]; then
        python_cmd="$VENV_DIR/bin/python"
    fi

    local browser_path="$PROJECT_ROOT/.playwright-browsers"
    mkdir -p "$browser_path"

    ensure_browser_services_ready
    print_info "运行 Performance 烟雾测试..."
    PLAYWRIGHT_BROWSERS_PATH="$browser_path" "$python_cmd" "$script" "$@"
}

smoke_all() {
    local exit_code=0

    smoke_mock_relay || exit_code=$?
    smoke_external_inbound_memory || exit_code=$?
    smoke_bound_channel_dispatch || exit_code=$?
    smoke_browser_e2e "$@" || exit_code=$?

    return "$exit_code"
}

smoke_browser_e2e() {
    local exit_code=0

    smoke_config "$@" || exit_code=$?
    smoke_agent_assets "$@" || exit_code=$?
    smoke_dashboard "$@" || exit_code=$?
    smoke_skills "$@" || exit_code=$?
    smoke_performance "$@" || exit_code=$?
    smoke_chat_error_retry "$@" || exit_code=$?
    smoke_chat_memory_trace "$@" || exit_code=$?
    smoke_chat_interrupt "$@" || exit_code=$?
    smoke_chat_attachments "$@" || exit_code=$?
    smoke_chat_office_attachments "$@" || exit_code=$?
    smoke_chat_media_attachments "$@" || exit_code=$?
    smoke_chat_paste_attachments "$@" || exit_code=$?
    smoke_chat_drag_attachments "$@" || exit_code=$?
    smoke_chat_retry_attachments "$@" || exit_code=$?
    smoke_chat_order_attachments "$@" || exit_code=$?
    smoke_dm_chat "$@" || exit_code=$?
    smoke_dm_team_dispatch "$@" || exit_code=$?
    smoke_team_chat "$@" || exit_code=$?

    return "$exit_code"
}

smoke_test() {
    local target="${1:-chat-ui}"
    shift || true

    case "$target" in
        all)
            smoke_all "$@"
            ;;
        mock-relay)
            smoke_mock_relay "$@"
            ;;
        external-inbound-memory)
            smoke_external_inbound_memory "$@"
            ;;
        bound-channel-dispatch)
            smoke_bound_channel_dispatch "$@"
            ;;
        browser-e2e)
            smoke_browser_e2e "$@"
            ;;
        chat-error-retry)
            smoke_chat_error_retry "$@"
            ;;
        chat-memory)
            smoke_chat_memory_trace "$@"
            ;;
        chat-attachments)
            smoke_chat_attachments "$@"
            ;;
        chat-office-attachments)
            smoke_chat_office_attachments "$@"
            ;;
        chat-media)
            smoke_chat_media_attachments "$@"
            ;;
        chat-paste)
            smoke_chat_paste_attachments "$@"
            ;;
        chat-drag)
            smoke_chat_drag_attachments "$@"
            ;;
        chat-retry-attachments)
            smoke_chat_retry_attachments "$@"
            ;;
        chat-order-attachments)
            smoke_chat_order_attachments "$@"
            ;;
        dashboard)
            smoke_dashboard "$@"
            ;;
        config)
            smoke_config "$@"
            ;;
        agent-assets)
            smoke_agent_assets "$@"
            ;;
        skills)
            smoke_skills "$@"
            ;;
        performance)
            smoke_performance "$@"
            ;;
        chat-interrupt)
            smoke_chat_interrupt "$@"
            ;;
        chat-ui)
            smoke_chat_ui "$@"
            ;;
        team-chat)
            smoke_team_chat "$@"
            ;;
        dm-chat)
            smoke_dm_chat "$@"
            ;;
        dm-team-dispatch)
            smoke_dm_team_dispatch "$@"
            ;;
        *)
            print_error "未知烟测目标: $target"
            return 1
            ;;
    esac
}
# 显示帮助
show_help() {
    print_logo
    echo "用法: $0 <命令> [参数]"
    echo ""
    echo "命令:"
    echo "  check              检查所有依赖"
    echo "  check backend      检查后端依赖"
    echo "  check frontend     检查前端依赖"
    echo ""
    echo "  install            安装所有依赖并创建默认配置"
    echo "  install backend    安装后端依赖"
    echo "  install frontend   安装前端依赖"
    echo ""
    echo "  config             创建默认配置文件"
    echo ""
    echo "  start              启动所有服务"
    echo "  start backend      启动后端服务"
    echo "  start frontend     启动前端服务"
    echo "  start gateway      启动 Gateway 服务"
    echo ""
    echo "  stop               停止所有服务"
    echo "  stop backend       停止后端服务"
    echo "  stop frontend      停止前端服务"
    echo "  stop gateway       停止 Gateway 服务"
    echo ""
    echo "  restart            重启所有服务"
    echo "  restart <service>  重启指定服务 (backend/frontend/gateway)"
    echo ""
    echo "  archive legacy-main-workspace  归档旧主 Agent 工作区和错误嵌套残留"
    echo ""
    echo "  smoke all          运行全部聊天烟雾测试"
    echo "  smoke mock-relay   运行本地 mock relay SSE 回归"
    echo "  smoke external-inbound-memory  运行外部入站 -> agent 执行 -> 来源记忆元数据回查烟雾测试"
    echo "  smoke bound-channel-dispatch  运行单聊 -> Agent 工具调用 -> 绑定外部渠道路由烟雾测试"
    echo "  smoke browser-e2e  运行真实浏览器端到端回归（Configuration + Agent 资产 + Dashboard + Skills + Performance + 失败重试 + 记忆引用 + 接力中断 + 附件上传 + 办公附件上传 + 图片/音频识别 + 粘贴上传 + 拖拽上传 + 附件重试 + 附件顺序 + 单聊 + 团队接力）"
    echo "  smoke config       运行 Configuration 页面烟雾测试"
    echo "  smoke agent-assets 运行多 Agent 页面资产管理烟雾测试"
    echo "  smoke dashboard    运行 Dashboard 页面烟雾测试"
    echo "  smoke skills       运行 Skills 页面烟雾测试"
    echo "  smoke performance  运行关键页面性能采样烟雾测试"
    echo "  smoke chat-error-retry  运行聊天失败态与重试烟雾测试"
    echo "  smoke chat-interrupt  运行团队接力停止/打断烟雾测试"
    echo "  smoke chat-memory  运行聊天记忆引用详情烟雾测试"
    echo "  smoke chat-attachments  运行聊天附件上传（PDF/DOCX）烟雾测试"
    echo "  smoke chat-office-attachments  运行聊天办公附件上传（XLSX/PPTX）烟雾测试"
    echo "  smoke chat-media   运行图片与音频识别烟雾测试"
    echo "  smoke chat-paste   运行 Cmd/Ctrl+V 粘贴图片/文件烟雾测试"
    echo "  smoke chat-drag    运行拖拽上传图片/文件烟雾测试"
    echo "  smoke chat-retry-attachments  运行附件失败后保留并重试烟雾测试"
    echo "  smoke chat-order-attachments  运行附件重排后请求顺序一致烟雾测试"
    echo "  smoke chat-ui      运行团队接力聊天页面烟雾测试"
    echo "  smoke team-chat    运行团队接力聊天页面烟雾测试"
    echo "  smoke dm-chat      运行单聊页面烟雾测试"
    echo "  smoke dm-team-dispatch  运行私聊触发团队群聊与群内接力烟雾测试"
    echo "  smoke chat-ui --headed  可视化运行聊天页面烟雾测试"
    echo ""
    echo "  status             查看服务状态"
    echo "  logs <service>     查看服务日志 (backend/frontend/gateway)"
    echo ""
    echo "  dev                开发模式（启动后端和前端，带热重载）"
    echo "  help               显示此帮助信息"
    echo ""
    echo "配置文件: $(display_config_file_rel)"
    echo ""
}

# 开发模式
dev_mode() {
    print_info "启动开发模式..."
    
    if [ -d "$VENV_DIR" ]; then
        source "$VENV_DIR/bin/activate"
    fi
    
    cd "$FRONTEND_DIR"
    if [ ! -d "node_modules" ]; then
        print_error "前端依赖未安装，请先运行: $0 install frontend"
        return 1
    fi
    cd "$PROJECT_ROOT"
    
    print_info "启动后端服务（带热重载）..."
    python -m uvicorn horbot.web.main:app --host 127.0.0.1 --port 8000 --reload &
    local BACKEND_PID=$!
    
    sleep 2
    
    print_info "启动前端服务（带热重载）..."
    cd "$FRONTEND_DIR"
    npm run dev &
    local FRONTEND_PID=$!
    cd "$PROJECT_ROOT"
    
    echo ""
    print_success "开发模式已启动"
    print_info "后端地址: http://localhost:8000"
    print_info "前端地址: http://localhost:3000"
    print_info "按 Ctrl+C 停止所有服务"
    echo ""
    
    cleanup_dev_mode() {
        trap - SIGINT SIGTERM EXIT
        terminate_pid_tree "$BACKEND_PID"
        terminate_pid_tree "$FRONTEND_PID"
        cleanup_port 8000 >/dev/null 2>&1 || true
        cleanup_port 3000 >/dev/null 2>&1 || true
        print_success "服务已停止"
    }

    trap "cleanup_dev_mode; exit 0" SIGINT SIGTERM
    trap "cleanup_dev_mode" EXIT
    
    wait
}

# 主入口
main() {
    if [ $# -eq 0 ]; then
        show_help
        exit 0
    fi
    
    case "$1" in
        check)
            case "${2:-all}" in
                all) check_all ;;
                backend) check_backend ;;
                frontend) check_frontend ;;
                *) print_error "未知参数: $2"; show_help; exit 1 ;;
            esac
            ;;
        install)
            case "${2:-all}" in
                all) install_all ;;
                backend) install_backend ;;
                frontend) install_frontend ;;
                *) print_error "未知参数: $2"; show_help; exit 1 ;;
            esac
            ;;
        start)
            case "${2:-all}" in
                all) start_all ;;
                backend) start_backend ;;
                frontend) start_frontend ;;
                gateway) start_gateway ;;
                *) print_error "未知参数: $2"; show_help; exit 1 ;;
            esac
            ;;
        stop)
            case "${2:-all}" in
                all) stop_all ;;
                backend) stop_service backend ;;
                frontend) stop_service frontend ;;
                gateway) stop_service gateway ;;
                *) print_error "未知参数: $2"; show_help; exit 1 ;;
            esac
            ;;
        restart)
            restart "${2:-all}"
            ;;        smoke)
            smoke_test "${2:-chat-ui}" "${@:3}"
            ;;
        status)
            status
            ;;
        logs)
            if [ -z "$2" ]; then
                print_error "请指定服务名称: backend, frontend, gateway"
                exit 1
            fi
            logs "$2"
            ;;
        config)
            create_default_config
            ;;
        dev)
            dev_mode
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
