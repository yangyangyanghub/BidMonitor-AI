# BidMonitor 生产级部署脚本设计文档

> **日期:** 2026-04-20
> **作者:** Sisyphus-Junior
> **状态:** 已批准

## 1. 设计目标

创建一个生产级的一键部署脚本 `server/deploy/deploy.sh`，支持 Ubuntu 20.04/22.04 和 CentOS 7/8/AlmaLinux，实现首次部署和增量更新。

## 2. 架构总览

### 2.1 文件结构

```
server/deploy/
├── deploy.sh              # 主脚本（约 600 行，函数模块化）
└── bidmonitor.service     # 复制现有 systemd 配置（增强版）
```

### 2.2 目录约定

| 路径 | 用途 | 备注 |
|------|------|------|
| `/opt/bidmonitor` | 安装根目录 | 幂等创建 |
| `/opt/bidmonitor/venv` | Python 虚拟环境 | 独立于系统 Python |
| `/opt/bidmonitor/server` | 服务端代码 | FastAPI 应用 |
| `/opt/bidmonitor/src` | 核心模块 | 爬虫、通知、匹配等 |
| `/opt/bidmonitor/data` | 数据库目录 | SQLite 存储 |
| `/opt/bidmonitor/server/logs` | 日志目录 | 轮转管理 |
| `/opt/bidmonitor/.rollback` | 回滚快照 | 自动清理旧快照 |

## 3. 核心功能模块

### 3.1 系统检查 (`check_system`)

- **OS 检测**: 读取 `/etc/os-release`，提取 `ID` 和 `VERSION_ID`
- **支持的发行版**:
  - Ubuntu: 20.04, 22.04
  - CentOS: 7, 8
  - AlmaLinux: 8, 9
  - Rocky Linux: 8, 9
- **Python 版本**: 检查 `python3 >= 3.8`，版本过低时给出升级提示
- **内存检查**: 至少 512MB 可用内存（`free -m`）
- **磁盘空间**: `/opt` 分区至少 1GB 可用空间（`df -h`）
- **Root 权限**: 检测 `EUID`，非 root 时提示 `sudo`

### 3.2 依赖安装 (`install_dependencies`)

根据 OS 类型自动选择包管理器：

| 包名称 | Ubuntu | CentOS/AlmaLinux |
|--------|--------|------------------|
| Python 3 | `python3` | `python3` |
| venv | `python3-venv` | `python3-devel` (CentOS 7) / `python3-venv` (AlmaLinux) |
| pip | `python3-pip` | `python3-pip` |
| 浏览器 | `chromium-browser` / `google-chrome-stable` | `chromium` / `google-chrome-stable` |
| unzip | `unzip` | `unzip` |
| Nginx (可选) | `nginx` | `nginx` |

**幂等性保证**:
- 每个包安装前检查 `command -v` 或 `rpm -q`/`dpkg -l`
- 已安装则跳过，已安装则升级

### 3.3 项目目录创建 (`create_directories`)

```bash
# 幂等创建
mkdir -p /opt/bidmonitor/{server/logs,data,.rollback}
```

权限设置：
- 如果使用非 root 用户运行：`chown -R $USER:$USER /opt/bidmonitor`
- 如果创建专用用户：`chown -R bidmonitor:bidmonitor /opt/bidmonitor`

### 3.4 部署模式检测 (`detect_deploy_mode`)

自动检测部署方式（优先级从高到低）：

1. **Git 模式**: 检测到 `.git` 目录或 `--git` 参数
   - 首次：`git clone <repo_url> /opt/bidmonitor`
   - 更新：`cd /opt/bidmonitor && git pull`
2. **ZIP 模式**: 检测到 `*.zip` 文件或 `--zip <path>` 参数
   - 解压并覆盖 `server/` 和 `src/` 目录
3. **本地模式**: 脚本所在目录即为项目根目录
   - 复制文件到 `/opt/bidmonitor`

### 3.5 虚拟环境管理 (`setup_venv`)

