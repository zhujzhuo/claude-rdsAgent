"""TaskExecution Django ORM Model.

Corresponds to Pydantic TaskExecution in state.py.
"""

import uuid
from django.db import models
from django.utils import timezone


class ExecutionStatus(models.TextChoices):
    """执行状态"""
    RUNNING = "running", "运行中"
    SUCCESS = "success", "成功"
    FAILURE = "failure", "失败"


class TaskExecution(models.Model):
    """任务执行记录"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name="执行ID")
    task = models.ForeignKey(
        "scheduler.InspectionTask",
        on_delete=models.CASCADE,
        related_name="executions",
        verbose_name="关联任务"
    )
    instance_name = models.CharField("实例名称", max_length=100)

    # 执行信息
    start_time = models.DateTimeField("开始时间", auto_now_add=True)
    end_time = models.DateTimeField("结束时间", null=True, blank=True)
    duration_seconds = models.FloatField("执行时长(秒)", null=True, blank=True)

    # 结果信息
    status = models.CharField(
        "执行状态",
        max_length=20,
        choices=ExecutionStatus.choices,
        default=ExecutionStatus.RUNNING
    )
    overall_score = models.IntegerField("健康分数", null=True, blank=True)
    overall_status = models.CharField("健康状态", max_length=20, null=True, blank=True)

    # 员警信息
    alerts_triggered = models.JSONField("触发告警", default=list)
    critical_count = models.IntegerField("严重问题数", default=0)
    warning_count = models.IntegerField("警告数", default=0)

    # 结果路径和数据
    report_path = models.CharField("报告路径", max_length=255, null=True, blank=True)
    result_data = models.JSONField("结果数据", null=True, blank=True)

    # 错误信息
    error_message = models.TextField("错误信息", null=True, blank=True)

    # Celery任务ID
    celery_task_id = models.CharField("Celery任务ID", max_length=100, null=True, blank=True)

    class Meta:
        db_table = "scheduler_task_executions"
        verbose_name = "任务执行记录"
        verbose_name_plural = "任务执行记录"
        ordering = ["-start_time"]
        indexes = [
            models.Index(fields=["task", "start_time"]),
            models.Index(fields=["instance_name"]),
        ]

    def __str__(self):
        return f"{self.task.name} - {self.instance_name} ({self.status})"

    def complete(self, success: bool = True, error_message: str = None):
        """完成执行"""
        self.end_time = timezone.now()
        self.duration_seconds = (self.end_time - self.start_time).total_seconds()
        if success:
            self.status = ExecutionStatus.SUCCESS
        else:
            self.status = ExecutionStatus.FAILURE
            if error_message:
                self.error_message = error_message
        self.save()

    def set_result(self, overall_score: int, overall_status: str, critical_count: int, warning_count: int, result_data: dict):
        """设置结果"""
        self.overall_score = overall_score
        self.overall_status = overall_status
        self.critical_count = critical_count
        self.warning_count = warning_count
        self.result_data = result_data
        self.save()