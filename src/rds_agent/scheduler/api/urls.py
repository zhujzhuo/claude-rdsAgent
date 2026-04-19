"""URL configuration for Scheduler API."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from scheduler.api.views import (
    InspectionTaskViewSet,
    AlertRuleViewSet,
    AlertEventViewSet,
    HealthHistoryViewSet,
    NotificationChannelViewSet
)

router = DefaultRouter()
router.register(r"tasks", InspectionTaskViewSet, basename="task")
router.register(r"alerts/rules", AlertRuleViewSet, basename="alert-rule")
router.register(r"alerts/events", AlertEventViewSet, basename="alert-event")
router.register(r"history", HealthHistoryViewSet, basename="history")
router.register(r"notifications/channels", NotificationChannelViewSet, basename="notification-channel")

urlpatterns = [
    path("", include(router.urls)),
]