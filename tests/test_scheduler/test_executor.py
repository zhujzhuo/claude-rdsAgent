"""任务调度器测试。"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from rds_agent.scheduler.executor import TaskScheduler, get_scheduler
from rds_agent.scheduler.state import (
    InspectionTask,
    TaskExecution,
    TaskStatus,
    ScheduleType,
    TaskType,
)


class TestTaskScheduler:
    """任务调度器测试"""

    @pytest.fixture
    def scheduler(self):
        """创建调度器实例"""
        scheduler = TaskScheduler()
        scheduler.start()
        yield scheduler
        scheduler.shutdown(wait=False)

    def test_scheduler_initialization(self, scheduler):
        """测试调度器初始化"""
        assert scheduler.scheduler.running == True
        assert len(scheduler.tasks) == 0
        assert len(scheduler.executions) == 0

    def test_add_task(self, scheduler):
        """测试添加任务"""
        task = InspectionTask(
            name="测试任务",
            target_instances=["db-prod-01"],
            schedule_type=ScheduleType.INTERVAL,
            interval_seconds=3600,
        )

        task_id = scheduler.add_task(task)

        assert task_id is not None
        assert task.id == task_id
        assert len(scheduler.tasks) == 1
        assert scheduler.get_task(task_id) == task

    def test_add_cron_task(self, scheduler):
        """测试添加Cron任务"""
        task = InspectionTask(
            name="每日巡检",
            target_instances=["db-prod-01"],
            schedule_type=ScheduleType.CRON,
            cron_expression="0 9 * * *",
            status=TaskStatus.ENABLED,
        )

        task_id = scheduler.add_task(task)

        assert task_id is not None
        assert task.status == TaskStatus.ENABLED
        # 验证任务被调度
        job = scheduler.scheduler.get_job(f"task_{task_id}")
        assert job is not None

    def test_update_task(self, scheduler):
        """测试更新任务"""
        task = InspectionTask(
            name="测试任务",
            target_instances=["db-prod-01"],
        )

        task_id = scheduler.add_task(task)

        # 更新任务
        updated = scheduler.update_task(task_id, {
            "name": "更新后的任务",
            "interval_seconds": 1800,
        })

        assert updated is not None
        assert updated.name == "更新后的任务"
        assert updated.interval_seconds == 1800

    def test_remove_task(self, scheduler):
        """测试删除任务"""
        task = InspectionTask(
            name="测试任务",
            target_instances=["db-prod-01"],
            status=TaskStatus.ENABLED,
        )

        task_id = scheduler.add_task(task)

        # 删除任务
        result = scheduler.remove_task(task_id)

        assert result == True
        assert len(scheduler.tasks) == 0
        assert scheduler.get_task(task_id) is None

    def test_enable_disable_task(self, scheduler):
        """测试启用/禁用任务"""
        task = InspectionTask(
            name="测试任务",
            target_instances=["db-prod-01"],
        )

        task_id = scheduler.add_task(task)

        # 启用任务
        scheduler.enable_task(task_id)
        assert scheduler.get_task(task_id).status == TaskStatus.ENABLED

        # 禁用任务
        scheduler.disable_task(task_id)
        assert scheduler.get_task(task_id).status == TaskStatus.DISABLED

    def test_list_tasks(self, scheduler):
        """测试列出任务"""
        task1 = InspectionTask(name="任务1", target_instances=["db-01"])
        task2 = InspectionTask(name="任务2", target_instances=["db-02"])

        scheduler.add_task(task1)
        scheduler.add_task(task2)

        tasks = scheduler.list_tasks()

        assert len(tasks) == 2
        assert any(t.name == "任务1" for t in tasks)
        assert any(t.name == "任务2" for t in tasks)

    def test_get_scheduler_status(self, scheduler):
        """测试获取调度器状态"""
        task = InspectionTask(
            name="测试任务",
            target_instances=["db-01"],
            status=TaskStatus.ENABLED,
        )
        scheduler.add_task(task)

        status = scheduler.get_scheduler_status()

        assert status["running"] == True
        assert status["total_tasks"] == 1
        assert status["enabled_tasks"] == 1

    def test_run_task_now(self, scheduler):
        """测试立即执行任务"""
        task = InspectionTask(
            name="测试任务",
            target_instances=["db-01"],
        )

        task_id = scheduler.add_task(task)

        # 模拟诊断Agent
        with patch("rds_agent.scheduler.executor.get_diagnostic_agent") as mock_agent:
            mock_result = Mock()
            mock_result.overall_score = 85
            mock_result.overall_status = Mock(value="healthy")
            mock_result.critical_issues = []
            mock_result.warnings = []
            mock_result.suggestions = []
            mock_agent.return_value.run.return_value = mock_result

            with patch("rds_agent.scheduler.executor.get_report_generator") as mock_report:
                mock_report.return_value.save_report.return_value = Mock()

                executions = scheduler.run_task_now(task_id)

        assert executions is not None
        assert len(executions) == 1
        assert task.run_count == 1
        assert task.last_run_time is not None

    def test_get_task_executions(self, scheduler):
        """测试获取任务执行记录"""
        task = InspectionTask(
            name="测试任务",
            target_instances=["db-01"],
        )

        task_id = scheduler.add_task(task)

        # 添加执行记录
        execution = TaskExecution(
            task_id=task_id,
            instance_name="db-01",
        )
        scheduler.executions[execution.id] = execution

        executions = scheduler.get_task_executions(task_id)

        assert len(executions) == 1
        assert executions[0].task_id == task_id

    def test_set_components(self, scheduler):
        """测试设置组件"""
        mock_alert_engine = Mock()
        mock_history_store = Mock()

        scheduler.set_alert_engine(mock_alert_engine)
        scheduler.set_history_store(mock_history_store)

        assert scheduler.alert_engine == mock_alert_engine
        assert scheduler.history_store == mock_history_store


class TestGetScheduler:
    """获取调度器实例测试"""

    def test_get_scheduler_singleton(self):
        """测试单例模式"""
        # 清除全局实例
        from rds_agent.scheduler.executor import _scheduler
        import rds_agent.scheduler.executor as executor_module
        executor_module._scheduler = None

        scheduler1 = get_scheduler()
        scheduler2 = get_scheduler()

        assert scheduler1 == scheduler2

        # 清理
        scheduler1.shutdown(wait=False)
        executor_module._scheduler = None