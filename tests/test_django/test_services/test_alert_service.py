"""Tests for Alert Service."""

import pytest
from unittest.mock import Mock, patch


pytestmark = pytest.mark.django_db


class TestAlertService:
    """Test cases for AlertService."""

    def test_should_trigger_alert_below_threshold(self, task_factory):
        """Test alert triggering when value below threshold."""
        from scheduler.services.alert_service import AlertService
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
            overall_score=50,
        )

        rule = Mock(
            metric_name="overall_score",
            operator="<",
            threshold=60,
        )

        result = AlertService._should_trigger_alert(execution, rule)

        assert result is True

    def test_should_trigger_alert_above_threshold(self, task_factory):
        """Test alert not triggering when value above threshold."""
        from scheduler.services.alert_service import AlertService
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
            overall_score=90,
        )

        rule = Mock(
            metric_name="overall_score",
            operator="<",
            threshold=60,
        )

        result = AlertService._should_trigger_alert(execution, rule)

        assert result is False

    def test_should_trigger_alert_greater_than(self, task_factory):
        """Test alert triggering with greater than operator."""
        from scheduler.services.alert_service import AlertService
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
            critical_count=3,
        )

        rule = Mock(
            metric_name="critical_count",
            operator=">",
            threshold=0,
        )

        result = AlertService._should_trigger_alert(execution, rule)

        assert result is True

    def test_is_suppressed_no_recent_alerts(self, task_factory, alert_rule_factory):
        """Test suppression check with no recent alerts."""
        from scheduler.services.alert_service import AlertService

        rule = alert_rule_factory(suppress_duration=600)

        result = AlertService._is_suppressed("db-01", rule)

        assert result is False

    def test_is_suppressed_with_recent_alert(self, task_factory, alert_rule_factory):
        """Test suppression check with recent alert."""
        from scheduler.services.alert_service import AlertService
        from scheduler.models.alert import AlertEvent, AlertStatus
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        rule = alert_rule_factory(
            metric_name="overall_score",
            suppress_duration=600,
        )
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )

        # Create recent firing alert
        AlertEvent.objects.create(
            rule=rule,
            instance_name="db-01",
            metric_name="overall_score",
            status=AlertStatus.FIRING,
            execution=execution,
        )

        result = AlertService._is_suppressed("db-01", rule)

        assert result is True

    def test_create_alert_event(self, task_factory, alert_rule_factory):
        """Test creating alert event."""
        from scheduler.services.alert_service import AlertService
        from scheduler.models.alert import AlertRule, AlertEvent, AlertStatus
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        rule = alert_rule_factory(
            name="Score Alert",
            metric_name="overall_score",
            threshold=60,
            level="critical",
        )
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
            overall_score=50,
        )

        alert = AlertService._create_alert_event(execution, rule)

        assert alert.title == "Score Alert: db-01"
        assert alert.instance_name == "db-01"
        assert alert.metric_value == 50.0
        assert alert.threshold == 60
        assert alert.status == AlertStatus.FIRING

    def test_create_default_rules(self):
        """Test creating default alert rules."""
        from scheduler.services.alert_service import AlertService
        from scheduler.models.alert import AlertRule

        # Clear existing rules
        AlertRule.objects.all().delete()

        AlertService._create_default_rules()

        rules = AlertRule.objects.all()
        assert rules.count() == 4  # 4 default rules defined

    def test_check_and_trigger_alerts_disabled(self, task_factory):
        """Test check_and_trigger_alerts when alerts disabled."""
        from scheduler.services.alert_service import AlertService
        from scheduler.models.execution import TaskExecution

        task = task_factory(alert_enabled=False)
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )

        # Should return early without processing
        AlertService.check_and_trigger_alerts(str(execution.id), str(task.id))

        # No alerts should be triggered
        assert execution.alerts_triggered == []