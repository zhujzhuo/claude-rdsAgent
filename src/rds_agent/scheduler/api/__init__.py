"""Scheduler REST API Views."""

from .serializers import (
    InspectionTaskSerializer,
    TaskCreateSerializer,
    TaskExecutionSerializer,
    AlertRuleSerializer,
    AlertEventSerializer,
    HealthHistorySerializer,
    NotificationChannelSerializer,
)
from .views import (
    InspectionTaskViewSet,
    AlertRuleViewSet,
    AlertEventViewSet,
    HealthHistoryViewSet,
    NotificationChannelViewSet,
)

__all__ = [
    # Serializers
    "InspectionTaskSerializer",
    "TaskCreateSerializer",
    "TaskExecutionSerializer",
    "AlertRuleSerializer",
    "AlertEventSerializer",
    "HealthHistorySerializer",
    "NotificationChannelSerializer",
    # ViewSets
    "InspectionTaskViewSet",
    "AlertRuleViewSet",
    "AlertEventViewSet",
    "HealthHistoryViewSet",
    "NotificationChannelViewSet",
]