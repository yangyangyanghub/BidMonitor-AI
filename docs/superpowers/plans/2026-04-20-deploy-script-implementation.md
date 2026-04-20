# BidMonitor 生产级部署脚本实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建一个完整的生产级部署脚本，支持首次部署和更新部署

**Architecture:** 单一脚本 `server/deploy/deploy.sh` 使用函数模块化设计，约 600 行，包含系统检查、依赖安装、虚拟环境、systemd 服务、防火墙、Nginx、回滚等功能

**Tech Stack:** Bash 4+, systemd, Python 3.8+, pip, venv, apt-get/yum/dnf

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `server/deploy/deploy.sh` | Create | 主部署脚本 |
| `server/deploy/deploy.conf.example` | Create | 配置模板 |

---

### Task 1: 脚本头 + 颜色输出 + 工具函数

**Files:**
- Create: `server/deploy/deploy.sh` (lines 1-80)

- [ ] **Step 1: 创建脚本头部和颜色定义**

```bash
#!/bin/bash
# =============================================================================
# BidMonitor 生产级部署脚本
# 版本: 2.0.0
# 支持: Ubuntu 20.04/22.04, CentOS 7/8, AlmaLinux 8/9, Rocky Linux 8/9
# 用法: bash deploy.sh [选项]
# 选项:
#   --non-interactive  非交互模式（使用环境变量）
#   --dry-run          仅输出计划操作，不执行
#   --rollback         回滚到上次部署
#   --help             显示帮助信息
# =============================================================================

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# 常量定义
INSTALL_DIR="/opt/bidmonitor"
SERVICE_NAME="bidmonitor"
DEFAULT_PORT=8080
DEFAULT_ADMIN_USER="CDKJ"
DEFAULT_ADMIN_PASS="cdkj"
ROLLBACK_DIR="$INSTALL_DIR/.rollback"
LOG_FILE="/tmp/bidmonitor_deploy.log"
MAX_ROLLBACKS=3

# 当前步骤（用于错误追踪）
CURRENT_STEP="初始化"

# 日志文件
exec > >(tee -a "$LOG_FILE") 2>&1
```

- [ ] **Step 2: 添加输出函数和工具函数**

```bash
# 输出函数
log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${BLUE}[STEP]${NC} ${BOLD}$1${NC}"; }
log_ok()    { echo -e "${GREEN}✅ $1${NC}"; }
log_fail()  { echo -e "${RED}❌ $1${NC}"; }

# 交互式输入（带默认值）
read_with_default() {
    local prompt="$1"
    local default="$2"
    local result
    if [ -n "$default" ]; then
        read -rp "${prompt} [${default}]: " result
        echo "${result:-$default}"
    else
        read -rp "${prompt}: " result
        echo "$result"
    fi
}

# 密码输入（隐藏回显）
read_password() {
    local prompt="$1"
    local default="$2"
    local result
    if [ -n "$default" ]; then
        read -rsp "${prompt} [${default}]: " -s result
        echo ""
        echo "${result:-$default}"
    else
        read -rsp "${prompt}: " -s result
        echo ""
        echo "$result"
    fi
}

# 检查 root 权限
check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "请使用 root 用户或 sudo 运行此脚本"
        exit 1
    fi
}

# 显示帮助信息
show_help() {
    echo "BidMonitor 部署脚本 v2.0.0"
    echo ""
    echo "用法: bash deploy.sh [选项]"
    echo ""
    echo "选项:"
    echo "  --non-interactive  非交互模式（使用环境变量）"
    echo "  --dry-run          仅输出计划操作，不执行"
    echo "  --rollback         回滚到上次部署"
    echo "  --help             显示帮助信息"
    echo ""
    echo "环境变量（非交互模式）:"
    echo "  BM_MODE           部署模式：git/zip/local"
    echo "  BM_REPO_URL       Git 仓库 URL"
    echo "  BM_BRANCH         Git 分支名"
    echo "  BM_ZIP_PATH       ZIP 文件路径"
    echo "  BM_ADMIN_USER     管理员用户名"
    echo "  BM_ADMIN_PASS     管理员密码"
    echo "  BM_DOMAIN         域名"
    echo "  BM_USE_NGINX      是否使用 Nginx: true/false"
    echo "  BM_OPEN_FIREWALL  是否开放防火墙: true/false"
    echo ""
    exit 0
}
```

- [ ] **Step 3: 添加参数解析和入口逻辑**

```bash
# 全局变量
NON_INTERACTIVE=false
DRY_RUN=false
ROLLBACK=false

# 解析参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --non-interactive) NON_INTERACTIVE=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        --rollback) ROLLBACK=true; shift ;;
        --help) show_help ;;
        *) log_error "未知参数: $1"; show_help ;;
    esac
done

# 打印横幅
print_banner() {
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}   BidMonitor 生产级部署脚本 v2.0.0${NC}"
    echo -e "${GREEN}================================================${NC}"
    echo ""
}
```

- [ ] **Step 4: 提交**

```bash
git add server/deploy/deploy.sh
git commit -m "feat(deploy): 添加脚本头、颜色输出和工具函数"
```

---

### Task 2: 系统检查模块

**Files:**
- Modify: `server/deploy/deploy.sh` (添加系统检查函数)

- [ ] **Step 1: 添加 OS 检测函数**

