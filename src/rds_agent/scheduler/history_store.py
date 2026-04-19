"""健康历史存储 - 记录和查询健康趋势。"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path
from collections import defaultdict

from rds_agent.scheduler.state import (
    HealthHistory,
    TaskExecution,
)
from rds_agent.utils.logger import get_logger

logger = get_logger("history_store")


class HistoryStore:
    """健康历史存储"""

    def __init__(self, storage_path: Optional[str] = None):
        """初始化历史存储"""
        self.storage_path = Path(storage_path or "./data/history")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 内存缓存
        self.history: dict[str, HealthHistory] = {}

        # 按实例分组的索引
        self.instance_history: dict[str, list[str]] = defaultdict(list)

        logger.info(f"历史存储初始化: {self.storage_path}")

    def record_health(self, execution: TaskExecution) -> Optional[HealthHistory]:
        """记录健康数据"""
        if not execution.result_data:
            return None

        instance = execution.instance_name

        # 获取上一次记录（用于计算趋势）
        last_record = self.get_last_health(instance)

        # 创建记录
        history_id = str(uuid.uuid4())
        history = HealthHistory(
            id=history_id,
            instance_name=instance,
            overall_score=execution.overall_score or 0,
            overall_status=execution.overall_status or "unknown",
            category_scores=execution.result_data.get("category_scores", {}),
            critical_count=execution.critical_count,
            warning_count=execution.warning_count,
            recorded_at=execution.end_time or datetime.now(),
            execution_id=execution.id,
        )

        # 计算变化和趋势
        if last_record:
            history.score_change = history.overall_score - last_record.overall_score

            # 确定趋势
            if history.score_change > 5:
                history.trend = "improving"
            elif history.score_change < -5:
                history.trend = "degrading"
            else:
                history.trend = "stable"

        # 存储记录
        self.history[history_id] = history
        self.instance_history[instance].append(history_id)

        # 写入文件
        self._save_to_file(history)

        logger.info(f"记录健康数据: {instance}, 分数={history.overall_score}, 趋势={history.trend}")

        return history

    def get_last_health(self, instance: str) -> Optional[HealthHistory]:
        """获取最近的健康记录"""
        history_ids = self.instance_history.get(instance, [])
        if not history_ids:
            # 尝试从文件加载
            return self._load_last_from_file(instance)

        # 获取所有记录并按时间排序，返回最新的
        records = [self.history.get(hid) for hid in history_ids if hid in self.history]
        if not records:
            return None

        # 按recorded_at排序，返回最新的
        records.sort(key=lambda r: r.recorded_at, reverse=True)
        return records[0]

    def get_health_history(
        self,
        instance: str,
        days: int = 7,
        limit: int = 100
    ) -> list[HealthHistory]:
        """获取健康历史"""
        history_ids = self.instance_history.get(instance, [])

        # 如果内存中没有，从文件加载
        if not history_ids:
            return self._load_history_from_file(instance, days, limit)

        # 时间范围过滤
        start_time = datetime.now() - timedelta(days=days)

        records = []
        for hid in history_ids:
            record = self.history.get(hid)
            if record and record.recorded_at >= start_time:
                records.append(record)

        # 按时间排序（最新在前）
        records.sort(key=lambda r: r.recorded_at, reverse=True)

        return records[:limit]

    def get_health_trend(self, instance: str, days: int = 7) -> dict:
        """获取健康趋势分析"""
        history = self.get_health_history(instance, days)

        if not history:
            return {
                "instance": instance,
                "has_data": False,
                "message": "无历史数据",
            }

        # 计算趋势统计
        scores = [h.overall_score for h in history]

        avg_score = sum(scores) / len(scores)
        min_score = min(scores)
        max_score = max(scores)

        # 最近7条记录的趋势分析
        recent_records = history[:7]
        recent_trends = [h.trend for h in recent_records if h.trend]

        # 确定整体趋势
        improving_count = len([t for t in recent_trends if t == "improving"])
        degrading_count = len([t for t in recent_trends if t == "degrading"])

        overall_trend = "stable"
        if improving_count > degrading_count + 2:
            overall_trend = "improving"
        elif degrading_count > improving_count + 2:
            overall_trend = "degrading"

        return {
            "instance": instance,
            "has_data": True,
            "record_count": len(history),
            "current_score": history[0].overall_score if history else None,
            "avg_score": round(avg_score, 2),
            "min_score": min_score,
            "max_score": max_score,
            "overall_trend": overall_trend,
            "score_change_last_7": history[0].score_change if history and history[0].score_change else 0,
            "critical_count_avg": round(sum(h.critical_count for h in history) / len(history), 2),
            "warning_count_avg": round(sum(h.warning_count for h in history) / len(history), 2),
            "trend_summary": {
                "improving": improving_count,
                "stable": len([t for t in recent_trends if t == "stable"]),
                "degrading": degrading_count,
            },
        }

    def get_all_instances_trend(self, days: int = 7) -> list[dict]:
        """获取所有实例的趋势"""
        instances = list(self.instance_history.keys())

        # 如果内存中没有，从文件扫描
        if not instances:
            instances = self._scan_instances_from_file()

        trends = []
        for instance in instances:
            trend = self.get_health_trend(instance, days)
            trends.append(trend)

        # 按分数排序（最低在前）
        trends.sort(key=lambda t: t.get("current_score", 100) or 100)

        return trends

    def compare_health(
        self,
        instance: str,
        compare_days: int = 7
    ) -> dict:
        """健康对比分析"""
        current = self.get_last_health(instance)
        past = self._get_health_days_ago(instance, compare_days)

        if not current:
            return {"error": "无当前数据"}

        comparison = {
            "instance": instance,
            "current": {
                "score": current.overall_score,
                "status": current.overall_status,
                "critical": current.critical_count,
                "warning": current.warning_count,
                "recorded_at": current.recorded_at.isoformat(),
            },
            "past": None,
            "changes": {},
        }

        if past:
            comparison["past"] = {
                "score": past.overall_score,
                "status": past.overall_status,
                "critical": past.critical_count,
                "warning": past.warning_count,
                "recorded_at": past.recorded_at.isoformat(),
            }

            comparison["changes"] = {
                "score_change": current.overall_score - past.overall_score,
                "critical_change": current.critical_count - past.critical_count,
                "warning_change": current.warning_count - past.warning_count,
                "improved": current.overall_score > past.overall_score,
            }

        return comparison

    def _get_health_days_ago(self, instance: str, days: int) -> Optional[HealthHistory]:
        """获取指定天数前的记录"""
        target_time = datetime.now() - timedelta(days=days)

        history = self.get_health_history(instance, days=days + 1)

        # 找最接近目标时间的记录
        closest = None
        min_diff = timedelta(days=365)

        for record in history:
            diff = abs(record.recorded_at - target_time)
            if diff < min_diff:
                min_diff = diff
                closest = record

        return closest

    def _save_to_file(self, history: HealthHistory) -> None:
        """保存到文件"""
        instance_dir = self.storage_path / history.instance_name
        instance_dir.mkdir(parents=True, exist_ok=True)

        # 按日期存储
        date_str = history.recorded_at.strftime("%Y-%m-%d")
        file_path = instance_dir / f"{date_str}.json"

        # 读取现有数据
        records = []
        if file_path.exists():
            try:
                existing = json.loads(file_path.read_text())
                records = existing.get("records", [])
            except Exception:
                pass

        # 添加新记录 - 使用 mode='json' 序列化 datetime
        records.append(history.model_dump(mode='json'))

        # 写入文件
        data = {
            "instance": history.instance_name,
            "date": date_str,
            "records": records,
        }

        file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def _load_last_from_file(self, instance: str) -> Optional[HealthHistory]:
        """从文件加载最近记录"""
        instance_dir = self.storage_path / instance

        if not instance_dir.exists():
            return None

        # 获取最新的日期文件
        date_files = sorted(instance_dir.glob("*.json"), reverse=True)

        if not date_files:
            return None

        # 读取最新文件
        try:
            data = json.loads(date_files[0].read_text())
            records = data.get("records", [])

            if records:
                # 返回最后一条记录
                last_record = records[-1]
                return HealthHistory(**last_record)

        except Exception as e:
            logger.warning(f"加载历史失败: {instance} - {e}")

        return None

    def _load_history_from_file(
        self,
        instance: str,
        days: int,
        limit: int
    ) -> list[HealthHistory]:
        """从文件加载历史"""
        instance_dir = self.storage_path / instance

        if not instance_dir.exists():
            return []

        start_date = datetime.now() - timedelta(days=days)
        records = []

        # 读取日期范围内的文件
        for date_file in sorted(instance_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(date_file.read_text())
                for record in data.get("records", []):
                    recorded_at = datetime.fromisoformat(record["recorded_at"])
                    if recorded_at >= start_date:
                        records.append(HealthHistory(**record))

            except Exception as e:
                logger.warning(f"加载历史文件失败: {date_file} - {e}")

        records.sort(key=lambda r: r.recorded_at, reverse=True)
        return records[:limit]

    def _scan_instances_from_file(self) -> list[str]:
        """扫描文件中的实例"""
        instances = []

        if not self.storage_path.exists():
            return instances

        for instance_dir in self.storage_path.iterdir():
            if instance_dir.is_dir():
                instances.append(instance_dir.name)

        return instances

    def cleanup_old_records(self, days: int = 30) -> int:
        """清理旧记录"""
        cutoff_date = datetime.now() - timedelta(days=days)
        removed_count = 0

        # 清理内存
        for history_id, record in list(self.history.items()):
            if record.recorded_at < cutoff_date:
                del self.history[history_id]
                removed_count += 1

        # 清理实例索引
        for instance, history_ids in list(self.instance_history.items()):
            self.instance_history[instance] = [
                hid for hid in history_ids
                if hid in self.history
            ]

        # 清理文件
        for instance_dir in self.storage_path.iterdir():
            if instance_dir.is_dir():
                for date_file in instance_dir.glob("*.json"):
                    date_str = date_file.stem
                    file_date = datetime.strptime(date_str, "%Y-%m-%d")

                    if file_date < cutoff_date:
                        date_file.unlink()
                        removed_count += 1

        logger.info(f"清理历史记录: {removed_count} 条")
        return removed_count


# 全局历史存储
_history_store: Optional[HistoryStore] = None


def get_history_store() -> HistoryStore:
    """获取历史存储实例"""
    global _history_store
    if _history_store is None:
        _history_store = HistoryStore()
    return _history_store