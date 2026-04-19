"""Tests for InspectionTask model."""

import pytest
from django.utils import timezone


pytestmark = pytest.mark.django_db


class TestInspectionTaskModel:
    """Test cases for InspectionTask model."""

    def test_create_task_with_defaults(self, task_factory):
        """Test creating task with default values."""
        task = task_factory()

        assert task.name == "Test Task"
        assert task.description == "Test task description"
        assert task.target_instances == ["db-test-01"]
        assert task.task_type == "full_inspection"
        assert task.status == "enabled"
        assert task.run_count == 0
        assert task.success_count == 0
        assert task.failure_count == 0

    def test_create_task_with_custom_values(self, task_factory):
        """Test creating task with custom values."""
        task = task_factory(
            name="Custom Task",
            target_instances=["db-01", "db-02", "db-03"],
            task_type="quick_check",
            cron_expression="0 9 * * *",
            schedule_type="cron",
        )

        assert task.name == "Custom Task"
        assert len(task.target_instances) == 3
        assert task.task_type == "quick_check"
        assert task.cron_expression == "0 9 * * *"
        assert task.schedule_type == "cron"

    def test_task_str_representation(self, task_factory):
        """Test task string representation."""
        task = task_factory(name="My Task")
        assert str(task) == "My Task"

    def test_task_uuid_primary_key(self, task_factory):
        """Test that task uses UUID primary key."""
        task = task_factory()
        assert task.id is not None
        # UUID should be a valid UUID format
        from uuid import UUID
        UUID(str(task.id))

    def test_task_status_choices(self, task_factory):
        """Test task status enum choices."""
        from scheduler.models.task import TaskStatus

        task_enabled = task_factory(status=TaskStatus.ENABLED)
        task_disabled = task_factory(status=TaskStatus.DISABLED)

        assert task_enabled.status == TaskStatus.ENABLED
        assert task_disabled.status == TaskStatus.DISABLED

    def test_task_schedule_type_choices(self, task_factory):
        """Test task schedule type enum choices."""
        from scheduler.models.task import ScheduleType

        task_cron = task_factory(schedule_type=ScheduleType.CRON, cron_expression="0 9 * * *")
        task_interval = task_factory(schedule_type=ScheduleType.INTERVAL, interval_seconds=300)
        task_once = task_factory(schedule_type=ScheduleType.ONCE)

        assert task_cron.schedule_type == ScheduleType.CRON
        assert task_interval.schedule_type == ScheduleType.INTERVAL
        assert task_once.schedule_type == ScheduleType.ONCE

    def test_task_alert_configuration(self, task_factory):
        """Test task alert configuration."""
        task = task_factory(
            alert_enabled=True,
            alert_channels=["dingtalk", "email"],
            alert_suppress_duration=600,
        )

        assert task.alert_enabled is True
        assert task.alert_channels == ["dingtalk", "email"]
        assert task.alert_suppress_duration == 600

    def test_task_statistics_update(self, task_factory):
        """Test task statistics fields."""
        task = task_factory()
        task.run_count = 10
        task.success_count = 8
        task.failure_count = 2
        task.last_run_time = timezone.now()
        task.save()

        assert task.run_count == 10
        assert task.success_count == 8
        assert task.failure_count == 2
        assert task.last_run_time is not None

    def test_task_json_field_target_instances(self, task_factory):
        """Test JSON field for target_instances."""
        instances = ["db-master-01", "db-slave-01", "db-slave-02"]
        task = task_factory(target_instances=instances)

        assert task.target_instances == instances
        # Test modification
        task.target_instances.append("db-new-01")
        task.save()
        assert len(task.target_instances) == 4

    def test_task_optional_fields(self, task_factory):
        """Test optional fields can be null."""
        task = task_factory(
            cron_expression=None,
            interval_seconds=None,
            celery_task_id=None,
            next_run_time=None,
            last_run_time=None,
        )

        assert task.cron_expression is None
        assert task.interval_seconds is None
        assert task.celery_task_id is None
        assert task.next_run_time is None
        assert task.last_run_time is None