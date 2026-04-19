"""Tests for Alert models."""

import pytest
from django.utils import timezone


pytestmark = pytest.mark.django_db


class TestAlertRuleModel:
    """Test cases for AlertRule model."""

    def test_create_alert_rule_with_defaults(self, alert_rule_factory):
        """Test creating alert rule with default values."""
        rule = alert_rule_factory()

        assert rule.name == "Test Rule"
        assert rule.metric_name == "overall_score"
        assert rule.operator == "<"
        assert rule.threshold == 60
        assert rule.level == "critical"
        assert rule.enabled is True

    def test_create_alert_rule_custom_values(self, alert_rule_factory):
        """Test creating alert rule with custom values."""
        rule = alert_rule_factory(
            name="Warning Count Alert",
            metric_name="warning_count",
            operator=">",
            threshold=5,
            level="warning",
            suppress_duration=600,
        )

        assert rule.name == "Warning Count Alert"
        assert rule.metric_name == "warning_count"
        assert rule.operator == ">"
        assert rule.threshold == 5
        assert rule.level == "warning"
        assert rule.suppress_duration == 600

    def test_alert_rule_str_representation(self, alert_rule_factory):
        """Test alert rule string representation."""
        rule = alert_rule_factory(name="My Alert Rule")
        assert str(rule) == "My Alert Rule"

    def test_alert_rule_uuid_primary_key(self, alert_rule_factory):
        """Test that alert rule uses UUID primary key."""
        from uuid import UUID

        rule = alert_rule_factory()
        assert rule.id is not None
        UUID(str(rule.id))

    def test_alert_rule_level_choices(self, alert_rule_factory):
        """Test alert level enum choices."""
        from scheduler.models.alert import AlertLevel

        rule_critical = alert_rule_factory(level=AlertLevel.CRITICAL)
        rule_warning = alert_rule_factory(level=AlertLevel.WARNING)
        rule_info = alert_rule_factory(level=AlertLevel.INFO)

        assert rule_critical.level == AlertLevel.CRITICAL
        assert rule_warning.level == AlertLevel.WARNING
        assert rule_info.level == AlertLevel.INFO

    def test_alert_rule_operator_choices(self, alert_rule_factory):
        """Test alert operator choices."""
        rule_gt = alert_rule_factory(operator=">")
        rule_lt = alert_rule_factory(operator="<")
        rule_gte = alert_rule_factory(operator=">=")
        rule_lte = alert_rule_factory(operator="<=")

        assert rule_gt.operator == ">"
        assert rule_lt.operator == "<"
        assert rule_gte.operator == ">="
        assert rule_lte.operator == "<="


class TestAlertEventModel:
    """Test cases for AlertEvent model."""

    def test_create_alert_event(self, task_factory, alert_rule_factory):
        """Test creating alert event."""
        from scheduler.models.alert import AlertEvent
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        rule = alert_rule_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )

        event = AlertEvent.objects.create(
            rule=rule,
            instance_name="db-01",
            level="critical",
            title="健康分数过低: db-01",
            message="当前值: 50, 阈值: 60",
            metric_name="overall_score",
            metric_value=50.0,
            threshold=60,
            execution=execution,
        )

        assert event.rule == rule
        assert event.instance_name == "db-01"
        assert event.title == "健康分数过低: db-01"
        assert event.metric_value == 50.0
        assert event.status == "firing"

    def test_alert_event_status_choices(self, task_factory, alert_rule_factory):
        """Test alert event status choices."""
        from scheduler.models.alert import AlertEvent, AlertStatus
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        rule = alert_rule_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )

        event_firing = AlertEvent.objects.create(
            rule=rule,
            instance_name="db-01",
            status=AlertStatus.FIRING,
        )
        event_resolved = AlertEvent.objects.create(
            rule=rule,
            instance_name="db-02",
            status=AlertStatus.RESOLVED,
        )

        assert event_firing.status == AlertStatus.FIRING
        assert event_resolved.status == AlertStatus.RESOLVED

    def test_alert_event_notification_tracking(self, task_factory, alert_rule_factory):
        """Test alert event notification tracking."""
        from scheduler.models.alert import AlertEvent
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        rule = alert_rule_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )

        event = AlertEvent.objects.create(
            rule=rule,
            instance_name="db-01",
            notification_sent=True,
            notification_channels=["channel-1", "channel-2"],
            execution=execution,
        )

        assert event.notification_sent is True
        assert event.notification_channels == ["channel-1", "channel-2"]

    def test_alert_event_resolved_at(self, task_factory, alert_rule_factory):
        """Test alert event resolved_at field."""
        from scheduler.models.alert import AlertEvent
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        rule = alert_rule_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )

        event = AlertEvent.objects.create(
            rule=rule,
            instance_name="db-01",
            status="resolved",
            resolved_at=timezone.now(),
            execution=execution,
        )

        assert event.resolved_at is not None