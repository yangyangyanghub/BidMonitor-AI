# PROJECT KNOWLEDGE BASE

**Generated:** 2026-02-25
**Commit:** 63a0e13
**Branch:** main

## OVERVIEW

BidMonitor AI - 智能招投标监控系统。Python 3.8+ 双端应用（桌面 GUI + 服务器 Web）。

## STRUCTURE

```
BidMonitor-AI/
├── run.py              # 桌面版入口 → src.gui.main
├── requirements.txt    # 主依赖
├── src/                # 核心模块
│   ├── gui.py          # Tkinter 桌面界面
│   ├── monitor_core.py # 监控核心
│   ├── ai_guard.py     # AI 过滤
│   ├── crawler/        # 爬虫模块 (13+ 网站)
│   ├── notifier/       # 通知 (邮件/短信/微信/语音)
│   ├── matcher/        # 关键词匹配
│   ├── scheduler/      # 定时任务
│   ├── database/       # SQLite 存储
│   └── utils/          # 工具函数
└── server/             # FastAPI Web 服务
    ├── app.py          # 入口
    ├── static/         # Web 前端
    └── *.sh            # 部署脚本
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| 修改桌面 GUI | `src/gui.py` | Tkinter 主界面 |
| 修改 Web 后端 | `server/app.py` | FastAPI 应用 |
| 添加新爬虫 | `src/crawler/` | 继承 `BaseCrawler` |
| 修改通知逻辑 | `src/notifier/` | email/voice/sms/wechat |
| 修改匹配规则 | `src/matcher/keyword.py` | 关键词算法 |
| 监控系统核心 | `src/monitor_core.py` | 主监控逻辑 |

## CONVENTIONS

- **Python 版本**: 3.8+
- **无类型标注**: 项目未使用 Type Hints
- **中文注释**: 代码使用中文注释
- **无测试目录**: requirements.txt 中有 pytest 但无 tests/
- **配置存储**: `user_config.json` (运行时生成)
- **数据库**: SQLite (`bidmonitor.db`)

## ANTI-PATTERNS (THIS PROJECT)

- **无标准配置**: 缺少 `pyproject.toml`、`setup.py`
- **无 CI/CD**: 纯手动部署，无 GitHub Actions
- **敏感信息明文**: `pack.bat` 包含明文服务器密码
- **无容器化**: 未使用 Docker

## COMMANDS

```bash
# 桌面版
python run.py

# CLI 模式
python src/main.py --crawl-once
python src/main.py --test-email

# 服务器版
cd server
pip install -r requirements.txt
python app.py
```

## NOTES

- 双入口架构：桌面版 (`run.py`) + 服务器版 (`server/app.py`)
- 爬虫使用 `requests` + `BeautifulSoup4` + `lxml`，部分使用 Selenium
- AI 过滤支持 DeepSeek / OpenAI API