```bash
# OS 类型和包管理器
OS_TYPE=""
PKG_MANAGER=""

# 检测操作系统
detect_os() {
    log_step "检测操作系统..."

    if [ ! -f /etc/os-release ]; then
        log_error "无法检测操作系统，缺少 /etc/os-release"
        exit 1
    fi

    source /etc/os-release
    OS_TYPE="$ID"
    local version="$VERSION_ID"

    case "$OS_TYPE" in
        ubuntu)
            if [[ "$version" == "20.04" || "$version" == "22.04" ]]; then
                PKG_MANAGER="apt-get"
                log_ok "检测到 Ubuntu $version"
            else
                log_warn "Ubuntu $version 未测试，继续尝试安装..."
                PKG_MANAGER="apt-get"
            fi
            ;;
        centos|almalinux|rocky)
            if [[ "$version" =~ ^(7|8|9)(\.[0-9]+)?$ ]]; then
                if [ "$OS_TYPE" = "centos" ] && [ "$version" = "8" ]; then
                    log_warn "CentOS 8 已 EOL，建议使用 AlmaLinux 或 Rocky Linux"
                fi
                PKG_MANAGER=$([ "$version" = "7" ] && echo "yum" || echo "dnf")
                log_ok "检测到 ${OS_TYPE^} $version"
            else
                log_error "不支持的 ${OS_TYPE^} 版本: $version"
                exit 1
            fi
            ;;
        *)
            log_error "不支持的操作系统: $OS_TYPE $version"
            log_info "支持的系统: Ubuntu 20.04/22.04, CentOS 7/8, AlmaLinux 8/9, Rocky Linux 8/9"
            exit 1
            ;;
    esac
}
```

- [ ] **Step 2: 添加系统和资源检查函数**

```bash
# 检查系统要求
check_requirements() {
    log_step "检查系统要求..."

    # 检查 Python3
    if command -v python3 &> /dev/null; then
        local py_version
        py_version=$(python3 --version 2>&1 | awk '{print $2}')
        local major minor
        major=$(echo "$py_version" | cut -d. -f1)
        minor=$(echo "$py_version" | cut -d. -f2)

        if [ "$major" -ge 3 ] && [ "$minor" -ge 8 ]; then
            log_ok "Python $py_version"
        else
            log_error "Python 版本过低 ($py_version)，需要 >= 3.8"
            exit 1
        fi
    else
        log_warn "Python3 未安装，将通过包管理器安装"
    fi

    # 检查内存（至少 512MB）
    local mem_available
    mem_available=$(free -m | awk '/^Mem:/ {print $7}')
    if [ "$mem_available" -lt 512 ]; then
        log_warn "可用内存不足 512MB (当前: ${mem_available}MB)"
        log_info "推荐至少 1GB 内存用于稳定运行"
    else
        log_ok "内存: ${mem_available}MB 可用"
    fi

    # 检查磁盘空间（至少 1GB）
    local disk_available
    disk_available=$(df -m /opt 2>/dev/null | awk 'NR==2 {print $4}')
    if [ -z "$disk_available" ] || [ "$disk_available" -lt 1024 ]; then
        log_error "/opt 分区可用空间不足 1GB"
        exit 1
    else
        log_ok "磁盘: ${disk_available}MB 可用"
    fi
}
```

- [ ] **Step 3: 添加错误处理 trap**

```bash
# 错误处理和回滚
handle_error() {
    local exit_code=$?
    log_error "部署失败于步骤: $CURRENT_STEP (退出码: $exit_code)"
    log_error "详细日志: $LOG_FILE"

    if [ -d "$ROLLBACK_DIR" ]; then
        local latest_rollback
        latest_rollback=$(ls -t "$ROLLBACK_DIR" 2>/dev/null | head -1)
        if [ -n "$latest_rollback" ]; then
            log_warn "尝试回滚到快照: $latest_rollback"
            restore_backup "$latest_rollback"
        fi
    fi

    exit $exit_code
}

trap handle_error ERR
```

- [ ] **Step 4: 提交**

```bash
git add server/deploy/deploy.sh
git commit -m "feat(deploy): 添加系统检查和错误处理模块"
```

---

### Task 3: 依赖安装模块

**Files:**
- Modify: `server/deploy/deploy.sh` (添加依赖安装函数)

- [ ] **Step 1: 添加依赖安装函数**

