#!/bin/bash
# ============================================================
# BidMonitor AI - 生产环境部署脚本
# 用法: sudo bash deploy.sh [选项]
# 选项:
#   --install     完整安装（创建用户、目录、安装依赖）
#   --update      更新代码并重启服务
#   --backup      备份当前配置和数据
#   --status      检查服务状态
#   --uninstall   卸载服务
# ============================================================

set -euo pipefail

# ============================================================
# 颜色输出
# ============================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ============================================================
# 配置变量
# ============================================================
APP_NAME="bidmonitor"
APP_DIR="/opt/bidmonitor"
VENV_DIR="${APP_DIR}/venv"
SERVER_DIR="${APP_DIR}/server"
DATA_DIR="${APP_DIR}/data"
LOG_DIR="${SERVER_DIR}/logs"
DEPLOY_DIR="${SERVER_DIR}/deploy"
SERVICE_USER="www-data"
SERVICE_FILE="${DEPLOY_DIR}/bidmonitor.service"
NGINX_CONF="${DEPLOY_DIR}/bidmonitor-nginx.conf"
LOGROTATE_CONF="${DEPLOY_DIR}/bidmonitor-logrotate"
SYSTEMD_DIR="/etc/systemd/system"
NGINX_SITES_AVAILABLE="/etc/nginx/sites-available"
NGINX_SITES_ENABLED="/etc/nginx/sites-enabled"

# 操作系统检测变量
OS_TYPE=""          # 人类可读的 OS 名称 (如 "Ubuntu 22.04")
OS_ID=""            # /etc/os-release 中的 ID (如 "ubuntu", "centos")
OS_VERSION=""       # 主版本号 (如 "22", "8", "9")
OS_VERSION_FULL=""  # 完整版本号 (如 "22.04")
PKG_MGR=""          # 包管理器命令 (apt-get / yum / dnf)
DEBIAN_FRONTEND=""  # Debian 系列环境变量

# ============================================================
# 检查 root 权限
# ============================================================
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "请使用 sudo 运行此脚本"
    fi
}

# ============================================================
# 检测操作系统类型
# ============================================================
detect_os() {
    info "检测操作系统..."

    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS_ID="${ID,,}"  # 转小写
        OS_VERSION="${VERSION_ID%%.*}"       # 主版本号
        OS_VERSION_FULL="${VERSION_ID}"      # 完整版本号

        case "${OS_ID}" in
            ubuntu)
                if [[ "${OS_VERSION}" == "20" || "${OS_VERSION}" == "22" || "${OS_VERSION}" == "24" ]]; then
                    OS_TYPE="Ubuntu ${OS_VERSION_FULL}"
                    PKG_MGR="apt-get"
                    DEBIAN_FRONTEND="noninteractive"
                    success "检测到: ${OS_TYPE} (包管理器: ${PKG_MGR})"
                else
                    warn "Ubuntu 版本 ${OS_VERSION_FULL} 未经充分测试，继续尝试..."
                    OS_TYPE="Ubuntu ${OS_VERSION_FULL}"
                    PKG_MGR="apt-get"
                    DEBIAN_FRONTEND="noninteractive"
                fi
                ;;
            centos)
                if [[ "${OS_VERSION}" == "7" || "${OS_VERSION}" == "8" ]]; then
                    OS_TYPE="CentOS ${OS_VERSION_FULL}"
                    PKG_MGR="yum"
                    DEBIAN_FRONTEND=""
                    SERVICE_USER="nginx"
                    NGINX_SITES_AVAILABLE="/etc/nginx/conf.d"
                    NGINX_SITES_ENABLED="/etc/nginx/conf.d"
                    success "检测到: ${OS_TYPE} (包管理器: ${PKG_MGR})"
                else
                    error "不支持的 CentOS 版本: ${OS_VERSION_FULL} (仅支持 7/8)"
                fi
                ;;
            almalinux|rocky)
                if [[ "${OS_VERSION}" == "8" || "${OS_VERSION}" == "9" ]]; then
                    OS_TYPE="${OS_ID^} ${OS_VERSION_FULL}"
                    PKG_MGR="dnf"
                    DEBIAN_FRONTEND=""
                    SERVICE_USER="nginx"
                    NGINX_SITES_AVAILABLE="/etc/nginx/conf.d"
                    NGINX_SITES_ENABLED="/etc/nginx/conf.d"
                    success "检测到: ${OS_TYPE} (包管理器: ${PKG_MGR})"
                else
                    error "不支持的 ${OS_ID} 版本: ${OS_VERSION_FULL} (仅支持 8/9)"
                fi
                ;;
            *)
                warn "未知操作系统: ${ID} ${VERSION_ID}，尝试使用 yum 作为包管理器"
                OS_TYPE="${ID^} ${VERSION_ID}"
                OS_ID="${ID}"
                PKG_MGR="yum"
                DEBIAN_FRONTEND=""
                ;;
        esac
    else
        error "无法检测操作系统，找不到 /etc/os-release"
    fi
}

