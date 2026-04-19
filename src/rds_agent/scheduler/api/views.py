"""Django REST Framework Views for Scheduler API."""

from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta

from scheduler.models.task import InspectionTask, TaskStatus
from scheduler.models.execution import TaskExecution, ExecutionStatus
from scheduler.models.alert import AlertRule, AlertEvent, AlertStatus
from scheduler.models.history import HealthHistory, TrendType
from scheduler.models.notification import NotificationChannel
from scheduler.api.serializers import (
    InspectionTaskSerializer,
    TaskCreateSerializer,
    TaskExecutionSerializer,
    AlertRuleSerializer,
    AlertRuleCreateSerializer,
    AlertEventSerializer,
    HealthHistorySerializer,
    NotificationChannelSerializer,
    NotificationChannelCreateSerializer,
    HealthTrendSerializer,
    TaskRunResponseSerializer,
)
from scheduler.services.task_service import TaskService


class InspectionTaskViewSet(viewsets.ModelViewSet):
    """巡检任务ViewSet"""

    queryset = InspectionTask.objects.all()
    serializer_class = InspectionTaskSerializer

    def get_serializer_class(self):
        if self.action == "create":
            return TaskCreateSerializer
        return InspectionTaskSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        # Filter by status
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        # Filter by task_type
        task_type = self.request.query_params.get("task_type")
        if task_type:
            queryset = queryset.filter(task_type=task_type)
        # Search by name
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset

    @action(detail=True, methods=["post"])
    def enable(self, request, pk=None):
        """启用任务"""
        task = self.get_object()
        task.enable()

        # Schedule Celery task
        TaskService.schedule_task(task)

        return Response({
            "status": "enabled",
            "message": "任务已启用",
            "next_run_time": task.next_run_time
        })

    @action(detail=True, methods=["post"])
    def disable(self, request, pk=None):
        """禁用任务"""
        task = self.get_object()
        task.disable()

        # Cancel Celery task
        TaskService.cancel_task(task)

        return Response({
            "status": "disabled",
            "message": "任务已禁用"
        })

    @action(detail=True, methods=["post"])
    def run(self, request, pk=None):
        """立即执行任务"""
        task = self.get_object()

        # Trigger Celery task
        celery_task_id = TaskService.run_task_now(task)

        serializer = TaskRunResponseSerializer({
            "message": "任务已触发执行",
            "celery_task_id": celery_task_id,
            "target_instances": task.target_instances
        })
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["get"])
    def executions(self, request, pk=None):
        """获取执行历史"""
        task = self.get_object()
        limit = int(request.query_params.get("limit", 10))
        executions = task.executions.all()[:limit]
        serializer = TaskExecutionSerializer(executions, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def status_summary(self, request):
        """获取任务状态统计"""
        enabled_count = InspectionTask.objects.filter(status=TaskStatus.ENABLED).count()
        disabled_count = InspectionTask.objects.filter(status=TaskStatus.DISABLED).count()
        running_count = InspectionTask.objects.filter(status=TaskStatus.RUNNING).count()
        total_runs = sum(t.run_count for t in InspectionTask.objects.all())
        total_success = sum(t.success_count for t in InspectionTask.objects.all())
        total_failure = sum(t.failure_count for t in InspectionTask.objects.all())

        return Response({
            "enabled": enabled_count,
            "disabled": disabled_count,
            "running": running_count,
            "total_runs": total_runs,
            "total_success": total_success,
            "total_failure": total_failure,
            "success_rate": round(total_success / total_runs * 100 if total_runs > 0 else 0, 2)
        })


class AlertRuleViewSet(viewsets.ModelViewSet):
    """告警规则ViewSet"""

    queryset = AlertRule.objects.all()
    serializer_class = AlertRuleSerializer

    def get_serializer_class(self):
        if self.action == "create":
            return AlertRuleCreateSerializer
        return AlertRuleSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        enabled = self.request.query_params.get("enabled")
        if enabled:
            queryset = queryset.filter(enabled=enabled == "true")
        level = self.request.query_params.get("level")
        if level:
            queryset = queryset.filter(level=level)
        return queryset


class AlertEventViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """告警事件ViewSet (只读+操作)"""

    queryset = AlertEvent.objects.all()
    serializer_class = AlertEventSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        instance = self.request.query_params.get("instance")
        if instance:
            queryset = queryset.filter(instance_name=instance)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        level = self.request.query_params.get("level")
        if level:
            queryset = queryset.filter(level=level)
        # Default to firing alerts
        if not status_filter:
            queryset = queryset.filter(status=AlertStatus.FIRING)
        return queryset

    @action(detail=False, methods=["get"])
    def active(self, request):
        """获取活跃告警"""
        alerts = AlertEvent.objects.filter(
            status__in=[AlertStatus.FIRING, AlertStatus.ACKNOWLEDGED]
        ).order_by("-triggered_at")
        serializer = self.get_serializer(alerts, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        """确认告警"""
        alert = self.get_object()
        alert.acknowledge()
        return Response({
            "status": "acknowledged",
            "acknowledged_at": alert.acknowledged_at
        })

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        """恢复告警"""
        alert = self.get_object()
        alert.resolve()
        return Response({
            "status": "resolved",
            "resolved_at": alert.resolved_at
        })


class HealthHistoryViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """健康历史ViewSet (只读)"""

    queryset = HealthHistory.objects.all()
    serializer_class = HealthHistorySerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        instance = self.request.query_params.get("instance")
        if instance:
            queryset = queryset.filter(instance_name=instance)
        days = int(self.request.query_params.get("days", 7))
        start_date = timezone.now() - timedelta(days=days)
        queryset = queryset.filter(recorded_at__gte=start_date)
        return queryset

    @action(detail=False, methods=["get"])
    def trends(self, request):
        """获取所有实例趋势"""
        days = int(request.query_params.get("days", 7))
        start_date = timezone.now() - timedelta(days=days)

        # Get latest record for each instance
        instances = HealthHistory.objects.filter(
            recorded_at__gte=start_date
        ).values_list("instance_name", flat=True).distinct()

        trends = []
        for instance in instances:
            records = HealthHistory.objects.filter(
                instance_name=instance,
                recorded_at__gte=start_date
            ).order_by("-recorded_at")

            if records.count() >= 2:
                latest = records[0]
                previous = records[1]
                score_change = latest.overall_score - previous.overall_score

                if score_change > 5:
                    trend = TrendType.IMPROVING
                elif score_change < -5:
                    trend = TrendType.DGRADING
                else:
                    trend = TrendType.STABLE

                trends.append({
                    "instance_name": instance,
                    "current_score": latest.overall_score,
                    "previous_score": previous.overall_score,
                    "score_change": score_change,
                    "trend": trend,
                    "trend_display": dict(TrendType.choices).get(trend, ""),
                    "last_recorded_at": latest.recorded_at
                })

        serializer = HealthTrendSerializer(trends, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def compare(self, request, pk=None):
        """健康对比分析"""
        record = self.get_object()
        days = int(request.query_params.get("days", 7))

        # Get previous records
        previous_records = HealthHistory.objects.filter(
            instance_name=record.instance_name,
            recorded_at__lt=record.recorded_at
        ).order_by("-recorded_at")[:days]

        if previous_records.exists():
            avg_score = sum(r.overall_score for r in previous_records) / previous_records.count()
            score_diff = record.overall_score - avg_score

            return Response({
                "current": HealthHistorySerializer(record).data,
                "average_score": round(avg_score, 2),
                "score_difference": round(score_diff, 2),
                "comparison_count": previous_records.count()
            })
        else:
            return Response({
                "current": HealthHistorySerializer(record).data,
                "average_score": None,
                "score_difference": None,
                "comparison_count": 0
            })


class NotificationChannelViewSet(viewsets.ModelViewSet):
    """通知渠道ViewSet"""

    queryset = NotificationChannel.objects.all()
    serializer_class = NotificationChannelSerializer

    def get_serializer_class(self):
        if self.action == "create":
            return NotificationChannelCreateSerializer
        return NotificationChannelSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        enabled = self.request.query_params.get("enabled")
        if enabled:
            queryset = queryset.filter(enabled=enabled == "true")
        type_filter = self.request.query_params.get("type")
        if type_filter:
            queryset = queryset.filter(type=type_filter)
        return queryset