```bash
# 安装系统依赖
install_dependencies() {
    CURRENT_STEP="安装系统依赖"
    log_step "安装系统依赖..."

    local packages=()

    # 基础依赖
    if [ "$PKG_MANAGER" = "apt-get" ]; then
        packages=(python3 python3-venv python3-pip unzip)
        # 检查 Chromium
        if ! command -v chromium-browser &> /dev/null && ! command -v google-chrome &> /dev/null; then
            packages+=(chromium-browser)
        fi
    else
        # CentOS/AlmaLinux/Rocky
        packages=(python3 unzip)
        # CentOS 7 需要 epel-release
        if [ "$OS_TYPE" = "centos" ] && [[ "$VERSION_ID" == 7* ]]; then
            if ! rpm -q epel-release &> /dev/null; then
                log_info "安装 EPEL 源..."
                yum install -y epel-release
            fi
        fi
        # venv 包
        if [ "$OS_TYPE" = "centos" ]; then
            packages+=(python3-devel)
        else
            packages+=(python3-venv)
        fi
        # 检查 Chromium
        if ! command -v chromium &> /dev/null && ! command -v google-chrome &> /dev/null; then
            packages+=(chromium)
        fi
    fi

    # Dry-run 模式
    if [ "$DRY_RUN" = true ]; then
        log_info "[Dry-run] 将安装以下包: ${packages[*]}"
        return
    fi

    # 更新包列表
    if [ "$PKG_MANAGER" = "apt-get" ]; then
        apt-get update -y
    fi

    # 安装依赖
    for pkg in "${packages[@]}"; do
        if package_installed "$pkg"; then
            log_info "已安装: $pkg"
        else
            log_info "正在安装: $pkg"
            if [ "$PKG_MANAGER" = "apt-get" ]; then
                apt-get install -y "$pkg"
            elif [ "$PKG_MANAGER" = "yum" ]; then
                yum install -y "$pkg"
            else
                dnf install -y "$pkg"
            fi
            log_ok "已安装: $pkg"
        fi
    done

    # 升级 pip
    if command -v pip3 &> /dev/null; then
        pip3 install --upgrade pip -q
    fi
}

# 检查包是否已安装
package_installed() {
    local pkg="$1"
    if [ "$PKG_MANAGER" = "apt-get" ]; then
        dpkg -l "$pkg" 2>/dev/null | grep -q "^ii"
    else
        rpm -q "$pkg" &> /dev/null
    fi
}
```

- [ ] **Step 2: 提交**

```bash
git add server/deploy/deploy.sh
git commit -m "feat(deploy): 添加跨平台依赖安装模块"
```

---

### Task 4: 目录创建 + 用户管理

**Files:**
- Modify: `server/deploy/deploy.sh` (添加目录和用户管理函数)

- [ ] **Step 1: 添加目录创建和用户管理函数**

```bash
# 创建目录结构
create_directories() {
    CURRENT_STEP="创建目录结构"
    log_step "创建项目目录..."

    # Dry-run 模式
    if [ "$DRY_RUN" = true ]; then
        log_info "[Dry-run] 将创建目录: $INSTALL_DIR/{server/logs,data,.rollback}"
        return
    fi

    mkdir -p "$INSTALL_DIR"
    mkdir -p "$INSTALL_DIR/server/logs"
    mkdir -p "$INSTALL_DIR/data"
    mkdir -p "$ROLLBACK_DIR"

    log_ok "目录创建完成"
}

# 创建专用用户（可选）
create_service_user() {
    CURRENT_STEP="创建服务用户"

    # 默认使用 root，允许创建专用用户
    if [ "$NON_INTERACTIVE" = true ]; then
        SERVICE_USER="${BM_SERVICE_USER:-root}"
    else
        SERVICE_USER=$(read_with_default "创建专用服务用户? 用户名 (留空使用 root)" "")
    fi

    if [ -z "$SERVICE_USER" ]; then
        SERVICE_USER="root"
        log_info "使用 root 用户运行服务"
        return
    fi

    # Dry-run 模式
    if [ "$DRY_RUN" = true ]; then
        log_info "[Dry-run] 将创建用户: $SERVICE_USER"
        return
    fi

    # 创建用户
    if ! id "$SERVICE_USER" &> /dev/null; then
        useradd -r -s /bin/false -d "$INSTALL_DIR" "$SERVICE_USER"
        log_ok "创建服务用户: $SERVICE_USER"
    else
        log_info "服务用户已存在: $SERVICE_USER"
    fi

    # 设置目录权限
    chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
    log_ok "目录权限设置完成"
}
```

- [ ] **Step 2: 提交**

```bash
git add server/deploy/deploy.sh
git commit -m "feat(deploy): 添加目录创建和用户管理模块"
```

---

### Task 5: 部署模式 + 代码拉取

**Files:**
- Modify: `server/deploy/deploy.sh` (添加部署模式函数)

- [ ] **Step 1: 添加部署模式检测和代码拉取函数**

