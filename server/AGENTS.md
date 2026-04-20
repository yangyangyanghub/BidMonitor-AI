# server - Web 服务端

**模块**: FastAPI Web 应用

## OVERVIEW

基于 FastAPI 的 Web 服务器，提供 REST API 和 Web 界面。

## STRUCTURE

```
server/
├── app.py              # FastAPI 入口
├── requirements.txt    # 依赖
├── static/             # 前端资源
│   └── index.html     # Web 界面
├── setup.sh            # 一键部署
├── deploy.sh           # 部署脚本
├── start.sh            # 启动脚本
├── stop.sh             # 停止脚本
└── bidmonitor.service # systemd 服务
```

## WHERE TO LOOK

| Task | Location |
|------|----------|
| API 接口 | `server/app.py` |
| Web 前端 | `server/static/index.html` |
| 部署配置 | `server/*.sh` |

## CONVENTIONS

- FastAPI 框架
- 静态文件托管于 `/static`
- 服务配置文件 `bidmonitor.service`
- 手动部署（无 CI/CD）
