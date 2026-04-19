"""Tests for TaskExecution model."""

import pytest
from django.utils import timezone


pytestmark = pytest.mark.django_db


class TestTaskExecutionModel:
    """Test cases for TaskExecution model."""

    def test_create_execution_with_defaults(self, task_factory):
        """Test creating execution with default values."""
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-test-01",
        )

        assert execution.task == task
        assert execution.instance_name == "db-test-01"
        assert execution.status == "pending"
        assert execution.started_at is None

    def test_create_execution_with_results(self, task_factory):
        """Test creating execution with inspection results."""
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-test-01",
            status="completed",
            overall_score=85,
            overall_status="healthy",
            critical_count=0,
            warning_count=2,
            result_data={
                "category_scores": {
                    "performance": 90,
                    "security": 80,
                    "availability": 85,
                },
                "issues": [],
            },
        )

        assert execution.overall_score == 85
        assert execution.overall_status == "healthy"
        assert execution.critical_count == 0
        assert execution.warning_count == 2

    def test_execution_str_representation(self, task_factory):
        """Test execution string representation."""
        from scheduler.models.execution import TaskExecution

        task = task_factory(name="My Task")
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )

        str_repr = str(execution)
        assert "My Task" in str_repr
        assert "db-01" in str_repr

    def test_execution_uuid_primary_key(self, task_factory):
        """Test that execution uses UUID primary key."""
        from scheduler.models.execution import TaskExecution
        from uuid import UUID

        task = task_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )

        assert execution.id is not None
        UUID(str(execution.id))

    def test_execution_status_choices(self, task_factory):
        """Test execution status enum choices."""
        from scheduler.models.execution import TaskExecution, ExecutionStatus

        task = task_factory()

        execution_pending = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
            status=ExecutionStatus.PENDING,
        )
        execution_running = TaskExecution.objects.create(
            task=task,
            instance_name="db-02",
            status=ExecutionStatus.RUNNING,
        )
        execution_completed = TaskExecution.objects.create(
            task=task,
            instance_name="db-03",
            status=ExecutionStatus.COMPLETED,
        )

        assert execution_pending.status == ExecutionStatus.PENDING
        assert execution_running.status == ExecutionStatus.RUNNING
        assert execution_completed.status == ExecutionStatus.COMPLETED

    def test_execution_duration_calculation(self, task_factory):
        """Test execution duration calculation."""
        from scheduler.models.execution import TaskExecution
        from datetime import timedelta

        task = task_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
            started_at=timezone.now() - timedelta(minutes=5),
            completed_at=timezone.now(),
            status="completed",
        )

        # Duration should be calculable
        duration = execution.completed_at - execution.started_at
        assert duration.total_seconds() == 300

    def test_execution_error_message(self, task_factory):
        """Test execution error message field."""
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
            status="failed",
            error_message="Connection refused",
        )

        assert execution.error_message == "Connection refused"

    def test_execution_alerts_triggered(self, task_factory):
        """Test execution alerts_triggered JSON field."""
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
            alerts_triggered=[
                {"rule": "健康分数过低", "level": "critical", "alert_id": "abc123"},
                {"rule": "警告数量过多", "level": "warning", "alert_id": "def456"},
            ],
        )

        assert len(execution.alerts_triggered) == 2
        assert execution.alerts_triggered[0]["rule"] == "健康分数过低"

    def test_execution_report_path(self, task_factory):
        """Test execution report_path field."""
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
            report_path="/tmp/reports/db-01_20240101.json",
        )

        assert execution.report_path == "/tmp/reports/db-01_20240101.json"

    def test_execution_related_to_task(self, task_factory):
        """Test execution relationship to task."""
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        execution1 = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )
        execution2 = TaskExecution.objects.create(
            task=task,
            instance_name="db-02",
        )

        # Task should have multiple executions
        assert task.executions.count() == 2
        assert execution1 in task.executions.all()
        assert execution2 in task.executions.all()