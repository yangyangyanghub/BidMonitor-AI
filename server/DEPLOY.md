# BidMonitor 服务器部署指南

## 一、准备工作

### 1. 安装 Python 3.9

```bash
# 安装编译依赖
sudo yum install -y gcc openssl-devel bzip2-devel libffi-devel zlib-devel wget make

# 下载并安装
cd /tmp
wget https://www.python.org/ftp/python/3.9.18/Python-3.9.18.tgz
tar xzf Python-3.9.18.tgz
cd Python-3.9.18
./configure --enable-optimizations
make -j4
sudo make altinstall

# 验证
python3.9 --version
```

### 2. 创建项目目录

```bash
sudo mkdir -p /opt/bidmonitor
cd /opt/bidmonitor
python3.9 -m venv venv
source venv/bin/activate
```

---

## 二、上传代码

### 方法1：使用 SCP（推荐）

在本地 Windows 电脑上执行：

```powershell
# 打包代码
cd G:\BidMonitor
Compress-Archive -Path src,server,data -DestinationPath bidmonitor_deploy.zip -Force

# 上传到服务器（替换 YOUR_SERVER_IP 为实际IP）
scp bidmonitor_deploy.zip root@YOUR_SERVER_IP:/opt/bidmonitor/
```

在服务器上解压：

```bash
cd /opt/bidmonitor
unzip bidmonitor_deploy.zip
```

### 方法2：使用 Git

```bash
cd /opt/bidmonitor
git clone https://github.com/zhiqianzheng/BidMonitor.git .
```

---

## 三、安装依赖

```bash
cd /opt/bidmonitor
source venv/bin/activate
pip install -r server/requirements.txt
```

---

## 四、启动服务

### 测试运行（前台）

```bash
cd /opt/bidmonitor/server
python app.py
```

访问 http://YOUR_SERVER_IP:8080 测试

### 后台运行

```bash
chmod +x /opt/bidmonitor/server/*.sh
/opt/bidmonitor/server/start.sh
```

### 停止服务

```bash
/opt/bidmonitor/server/stop.sh
```

---

## 五、配置开机自启动

```bash
# 复制服务文件
sudo cp /opt/bidmonitor/server/bidmonitor.service /etc/systemd/system/

# 重载配置
sudo systemctl daemon-reload

# 启用自启动
sudo systemctl enable bidmonitor

# 启动服务
sudo systemctl start bidmonitor

# 查看状态
sudo systemctl status bidmonitor
```

---

## 六、配置防火墙

### 服务器防火墙

```bash
sudo firewall-cmd --zone=public --add-port=8080/tcp --permanent
sudo firewall-cmd --reload
```

### 阿里云安全组

1. 登录阿里云控制台
2. 进入 ECS 实例 → 安全组
3. 添加入站规则：
   - 端口范围：8080/8080
   - 授权对象：0.0.0.0/0

---

## 七、访问地址

手机浏览器打开：
```
http://YOUR_SERVER_IP:8080
```

---

## 八、常用命令

```bash
# 查看日志
tail -f /var/log/bidmonitor.log

# 重启服务
sudo systemctl restart bidmonitor

# 查看服务状态
sudo systemctl status bidmonitor
```

---

## 九、新版部署脚本（推荐）

`server/deploy/` 目录下提供了一键部署脚本，支持 Ubuntu 20.04/22.04 和 CentOS 7/8/AlmaLinux：

```bash
cd /opt/bidmonitor/server/deploy/

# 完整安装
sudo bash deploy.sh --install

# 更新代码
sudo bash deploy.sh --update

# 查看状态
sudo bash deploy.sh --status

# 备份数据
sudo bash deploy.sh --backup
```

---

## 十、Docker 部署

```bash
cd /opt/bidmonitor/server/deploy/

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f bidmonitor

# 更新
docker-compose pull && docker-compose up -d --build
```

---

## 十一、Nginx 反向代理 + HTTPS

```bash
# 1. 复制配置
sudo cp server/deploy/bidmonitor-nginx.conf /etc/nginx/sites-available/bidmonitor
sudo ln -s /etc/nginx/sites-available/bidmonitor /etc/nginx/sites-enabled/

# 2. 测试并重载
sudo nginx -t && sudo systemctl reload nginx

# 3. 启用 HTTPS
sudo certbot --nginx -d your_domain.com
```

详见 `server/deploy/bidmonitor-nginx.conf` 中的 HTTPS 配置模板。
