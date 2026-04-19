"""InspectionTask Django ORM Model.

Corresponds to Pydantic InspectionTask in state.py.
"""

import uuid
from django.db import models
from django.utils import timezone


class ScheduleType(models.TextChoices):
    """调度类型"""
    CRON = "cron", "Cron表达式"
    INTERVAL = "interval", "固定间隔"
    ONCE = "once", "单次执行"


class TaskStatus(models.TextChoices):
    """任务状态"""
    ENABLED = "enabled", "启用"
    DISABLED = "disabled", "禁用"
    RUNNING = "running", "运行中"
    PAUSED = "paused", "暂停"


class TaskType(models.TextChoices):
    """任务类型"""
    FULL_INSPECTION = "full_inspection", "完整巡检"
    QUICK_CHECK = "quick_check", "快速检查"
    PERFORMANCE_DIAG = "performance_diag", "性能诊断"
    CONNECTION_DIAG = "connection_diag", "连接诊断"
    STORAGE_DIAG = "storage_diag", "存储诊断"
    PARAMETER_DIAG = "parameter_diag", "参数诊断"
    SECURITY_DIAG = "security_diag", "安全诊断"


class InspectionTask(models.Model):
    """巡检任务定义"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name="任务ID")
    name = models.CharField("任务名称", max_length=100)
    description = models.TextField("任务描述", default="", blank=True)

    # 目标实例 - JSONField存储列表
    target_instances = models.JSONField("目标实例列表", default=list)

    # 任务类型
    task_type = models.CharField(
        "任务类型",
        max_length=20,
        choices=TaskType.choices,
        default=TaskType.FULL_INSPECTION
    )

    # 调度配置
    schedule_type = models.CharField(
        "调度类型",
        max_length=20,
        choices=ScheduleType.choices,
        default=ScheduleType.INTERVAL
    )
    cron_expression = models.CharField("Cron表达式", max_length=100, null=True, blank=True)
    interval_seconds = models.IntegerField("间隔秒数", null=True, blank=True)
    scheduled_time = models.DateTimeField("计划执行时间", null=True, blank=True)

    # 状态
    status = models.CharField(
        "任务状态",
        max_length=20,
        choices=TaskStatus.choices,
        default=TaskStatus.DISABLED
    )

    # 员警配置
    alert_enabled = models.BooleanField("启用告警", default=True)
    alert_levels = models.JSONField("告警级别", default=list)  # 存储级别列表
    alert_channels = models.JSONField("告警渠道", default=list)

    # 配置
    thresholds = models.JSONField("阈值配置", default=dict)
    tags = models.JSONField("标签", default=dict)

    # 时间信息
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    last_run_time = models.DateTimeField("上次执行时间", null=True, blank=True)
    next_run_time = models.DateTimeField("下次执行时间", null=True, blank=True)

    # 执行统计
    run_count = models.IntegerField("执行次数", default=0)
    success_count = models.IntegerField("成功次数", default=0)
    failure_count = models.IntegerField("失败次数", default=0)

    # Celery任务ID (关联django_celery_beat)
    celery_task_id = models.CharField("Celery任务ID", max_length=100, null=True, blank=True)

    class Meta:
        db_table = "scheduler_inspection_tasks"
        verbose_name = "巡检任务"
        verbose_name_plural = "巡检任务"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_task_type_display()})"

    def enable(self):
        """启用任务"""
        self.status = TaskStatus.ENABLED
        self.save()

    def disable(self):
        """禁用任务"""
        self.status = TaskStatus.DISABLED
        self.save()

    def increment_run(self, success: bool = True):
        """增加执行统计"""
        self.run_count += 1
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        self.last_run_time = timezone.now()
        self.save()