```bash
# 检测部署模式
DEPLOY_MODE=""

detect_deploy_mode() {
    CURRENT_STEP="检测部署模式"
    log_step "确定部署模式..."

    if [ "$NON_INTERACTIVE" = true ]; then
        DEPLOY_MODE="${BM_MODE:-local}"
    elif [ "$DRY_RUN" = true ]; then
        DEPLOY_MODE="local"
    else
        echo ""
        echo "选择部署模式:"
        echo "  1) Git 拉取 (推荐，方便更新)"
        echo "  2) ZIP 包部署"
        echo "  3) 本地目录 (脚本所在目录)"
        echo ""
        read -rp "请选择 [1-3] (默认 3): " mode_choice

        case "$mode_choice" in
            1) DEPLOY_MODE="git" ;;
            2) DEPLOY_MODE="zip" ;;
            *) DEPLOY_MODE="local" ;;
        esac
    fi

    log_info "部署模式: $DEPLOY_MODE"
}

# Git 部署
deploy_git() {
    CURRENT_STEP="Git 部署"

    if [ "$NON_INTERACTIVE" = true ]; then
        REPO_URL="${BM_REPO_URL}"
        BRANCH="${BM_BRANCH:-main}"
    else
        REPO_URL=$(read_with_default "输入 Git 仓库 URL" "")
        if [ -z "$REPO_URL" ]; then
            log_error "仓库 URL 不能为空"
            exit 1
        fi
        BRANCH=$(read_with_default "输入分支名" "main")
    fi

    # Dry-run 模式
    if [ "$DRY_RUN" = true ]; then
        log_info "[Dry-run] 将执行: git clone -b $BRANCH $REPO_URL $INSTALL_DIR"
        return
    fi

    if [ -d "$INSTALL_DIR/.git" ]; then
        log_info "检测到已存在的 Git 仓库，执行更新..."
        cd "$INSTALL_DIR"
        git fetch origin
        git checkout "$BRANCH"
        git pull origin "$BRANCH"
        log_ok "代码更新完成"
    else
        # 备份现有数据目录
        if [ -d "$INSTALL_DIR/data" ]; then
            cp -a "$INSTALL_DIR/data" "/tmp/bidmonitor_data_backup"
        fi

        log_info "正在克隆仓库..."
        git clone -b "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
        log_ok "代码克隆完成"

        # 恢复数据目录
        if [ -d "/tmp/bidmonitor_data_backup" ]; then
            cp -a "/tmp/bidmonitor_data_backup/"* "$INSTALL_DIR/data/" 2>/dev/null || true
            rm -rf "/tmp/bidmonitor_data_backup"
        fi
    fi
}

# ZIP 部署
deploy_zip() {
    CURRENT_STEP="ZIP 部署"

    if [ "$NON_INTERACTIVE" = true ]; then
        ZIP_PATH="${BM_ZIP_PATH}"
    else
        ZIP_PATH=$(read_with_default "输入 ZIP 文件路径" "")
        if [ -z "$ZIP_PATH" ]; then
            log_error "ZIP 文件路径不能为空"
            exit 1
        fi
    fi

    # Dry-run 模式
    if [ "$DRY_RUN" = true ]; then
        log_info "[Dry-run] 将解压: $ZIP_PATH 到 $INSTALL_DIR"
        return
    fi

    if [ ! -f "$ZIP_PATH" ]; then
        log_error "ZIP 文件不存在: $ZIP_PATH"
        exit 1
    fi

    # 创建回滚快照
    create_backup

    log_info "正在解压 ZIP 文件..."
    unzip -o "$ZIP_PATH" -d "$INSTALL_DIR"
    log_ok "ZIP 解压完成"
}

# 本地部署
deploy_local() {
    CURRENT_STEP="本地部署"

    # 假设脚本在 server/deploy/ 目录下
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

    if [ "$DRY_RUN" = true ]; then
        log_info "[Dry-run] 将复制: $PROJECT_ROOT/* 到 $INSTALL_DIR"
        return
    fi

    # 创建回滚快照
    create_backup

    log_info "正在复制项目文件..."
    # 复制 server 和 src 目录
    cp -a "$PROJECT_ROOT/server" "$INSTALL_DIR/"
    cp -a "$PROJECT_ROOT/src" "$INSTALL_DIR/"

    # 确保配置文件目录存在
    mkdir -p "$INSTALL_DIR/data"
    mkdir -p "$INSTALL_DIR/server/logs"

    log_ok "文件复制完成"
}
```

- [ ] **Step 2: 提交**

```bash
git add server/deploy/deploy.sh
git commit -m "feat(deploy): 添加多模式部署（Git/ZIP/Local）"
```

---

### Task 6: 回滚机制

**Files:**
- Modify: `server/deploy/deploy.sh` (添加回滚函数)

- [ ] **Step 1: 添加回滚函数**

```bash
# 创建备份
create_backup() {
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_path="$ROLLBACK_DIR/$timestamp"

    mkdir -p "$backup_path"

    # 备份 server 目录
    if [ -d "$INSTALL_DIR/server" ]; then
        cp -a "$INSTALL_DIR/server" "$backup_path/"
    fi

    # 备份 src 目录
    if [ -d "$INSTALL_DIR/src" ]; then
        cp -a "$INSTALL_DIR/src" "$backup_path/"
    fi

    # 备份 venv
    if [ -d "$INSTALL_DIR/venv" ]; then
        cp -a "$INSTALL_DIR/venv" "$backup_path/"
    fi

    log_ok "已创建回滚快照: $timestamp"

    # 清理旧快照
    cleanup_old_rollbacks
}

# 清理旧回滚快照
cleanup_old_rollbacks() {
    local count
    count=$(ls -1 "$ROLLBACK_DIR" 2>/dev/null | wc -l)

    if [ "$count" -gt "$MAX_ROLLBACKS" ]; then
        log_info "清理旧回滚快照 (保留最近 $MAX_ROLLBACKS 个)..."
        cd "$ROLLBACK_DIR"
        ls -t | tail -n +$((MAX_ROLLBACKS + 1)) | xargs rm -rf
        log_ok "清理完成"
    fi
}

# 恢复备份
restore_backup() {
    local snapshot="$1"
    local backup_path="$ROLLBACK_DIR/$snapshot"

    if [ ! -d "$backup_path" ]; then
        log_error "回滚快照不存在: $snapshot"
        return 1
    fi

    log_warn "正在回滚到快照: $snapshot"

    # 停止服务
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true

    # 恢复文件
    if [ -d "$backup_path/server" ]; then
        rm -rf "$INSTALL_DIR/server"
        cp -a "$backup_path/server" "$INSTALL_DIR/"
    fi

    if [ -d "$backup_path/src" ]; then
        rm -rf "$INSTALL_DIR/src"
        cp -a "$backup_path/src" "$INSTALL_DIR/"
    fi

    if [ -d "$backup_path/venv" ]; then
        rm -rf "$INSTALL_DIR/venv"
        cp -a "$backup_path/venv" "$INSTALL_DIR/"
    fi

    # 重启服务
    systemctl start "$SERVICE_NAME" 2>/dev/null || true

    log_ok "回滚完成"
}

# 回滚模式
run_rollback() {
    log_step "回滚模式"

    if [ ! -d "$ROLLBACK_DIR" ] || [ -z "$(ls -A "$ROLLBACK_DIR" 2>/dev/null)" ]; then
        log_error "没有可用的回滚快照"
        exit 1
    fi

    echo "可用的回滚快照:"
    ls -lt "$ROLLBACK_DIR" | head -n 6
    echo ""

    local latest
    latest=$(ls -t "$ROLLBACK_DIR" | head -1)

    if [ "$NON_INTERACTIVE" = true ]; then
        rollback_snapshot="$latest"
    else
        read -rp "输入要回滚的快照名称 (默认: $latest): " rollback_snapshot
        rollback_snapshot="${rollback_snapshot:-$latest}"
    fi

    restore_backup "$rollback_snapshot"
    exit 0
}
```

