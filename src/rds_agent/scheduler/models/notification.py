"""NotificationChannel Django ORM Model.

Corresponds to Pydantic NotificationChannel in state.py.
"""

import uuid
from django.db import models
from django.utils import timezone


class ChannelType(models.TextChoices):
    """渠道类型"""
    DINGTALK = "dingtalk", "钉钉"
    EMAIL = "email", "邮件"
    WECHAT = "wechat", "企业微信"
    WEBHOOK = "webhook", "Webhook"


class NotificationChannel(models.Model):
    """通知渠道配置"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name="渠道ID")
    name = models.CharField("渠道名称", max_length=100)
    type = models.CharField(
        "渠道类型",
        max_length=20,
        choices=ChannelType.choices
    )

    # 配置 (JSONField存储各类型配置)
    # DingTalk: {"webhook": "...", "secret": "..."}
    # Email: {"host": "...", "port": ..., "user": "...", "password": "..."}
    # WeChat: {"corp_id": "...", "agent_id": "...", "secret": "..."}
    # Webhook: {"url": "...", "headers": {...}}
    config = models.JSONField("配置参数", default=dict)

    enabled = models.BooleanField("启用", default=True)

    # 时间
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    last_used_at = models.DateTimeField("上次使用时间", null=True, blank=True)

    class Meta:
        db_table = "scheduler_notification_channels"
        verbose_name = "通知渠道"
        verbose_name_plural = "通知渠道"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"

    def mark_used(self):
        """标记已使用"""
        self.last_used_at = timezone.now()
        self.save()