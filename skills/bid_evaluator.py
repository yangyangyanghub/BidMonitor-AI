"""
招投标信息评估筛选模块

对 bids.db 中每天发现的招投标信息进行多维度评估，筛选出最有参考性的项目
"""
import sqlite3
import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging


@dataclass
class BidScore:
    """招投标评分结果"""
    bid_id: int
    title: str
    url: str
    source: str
    publish_date: str
    purchaser: str

    # 各维度评分 (0-100)
    relevance_score: float      # 相关性评分
    freshness_score: float      # 时效性评分
    authority_score: float      # 权威性评分
    completeness_score: float   # 完整性评分
    scale_score: float          # 规模评分

    # 总分
    total_score: float
    rank: int = 0


class BidEvaluator:
    """招投标信息评估器"""

    def __init__(self, db_path: str = "data/bids.db", config: Dict[str, Any] = None):
        """
        初始化评估器

        Args:
            db_path: 数据库路径
            config: 评估配置，包括权重和参数
        """
        self.db_path = db_path
        self.config = self._default_config()
        if config:
            self.config.update(config)

        # 来源网站权威性评分表
        self.authority_map = {
            "中国政府采购网": 100,
            "中国政府采购网中央公告": 100,
            "中国政府采购网地方公告": 95,
            "采购与招标网": 90,
            "国家电网电子商务平台": 95,
            "中国能建电子采购平台": 90,
            "华能集团电子商务平台": 90,
            "中国电建采购电子商务平台": 85,
            "公共资源交易中心": 85,
        }

        self.logger = logging.getLogger(__name__)

    def _default_config(self) -> Dict[str, Any]:
        """默认配置"""
        return {
            # 各维度权重 (总和应为1.0)
            "weights": {
                "relevance": 0.30,      # 相关性 30%
                "freshness": 0.25,       # 时效性 25%
                "authority": 0.20,       # 权威性 20%
                "completeness": 0.15,   # 完整性 15%
                "scale": 0.10,           # 规模 10%
            },
            # 筛选参数
            "min_score": 50.0,          # 最低总分阈值
            "top_n": 20,                # 每天返回 Top N 项
            "days": 7,                  # 评估最近 N 天的数据
            # 相关性关键词
            "relevance_keywords": [
                "采购", "招标", "招标", "服务", "项目", "工程",
                "建设", "运维", "系统", "平台", "软件", "开发"
            ],
            # 规模关键词 (从大到小)
            "scale_keywords": {
                "国家": 100,
                "中央": 100,
                "省": 90,
                "市级": 80,
                "市级": 70,
                "县级": 60,
                "乡镇": 50,
            }
        }

    def evaluate_daily(self, days: int = None) -> List[BidScore]:
        """
        评估最近 N 天的招投标信息

        Args:
            days: 评估最近几天的数据 (默认使用配置值)

        Returns:
            评分结果列表，按总分降序排列
        """
        days = days or self.config["days"]

        # 获取数据
        bids = self._fetch_bids(days)
        if not bids:
            self.logger.warning(f"最近 {days} 天没有找到招投标数据")
            return []

        self.logger.info(f"开始评估 {len(bids)} 条招投标记录...")

        # 逐条评估
        scores = []
        for bid in bids:
            score = self._evaluate_single(bid)
            scores.append(score)

        # 排序并设置排名
        scores.sort(key=lambda x: x.total_score, reverse=True)
        for idx, score in enumerate(scores, 1):
            score.rank = idx

        # 筛选高分项目
        min_score = self.config["min_score"]
        top_n = self.config["top_n"]
        high_scores = [s for s in scores if s.total_score >= min_score][:top_n]

        self.logger.info(f"评估完成: {len(high_scores)}/{len(bids)} 条高分项目")

        return high_scores

    def _fetch_bids(self, days: int) -> List[Dict[str, Any]]:
        """从数据库获取最近 N 天的数据"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, title, url, publish_date, source, content, purchaser, created_at
            FROM bids
            WHERE datetime(created_at) > datetime('now', ?)
            ORDER BY created_at DESC
        """, (f'-{days} days',))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def _evaluate_single(self, bid: Dict[str, Any]) -> BidScore:
        """评估单条招投标信息"""

        # 1. 相关性评分
        relevance = self._score_relevance(bid)

        # 2. 时效性评分
        freshness = self._score_freshness(bid)

        # 3. 权威性评分
        authority = self._score_authority(bid)

        # 4. 完整性评分
        completeness = self._score_completeness(bid)

        # 5. 规模评分
        scale = self._score_scale(bid)

        # 计算加权总分
        weights = self.config["weights"]
        total = (
            relevance * weights["relevance"] +
            freshness * weights["freshness"] +
            authority * weights["authority"] +
            completeness * weights["completeness"] +
            scale * weights["scale"]
        )

        return BidScore(
            bid_id=bid["id"],
            title=bid["title"],
            url=bid["url"],
            source=bid["source"],
            publish_date=bid["publish_date"],
            purchaser=bid["purchaser"] or "",
            relevance_score=relevance,
            freshness_score=freshness,
            authority_score=authority,
            completeness_score=completeness,
            scale_score=scale,
            total_score=total,
        )

    def _score_relevance(self, bid: Dict[str, Any]) -> float:
        """相关性评分: 基于标题和内容的关键词密度"""
        text = (bid["title"] + " " + (bid["content"] or "")).lower()
        keywords = self.config["relevance_keywords"]

        # 统计关键词出现次数
        matched = sum(1 for kw in keywords if kw in text)

        # 计算得分: 匹配数 / 关键词数 * 100
        score = min(100.0, (matched / len(keywords)) * 100) if keywords else 0

        return score

    def _score_freshness(self, bid: Dict[str, Any]) -> float:
        """时效性评分: 基于创建时间"""
        try:
            created_at = datetime.strptime(bid["created_at"], "%Y-%m-%d %H:%M:%S")
        except:
            created_at = datetime.now()

        days_ago = (datetime.now() - created_at).days

        # 衰减函数: 1 天 = 100 分，7 天 = 50 分，14 天 = 20 分
        if days_ago <= 1:
            return 100.0
        elif days_ago <= 3:
            return 80.0
        elif days_ago <= 7:
            return 50.0
        elif days_ago <= 14:
            return 20.0
        else:
            return 10.0

    def _score_authority(self, bid: Dict[str, Any]) -> float:
        """权威性评分: 基于来源网站"""
        source = bid["source"]

        # 在权威性表中查找
        for key, value in self.authority_map.items():
            if key in source:
                return float(value)

        # 默认评分: 根据来源名称特征
        if "政府采购" in source or "国家" in source or "中央" in source:
            return 85.0
        elif "省" in source or "集团" in source:
            return 75.0
        elif "市" in source:
            return 65.0
        else:
            return 50.0

    def _score_completeness(self, bid: Dict[str, Any]) -> float:
        """完整性评分: 基于字段填充情况"""
        score = 0.0

        # 必备字段
        if bid["title"] and len(bid["title"]) >= 10:
            score += 25.0
        if bid["url"]:
            score += 15.0
        if bid["publish_date"]:
            score += 15.0
        if bid["source"]:
            score += 15.0
        if bid["purchaser"]:
            score += 15.0
        if bid["content"] and len(bid["content"]) >= 50:
            score += 15.0

        return score

    def _score_scale(self, bid: Dict[str, Any]) -> float:
        """规模评分: 基于标题和发布单位推测项目规模"""
        text = (bid["title"] + " " + (bid["purchaser"] or "")).lower()
        scale_keywords = self.config["scale_keywords"]

        # 查找规模关键词
        for key, value in scale_keywords.items():
            if key in text:
                return float(value)

        # 默认评分
        return 60.0

    def generate_summary(self, scores: List[BidScore]) -> str:
        """生成评估报告摘要"""

        if not scores:
            return "未找到符合条件的高分招投标项目"

        lines = [
            "=" * 60,
            f"📊 招投标信息评估报告 (Top {len(scores)})",
            "=" * 60,
            "",
        ]

        # 统计信息
        avg_score = sum(s.total_score for s in scores) / len(scores)
        sources = {}
        for s in scores:
            sources[s.source] = sources.get(s.source, 0) + 1

        lines.append(f"✅ 平均评分: {avg_score:.1f}")
        lines.append(f"📁 来源分布: {dict(sorted(sources.items(), key=lambda x: x[1], reverse=True))}")
        lines.append("")

        # Top 项目详情
        lines.append("🔥 推荐项目列表:")
        lines.append("-" * 60)

        for idx, score in enumerate(scores, 1):
            lines.append("")
            lines.append(f"【{idx}】总分: {score.total_score:.1f} | {score.source}")
            lines.append(f"    标题: {score.title[:50]}...")
            lines.append(f"    发布: {score.publish_date} | 采购方: {score.purchaser[:30] or '未知'}")
            lines.append(f"    链接: {score.url}")

            # 各维度评分
            lines.append(f"    评分: 相关={score.relevance_score:.0f} "
                        f"时效={score.freshness_score:.0f} "
                        f"权威={score.authority_score:.0f} "
                        f"完整={score.completeness_score:.0f} "
                        f"规模={score.scale_score:.0f}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)


def main():
    """测试运行"""
    logging.basicConfig(level=logging.INFO)

    # 创建评估器
    evaluator = BidEvaluator()

    # 评估最近 7 天的数据
    results = evaluator.evaluate_daily(days=7)

    # 生成并保存报告
    report = evaluator.generate_summary(results)
    with open("bid_evaluation_report.txt", "w", encoding="utf-8") as f:
        f.write(report)
    # 保存到文件
    with open("bid_evaluation_report.txt", "w", encoding="utf-8") as f:
        f.write(report)

    print("\n报告已保存到: bid_evaluation_report.txt")


if __name__ == "__main__":
    main()
