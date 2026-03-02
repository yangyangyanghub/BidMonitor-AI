"""
自定义通用爬虫 - 用于用户添加的网站
"""
from typing import List
from urllib.parse import urljoin, urlparse, parse_qs
from datetime import datetime
from .base import BaseCrawler, BidInfo

import requests
import json
import re
import random


class CustomCrawler(BaseCrawler):
    """自定义通用爬虫"""
    
    def __init__(self, config: dict, name: str, url: str):
        self._name = name  # 必须在 super().__init__() 之前设置，因为父类会访问 self.name
        self.url = url
        
        # 检测是否为河北省招标网
        self._is_hebei_api = 'szj.hebei.gov.cn' in url and '/zbtbfwpt/' in url
        
        # 如果是河北省招标网，解析selectype参数确定API端点
        self._hebei_api_endpoint = None
        if self._is_hebei_api:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            selectype = params.get('selectype', ['zbgg'])[0]
            # 根据selectype确定API端点
            endpoint_map = {
                'zbgg': 'zbgg.do',      # 招标公告
                'bggg': 'bggg.do',      # 变更公告
                'dygs': 'dygs.do',      # 答疑公示
                'kbjl': 'kbjl.do',      # 开标记录
                'pbgs': 'pbgs.do',      # 中标候选人公示
                'zhongbgg': 'zhongbgg.do',  # 中标结果公示
                'qylx': 'qylx.do',      # 签约履行
                'zbpro': 'zbpro.do',    # 招标计划公告
            }
            self._hebei_api_endpoint = endpoint_map.get(selectype, 'zbgg.do')
        
        super().__init__(config)
        
    @property
    def name(self) -> str:
        return self._name
        
    def get_list_urls(self) -> List[str]:
        return [self.url]
    
    def fetch(self, url: str, params=None) -> str:
        """重写fetch方法，处理河北省招标网API"""
        
        # 如果是河北省招标网的招标计划公告(zbpro)，需要特殊处理
        if self._is_hebei_api and self._hebei_api_endpoint == 'zbpro.do':
            return self._fetch_hebei_zbpro()
        
        # 如果是河北省招标网，使用API获取数据
        if self._is_hebei_api and self._hebei_api_endpoint:
            return self._fetch_hebei_api()
        
        # 否则使用默认的HTML获取方式
        return super().fetch(url, params)
    
    def _fetch_hebei_api(self) -> str:
        """通过API获取河北省招标网数据"""
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # 构造API URL
        base_url = 'https://szj.hebei.gov.cn/zbtbfwpt/tender/xxgk/'
        api_url = base_url + self._hebei_api_endpoint
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://szj.hebei.gov.cn/zbtbfwpt/tender/xxgk/list.do?selectype=zbgg',
        }
        
        # POST数据
        data = {
            'page': '1',
            'TimeStr': '',
            'allDq': '',
            'allHy': 'reset1,',
            'AllPtName': '',
            'KeyStr': '',
            'KeyType': 'ggname',
            'captcha': ''
        }
        
        for attempt in range(self.max_retries):
            try:
                self.logger.debug(f"正在请求河北省招标网API: {api_url} (尝试 {attempt + 1}/{self.max_retries})")
                
                response = self.session.post(
                    api_url,
                    headers=headers,
                    data=data,
                    timeout=self.timeout,
                    verify=False
                )
                response.raise_for_status()
                
                # 验证返回的是JSON且有数据
                try:
                    json_data = response.json()
                    if json_data.get('result') is True:
                        # 添加请求延迟
                        delay = self.request_delay + random.uniform(0, 2)
                        self.logger.debug(f"请求成功，等待 {delay:.1f} 秒")
                        import time
                        time.sleep(delay)
                        return response.text
                    else:
                        self.logger.warning(f"API返回结果为false: {api_url}")
                except json.JSONDecodeError:
                    self.logger.warning(f"API返回的不是JSON: {api_url}")
                    
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"API请求失败: {api_url}, 错误: {e}")
                
            if attempt < self.max_retries - 1:
                wait_time = (2 ** (attempt + 1)) + random.uniform(0, 1)
                self.logger.info(f"等待 {wait_time:.1f} 秒后重试...")
                import time
                time.sleep(wait_time)
        
        # API失败，回退到普通HTML获取方式
        self.logger.warning(f"API请求失败，回退到普通HTML解析: {api_url}")
        return super().fetch(self.url, None)
    
    def _fetch_hebei_zbpro(self) -> str:
        """获取招标计划公告数据 - 需要使用Selenium模拟点击"""
        # 尝试导入Selenium
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from webdriver_manager.chrome import ChromeDriverManager
            import time
        except ImportError as e:
            self.logger.warning(f"Selenium未安装: {e}，回退到普通方式")
            return super().fetch(self.url, None)
        
        self.logger.info(f"使用Selenium点击获取招标计划公告数据")
        
        driver = None
        try:
            # 配置Chrome选项
            options = Options()
            options.add_argument('--headless=new')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # 初始化浏览器
            try:
                driver = webdriver.Chrome(options=options)
            except:
                try:
                    service = Service(ChromeDriverManager().install())
                    driver = webdriver.Chrome(service=service, options=options)
                except Exception as e2:
                    self.logger.error(f"初始化Chrome失败: {e2}")
                    return super().fetch(self.url, None)
            
            # 访问页面
            driver.get(self.url)
            time.sleep(3)  # 等待页面加载
            
            # 查找并点击"招标计划公告"链接
            try:
                # 等待页面加载完成
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # 查找招标计划公告链接 - 使用XPath
                zbpro_link = driver.find_element(By.XPATH, "//a[contains(text(),'招标计划公告')]")
                if zbpro_link:
                    self.logger.info("点击招标计划公告链接")
                    zbpro_link.click()
                    time.sleep(3)  # 等待数据加载
                    
            except Exception as e:
                self.logger.warning(f"点击招标计划公告失败: {e}，尝试获取当前页面")
            
            # 获取页面源码
            html = driver.page_source
            self.logger.info(f"获取到页面，长度: {len(html)}")
            
            return html
            
        except Exception as e:
            self.logger.error(f"Selenium获取招标计划公告失败: {e}")
            return super().fetch(self.url, None)
        
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
    def parse(self, html: str) -> List[BidInfo]:
        # 如果是河北省招标网的招标计划公告，使用专门的解析方法
        if self._is_hebei_api and self._hebei_api_endpoint == 'zbpro.do':
            return self._parse_hebei_zbpro_html(html)
        
        # 如果是河北省招标网，检测是JSON还是HTML
        if self._is_hebei_api:
            # 检查是否是JSON响应（API成功）还是HTML（API失败回退）
            if html and html.strip().startswith('{'):
                return self._parse_hebei_json(html)
            else:
                # API失败，回退到HTML解析
                return self._parse_html_generic(html)
        
        # 默认HTML解析
        return self._parse_html_generic(html)
    
    def _parse_hebei_zbpro_html(self, html: str) -> List[BidInfo]:
        """专门解析招标计划公告的HTML页面"""
        from bs4 import BeautifulSoup
        from datetime import datetime
        
        soup = BeautifulSoup(html, 'lxml')
        bids = []
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 查找所有详情链接 - 招标计划公告的链接包含 /infogk/detail.do 且 categoryid=zbjhgg
        seen_urls = set()
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)
            
            # 只提取招标计划公告的详情链接
            if '/infogk/detail.do' not in href:
                continue
            if 'categoryid=zbjhgg' not in href:
                continue
            
            # 过滤无效标题
            if not text or len(text) < 4:
                continue
            if href.lower().startswith(('javascript:', '#', 'mailto:', 'tel:')):
                continue
            
            # 补全URL
            full_url = urljoin(self.url, href)
            
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            
            bids.append(BidInfo(
                title=text,
                url=full_url,
                publish_date=today,
                source=self.name
            ))
        
        self.logger.debug(f"解析到 {len(bids)} 条招标计划公告")
        return bids
    
    def _parse_hebei_json(self, json_str: str) -> List[BidInfo]:
        """解析河北省招标网API返回的JSON数据"""
        bids = []
        
        try:
            data = json.loads(json_str)
            # 根据API端点确定数据键名
            endpoint_to_key = {
                'zbgg.do': 'search_ZbGg',
                'bggg.do': 'search_BgGg',
                'dygs.do': 'search_DyGs',
                'kbjl.do': 'search_KbJl',
                'pbgs.do': 'search_PbGs',
                'zhongbgg.do': 'search_ZhongbGg',
                'qylx.do': 'search_QyLx',
                'zbpro.do': 'search_ZbPro',
            }
            key = endpoint_to_key.get(self._hebei_api_endpoint, 'search_ZbGg')
            items = data.get('t', {}).get(key, [])
            
            base_detail_url = 'https://szj.hebei.gov.cn/zbtbfwpt/infogk/detail.do'
            
            for item in items:
                # 解析发布时间
                publish_time = item.get('bulletinissuetime')
                if publish_time:
                    # 时间戳转换为日期字符串
                    publish_date = datetime.fromtimestamp(publish_time / 1000).strftime('%Y-%m-%d')
                else:
                    publish_date = datetime.now().strftime('%Y-%m-%d')
                
                # 构造详情页URL
                infoid = item.get('tenderbulletincode', '')
                categoryid = item.get('tenderprojectclassifycode', '')
                bdcodes = item.get('bidSectionCodes', '')
                detail_url = f"{base_detail_url}?categoryid=101101&infoid={infoid}&bdcodes={bdcodes},"
                
                title = item.get('bulletinname', '')
                if not title:
                    continue
                
                bids.append(BidInfo(
                    title=title,
                    url=detail_url,
                    publish_date=publish_date,
                    source=self.name
                ))
            
            self.logger.debug(f"解析到 {len(bids)} 条招标信息")
            
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            self.logger.error(f"解析JSON失败: {e}")
        
        return bids
    
    def _parse_html_generic(self, html: str) -> List[BidInfo]:
        """通用的HTML解析方法"""
        soup = self.parse_html(html)
        bids = []
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 提取所有链接
        seen_urls = set()
        
        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True)
            href = a['href']
            
            # 简单过滤无效链接
            if not text or len(text) < 4: # 标题太短通常不是招标信息
                continue
            if href.lower().startswith(('javascript:', '#', 'mailto:', 'tel:')):
                continue
                
            # 补全URL
            full_url = urljoin(self.url, href)
            
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            
            # 创建BidInfo
            # 注意：这里我们返回页面上所有看起来像标题的链接
            # 真正的关键字过滤会在 MonitorCore 中进行
            bids.append(BidInfo(
                title=text,
                url=full_url,
                publish_date=today, # 通用爬虫很难准确提取日期，使用当前日期
                source=self.name
            ))
        
        return bids
    
    def crawl(self, stop_event=None):
        """重写crawl方法，绕过zbpro的anti-crawler检测"""
        from typing import List
        import time
        
        # Check stop signal
        if stop_event and stop_event.is_set():
            self.logger.info(f"[{self.name}] 检测到停止信号，跳过爬取")
            return []
        
        self.logger.info(f"[{self.name}] Starting crawl, 1 page(s)")
        
        all_bids = []
        urls = self.get_list_urls()
        
        for url in urls:
            # Check stop signal
            if stop_event and stop_event.is_set():
                self.logger.info(f"[{self.name}] 检测到停止信号，中断爬取")
                break
            
            html = self.fetch(url)
            if html:
                # 对于zbpro，绕过anti-crawler检测（因为页面包含captcha关键字但实际有数据）
                if self._is_hebei_api and self._hebei_api_endpoint == 'zbpro.do':
                    self.logger.debug(f"[{self.name}] 跳过anti-crawler检测 (zbpro特殊处理)")
                elif self._is_blocked(html):
                    self.logger.warning(f"[{self.name}] BLOCKED by anti-crawler at {url}")
                    continue
                
                try:
                    bids = self.parse(html)
                    all_bids.extend(bids)
                    self.logger.info(f"[{self.name}] Got {len(bids)} items from {url}")
                except Exception as e:
                    self.logger.error(f"[{self.name}] Parse failed {url}: {e}")
            
            # 请求间隔
            delay = self.request_delay + random.uniform(0, 2)
            time.sleep(delay)
        
        self.logger.info(f"[{self.name}] Crawl done, got {len(all_bids)} items total")
        return all_bids
