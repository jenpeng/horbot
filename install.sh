#!/bin/bash

# horbot 安装脚本
# 自动创建 Python 虚拟环境并安装所有依赖

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${PROJECT_DIR}/.venv"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}    horbot 安装脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查 Python 版本
check_python_version() {
    local python_cmd=$1
    local version=$($python_cmd --version 2>&1 | awk '{print $2}')
    local major=$(echo $version | cut -d. -f1)
    local minor=$(echo $version | cut -d. -f2)
    
    if [ "$major" -lt 3 ] || ([ "$major" -eq 3 ] && [ "$minor" -lt 11 ]); then
        return 1
    fi
    return 0
}

# 查找合适的 Python 版本
find_python() {
    for cmd in python3.12 python3.11 python3 python; do
        if command -v $cmd &> /dev/null; then
            if check_python_version $cmd; then
                echo $cmd
                return 0
            fi
        fi
    done
    return 1
}

# 检查 Python
echo -e "${YELLOW}[1/4] 检查 Python 环境...${NC}"
PYTHON_CMD=$(find_python)
if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}错误: 未找到 Python 3.11 或更高版本${NC}"
    echo "请安装 Python 3.11+ 后重试"
    exit 1
fi
PYTHON_VERSION=$($PYTHON_CMD --version)
echo -e "${GREEN}✓ 找到 Python: ${PYTHON_VERSION}${NC}"
echo ""

# 检查或创建虚拟环境
echo -e "${YELLOW}[2/4] 检查虚拟环境...${NC}"
if [ -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}虚拟环境已存在: ${VENV_DIR}${NC}"
    read -p "是否删除并重新创建? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}删除现有虚拟环境...${NC}"
        rm -rf "$VENV_DIR"
    else
        echo -e "${BLUE}保留现有虚拟环境，继续安装依赖...${NC}"
    fi
fi

if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}创建虚拟环境: ${VENV_DIR}${NC}"
    $PYTHON_CMD -m venv "$VENV_DIR"
    echo -e "${GREEN}✓ 虚拟环境创建成功${NC}"
fi
echo ""

# 安装依赖
echo -e "${YELLOW}[3/4] 安装依赖...${NC}"
source "${VENV_DIR}/bin/activate"

# 升级 pip
echo -e "${BLUE}升级 pip...${NC}"
pip install --upgrade pip -q

# 安装项目依赖
echo -e "${BLUE}安装项目依赖...${NC}"
if [ -f "${PROJECT_DIR}/pyproject.toml" ]; then
    pip install -e "${PROJECT_DIR}" -q
elif [ -f "${PROJECT_DIR}/requirements.txt" ]; then
    pip install -r "${PROJECT_DIR}/requirements.txt" -q
else
    echo -e "${RED}错误: 未找到 pyproject.toml 或 requirements.txt${NC}"
    exit 1
fi

echo -e "${GREEN}✓ 依赖安装完成${NC}"
echo ""

# 构建前端代码
echo -e "${YELLOW}[4/5] 构建前端代码...${NC}"
frontend_dir="${PROJECT_DIR}/horbot/web/frontend"
if [ -d "$frontend_dir" ] && [ -f "$frontend_dir/package.json" ]; then
    echo -e "${BLUE}检查前端依赖...${NC}"
    if command -v npm &> /dev/null; then
        cd "$frontend_dir"
        npm install -q
        echo -e "${BLUE}构建前端代码...${NC}"
        npm run build -q
        # 创建 build 目录并复制 dist 内容
        mkdir -p build
        cp -r dist/* build/
        cd "$PROJECT_DIR"
        echo -e "${GREEN}✓ 前端代码构建完成${NC}"
    else
        echo -e "${YELLOW}⚠ npm 未安装，跳过前端代码构建${NC}"
    fi
else
    echo -e "${YELLOW}⚠ 前端目录不存在，跳过前端代码构建${NC}"
fi
echo ""

# 验证安装
echo -e "${YELLOW}[5/5] 验证安装...${NC}"
if [ -x "${VENV_DIR}/bin/horbot" ]; then
    HORBOT_VERSION=$("${VENV_DIR}/bin/horbot" --version 2>&1 || echo "unknown")
    echo -e "${GREEN}✓ horbot 安装成功${NC}"
    echo -e "${BLUE}版本: ${HORBOT_VERSION}${NC}"
else
    echo -e "${YELLOW}⚠ horbot 命令不可用，请手动验证${NC}"
fi
echo ""

# 显示完成信息
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}    安装完成!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "虚拟环境位置: ${BLUE}${VENV_DIR}${NC}"
echo ""
echo -e "${YELLOW}后续步骤:${NC}"
echo -e "  1. 激活虚拟环境:"
echo -e "     ${BLUE}source .venv/bin/activate${NC}"
echo ""
echo -e "  2. 或使用启动脚本运行:"
echo -e "     ${BLUE}./run.sh --help${NC}"
echo -e "     或者使用:"
echo -e "     ${BLUE}./run-web.sh}"
echo ""
echo -e "  3. 配置 horbot:"
echo -e "     ${BLUE}horbot config init${NC}"
echo ""
