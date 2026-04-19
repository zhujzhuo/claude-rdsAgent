"""Django REST Framework Serializers for Scheduler API."""

from rest_framework import serializers
from scheduler.models.task import InspectionTask, TaskType, ScheduleType, TaskStatus
from scheduler.models.execution import TaskExecution, ExecutionStatus
from scheduler.models.alert import AlertRule, AlertEvent, AlertLevel, AlertStatus
from scheduler.models.history import HealthHistory, TrendType
from scheduler.models.notification import NotificationChannel, ChannelType


class InspectionTaskSerializer(serializers.ModelSerializer):
    """巡检任务序列化器"""

    task_type_display = serializers.CharField(source="get_task_type_display", read_only=True)
    schedule_type_display = serializers.CharField(source="get_schedule_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = InspectionTask
        fields = "__all__"
        read_only_fields = [
            "id", "created_at", "updated_at",
            "run_count", "success_count", "failure_count",
            "celery_task_id"
        ]


class TaskCreateSerializer(serializers.ModelSerializer):
    """创建任务请求序列化器"""

    class Meta:
        model = InspectionTask
        fields = [
            "name", "description", "target_instances", "task_type",
            "schedule_type", "cron_expression", "interval_seconds",
            "scheduled_time", "alert_enabled", "alert_levels",
            "alert_channels", "thresholds", "tags"
        ]


class TaskExecutionSerializer(serializers.ModelSerializer):
    """任务执行记录序列化器"""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    task_name = serializers.CharField(source="task.name", read_only=True)

    class Meta:
        model = TaskExecution
        fields = "__all__"


class AlertRuleSerializer(serializers.ModelSerializer):
    """告警规则序列化器"""

    level_display = serializers.CharField(source="get_level_display", read_only=True)

    class Meta:
        model = AlertRule
        fields = "__all__"
        read_only_fields = ["id", "created_at"]


class AlertRuleCreateSerializer(serializers.ModelSerializer):
    """创建告警规则序列化器"""

    class Meta:
        model = AlertRule
        fields = [
            "name", "description", "metric_name", "operator",
            "threshold", "duration_seconds", "level",
            "notification_channels", "notification_template",
            "suppress_duration", "max_alerts_per_hour", "enabled", "task"
        ]


class AlertEventSerializer(serializers.ModelSerializer):
    """告警事件序列化器"""

    level_display = serializers.CharField(source="get_level_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    rule_name = serializers.CharField(source="rule.name", read_only=True)

    class Meta:
        model = AlertEvent
        fields = "__all__"


class HealthHistorySerializer(serializers.ModelSerializer):
    """健康历史序列化器"""

    trend_display = serializers.CharField(source="get_trend_display", read_only=True)

    class Meta:
        model = HealthHistory
        fields = "__all__"


class NotificationChannelSerializer(serializers.ModelSerializer):
    """通知渠道序列化器"""

    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = NotificationChannel
        fields = "__all__"
        read_only_fields = ["id", "created_at"]


class NotificationChannelCreateSerializer(serializers.ModelSerializer):
    """创建通知渠道序列化器"""

    class Meta:
        model = NotificationChannel
        fields = ["name", "type", "config", "enabled"]


class HealthTrendSerializer(serializers.Serializer):
    """健康趋势序列化器"""

    instance_name = serializers.CharField()
    current_score = serializers.IntegerField()
    previous_score = serializers.IntegerField()
    score_change = serializers.FloatField()
    trend = serializers.CharField()
    trend_display = serializers.CharField()
    last_recorded_at = serializers.DateTimeField()


class TaskRunResponseSerializer(serializers.Serializer):
    """任务执行响应序列化器"""

    message = serializers.CharField()
    celery_task_id = serializers.CharField()
    target_instances = serializers.ListField(child=serializers.CharField())