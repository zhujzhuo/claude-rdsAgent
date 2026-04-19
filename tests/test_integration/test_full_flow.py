"""Integration test for full task execution flow."""

import pytest
from unittest.mock import Mock, patch, MagicMock


pytestmark = pytest.mark.django_db


class TestFullTaskFlow:
    """Integration tests for complete task execution flow."""

    def test_task_creation_to_execution(self, mock_diagnostic_agent, mock_platform_client, mock_report_generator):
        """Test full flow from task creation to execution."""
        from scheduler.models.task import InspectionTask, TaskStatus
        from scheduler.models.execution import TaskExecution, ExecutionStatus
        from scheduler.services.task_service import TaskService

        # Create task
        task = InspectionTask.objects.create(
            name="Integration Test Task",
            target_instances=["db-test-01"],
            task_type="full_inspection",
            schedule_type="once",
            status=TaskStatus.ENABLED,
            alert_enabled=True,
        )

        # Run task immediately
        with patch("scheduler.tasks.inspection.run_single_inspection") as mock_run:
            mock_run.return_value = {"success": True, "score": 85}

            TaskService.run_task_now(task)

        # Verify execution was created
        executions = TaskExecution.objects.filter(task=task)
        assert executions.count() > 0

    def test_task_schedule_to_celery(self, task_factory):
        """Test task scheduling with Celery Beat."""
        from scheduler.services.task_service import TaskService

        task = task_factory(
            schedule_type="interval",
            interval_seconds=3600,
        )

        with patch("django_celery_beat.models.PeriodicTask.objects.create") as mock_create:
            with patch("django_celery_beat.models.IntervalSchedule.objects.get_or_create") as mock_interval:
                mock_interval.return_value = (Mock(), True)
                mock_periodic = Mock(name=f"task_{task.id}")
                mock_create.return_value = mock_periodic

                TaskService.schedule_task(task)

                task.refresh_from_db()
                assert task.celery_task_id is not None

    def test_alert_triggering_flow(self, task_factory, alert_rule_factory, notification_channel_factory):
        """Test full alert triggering and notification flow."""
        from scheduler.models.execution import TaskExecution
        from scheduler.models.alert import AlertEvent, AlertStatus
        from scheduler.services.alert_service import AlertService

        # Setup
        task = task_factory(alert_enabled=True, alert_channels=["test-channel"])
        rule = alert_rule_factory(
            metric_name="overall_score",
            operator="<",
            threshold=60,
            level="critical",
        )
        channel = notification_channel_factory(name="test-channel", enabled=True)

        # Create execution with low score
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
            overall_score=50,  # Below threshold
            overall_status="critical",
        )

        with patch("scheduler.services.alert_service.AlertService._trigger_notification") as mock_notify:
            AlertService.check_and_trigger_alerts(str(execution.id), str(task.id))

        # Verify alert was created
        alert = AlertEvent.objects.filter(instance_name="db-01").first()
        assert alert is not None
        assert alert.status == AlertStatus.FIRING

    def test_health_history_flow(self, task_factory):
        """Test health history recording flow."""
        from scheduler.models.execution import TaskExecution
        from scheduler.models.history import HealthHistory
        from scheduler.services.history_service import HistoryService

        task = task_factory()

        # Create execution with result
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
            overall_score=85,
            overall_status="healthy",
            critical_count=0,
            warning_count=2,
            result_data={"category_scores": {"performance": 90}},
        )

        # Record health
        HistoryService.record_health(str(execution.id))

        # Verify history was created
        history = HealthHistory.objects.filter(instance_name="db-01").first()
        assert history is not None
        assert history.overall_score == 85

    def test_trend_analysis_flow(self, task_factory):
        """Test trend analysis over multiple executions."""
        from scheduler.models.execution import TaskExecution
        from scheduler.models.history import HealthHistory, TrendType
        from scheduler.services.history_service import HistoryService

        task = task_factory()

        # Create multiple executions with improving scores
        for score in [70, 75, 80, 85, 90]:
            execution = TaskExecution.objects.create(
                task=task,
                instance_name="db-01",
                overall_score=score,
                overall_status="healthy",
            )

            HistoryService.objects.create(
                instance_name="db-01",
                overall_score=score,
                overall_status="healthy",
                execution=execution,
            )

        # Get trend
        trend = HistoryService.get_health_trend("db-01", days=7)

        assert trend["overall_trend"] == TrendType.IMPROVING


class TestAPIIntegration:
    """Integration tests for API endpoints."""

    def test_task_api_full_flow(self):
        """Test full task API flow: create, run, check status."""
        from rest_framework.test import APIClient
        from scheduler.models.task import InspectionTask

        client = APIClient()

        # Create task
        create_response = client.post("/api/scheduler/tasks/", {
            "name": "API Test Task",
            "target_instances": ["db-01"],
            "task_type": "quick_check",
            "schedule_type": "once",
        }, format="json")

        assert create_response.status_code == 201
        task_id = create_response.data["id"]

        # Retrieve task
        get_response = client.get(f"/api/scheduler/tasks/{task_id}/")
        assert get_response.status_code == 200
        assert get_response.data["name"] == "API Test Task"

        # Run task
        with patch("scheduler.services.task_service.TaskService.run_task_now") as mock_run:
            mock_run.return_value = "celery-id-123"
            run_response = client.post(f"/api/scheduler/tasks/{task_id}/run/")
            assert run_response.status_code == 200

        # Disable task
        disable_response = client.post(f"/api/scheduler/tasks/{task_id}/disable/")
        assert disable_response.status_code == 200
        assert disable_response.data["status"] == "disabled"

    def test_alert_api_integration(self, task_factory, alert_rule_factory):
        """Test alert API integration."""
        from rest_framework.test import APIClient
        from scheduler.models.alert import AlertEvent
        from scheduler.models.execution import TaskExecution

        client = APIClient()

        # Create rule via API
        rule_response = client.post("/api/scheduler/alerts/rules/", {
            "name": "API Rule",
            "metric_name": "overall_score",
            "operator": "<",
            "threshold": 60,
            "level": "critical",
        }, format="json")

        assert rule_response.status_code == 201

        # Create execution and alert manually
        task = task_factory()
        rule = alert_rule_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
            overall_score=50,
        )

        AlertEvent.objects.create(
            rule=rule,
            instance_name="db-01",
            title="API Alert",
            level="critical",
        )

        # List events
        events_response = client.get("/api/scheduler/alerts/events/")
        assert events_response.status_code == 200
        assert events_response.data["count"] > 0


class TestCeleryIntegration:
    """Integration tests for Celery task execution."""

    def test_inspection_task_chain(self, task_factory, mock_diagnostic_agent, mock_platform_client):
        """Test inspection task chain execution."""
        from scheduler.tasks.inspection import run_inspection_task, run_single_inspection

        task = task_factory(target_instances=["db-01"])

        with patch("scheduler.tasks.inspection.run_single_inspection") as mock_single:
            mock_single.return_value = {"success": True, "score": 85}

            result = run_inspection_task(str(task.id))

            # Should execute for target instance
            mock_single.assert_called()

    def test_notification_task_chain(self, notification_channel_factory):
        """Test notification task chain."""
        from scheduler.tasks.notification import send_notification

        channel = notification_channel_factory(type="webhook")

        with patch("scheduler.tasks.notification._send_webhook") as mock_webhook:
            mock_webhook.return_value = {"success": True}

            result = send_notification(
                str(channel.id),
                None,
                {"title": "Test", "message": "Test message"}
            )

            assert result.get("success") is True