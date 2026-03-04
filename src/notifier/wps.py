"""
WPS多维表格Webhook通知模块
用于将爬取的数据写入WPS多维表格
"""
import requests
import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class WPSNotifier:
    """WPS多维表格Webhook通知器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化WPS通知器
        
        Args:
            config: 配置字典，包含以下字段:
                - webhook_url: WPS多维表格的Webhook地址
                - api_token: API令牌（可选）
                - table_name: 表格名称（可选，用于日志）
        """
        self.webhook_url = config.get('webhook_url', '')
        self.api_token = config.get('api_token', '')
        self.table_name = config.get('table_name', 'WPS多维表格')
        
        # 验证配置
        if not self.webhook_url:
            logger.warning("WPS Webhook URL未配置，跳过WPS通知")
            self.enabled = False
        else:
            self.enabled = True
            logger.info(f"WPS通知器已启用: {self.table_name}")
    
    def send(self, bids: List) -> bool:
        """
        发送招标信息到WPS多维表格
        
        Args:
            bids: BidInfo列表
            
        Returns:
            是否成功
        """
        if not self.enabled:
            logger.debug("WPS通知未启用，跳过")
            return True
        
        if not bids:
            logger.info("没有数据需要发送到WPS")
            return True
        
        success_count = 0
        failed_count = 0
        
        for bid in bids:
            try:
                # 准备数据 - 根据WPS多维表格Webhook格式
                data = {
                    "title": bid.title,
                    "url": bid.url,
                    "publish_date": bid.publish_date,
                    "source": bid.source,
                    "content": bid.content if hasattr(bid, 'content') else '',
                }
                
                # 发送POST请求到Webhook
                headers = {
                    'Content-Type': 'application/json',
                }
                if self.api_token:
                    headers['Authorization'] = f'Bearer {self.api_token}'
                
                response = requests.post(
                    self.webhook_url,
                    json=data,
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code in [200, 201]:
                    success_count += 1
                    logger.debug(f"[WPS] 发送成功: {bid.title[:30]}...")
                else:
                    failed_count += 1
                    logger.warning(f"[WPS] 发送失败: {response.status_code} - {response.text[:100]}")
            
            except requests.exceptions.RequestException as e:
                failed_count += 1
                logger.error(f"[WPS] 发送异常: {e}")
            except Exception as e:
                failed_count += 1
                logger.error(f"[WPS] 未知错误: {e}")
        
        # 发送完成统计
        total = len(bids)
        logger.info(f"[WPS] 发送完成: 成功{success_count}条, 失败{failed_count}条, 共{total}条")
        
        return failed_count == 0
    
    def send_batch(self, bids: List, batch_size: int = 10) -> bool:
        """
        批量发送数据到WPS多维表格
        
        Args:
            bids: BidInfo列表
            batch_size: 每批数量
            
        Returns:
            是否成功
        """
        if not self.enabled or not bids:
            return True
        
        # 分批处理
        for i in range(0, len(bids), batch_size):
            batch = bids[i:i+batch_size]
            logger.info(f"[WPS] 发送第 {i//batch_size + 1} 批 ({len(batch)} 条)")
            
            if not self.send(batch):
                logger.error(f"[WPS] 批次 {i//batch_size + 1} 发送失败")
                return False
        
        return True


class WPSNotifierSimple:
    """简化的WPS通知器 - 直接写入HTTP API"""
    
    def __init__(self, webhook_url: str, api_token: str = ''):
        self.webhook_url = webhook_url
        self.api_token = api_token
    
    def add_row(self, data: Dict[str, Any]) -> bool:
        """
        添加一行数据到多维表格
        
        Args:
            data: 字典，键为字段名，值为数据
            
        Returns:
            是否成功
        """
        try:
            headers = {'Content-Type': 'application/json'}
            if self.api_token:
                headers['Authorization'] = f'Bearer {self.api_token}'
            
            response = requests.post(
                self.webhook_url,
                json=data,
                headers=headers,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"[WPS] 添加成功: {data.get('title', 'N/A')}")
                return True
            else:
                logger.warning(f"[WPS] 添加失败: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"[WPS] 添加异常: {e}")
            return False
    
    def add_rows_batch(self, data_list: List[Dict[str, Any]]) -> int:
        """
        批量添加数据
        
        Args:
            data_list: 数据列表
            
        Returns:
            成功数量
        """
        success = 0
        for data in data_list:
            if self.add_row(data):
                success += 1
        return success


# 便捷函数
def create_wps_notifier(config: Dict[str, Any]) -> WPSNotifier:
    """创建WPS通知器的便捷函数"""
    return WPSNotifier(config)