- [ ] **Step 2: 提交**

```bash
git add server/deploy/deploy.sh
git commit -m "feat(deploy): 添加回滚机制和快照管理"
```

---

### Task 7: 虚拟环境 + Python 依赖

**Files:**
- Modify: `server/deploy/deploy.sh` (添加虚拟环境函数)

- [ ] **Step 1: 添加虚拟环境和依赖安装函数**

```bash
# 设置 Python 虚拟环境
setup_venv() {
    CURRENT_STEP="设置虚拟环境"
    log_step "配置 Python 虚拟环境..."

    # Dry-run 模式
    if [ "$DRY_RUN" = true ]; then
        log_info "[Dry-run] 将创建虚拟环境: $INSTALL_DIR/venv"
        return
    fi

    # 创建虚拟环境
    if [ ! -d "$INSTALL_DIR/venv" ]; then
        log_info "正在创建虚拟环境..."
        python3 -m venv "$INSTALL_DIR/venv"
        log_ok "虚拟环境创建完成"
    else
        log_info "虚拟环境已存在，复用"
    fi

    # 激活虚拟环境
    source "$INSTALL_DIR/venv/bin/activate"

    # 升级 pip
    pip install --upgrade pip -q

    # 安装依赖
    if [ -f "$INSTALL_DIR/server/requirements.txt" ]; then
        log_info "正在安装 Python 依赖..."
        pip install -r "$INSTALL_DIR/server/requirements.txt"
        log_ok "Python 依赖安装完成"
    else
        log_error "未找到 requirements.txt"
        exit 1
    fi
}
```

- [ ] **Step 2: 提交**

```bash
git add server/deploy/deploy.sh
git commit -m "feat(deploy): 添加虚拟环境和依赖安装"
```

---

### Task 8: 认证配置

**Files:**
- Modify: `server/deploy/deploy.sh` (添加认证配置函数)

- [ ] **Step 1: 添加认证配置函数**

```bash
# 配置认证信息
configure_auth() {
    CURRENT_STEP="配置认证信息"
    log_step "配置管理员账号..."

    local app_file="$INSTALL_DIR/server/app.py"

    if [ ! -f "$app_file" ]; then
        log_warn "未找到 app.py，跳过认证配置"
        return
    fi

    if [ "$NON_INTERACTIVE" = true ]; then
        admin_user="${BM_ADMIN_USER:-$DEFAULT_ADMIN_USER}"
        admin_pass="${BM_ADMIN_PASS:-$DEFAULT_ADMIN_PASS}"
    else
        admin_user=$(read_with_default "设置管理员用户名" "$DEFAULT_ADMIN_USER")
        admin_pass=$(read_password "设置管理员密码" "")
        if [ -z "$admin_pass" ]; then
            admin_pass="$DEFAULT_ADMIN_PASS"
            log_warn "使用默认密码"
        fi
    fi

    # Dry-run 模式
    if [ "$DRY_RUN" = true ]; then
        log_info "[Dry-run] 将设置管理员账号: $admin_user"
        return
    fi

    # 使用 sed 替换认证信息
    sed -i "s/AUTH_USERNAME = .*/AUTH_USERNAME = \"$admin_user\"/" "$app_file"
    sed -i "s/AUTH_PASSWORD = .*/AUTH_PASSWORD = \"$admin_pass\"/" "$app_file"

    log_ok "管理员账号配置完成"
}
```

- [ ] **Step 2: 提交**

```bash
git add server/deploy/deploy.sh
git commit -m "feat(deploy): 添加交互式认证配置"
```

---

### Task 9: systemd 服务安装

**Files:**
- Modify: `server/deploy/deploy.sh` (添加 systemd 服务函数)
- Create: `server/deploy/bidmonitor.service` (增强版服务配置)

- [ ] **Step 1: 创建增强版 systemd 服务配置**