# ============================================================
# 检查系统依赖
# ============================================================
check_dependencies() {
    info "检查系统依赖..."

    local deps=()
    local install_cmd=""

    case "${PKG_MGR}" in
        apt-get)
            deps=("python3" "python3-venv" "python3-pip" "nginx")
            export DEBIAN_FRONTEND="${DEBIAN_FRONTEND}"
            install_cmd="apt-get install -y"
            ;;
        yum|dnf)
            deps=("python3" "python3-pip" "nginx")
            install_cmd="${PKG_MGR} install -y"
            ;;
        *)
            error "不支持的包管理器: ${PKG_MGR}"
            ;;
    esac

    local missing=()
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &>/dev/null; then
            missing+=("$dep")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        warn "缺少依赖: ${missing[*]}"
        info "正在安装..."

        if [[ "${PKG_MGR}" == "apt-get" ]]; then
            apt-get update -qq
        fi

        if ${install_cmd} "${missing[@]}"; then
            success "依赖安装完成"
        else
            error "依赖安装失败，请手动安装: ${missing[*]}"
        fi
    else
        success "所有依赖已满足"
    fi
}

# ============================================================
# 安装 Chrome/Chromium (Selenium 需要)
# ============================================================
install_chrome_for_selenium() {
    info "安装 Chromium 浏览器 (供 Selenium 使用)..."

    if command -v chromium-browser &>/dev/null || command -v chromium &>/dev/null || command -v google-chrome &>/dev/null; then
        success "Chrome/Chromium 已安装，跳过"
        return
    fi

    case "${PKG_MGR}" in
        apt-get)
            if apt-get install -y chromium-browser 2>/dev/null; then
                success "chromium-browser 安装完成"
            elif apt-get install -y chromium 2>/dev/null; then
                success "chromium 安装完成"
            else
                warn "Chromium 安装失败，Selenium 爬虫可能无法工作"
            fi
            ;;
        yum|dnf)
            if ${PKG_MGR} install -y chromium 2>/dev/null; then
                success "chromium 安装完成"
            else
                warn "Chromium 安装失败，Selenium 爬虫可能无法工作"
            fi
            ;;
        *)
            warn "不支持的包管理器，跳过 Chromium 安装"
            ;;
    esac
}

# ============================================================
# 创建目录结构
# ============================================================
create_directories() {
    info "创建目录结构..."

    mkdir -p "${SERVER_DIR}" "${DATA_DIR}" "${LOG_DIR}" "${DEPLOY_DIR}"

    # 设置权限
    chown -R "${SERVICE_USER}:${SERVICE_USER}" "${APP_DIR}"
    chmod -R 755 "${APP_DIR}"
    chmod 700 "${DATA_DIR}"

    success "目录创建完成"
}

# ============================================================
# 创建虚拟环境
# ============================================================
setup_venv() {
    info "配置 Python 虚拟环境..."

    if [[ -d "${VENV_DIR}" ]]; then
        warn "虚拟环境已存在，跳过创建"
    else
        cd "${APP_DIR}"
        python3 -m venv venv
        success "虚拟环境创建完成"
    fi

    # 安装依赖
    info "安装 Python 依赖..."
    if [[ -f "${SERVER_DIR}/requirements.txt" ]]; then
        "${VENV_DIR}/bin/pip" install --upgrade pip -qq
        "${VENV_DIR}/bin/pip" install -r "${SERVER_DIR}/requirements.txt" -qq
        success "Python 依赖安装完成"
    else
        warn "requirements.txt 不存在，跳过依赖安装"
    fi
}

