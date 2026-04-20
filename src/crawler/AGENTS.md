# src/crawler - 爬虫模块

**模块**: 13+ 网站爬虫实现

## OVERVIEW

多网站爬虫模块，支持政府采购、电力、能源等行业招标信息抓取。继承基类模式。

## STRUCTURE

```
src/crawler/
├── __init__.py           # 导出入口
├── base.py              # BaseCrawler 基类
├── selenium_crawler.py  # Selenium 通用爬虫
├── custom.py            # 自定义网站模板
├── ggzy.py              # 公共资源交易网
├── ccgp.py              # 中国政府采购网
├── chinabidding.py      # 中国招标网
├── chinatender.py       # 中国招标与采购网
├── dlnyzb.py            # 电力能源招标
├── ebnew.py             # 东方财富招标
├── pvyuan.py            # PV 光伏招标
├── qianlima.py          # 千里马
├── solarbe.py          # Solarbe 光伏
├── youuav.py           # 无人机招标
├── bidcenter.py        # 招标中心
└── plap.py             # PLAP 平台
```

## WHERE TO LOOK

| Task | File |
|------|------|
| 新增爬虫 | `custom.py` 或复制现有 |
| 修改抓取逻辑 | `base.py` |
| 反爬处理 | `selenium_crawler.py` |

## CONVENTIONS

- 继承 `BaseCrawler` 实现 `parse_list()` 和 `parse_detail()`
- 返回 `CrawlerResult` 对象
- 使用 `BeautifulSoup4` + `lxml` 解析
- 复杂站点用 Selenium