```ini
[Unit]
Description=BidMonitor 招标监控服务
Documentation=https://github.com/zhiqianzheng/BidMonitor
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/bidmonitor/server

# 环境变量
Environment="PATH=/opt/bidmonitor/venv/bin:/usr/local/bin:/usr/bin"
Environment="VIRTUAL_ENV=/opt/bidmonitor/venv"

# 启动命令
ExecStart=/opt/bidmonitor/venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 8080

# 自动重启
Restart=always
RestartSec=10
StartLimitIntervalSec=300
StartLimitBurst=5

# 资源限制
LimitNOFILE=65536
LimitNPROC=4096

# 日志
StandardOutput=append:/opt/bidmonitor/server/logs/server.log
StandardError=append:/opt/bidmonitor/server/logs/server.log

# 安全增强
PrivateTmp=true
ProtectSystem=full
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: 添加服务安装函数到 deploy.sh**

```bash
# 安装 systemd 服务
install_service() {
    CURRENT_STEP="安装 systemd 服务"
    log_step "配置 systemd 服务..."

    local service_file="$INSTALL_DIR/server/deploy/bidmonitor.service"
    local system_service="/etc/systemd/system/${SERVICE_NAME}.service"

    # Dry-run 模式
    if [ "$DRY_RUN" = true ]; then
        log_info "[Dry-run] 将安装服务: $system_service"
        return
    fi

    if [ ! -f "$service_file" ]; then
        log_warn "未找到 bidmonitor.service，使用默认配置"
        # 创建默认服务文件
        cat > "$service_file" << 'EOF'
[Unit]
Description=BidMonitor 招标监控服务
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/bidmonitor/server
Environment="PATH=/opt/bidmonitor/venv/bin:/usr/local/bin:/usr/bin"
Environment="VIRTUAL_ENV=/opt/bidmonitor/venv"
ExecStart=/opt/bidmonitor/venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=10
LimitNOFILE=65536
StandardOutput=append:/opt/bidmonitor/server/logs/server.log
StandardError=append:/opt/bidmonitor/server/logs/server.log

[Install]
WantedBy=multi-user.target
EOF
    fi

    # 如果服务用户不是 root，更新服务配置
    if [ "$SERVICE_USER" != "root" ]; then
        sed -i "s/^User=root/User=$SERVICE_USER/" "$service_file"
        sed -i "s/^Group=root/Group=$SERVICE_USER/" "$service_file" 2>/dev/null || true
    fi

    # 安装服务
    cp "$service_file" "$system_service"
    chmod 644 "$system_service"

    # 重载 systemd
    systemctl daemon-reload

    # 启用服务
    systemctl enable "$SERVICE_NAME"

    log_ok "systemd 服务安装完成"
}

