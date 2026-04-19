"""AlertRule and AlertEvent Django ORM Models.

Corresponds to Pydantic AlertRule and AlertEvent in state.py.
"""

import uuid
from django.db import models
from django.utils import timezone


class AlertLevel(models.TextChoices):
    """告警级别"""
    INFO = "info", "信息"
    WARNING = "warning", "警告"
    CRITICAL = "critical", "严重"
    EMERGENCY = "emergency", "紧急"


class AlertStatus(models.TextChoices):
    """告警状态"""
    FIRING = "firing", "触发"
    RESOLVED = "resolved", "已恢复"
    ACKNOWLEDGED = "acknowledged", "已确认"


class AlertRule(models.Model):
    """告警规则"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name="规则ID")
    name = models.CharField("规则名称", max_length=100)
    description = models.TextField("规则描述", default="", blank=True)

    # 触发条件
    metric_name = models.CharField("指标名称", max_length=100)
    operator = models.CharField("比较运算符", max_length=10, default=">")  # >, <, >=, <=, ==, !=
    threshold = models.FloatField("阈值")
    duration_seconds = models.IntegerField("持续时间(秒)", null=True, blank=True)

    # 告警级别
    level = models.CharField(
        "告警级别",
        max_length=20,
        choices=AlertLevel.choices,
        default=AlertLevel.WARNING
    )

    # 通知配置
    notification_channels = models.JSONField("通知渠道", default=list)
    notification_template = models.TextField("通知模板", null=True, blank=True)

    # 抑制配置
    suppress_duration = models.IntegerField("抑制时长(秒)", default=300)
    max_alerts_per_hour = models.IntegerField("每小时最大告警数", default=10)

    # 状态
    enabled = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    # 关联任务 (可选)
    task = models.ForeignKey(
        "scheduler.InspectionTask",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alert_rules",
        verbose_name="关联任务"
    )

    class Meta:
        db_table = "scheduler_alert_rules"
        verbose_name = "告警规则"
        verbose_name_plural = "告警规则"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.metric_name} {self.operator} {self.threshold})"

    def check_threshold(self, value: float) -> bool:
        """检查阈值是否触发"""
        ops = {
            ">": value > self.threshold,
            "<": value < self.threshold,
            ">=": value >= self.threshold,
            "<=": value <= self.threshold,
            "==": value == self.threshold,
            "!=": value != self.threshold,
        }
        return ops.get(self.operator, False)


class AlertEvent(models.Model):
    """告警事件"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name="告警ID")
    rule = models.ForeignKey(
        AlertRule,
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name="关联规则"
    )
    instance_name = models.CharField("实例名称", max_length=100)

    # 告警信息
    level = models.CharField("告警级别", max_length=20, choices=AlertLevel.choices)
    title = models.CharField("告警标题", max_length=200)
    message = models.TextField("告警内容")
    metric_name = models.CharField("指标名称", max_length=100)
    metric_value = models.FloatField("指标值")
    threshold = models.FloatField("阈值")

    # 时间信息
    triggered_at = models.DateTimeField("触发时间", auto_now_add=True)
    resolved_at = models.DateTimeField("恢复时间", null=True, blank=True)
    acknowledged_at = models.DateTimeField("确认时间", null=True, blank=True)

    # 状态
    status = models.CharField(
        "状态",
        max_length=20,
        choices=AlertStatus.choices,
        default=AlertStatus.FIRING
    )

    # 通知状态
    notification_sent = models.BooleanField("已发送通知", default=False)
    notification_channels = models.JSONField("已发送渠道", default=list)

    # 关联执行
    execution = models.ForeignKey(
        "scheduler.TaskExecution",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alerts",
        verbose_name="关联执行"
    )
    suggestion = models.TextField("处理建议", null=True, blank=True)

    class Meta:
        db_table = "scheduler_alert_events"
        verbose_name = "告警事件"
        verbose_name_plural = "告警事件"
        ordering = ["-triggered_at"]
        indexes = [
            models.Index(fields=["instance_name", "status"]),
            models.Index(fields=["level", "triggered_at"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.instance_name} ({self.get_status_display()})"

    def acknowledge(self):
        """确认告警"""
        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_at = timezone.now()
        self.save()

    def resolve(self):
        """恢复告警"""
        self.status = AlertStatus.RESOLVED
        self.resolved_at = timezone.now()
        self.save()