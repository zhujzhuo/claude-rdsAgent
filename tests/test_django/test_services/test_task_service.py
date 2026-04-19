"""Tests for Task Service."""

import pytest
from unittest.mock import Mock, patch, MagicMock


pytestmark = pytest.mark.django_db


class TestTaskService:
    """Test cases for TaskService."""

    def test_schedule_interval_task(self, task_factory):
        """Test scheduling an interval task."""
        from scheduler.services.task_service import TaskService

        task = task_factory(
            schedule_type="interval",
            interval_seconds=3600,
        )

        with patch("django_celery_beat.models.PeriodicTask.objects.create") as mock_create:
            with patch("django_celery_beat.models.IntervalSchedule.objects.get_or_create") as mock_interval:
                mock_interval.return_value = (Mock(), True)
                mock_create.return_value = Mock(name=f"task_{task.id}")

                TaskService.schedule_task(task)

                mock_interval.assert_called_once()

    def test_schedule_cron_task(self, task_factory):
        """Test scheduling a cron task."""
        from scheduler.services.task_service import TaskService

        task = task_factory(
            schedule_type="cron",
            cron_expression="0 9 * * *",
        )

        with patch("django_celery_beat.models.PeriodicTask.objects.create") as mock_create:
            with patch("django_celery_beat.models.CrontabSchedule.objects.get_or_create") as mock_crontab:
                mock_crontab.return_value = (Mock(), True)
                mock_create.return_value = Mock(name=f"task_{task.id}")

                TaskService.schedule_task(task)

                mock_crontab.assert_called_once()

    def test_schedule_once_task(self, task_factory):
        """Test scheduling a one-time task."""
        from scheduler.services.task_service import TaskService

        task = task_factory(schedule_type="once")

        with patch.object(TaskService, "run_task_now") as mock_run:
            mock_run.return_value = "celery-task-id"

            TaskService.schedule_task(task)

            mock_run.assert_called_once_with(task)

    def test_schedule_disabled_task(self, task_factory):
        """Test scheduling a disabled task."""
        from scheduler.services.task_service import TaskService
        from scheduler.models.task import TaskStatus

        task = task_factory(status=TaskStatus.DISABLED)

        with patch("django_celery_beat.models.PeriodicTask.objects.create") as mock_create:
            TaskService.schedule_task(task)

            # Should not create periodic task
            mock_create.assert_not_called()

    def test_cancel_task(self, task_factory):
        """Test canceling a task."""
        from scheduler.services.task_service import TaskService

        task = task_factory(celery_task_id="task_123")

        with patch("django_celery_beat.models.PeriodicTask.objects.filter") as mock_filter:
            mock_periodic = Mock()
            mock_filter.return_value.first.return_value = mock_periodic

            TaskService.cancel_task(task)

            mock_periodic.delete.assert_called_once()

    def test_cancel_nonexistent_task(self, task_factory):
        """Test canceling a task with no schedule."""
        from scheduler.services.task_service import TaskService

        task = task_factory(celery_task_id=None)

        with patch("django_celery_beat.models.PeriodicTask.objects.filter") as mock_filter:
            mock_filter.return_value.first.return_value = None

            TaskService.cancel_task(task)

            # Should not raise error
            assert task.celery_task_id is None

    def test_run_task_now(self, task_factory):
        """Test running task immediately."""
        from scheduler.services.task_service import TaskService

        task = task_factory()

        with patch("scheduler.tasks.inspection.run_inspection_task.delay") as mock_delay:
            mock_result = Mock(id="celery-task-123")
            mock_delay.return_value = mock_result

            result = TaskService.run_task_now(task)

            assert result == "celery-task-123"
            mock_delay.assert_called_once_with(str(task.id))

    def test_update_statistics_success(self, task_factory):
        """Test updating task statistics on success."""
        from scheduler.services.task_service import TaskService

        task = task_factory(run_count=5, success_count=3)

        TaskService.update_task_statistics(task, success=True)

        assert task.run_count == 6
        assert task.success_count == 4
        assert task.failure_count == 0

    def test_update_statistics_failure(self, task_factory):
        """Test updating task statistics on failure."""
        from scheduler.services.task_service import TaskService

        task = task_factory(run_count=5, failure_count=1)

        TaskService.update_task_statistics(task, success=False)

        assert task.run_count == 6
        assert task.failure_count == 2