```bash
# 创建或复用
if [ ! -d "/opt/bidmonitor/venv" ]; then
    python3 -m venv /opt/bidmonitor/venv
fi

# 激活并安装
source /opt/bidmonitor/venv/bin/activate
pip install --upgrade pip
pip install -r /opt/bidmonitor/server/requirements.txt
```

**幂等性**:
- 虚拟环境已存在则跳过创建
- 依赖安装使用 `pip install -r`，已有包则跳过

### 3.6 认证配置 (`configure_auth`)

交互式配置管理员账号：

```bash
# 提示输入
read -p "设置管理员用户名 [CDKJ]: " admin_user
read -s -p "设置管理员密码 [cdkj]: " admin_pass
```

- 使用 `sed` 替换 `app.py` 中的 `AUTH_USERNAME` 和 `AUTH_PASSWORD`
- 非交互模式：使用环境变量 `BM_ADMIN_USER`、`BM_ADMIN_PASS`
- 密码使用 Python 的 `secrets` 模块生成时启用强密码策略

### 3.7 systemd 服务安装 (`install_service`)

1. 复制并增强 `bidmonitor.service`：
   - 添加 `User=bidmonitor`（可选 root）
   - 添加 `LimitNOFILE=65536`
   - 添加 `StandardOutput=append:/opt/bidmonitor/server/logs/server.log`
2. 安装到 `/etc/systemd/system/`
3. 启用并启动：
   ```bash
   systemctl daemon-reload
   systemctl enable bidmonitor
   systemctl restart bidmonitor
   systemctl status bidmonitor --no-pager
   ```

### 3.8 防火墙配置 (`configure_firewall`)

**默认不开放公网端口**，需用户显式确认：

```bash
# 交互式提示
read -p "是否开放公网端口 8080? (y/N): " open_port
if [[ "$open_port" =~ ^[Yy]$ ]]; then
    # Ubuntu
    ufw allow 8080/tcp 2>/dev/null
    # CentOS/AlmaLinux
    firewall-cmd --permanent --add-port=8080/tcp 2>/dev/null
    firewall-cmd --reload 2>/dev/null
fi
```

安全建议：
- 默认仅监听 `127.0.0.1:8080`
- 如需公网访问，建议配置 Nginx 反向代理 + HTTPS

### 3.9 Nginx 反向代理 (`setup_nginx`)

可选安装：

```bash
# 交互式提示
read -p "是否安装 Nginx 反向代理? (y/N): " use_nginx
```

配置模板：
```nginx
server {
    listen 80;
    server_name ${DOMAIN:-_};

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

HTTPS 支持（可选）：
- 集成 `certbot` 申请 Let's Encrypt 证书

### 3.10 回滚机制 (`create_rollback` / `rollback`)

**部署前快照**:
```bash
ROLLBACK_DIR="/opt/bidmonitor/.rollback/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$ROLLBACK_DIR"
if [ -d "/opt/bidmonitor/server" ]; then
    cp -a /opt/bidmonitor/server "$ROLLBACK_DIR/"
fi
if [ -d "/opt/bidmonitor/venv" ]; then
    cp -a /opt/bidmonitor/venv "$ROLLBACK_DIR/"
fi
```

**失败回滚**:
```bash
rollback() {
    LATEST=$(ls -t /opt/bidmonitor/.rollback/ 2>/dev/null | head -1)
    if [ -n "$LATEST" ]; then
        echo "正在回滚到快照: $LATEST"
        cp -a "/opt/bidmonitor/.rollback/$LATEST/"* /opt/bidmonitor/
        systemctl restart bidmonitor
        echo "回滚完成"
    else
        echo "错误: 无可用回滚快照"
        exit 1
    fi
}
```

**自动清理**: 保留最近 3 个快照，其余删除：
```bash
cleanup_rollbacks() {
    cd /opt/bidmonitor/.rollback && ls -t | tail -n +4 | xargs rm -rf 2>/dev/null
}
```

### 3.11 访问信息输出 (`print_access_info`)

部署成功后输出：

```
========================================
   ✅ BidMonitor 部署成功！
