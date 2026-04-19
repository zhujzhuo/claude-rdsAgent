"""HealthHistory Django ORM Model.

Corresponds to Pydantic HealthHistory in state.py.
"""

import uuid
from django.db import models
from django.utils import timezone


class TrendType(models.TextChoices):
    """趋势类型"""
    IMPROVING = "improving", "改善"
    STABLE = "stable", "稳定"
    DEGRADING = "degrading", "恶化"


class HealthHistory(models.Model):
    """健康历史记录"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name="记录ID")
    instance_name = models.CharField("实例名称", max_length=100)

    # 健康信息
    overall_score = models.IntegerField("健康分数")
    overall_status = models.CharField("健康状态", max_length=20)

    # 分类分数
    category_scores = models.JSONField("分类分数", default=dict)

    # 问题统计
    critical_count = models.IntegerField("严重问题数", default=0)
    warning_count = models.IntegerField("警告数", default=0)

    # 时间
    recorded_at = models.DateTimeField("记录时间", auto_now_add=True)
    execution = models.ForeignKey(
        "scheduler.TaskExecution",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="health_records",
        verbose_name="执行ID"
    )

    # 趋势分析
    score_change = models.FloatField("分数变化", null=True, blank=True)
    trend = models.CharField(
        "趋势",
        max_length=20,
        choices=TrendType.choices,
        null=True,
        blank=True
    )

    class Meta:
        db_table = "scheduler_health_history"
        verbose_name = "健康历史"
        verbose_name_plural = "健康历史"
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["instance_name", "recorded_at"]),
        ]

    def __str__(self):
        return f"{self.instance_name} - {self.overall_score} ({self.recorded_at.strftime('%Y-%m-%d %H:%M')})"

    def calculate_trend(self):
        """计算趋势"""
        if self.score_change is not None:
            if self.score_change > 5:
                self.trend = TrendType.IMPROVING
            elif self.score_change < -5:
                self.trend = TrendType.DEGRADING
            else:
                self.trend = TrendType.STABLE
            self.save()