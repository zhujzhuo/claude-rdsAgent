"""Tests for Inspection Celery Tasks."""

import pytest
from unittest.mock import Mock, patch, MagicMock


pytestmark = pytest.mark.django_db


class TestInspectionTasks:
    """Test cases for inspection Celery tasks."""

    def test_run_inspection_task_creates_executions(self, task_factory):
        """Test run_inspection_task creates TaskExecution records."""
        from scheduler.tasks.inspection import run_inspection_task

        task = task_factory(
            target_instances=["db-01", "db-02"],
        )

        with patch("scheduler.tasks.inspection.run_single_inspection") as mock_run_single:
            mock_run_single.return_value = {"success": True, "score": 85}

            # Run the task
            result = run_inspection_task(str(task.id))

            # Should call run_single_inspection for each instance
            assert mock_run_single.call_count == 2

    def test_run_single_inspection_with_mock_agent(self, task_factory, mock_diagnostic_agent, mock_platform_client):
        """Test run_single_inspection with mocked diagnostic agent."""
        from scheduler.tasks.inspection import run_single_inspection
        from scheduler.models.execution import TaskExecution

        task = task_factory()

        # Create execution first
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-test-01",
        )

        result = run_single_inspection(str(execution.id))

        assert result is not None
        assert "success" in result

    def test_check_alerts_triggers_alert(self, task_factory, alert_rule_factory):
        """Test check_alerts triggers alert when threshold exceeded."""
        from scheduler.tasks.inspection import check_alerts
        from scheduler.models.execution import TaskExecution
        from scheduler.models.alert import AlertEvent

        task = task_factory(alert_enabled=True)
        rule = alert_rule_factory(metric_name="overall_score", operator="<", threshold=60)

        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
            overall_score=50,  # Below threshold
            overall_status="critical",
        )

        with patch("scheduler.tasks.inspection.AlertService.check_and_trigger_alerts") as mock_alert:
            mock_alert.return_value = None
            check_alerts(str(execution.id), str(task.id))

            mock_alert.assert_called_once()

    def test_check_alerts_disabled(self, task_factory):
        """Test check_alerts skipped when alert disabled."""
        from scheduler.tasks.inspection import check_alerts
        from scheduler.models.execution import TaskExecution

        task = task_factory(alert_enabled=False)
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )

        with patch("scheduler.tasks.inspection.AlertService.check_and_trigger_alerts") as mock_alert:
            check_alerts(str(execution.id), str(task.id))
            # Should not call alert service
            mock_alert.assert_not_called()

    def test_record_health_history(self, task_factory):
        """Test record_health_history creates HealthHistory."""
        from scheduler.tasks.inspection import record_health_history
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
            overall_score=85,
            overall_status="healthy",
            result_data={"category_scores": {"performance": 90}},
        )

        with patch("scheduler.tasks.inspection.HistoryService.record_health") as mock_history:
            mock_history.return_value = None
            record_health_history(str(execution.id))

            mock_history.assert_called_once_with(str(execution.id))


class TestNotificationTasks:
    """Test cases for notification Celery tasks."""

    def test_send_notification_success(self, notification_channel_factory, task_factory):
        """Test send_notification task success."""
        from scheduler.tasks.notification import send_notification

        channel = notification_channel_factory(
            type="webhook",
            config={"url": "https://example.com/webhook"},
        )

        task = task_factory()
        from scheduler.models.execution import TaskExecution
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )

        from scheduler.models.alert import AlertEvent
        alert = AlertEvent.objects.create(
            instance_name="db-01",
            level="warning",
            title="Test Alert",
        )

        message_data = {
            "title": "Test Alert",
            "message": "This is a test",
            "level": "warning",
            "instance_name": "db-01",
        }

        with patch("scheduler.tasks.notification._send_by_channel") as mock_send:
            mock_send.return_value = {"success": True}

            result = send_notification(str(channel.id), str(alert.id), message_data)

            assert result.get("success") is True

    def test_send_notification_channel_not_found(self):
        """Test send_notification when channel not found."""
        from scheduler.tasks.notification import send_notification

        result = send_notification("non-existent-id", None, {})

        assert result.get("success") is False
        assert "error" in result


class TestChannelSenders:
    """Test cases for channel sending functions."""

    def test_send_webhook_success(self):
        """Test webhook sending."""
        from scheduler.tasks.notification import _send_webhook

        config = {"url": "https://example.com/webhook", "headers": {}}
        message_data = {"title": "Alert", "message": "Test message", "level": "warning"}

        with patch("httpx.Client") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = _send_webhook(config, message_data)

            assert result.get("success") is True

    def test_send_webhook_no_url(self):
        """Test webhook sending without URL."""
        from scheduler.tasks.notification import _send_webhook

        config = {}
        message_data = {"title": "Alert"}

        result = _send_webhook(config, message_data)

        assert result.get("success") is False
        assert "URL" in result.get("error", "")

    def test_send_dingtalk_no_webhook(self):
        """Test DingTalk sending without webhook."""
        from scheduler.tasks.notification import _send_dingtalk

        config = {}
        message_data = {"title": "Alert", "message": "Test"}

        result = _send_dingtalk(config, message_data)

        assert result.get("success") is False
        assert "webhook" in result.get("error", "").lower()

    def test_send_email_placeholder(self):
        """Test email sending placeholder."""
        from scheduler.tasks.notification import _send_email

        config = {"smtp_host": "smtp.example.com"}
        message_data = {"title": "Email Test"}

        result = _send_email(config, message_data)

        # Email is placeholder, should return success
        assert result.get("success") is True

    def test_send_wechat_placeholder(self):
        """Test WeChat sending placeholder."""
        from scheduler.tasks.notification import _send_wechat

        config = {}
        message_data = {"title": "WeChat Test"}

        result = _send_wechat(config, message_data)

        # WeChat is placeholder
        assert result.get("success") is True