========================================

  访问地址: http://<IP>:8080
  管理员账号: ${ADMIN_USER}
  配置文件: /opt/bidmonitor/server/server_config.json

  常用命令:
    查看状态: sudo systemctl status bidmonitor
    查看日志: sudo journalctl -u bidmonitor -f
    重启服务: sudo systemctl restart bidmonitor
    停止服务: sudo systemctl stop bidmonitor

  回滚管理:
    查看快照: ls -lt /opt/bidmonitor/.rollback/
    手动回滚: sudo bash /opt/bidmonitor/server/deploy/deploy.sh --rollback
```

## 4. 交互模式设计

### 4.1 首次部署流程

```
1. 系统检查...
2. 安装系统依赖...
3. 创建项目目录...
4. 选择部署模式 [Git/ZIP/Local]:
   - Git: 输入仓库 URL
   - ZIP: 输入 ZIP 文件路径
   - Local: 使用当前目录
5. 设置管理员账号 (默认 CDKJ/cdkj)
6. 是否配置域名? (y/N)
   - 输入域名: monitor.example.com
7. 是否安装 Nginx 反向代理? (y/N)
   - 如果 y: 安装 Nginx + 配置反向代理
8. 是否开放防火墙端口? (y/N)
9. 创建虚拟环境...
10. 安装 Python 依赖...
11. 安装 systemd 服务...
12. 启动服务...
13. 输出访问信息...
```

### 4.2 增量更新流程

```
1. 系统检查...
2. 检查当前部署状态...
3. 创建回滚快照...
4. 拉取最新代码 (Git pull / 解压 ZIP)...
5. 更新虚拟环境依赖...
6. 重启服务...
7. 验证服务状态...
8. 输出更新信息...
```

### 4.3 非交互模式

支持环境变量：

```bash
export BM_MODE="git"
export BM_REPO_URL="https://github.com/example/bidmonitor.git"
export BM_BRANCH="main"
export BM_ADMIN_USER="admin"
export BM_ADMIN_PASS="secure_password"
export BM_DOMAIN="monitor.example.com"
export BM_USE_NGINX="true"
export BM_OPEN_FIREWALL="false"

bash deploy.sh --non-interactive
```

## 5. 错误处理

### 5.1 Trap 错误捕获

```bash
trap 'echo "❌ 部署失败于步骤: $CURRENT_STEP"; rollback; exit 1' ERR
```

### 5.2 关键错误点

| 步骤 | 错误处理 |
|------|----------|
| 系统检查失败 | 提示安装依赖，退出 |
| 依赖安装失败 | 显示错误日志，退出 |
| 虚拟环境创建失败 | 检查 Python 版本，退出 |
| pip 安装失败 | 显示详细错误，退出 |
| systemd 安装失败 | 提示手动安装，继续 |
| 服务启动失败 | 查看日志，回滚，退出 |

### 5.3 日志记录

记录到 `/tmp/bidmonitor_deploy.log`：

```bash
exec > >(tee -a /tmp/bidmonitor_deploy.log) 2>&1
```

## 6. 颜色输出

```bash
# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# 输出函数
log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${BLUE}[STEP]${NC} $1"; }
log_ok()    { echo -e "${GREEN}✅ $1${NC}"; }
```

## 7. 幂等性保证

所有操作均可重复执行：

- 目录创建：`mkdir -p`
- 依赖安装：检查已安装则跳过
- 虚拟环境：存在则复用
- systemd 服务：存在则覆盖
- 防火墙规则：存在则跳过
- 服务启动：`systemctl restart`

## 8. 安全考虑

- **不自动开放公网端口**
- **密码输入隐藏回显**: `read -s`
- **不使用 root 运行服务**: 创建 `bidmonitor` 用户
- **配置文件权限**: `chmod 600 server_config.json`
- **日志权限**: `chmod 644`（可读不可写）

## 9. 测试策略

由于是部署脚本，测试主要通过：

1. **Dry-run 模式**: `--dry-run` 参数，仅输出计划操作
2. **手动验证**: 在测试服务器上执行
3. **回滚测试**: 验证回滚机制正常工作
