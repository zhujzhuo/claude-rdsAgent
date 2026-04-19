"""Task Service - Task scheduling and execution management."""

import json
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class TaskService:
    """Service for managing task scheduling and execution"""

    @staticmethod
    def schedule_task(task):
        """Schedule task to Celery Beat

        Args:
            task: InspectionTask instance
        """
        from scheduler.models.task import ScheduleType, TaskStatus
        from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule

        if task.status != TaskStatus.ENABLED:
            logger.info(f"Task {task.name} is not enabled, skipping schedule")
            return

        # Cancel existing schedule first
        TaskService.cancel_task(task)

        try:
            if task.schedule_type == ScheduleType.CRON:
                # Parse cron expression
                parts = task.cron_expression.split() if task.cron_expression else ["*"] * 5

                crontab, _ = CrontabSchedule.objects.get_or_create(
                    minute=parts[0] if len(parts) > 0 else "*",
                    hour=parts[1] if len(parts) > 1 else "*",
                    day_of_month=parts[2] if len(parts) > 2 else "*",
                    month_of_year=parts[3] if len(parts) > 3 else "*",
                    day_of_week=parts[4] if len(parts) > 4 else "*",
                )

                periodic_task = PeriodicTask.objects.create(
                    name=f"task_{str(task.id)}",
                    task="scheduler.tasks.inspection.run_inspection_task",
                    crontab=crontab,
                    args=json.dumps([str(task.id)]),
                    enabled=True
                )

                logger.info(f"Task {task.name} scheduled with CRON: {task.cron_expression}")

            elif task.schedule_type == ScheduleType.INTERVAL:
                if not task.interval_seconds:
                    logger.warning(f"Task {task.name} has INTERVAL schedule but no interval_seconds")
                    return

                interval, _ = IntervalSchedule.objects.get_or_create(
                    every=task.interval_seconds,
                    period=IntervalSchedule.SECONDS
                )

                periodic_task = PeriodicTask.objects.create(
                    name=f"task_{str(task.id)}",
                    task="scheduler.tasks.inspection.run_inspection_task",
                    interval=interval,
                    args=json.dumps([str(task.id)]),
                    enabled=True
                )

                logger.info(f"Task {task.name} scheduled with INTERVAL: {task.interval_seconds}s")

            elif task.schedule_type == ScheduleType.ONCE:
                # For one-time tasks, just trigger immediately
                TaskService.run_task_now(task)
                return

            # Update task with celery task reference
            task.celery_task_id = periodic_task.name
            task.next_run_time = periodic_task.last_run_at or timezone.now()
            task.save()

        except Exception as e:
            logger.exception(f"Failed to schedule task {task.name}: {e}")

    @staticmethod
    def cancel_task(task):
        """Cancel task from Celery Beat

        Args:
            task: InspectionTask instance
        """
        from django_celery_beat.models import PeriodicTask

        try:
            periodic_task = PeriodicTask.objects.filter(
                name=f"task_{str(task.id)}"
            ).first()

            if periodic_task:
                periodic_task.delete()
                logger.info(f"Task {task.name} schedule cancelled")

        except Exception as e:
            logger.exception(f"Failed to cancel task {task.name}: {e}")

        task.celery_task_id = None
        task.save()

    @staticmethod
    def run_task_now(task):
        """Run task immediately (async)

        Args:
            task: InspectionTask instance

        Returns:
            str: Celery task ID
        """
        from scheduler.tasks.inspection import run_inspection_task

        result = run_inspection_task.delay(str(task.id))
        logger.info(f"Task {task.name} triggered immediately: {result.id}")
        return result.id

    @staticmethod
    def update_task_statistics(task, success: bool):
        """Update task execution statistics

        Args:
            task: InspectionTask instance
            success: Whether execution succeeded
        """
        task.run_count += 1
        if success:
            task.success_count += 1
        else:
            task.failure_count += 1
        task.last_run_time = timezone.now()
        task.save()