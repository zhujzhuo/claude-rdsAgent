"""任务调度执行器 - 使用APScheduler实现定时任务管理。"""

import json
import uuid
from datetime import datetime
from typing import Optional, Callable
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

from rds_agent.scheduler.state import (
    InspectionTask,
    TaskExecution,
    TaskStatus,
    ScheduleType,
    TaskType,
)
from rds_agent.diagnostic import get_diagnostic_agent, DiagnosticType
from rds_agent.diagnostic.report_generator import get_report_generator
from rds_agent.scheduler.history_store import get_history_store
from rds_agent.scheduler.alert_engine import get_alert_engine
from rds_agent.utils.logger import get_logger

logger = get_logger("scheduler")


class TaskScheduler:
    """任务调度器"""

    def __init__(self):
        """初始化调度器"""
        # 配置调度器
        self.scheduler = BackgroundScheduler(
            jobstores={"default": MemoryJobStore()},
            executors={"default": ThreadPoolExecutor(max_workers=5)},
            job_defaults={"coalesce": True, "max_instances": 1},
        )

        # 任务存储
        self.tasks: dict[str, InspectionTask] = {}

        # 执行记录存储
        self.executions: dict[str, TaskExecution] = {}

        # 告警引擎
        self.alert_engine = None

        # 历史存储
        self.history_store = None

        logger.info("任务调度器初始化完成")

    def start(self) -> None:
        """启动调度器"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("任务调度器已启动")

    def shutdown(self, wait: bool = True) -> None:
        """关闭调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            logger.info("任务调度器已关闭")

    def add_task(self, task: InspectionTask) -> str:
        """添加任务"""
        task.id = task.id or str(uuid.uuid4())
        task.created_at = datetime.now()
        task.updated_at = datetime.now()

        # 保存任务
        self.tasks[task.id] = task

        # 如果任务启用，添加到调度器
        if task.status == TaskStatus.ENABLED:
            self._schedule_task(task)

        logger.info(f"添加任务: {task.name} ({task.id})")
        return task.id

    def update_task(self, task_id: str, updates: dict) -> Optional[InspectionTask]:
        """更新任务"""
        task = self.tasks.get(task_id)
        if not task:
            return None

        # 更新字段
        for key, value in updates.items():
            if hasattr(task, key):
                setattr(task, key, value)

        task.updated_at = datetime.now()

        # 重新调度
        if task.status == TaskStatus.ENABLED:
            self._schedule_task(task)
        else:
            self._unschedule_task(task_id)

        logger.info(f"更新任务: {task.name}")
        return task

    def remove_task(self, task_id: str) -> bool:
        """移除任务"""
        task = self.tasks.get(task_id)
        if not task:
            return False

        # 从调度器移除
        self._unschedule_task(task_id)

        # 删除任务
        del self.tasks[task_id]

        logger.info(f"移除任务: {task.name}")
        return True

    def enable_task(self, task_id: str) -> bool:
        """启用任务"""
        task = self.tasks.get(task_id)
        if not task:
            return False

        task.status = TaskStatus.ENABLED
        task.updated_at = datetime.now()
        self._schedule_task(task)

        logger.info(f"启用任务: {task.name}")
        return True

    def disable_task(self, task_id: str) -> bool:
        """禁用任务"""
        task = self.tasks.get(task_id)
        if not task:
            return False

        task.status = TaskStatus.DISABLED
        task.updated_at = datetime.now()
        self._unschedule_task(task_id)

        logger.info(f"禁用任务: {task.name}")
        return True

    def run_task_now(self, task_id: str) -> Optional[list[TaskExecution]]:
        """立即执行任务"""
        task = self.tasks.get(task_id)
        if not task:
            return None

        task.status = TaskStatus.RUNNING
        executions = []

        for instance in task.target_instances:
            execution = self._execute_inspection(task, instance)
            executions.append(execution)

        task.run_count += 1
        task.last_run_time = datetime.now()
        task.status = TaskStatus.ENABLED if task.status != TaskStatus.PAUSED else TaskStatus.PAUSED

        return executions

    def get_task(self, task_id: str) -> Optional[InspectionTask]:
        """获取任务"""
        return self.tasks.get(task_id)

    def list_tasks(self) -> list[InspectionTask]:
        """列出所有任务"""
        return list(self.tasks.values())

    def get_task_executions(self, task_id: str, limit: int = 10) -> list[TaskExecution]:
        """获取任务执行记录"""
        executions = [e for e in self.executions.values() if e.task_id == task_id]
        executions.sort(key=lambda e: e.start_time, reverse=True)
        return executions[:limit]

    def _schedule_task(self, task: InspectionTask) -> None:
        """调度任务"""
        # 先取消现有调度
        self._unschedule_task(task.id)

        # 创建触发器
        trigger = self._create_trigger(task)
        if not trigger:
            logger.warning(f"无法创建触发器: {task.name}")
            return

        # 添加作业
        job_id = f"task_{task.id}"
        self.scheduler.add_job(
            self._run_task_callback,
            trigger=trigger,
            id=job_id,
            args=[task.id],
            replace_existing=True,
        )

        # 更新下次执行时间
        job = self.scheduler.get_job(job_id)
        if job:
            task.next_run_time = job.next_run_time

        logger.info(f"已调度任务: {task.name}, 下次执行: {task.next_run_time}")

    def _unschedule_task(self, task_id: str) -> None:
        """取消调度"""
        job_id = f"task_{task_id}"
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"取消调度: {task_id}")
        except Exception:
            pass

    def _create_trigger(self, task: InspectionTask):
        """创建触发器"""
        if task.schedule_type == ScheduleType.CRON:
            if task.cron_expression:
                return CronTrigger.from_crontab(task.cron_expression)

        elif task.schedule_type == ScheduleType.INTERVAL:
            if task.interval_seconds:
                return IntervalTrigger(seconds=task.interval_seconds)

        elif task.schedule_type == ScheduleType.ONCE:
            if task.scheduled_time:
                return DateTrigger(run_date=task.scheduled_time)

        return None

    def _run_task_callback(self, task_id: str) -> None:
        """任务执行回调"""
        task = self.tasks.get(task_id)
        if not task:
            logger.warning(f"任务不存在: {task_id}")
            return

        logger.info(f"开始执行任务: {task.name}")

        task.status = TaskStatus.RUNNING

        for instance in task.target_instances:
            try:
                execution = self._execute_inspection(task, instance)

                # 检查告警
                if task.alert_enabled and self.alert_engine:
                    self.alert_engine.check_alerts(execution, task)

                # 存储历史
                if self.history_store:
                    self.history_store.record_health(execution)

            except Exception as e:
                logger.error(f"任务执行失败: {task.name} - {instance} - {e}")

        # 更新统计
        task.run_count += 1
        task.last_run_time = datetime.now()

        # 更新下次执行时间
        job = self.scheduler.get_job(f"task_{task_id}")
        if job:
            task.next_run_time = job.next_run_time

        # 恢复状态
        task.status = TaskStatus.ENABLED

    def _execute_inspection(self, task: InspectionTask, instance_name: str) -> TaskExecution:
        """执行巡检"""
        execution_id = str(uuid.uuid4())
        execution = TaskExecution(
            id=execution_id,
            task_id=task.id,
            instance_name=instance_name,
            start_time=datetime.now(),
        )

        self.executions[execution_id] = execution

        try:
            # 获取诊断Agent
            agent = get_diagnostic_agent()

            # 映射任务类型到诊断类型
            type_mapping = {
                TaskType.FULL_INSPECTION: DiagnosticType.FULL_INSPECTION,
                TaskType.QUICK_CHECK: DiagnosticType.QUICK_CHECK,
                TaskType.PERFORMANCE_DIAG: DiagnosticType.PERFORMANCE_DIAG,
                TaskType.CONNECTION_DIAG: DiagnosticType.CONNECTION_DIAG,
                TaskType.STORAGE_DIAG: DiagnosticType.STORAGE_DIAG,
                TaskType.PARAMETER_DIAG: DiagnosticType.PARAMETER_DIAG,
                TaskType.SECURITY_DIAG: DiagnosticType.SECURITY_DIAG,
            }

            diagnostic_type = type_mapping.get(task.task_type, DiagnosticType.FULL_INSPECTION)

            # 执行诊断
            result = agent.run(instance_name, diagnostic_type)

            # 更新执行记录
            execution.end_time = datetime.now()
            execution.duration_seconds = (execution.end_time - execution.start_time).total_seconds()

            if result:
                execution.status = "success"
                execution.overall_score = result.overall_score
                execution.overall_status = result.overall_status.value
                execution.critical_count = len(result.critical_issues)
                execution.warning_count = len(result.warnings)

                # 保存报告
                report_generator = get_report_generator()
                report_path = report_generator.save_report(result, format="json")
                execution.report_path = str(report_path)

                # 存储结果数据
                execution.result_data = {
                    "overall_score": result.overall_score,
                    "overall_status": result.overall_status.value,
                    "critical_issues": result.critical_issues,
                    "warnings": result.warnings,
                    "suggestions": result.suggestions,
                }

                task.success_count += 1

            else:
                execution.status = "failure"
                execution.error_message = "诊断未能生成结果"
                task.failure_count += 1

        except Exception as e:
            execution.status = "failure"
            execution.error_message = str(e)
            execution.end_time = datetime.now()
            execution.duration_seconds = (execution.end_time - execution.start_time).total_seconds()
            task.failure_count += 1

            logger.error(f"执行巡检失败: {instance_name} - {e}")

        return execution

    def set_alert_engine(self, engine) -> None:
        """设置告警引擎"""
        self.alert_engine = engine

    def set_history_store(self, store) -> None:
        """设置历史存储"""
        self.history_store = store

    def get_scheduler_status(self) -> dict:
        """获取调度器状态"""
        jobs = self.scheduler.get_jobs()

        return {
            "running": self.scheduler.running,
            "total_tasks": len(self.tasks),
            "enabled_tasks": len([t for t in self.tasks.values() if t.status == TaskStatus.ENABLED]),
            "running_jobs": len([j for j in jobs if j.next_run_time]),
            "total_executions": len(self.executions),
        }


# 全局调度器
_scheduler: Optional[TaskScheduler] = None


def get_scheduler() -> TaskScheduler:
    """获取调度器实例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskScheduler()
        _scheduler.start()
    return _scheduler