# ============================================================
# 安装 systemd 服务
# ============================================================
install_service() {
    info "安装 systemd 服务..."

    if [[ ! -f "${SERVICE_FILE}" ]]; then
        error "服务配置文件不存在: ${SERVICE_FILE}"
    fi

    cp "${SERVICE_FILE}" "${SYSTEMD_DIR}/${APP_NAME}.service"
    systemctl daemon-reload
    systemctl enable "${APP_NAME}"

    success "systemd 服务安装完成"
}

# ============================================================
# 安装 Nginx 配置
# ============================================================
install_nginx() {
    info "配置 Nginx 反向代理..."

    if [[ ! -f "${NGINX_CONF}" ]]; then
        warn "Nginx 配置文件不存在: ${NGINX_CONF}"
        return
    fi

    mkdir -p "${NGINX_SITES_AVAILABLE}" "${NGINX_SITES_ENABLED}"

    cp "${NGINX_CONF}" "${NGINX_SITES_AVAILABLE}/${APP_NAME}"

    # 创建符号链接（如果不存在）
    if [[ ! -L "${NGINX_SITES_ENABLED}/${APP_NAME}" ]]; then
        ln -sf "${NGINX_SITES_AVAILABLE}/${APP_NAME}" "${NGINX_SITES_ENABLED}/${APP_NAME}"
    fi

    # 测试 Nginx 配置
    if nginx -t 2>/dev/null; then
        systemctl reload nginx
        success "Nginx 配置安装完成"
    else
        error "Nginx 配置测试失败，请检查配置文件"
    fi
}

# ============================================================
# 安装日志轮转配置
# ============================================================
install_logrotate() {
    info "配置日志轮转..."

    if [[ ! -f "${LOGROTATE_CONF}" ]]; then
        warn "日志轮转配置文件不存在: ${LOGROTATE_CONF}"
        return
    fi

    cp "${LOGROTATE_CONF}" "/etc/logrotate.d/${APP_NAME}"
    success "日志轮转配置完成"
}

# ============================================================
# 启动服务
# ============================================================
start_service() {
    info "启动服务..."

    systemctl restart "${APP_NAME}"
    sleep 2

    if systemctl is-active --quiet "${APP_NAME}"; then
        success "服务启动成功"
        systemctl status "${APP_NAME}" --no-pager
    else
        error "服务启动失败，请查看日志: journalctl -u ${APP_NAME} -e"
    fi
}

# ============================================================
# 完整安装
# ============================================================
do_install() {
    info "开始完整安装 BidMonitor AI..."

    check_root
    detect_os
    check_dependencies
    install_chrome_for_selenium
    create_directories
    setup_venv
    install_service
    install_nginx
    install_logrotate
    start_service

    echo ""
    success "============================================"
    success "BidMonitor AI 安装完成！"
    success "============================================"
    echo ""
    info "访问地址: http://your_domain.com 或 http://服务器IP"
    info "服务管理命令:"
    echo "  sudo systemctl status ${APP_NAME}    # 查看状态"
    echo "  sudo systemctl restart ${APP_NAME}   # 重启服务"
    echo "  sudo journalctl -u ${APP_NAME} -f    # 查看日志"
    echo ""
    info "证书申请（可选）:"
    echo "  sudo apt install certbot python3-certbot-nginx"
    echo "  sudo certbot --nginx -d your_domain.com"
    echo ""
}

# ============================================================
# 更新代码
# ============================================================
do_update() {
    info "开始更新 BidMonitor AI..."

    check_root

    # 备份当前配置
    do_backup

    # 停止服务
    info "停止服务..."
    systemctl stop "${APP_NAME}"

    # 安装新依赖
    if [[ -f "${SERVER_DIR}/requirements.txt" ]]; then
        info "更新 Python 依赖..."
        "${VENV_DIR}/bin/pip" install -r "${SERVER_DIR}/requirements.txt" -qq
    fi

    # 设置权限
    chown -R "${SERVICE_USER}:${SERVICE_USER}" "${APP_DIR}"

    # 启动服务
    start_service

    success "更新完成！"
}

