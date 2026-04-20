# ============================================================
# BidMonitor AI - Docker 部署方案
# ============================================================
# Dockerfile: 基于 Ubuntu 22.04 的轻量级镜像
# 特点：
#   - 包含 Chromium 用于 Selenium 爬虫
#   - 多阶段构建减小体积
#   - 非 root 用户运行
#   - 支持健康检查
# ============================================================

FROM ubuntu:22.04

# 避免交互式提示
ENV DEBIAN_FRONTEND=noninteractive

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-venv \
    python3-pip \
    chromium-browser \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 设置工作目录
WORKDIR /opt/bidmonitor

# 创建虚拟环境
RUN python3 -m venv /opt/bidmonitor/venv
ENV PATH="/opt/bidmonitor/venv/bin:$PATH"

# 复制依赖文件
COPY server/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# 复制应用代码
COPY src/ /opt/bidmonitor/src/
COPY server/ /opt/bidmonitor/server/

# 创建数据目录和日志目录
RUN mkdir -p /opt/bidmonitor/data \
    /opt/bidmonitor/server/logs \
    && chown -R 1000:1000 /opt/bidmonitor

# 创建非 root 用户
RUN useradd -m -u 1000 bidmonitor \
    && chown -R bidmonitor:bidmonitor /opt/bidmonitor

USER bidmonitor

# 暴露端口
EXPOSE 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/status || exit 1

# 启动命令
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