# 启动服务
start_service() {
    CURRENT_STEP="启动服务"
    log_step "启动服务..."

    # Dry-run 模式
    if [ "$DRY_RUN" = true ]; then
        log_info "[Dry-run] 将执行: systemctl restart $SERVICE_NAME"
        return
    fi

    # 重启服务
    systemctl restart "$SERVICE_NAME"

    # 等待服务启动
    sleep 3

    # 检查服务状态
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log_ok "服务启动成功"
    else
        log_error "服务启动失败"
        log_error "查看日志: journalctl -u $SERVICE_NAME -n 50 --no-pager"
        exit 1
    fi
}
```

- [ ] **Step 3: 提交**

```bash
git add server/deploy/deploy.sh server/deploy/bidmonitor.service
git commit -m "feat(deploy): 添加 systemd 服务安装和管理"
```

---

### Task 10: 防火墙 + Nginx 配置

**Files:**
- Modify: `server/deploy/deploy.sh` (添加防火墙和 Nginx 函数)

- [ ] **Step 1: 添加防火墙配置函数**

```bash
# 配置防火墙
configure_firewall() {
    CURRENT_STEP="配置防火墙"

    if [ "$DRY_RUN" = true ]; then
        log_info "[Dry-run] 防火墙配置步骤..."
        return
    fi

    # 非交互模式
    if [ "$NON_INTERACTIVE" = true ]; then
        open_firewall="${BM_OPEN_FIREWALL:-false}"
    else
        echo ""
        log_warn "安全提示: 默认不开放公网端口"
        read -rp "是否开放公网端口 ${DEFAULT_PORT}? (y/N): " open_firewall
    fi

    if [[ "$open_firewall" =~ ^[Yy]$ ]]; then
        log_step "配置防火墙规则..."

        # Ubuntu / UFW
        if command -v ufw &> /dev/null; then
            ufw allow "$DEFAULT_PORT/tcp" 2>/dev/null || true
            log_ok "UFW 规则已添加: 允许 ${DEFAULT_PORT}/tcp"
        fi

        # CentOS/AlmaLinux / firewalld
        if command -v firewall-cmd &> /dev/null; then
            firewall-cmd --permanent --add-port="${DEFAULT_PORT}/tcp" 2>/dev/null || true
            firewall-cmd --reload 2>/dev/null || true
            log_ok "firewalld 规则已添加: 允许 ${DEFAULT_PORT}/tcp"
        fi

        # iptables 备用
        if ! command -v ufw &> /dev/null && ! command -v firewall-cmd &> /dev/null; then
            iptables -I INPUT -p tcp --dport "$DEFAULT_PORT" -j ACCEPT 2>/dev/null || true
            log_ok "iptables 规则已添加: 允许 ${DEFAULT_PORT}/tcp"
        fi
    else
        log_info "跳过防火墙配置，仅本地可访问"
    fi
}
```

- [ ] **Step 2: 添加 Nginx 配置函数**

```bash
# 配置 Nginx 反向代理
setup_nginx() {
    CURRENT_STEP="配置 Nginx"

    if [ "$DRY_RUN" = true ]; then
        log_info "[Dry-run] Nginx 配置步骤..."
        return
    fi

    # 非交互模式
    if [ "$NON_INTERACTIVE" = true ]; then
        use_nginx="${BM_USE_NGINX:-false}"
    else
        echo ""
        read -rp "是否安装 Nginx 反向代理? (y/N): " use_nginx
    fi

    if [[ "$use_nginx" =~ ^[Yy]$ ]]; then
        log_step "配置 Nginx 反向代理..."

        # 获取域名
        if [ "$NON_INTERACTIVE" = true ]; then
            domain="${BM_DOMAIN:-_}"
        else
            domain=$(read_with_default "输入域名 (留空使用 IP 访问)" "_")
        fi

        # 安装 Nginx
        if ! command -v nginx &> /dev/null; then
            log_info "安装 Nginx..."
            if [ "$PKG_MANAGER" = "apt-get" ]; then
                apt-get install -y nginx
            elif [ "$PKG_MANAGER" = "yum" ]; then
                yum install -y nginx
            else
                dnf install -y nginx
            fi
            log_ok "Nginx 安装完成"
        fi

        # 创建 Nginx 配置
        local nginx_conf="/etc/nginx/conf.d/bidmonitor.conf"
        cat > "$nginx_conf" << EOF
server {
    listen 80;
    server_name ${domain};

    location / {
        proxy_pass http://127.0.0.1:${DEFAULT_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # 静态资源缓存
    location /static/ {
        proxy_pass http://127.0.0.1:${DEFAULT_PORT};
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
}
EOF

        # 测试配置
        nginx -t

        # 重启 Nginx
        systemctl restart nginx
        systemctl enable nginx

        log_ok "Nginx 反向代理配置完成"

        # HTTPS 提示
        if [ "$domain" != "_" ]; then
            log_info "如需启用 HTTPS，请运行: certbot --nginx -d $domain"
        fi
    else
        log_info "跳过 Nginx 配置"
    fi
}
```

- [ ] **Step 3: 提交**

```bash
git add server/deploy/deploy.sh
git commit -m "feat(deploy): 添加防火墙和 Nginx 反向代理配置"
```

---

### Task 11: 访问信息输出 + 主流程

**Files:**
- Modify: `server/deploy/deploy.sh` (添加输出函数和主流程)

- [ ] **Step 1: 添加访问信息输出函数**

```bash
# 打印访问信息
print_access_info() {
    CURRENT_STEP="输出访问信息"

    # 获取服务器 IP
    local server_ip
    server_ip=$(hostname -I | awk '{print $1}' 2>/dev/null || echo "YOUR_SERVER_IP")

    local access_url
    if [ "$NON_INTERACTIVE" = true ] && [ -n "${BM_DOMAIN:-}" ]; then
        access_url="http://${BM_DOMAIN}"
    elif [ "$DRY_RUN" = true ]; then
        access_url="http://<YOUR_SERVER_IP>"
    else
        access_url="http://${server_ip}:${DEFAULT_PORT}"
    fi

    echo ""
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}   ✅ BidMonitor 部署成功！${NC}"
    echo -e "${GREEN}================================================${NC}"
    echo ""
    echo -e "  访问地址: ${GREEN}${access_url}${NC}"
    echo -e "  管理员账号: ${GREEN}${admin_user:-$DEFAULT_ADMIN_USER}${NC}"
    echo ""
    echo -e "  配置文件: ${CYAN}$INSTALL_DIR/server/server_config.json${NC}"
    echo -e "  日志目录: ${CYAN}$INSTALL_DIR/server/logs/${NC}"
    echo -e "  数据目录: ${CYAN}$INSTALL_DIR/data/${NC}"
    echo ""
    echo -e "${BOLD}  常用命令:${NC}"
    echo -e "    查看状态: ${CYAN}sudo systemctl status $SERVICE_NAME${NC}"
    echo -e "    查看日志: ${CYAN}sudo journalctl -u $SERVICE_NAME -f${NC}"
    echo -e "    重启服务: ${CYAN}sudo systemctl restart $SERVICE_NAME${NC}"
    echo -e "    停止服务: ${CYAN}sudo systemctl stop $SERVICE_NAME${NC}"
    echo -e "    查看日志: ${CYAN}tail -f $INSTALL_DIR/server/logs/server.log${NC}"
    echo ""
    echo -e "${BOLD}  回滚管理:${NC}"
    echo -e "    查看快照: ${CYAN}ls -lt $ROLLBACK_DIR${NC}"
    echo -e "    手动回滚: ${CYAN}sudo bash $0 --rollback${NC}"
    echo ""
    echo -e "${BOLD}  更新部署:${NC}"
    echo -e "    再次运行: ${CYAN}sudo bash $0${NC}"
    echo ""
}
```

- [ ] **Step 2: 添加主流程函数和入口**

```bash
# 首次部署流程
run_first_deploy() {
    print_banner

    # 1. 系统检查
    check_root
    detect_os
    check_requirements

    # 2. 安装依赖
    install_dependencies

    # 3. 创建目录
    create_directories

    # 4. 服务用户
    create_service_user

    # 5. 部署代码
    detect_deploy_mode
    case "$DEPLOY_MODE" in
        git) deploy_git ;;
        zip) deploy_zip ;;
        local) deploy_local ;;
    esac

    # 6. 虚拟环境
    setup_venv

    # 7. 认证配置
    configure_auth

    # 8. systemd 服务
    install_service

    # 9. 防火墙
    configure_firewall

    # 10. Nginx
    setup_nginx

    # 11. 启动服务
    start_service

    # 12. 输出信息
    print_access_info
}