# ============================================================
# 备份配置和数据
# ============================================================
do_backup() {
    info "备份配置和数据..."

    local backup_dir="/opt/bidmonitor-backup-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "${backup_dir}"

    # 备份配置文件
    if [[ -f "${SERVER_DIR}/server_config.json" ]]; then
        cp "${SERVER_DIR}/server_config.json" "${backup_dir}/"
    fi

    # 备份数据库
    if [[ -d "${DATA_DIR}" ]]; then
        cp -r "${DATA_DIR}" "${backup_dir}/"
    fi

    # 备份日志（最近 7 天）
    if [[ -d "${LOG_DIR}" ]]; then
        find "${LOG_DIR}" -name "*.log" -mtime -7 -exec cp {} "${backup_dir}/" \;
    fi

    success "备份完成: ${backup_dir}"
}

# ============================================================
# 检查服务状态
# ============================================================
do_status() {
    echo ""
    info "BidMonitor AI 服务状态"
    echo "========================================"

    # 服务状态
    if systemctl is-active --quiet "${APP_NAME}"; then
        success "服务状态: 运行中"
    else
        error "服务状态: 已停止"
    fi

    # 进程信息
    echo ""
    info "进程信息:"
    ps aux | grep "[u]vicorn app:app" || echo "  未找到运行中的进程"

    # 端口监听
    echo ""
    info "端口监听:"
    ss -tlnp | grep 8080 || echo "  8080 端口未监听"

    # 磁盘使用
    echo ""
    info "磁盘使用:"
    du -sh "${APP_DIR}" 2>/dev/null || echo "  应用目录不存在"
    du -sh "${LOG_DIR}" 2>/dev/null || echo "  日志目录不存在"
    du -sh "${DATA_DIR}" 2>/dev/null || echo "  数据目录不存在"

    # 最近日志
    echo ""
    info "最近日志 (最后 10 行):"
    journalctl -u "${APP_NAME}" --no-pager -n 10 2>/dev/null || echo "  无日志记录"

    echo ""
}

# ============================================================
# 卸载服务
# ============================================================
do_uninstall() {
    warn "============================================"
    warn "警告: 这将卸载 BidMonitor AI 服务"
    warn "数据目录 ${DATA_DIR} 不会被删除"
    warn "============================================"
    read -p "确认继续？(y/N): " confirm

    if [[ "${confirm,,}" != "y" ]]; then
        info "取消卸载"
        exit 0
    fi

    info "停止并禁用服务..."
    systemctl stop "${APP_NAME}" 2>/dev/null || true
    systemctl disable "${APP_NAME}" 2>/dev/null || true

    info "删除服务文件..."
    rm -f "${SYSTEMD_DIR}/${APP_NAME}.service"
    systemctl daemon-reload

    info "删除 Nginx 配置..."
    rm -f "${NGINX_SITES_ENABLED}/${APP_NAME}"
    rm -f "${NGINX_SITES_AVAILABLE}/${APP_NAME}"
    systemctl reload nginx 2>/dev/null || true

    info "删除日志轮转配置..."
    rm -f "/etc/logrotate.d/${APP_NAME}"

    info "删除应用目录..."
    rm -rf "${APP_DIR}"

    success "卸载完成！"
}

# ============================================================
# 主函数
# ============================================================
main() {
    local action="${1:-install}"

    case "${action}" in
        --install|-i)
            do_install
            ;;
        --update|-u)
            do_update
            ;;
        --backup|-b)
            do_backup
            ;;
        --status|-s)
            do_status
            ;;
        --uninstall)
            do_uninstall
            ;;
        --help|-h)
            echo "用法: sudo bash $0 [选项]"
            echo "选项:"
            echo "  --install, -i     完整安装（默认）"
            echo "  --update, -u      更新代码并重启"
            echo "  --backup, -b      备份配置和数据"
            echo "  --status, -s      检查服务状态"
            echo "  --uninstall       卸载服务"
            echo "  --help, -h        显示帮助"
            ;;
        *)
            error "未知选项: ${action}，使用 --help 查看帮助"
            ;;
    esac
}

main "$@"
