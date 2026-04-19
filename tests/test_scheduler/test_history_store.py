"""健康历史存储测试。"""

import pytest
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile
import os

from rds_agent.scheduler.history_store import HistoryStore, get_history_store
from rds_agent.scheduler.state import HealthHistory, TaskExecution


class TestHistoryStore:
    """健康历史存储测试"""

    @pytest.fixture
    def temp_storage(self):
        """创建临时存储目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def store(self, temp_storage):
        """创建历史存储实例"""
        store = HistoryStore(storage_path=temp_storage)
        yield store

    def test_store_initialization(self, store, temp_storage):
        """测试存储初始化"""
        assert store.storage_path == Path(temp_storage)
        assert len(store.history) == 0
        assert len(store.instance_history) == 0

    def test_record_health(self, store):
        """测试记录健康数据"""
        execution = TaskExecution(
            task_id="task-001",
            instance_name="db-01",
            overall_score=85,
            overall_status="healthy",
            critical_count=0,
            warning_count=3,
            result_data={
                "overall_score": 85,
                "category_scores": {"performance": 90, "storage": 80},
            },
        )
        execution.end_time = datetime.now()

        history = store.record_health(execution)

        assert history is not None
        assert history.instance_name == "db-01"
        assert history.overall_score == 85
        assert len(store.history) == 1

    def test_record_health_with_previous(self, store):
        """测试记录健康数据（有前一次记录）"""
        # 第一次记录
        execution1 = TaskExecution(
            task_id="task-001",
            instance_name="db-01",
            overall_score=70,
            overall_status="warning",
            critical_count=1,
            warning_count=5,
            result_data={"overall_score": 70},
        )
        execution1.end_time = datetime.now()
        store.record_health(execution1)

        # 第二次记录（改善）
        execution2 = TaskExecution(
            task_id="task-002",
            instance_name="db-01",
            overall_score=85,
            overall_status="healthy",
            critical_count=0,
            warning_count=2,
            result_data={"overall_score": 85},
        )
        execution2.end_time = datetime.now()
        history2 = store.record_health(execution2)

        assert history2.score_change == 15
        assert history2.trend == "improving"

    def test_get_last_health(self, store):
        """测试获取最近健康记录"""
        execution = TaskExecution(
            task_id="task-001",
            instance_name="db-01",
            overall_score=85,
            overall_status="healthy",
            result_data={"overall_score": 85},
        )
        execution.end_time = datetime.now()
        store.record_health(execution)

        last = store.get_last_health("db-01")

        assert last is not None
        assert last.overall_score == 85

    def test_get_health_history(self, store):
        """测试获取健康历史"""
        # 添加多条记录
        for i in range(5):
            execution = TaskExecution(
                task_id=f"task-{i}",
                instance_name="db-01",
                overall_score=80 + i,
                overall_status="healthy",
                result_data={"overall_score": 80 + i},
            )
            execution.end_time = datetime.now() - timedelta(days=i)
            store.record_health(execution)

        history = store.get_health_history("db-01", days=7)

        assert len(history) == 5
        # 最新记录在前
        assert history[0].overall_score == 80

    def test_get_health_trend(self, store):
        """测试获取健康趋势"""
        # 添加记录 - 使用更大的分数增量以触发 "improving" 趋势 (score_change > 5)
        for i in range(7):
            execution = TaskExecution(
                task_id=f"task-{i}",
                instance_name="db-01",
                overall_score=60 + i * 10,  # 60, 70, 80, ... 每次增加10分，触发improving
                overall_status="healthy",
                critical_count=0,
                warning_count=3 - i // 2,
                result_data={"overall_score": 60 + i * 10},
            )
            execution.end_time = datetime.now() - timedelta(days=i)
            store.record_health(execution)

        trend = store.get_health_trend("db-01", days=7)

        assert trend["has_data"] == True
        assert trend["record_count"] == 7
        assert trend["avg_score"] > 60
        # 趋势取决于各记录的score_change，增量10>5应该触发improving
        assert trend["overall_trend"] == "improving"

    def test_get_all_instances_trend(self, store):
        """测试获取所有实例趋势"""
        # 添加两个实例的记录
        for instance in ["db-01", "db-02"]:
            for i in range(3):
                execution = TaskExecution(
                    task_id=f"task-{instance}-{i}",
                    instance_name=instance,
                    overall_score=80 + i,
                    overall_status="healthy",
                    result_data={"overall_score": 80 + i},
                )
                execution.end_time = datetime.now() - timedelta(days=i)
                store.record_health(execution)

        trends = store.get_all_instances_trend(days=7)

        assert len(trends) == 2
        assert any(t["instance"] == "db-01" for t in trends)
        assert any(t["instance"] == "db-02" for t in trends)

    def test_compare_health(self, store):
        """测试健康对比"""
        # 当前记录
        execution_current = TaskExecution(
            task_id="task-current",
            instance_name="db-01",
            overall_score=90,
            overall_status="healthy",
            critical_count=0,
            warning_count=1,
            result_data={"overall_score": 90},
        )
        execution_current.end_time = datetime.now()
        store.record_health(execution_current)

        # 过去记录（7天前）
        execution_past = TaskExecution(
            task_id="task-past",
            instance_name="db-01",
            overall_score=75,
            overall_status="warning",
            critical_count=1,
            warning_count=5,
            result_data={"overall_score": 75},
        )
        execution_past.end_time = datetime.now() - timedelta(days=7)
        store.record_health(execution_past)

        comparison = store.compare_health("db-01", compare_days=7)

        assert comparison["current"]["score"] == 90
        assert comparison["past"]["score"] == 75
        assert comparison["changes"]["score_change"] == 15
        assert comparison["changes"]["improved"] == True

    def test_save_to_file(self, store, temp_storage):
        """测试保存到文件"""
        execution = TaskExecution(
            task_id="task-001",
            instance_name="db-01",
            overall_score=85,
            overall_status="healthy",
            result_data={"overall_score": 85},
        )
        execution.end_time = datetime.now()
        history = store.record_health(execution)

        # 检查文件是否创建
        instance_dir = Path(temp_storage) / "db-01"
        assert instance_dir.exists()

        # 检查日期文件
        date_str = datetime.now().strftime("%Y-%m-%d")
        file_path = instance_dir / f"{date_str}.json"
        assert file_path.exists()

        # 验证内容
        data = json.loads(file_path.read_text())
        assert data["instance"] == "db-01"
        assert len(data["records"]) == 1

    def test_load_from_file(self, temp_storage):
        """测试从文件加载"""
        # 创建测试数据文件
        instance_dir = Path(temp_storage) / "db-01"
        instance_dir.mkdir(parents=True)

        date_str = datetime.now().strftime("%Y-%m-%d")
        file_path = instance_dir / f"{date_str}.json"

        data = {
            "instance": "db-01",
            "date": date_str,
            "records": [
                {
                    "id": "history-001",
                    "instance_name": "db-01",
                    "overall_score": 85,
                    "overall_status": "healthy",
                    "critical_count": 0,
                    "warning_count": 3,
                    "recorded_at": datetime.now().isoformat(),
                }
            ],
        }
        file_path.write_text(json.dumps(data))

        # 创建新存储实例
        store = HistoryStore(storage_path=temp_storage)

        # 加载最近记录
        last = store.get_last_health("db-01")

        assert last is not None
        assert last.overall_score == 85

    def test_cleanup_old_records(self, store):
        """测试清理旧记录"""
        # 添加旧记录和新记录
        old_execution = TaskExecution(
            task_id="task-old",
            instance_name="db-01",
            overall_score=80,
            overall_status="healthy",
            result_data={"overall_score": 80},
        )
        old_execution.end_time = datetime.now() - timedelta(days=35)
        store.record_health(old_execution)

        new_execution = TaskExecution(
            task_id="task-new",
            instance_name="db-01",
            overall_score=85,
            overall_status="healthy",
            result_data={"overall_score": 85},
        )
        new_execution.end_time = datetime.now()
        store.record_health(new_execution)

        # 清理30天前的记录
        removed = store.cleanup_old_records(days=30)

        assert removed >= 1
        assert len(store.history) == 1


class TestGetHistoryStore:
    """获取历史存储实例测试"""

    def test_get_store_singleton(self):
        """测试单例模式"""
        import rds_agent.scheduler.history_store as module
        module._history_store = None

        store1 = get_history_store()
        store2 = get_history_store()

        assert store1 == store2

        # 清理
        module._history_store = None