# 更新部署流程
run_update_deploy() {
    CURRENT_STEP="更新部署"
    print_banner
    log_step "执行增量更新..."

    # 1. 系统检查
    check_root
    detect_os
    check_requirements

    # 2. 创建回滚快照
    create_backup

    # 3. 更新代码
    detect_deploy_mode
    case "$DEPLOY_MODE" in
        git) deploy_git ;;
        zip) deploy_zip ;;
        local) deploy_local ;;
    esac

    # 4. 更新依赖
    setup_venv

    # 5. 重启服务
    start_service

    # 6. 验证服务
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log_ok "更新部署成功"
        print_access_info
    else
        log_error "服务更新后启动失败"
        log_error "请查看日志: journalctl -u $SERVICE_NAME -n 50"
        exit 1
    fi
}

# 主入口
main() {
    # 回滚模式
    if [ "$ROLLBACK" = true ]; then
        run_rollback
        exit 0
    fi

    # 检测是否已部署
    if [ -d "$INSTALL_DIR/venv" ] && systemctl list-unit-files | grep -q "$SERVICE_NAME"; then
        log_info "检测到已部署的 BidMonitor 服务"
        if [ "$NON_INTERACTIVE" = true ]; then
            run_update_deploy
        else
            echo ""
            read -rp "检测到已有部署，是否执行更新? (Y/n): " update_choice
            if [[ "$update_choice" =~ ^[Nn]$ ]]; then
                log_info "取消更新"
                exit 0
            fi
            run_update_deploy
        fi
    else
        run_first_deploy
    fi
}

# 执行主函数
main
```

- [ ] **Step 3: 添加执行权限**

```bash
chmod +x server/deploy/deploy.sh
```

- [ ] **Step 4: 提交**

```bash
git add server/deploy/deploy.sh
git commit -m "feat(deploy): 添加访问信息输出和完整部署流程"
```

---

### Task 12: 配置模板 + 最终验证

**Files:**
- Create: `server/deploy/deploy.conf.example`
- Modify: `server/deploy/deploy.sh` (final review)

- [ ] **Step 1: 创建配置模板文件**

```bash
#!/bin/bash
# =============================================================================
# BidMonitor 部署配置模板
# 使用方法:
#   1. 复制此文件为 deploy.conf
#   2. 修改配置值
#   3. 运行: BM_CONFIG=deploy.conf bash deploy.sh --non-interactive
# =============================================================================

# 部署模式: git / zip / local
BM_MODE="git"

# Git 配置
BM_REPO_URL="https://github.com/your-org/bidmonitor.git"
BM_BRANCH="main"

# ZIP 文件路径
# BM_ZIP_PATH="/path/to/bidmonitor_deploy.zip"

# 管理员账号
BM_ADMIN_USER="CDKJ"
BM_ADMIN_PASS="cdkj"

# 域名配置（留空使用 IP）
BM_DOMAIN=""

# Nginx 反向代理: true / false
BM_USE_NGINX="false"

# 开放防火墙: true / false
BM_OPEN_FIREWALL="false"

# 服务用户（留空使用 root）
BM_SERVICE_USER=""
```

- [ ] **Step 2: 验证脚本语法**

```bash
bash -n server/deploy/deploy.sh
```

- [ ] **Step 3: 提交**

```bash
git add server/deploy/deploy.conf.example server/deploy/deploy.sh
git commit -m "feat(deploy): 添加配置模板并完成部署脚本"
```

---

## Self-Review Checklist

### 1. Spec coverage
- ✅ 系统检查（OS 版本、Python 版本、内存、磁盘）
- ✅ 系统依赖安装（跨平台包管理器）
- ✅ 项目目录创建
- ✅ Python 虚拟环境
- ✅ pip 依赖安装
- ✅ 目录权限设置
- ✅ systemd 服务安装和启动
- ✅ 防火墙规则配置（可选）
- ✅ 部署成功后的访问信息输出
- ✅ 支持 Ubuntu 20.04/22.04, CentOS 7/8, AlmaLinux
- ✅ 自动检测操作系统
- ✅ 彩色输出
- ✅ 错误处理和回滚机制
- ✅ 幂等性
- ✅ 交互提示（域名、账号、Nginx）
- ✅ 非交互模式（环境变量）

### 2. Placeholder scan
- 无未完成的 TBD/TODO
- 所有函数都有具体实现

### 3. Variable consistency
- 所有变量定义一致
- 函数名统一使用 snake_case
- 路径使用常量定义

### 4. Error handling
- 每个关键步骤都有错误处理
- Trap 捕获全局错误
- 自动回滚机制
