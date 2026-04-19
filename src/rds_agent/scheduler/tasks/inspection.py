"""Celery Tasks for Inspection.

Corresponds to APScheduler jobs in executor.py.
"""

from celery import shared_task, chain
from django.utils import timezone
import logging
import sys
import os

# Add project path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_inspection_task(self, task_id: str):
    """执行巡检任务

    Args:
        task_id: InspectionTask UUID string

    Returns:
        dict: Execution summary
    """
    from scheduler.models.task import InspectionTask, TaskStatus, TaskType
    from scheduler.models.execution import TaskExecution, ExecutionStatus

    try:
        task = InspectionTask.objects.get(id=task_id)

        # Update task status
        task.status = TaskStatus.RUNNING
        task.save()

        results = []

        # Execute inspection for each target instance
        for instance_name in task.target_instances:
            execution_id = run_single_inspection(str(task.id), instance_name, task.task_type)
            results.append(execution_id)

        # Update task statistics
        task.run_count += 1
        task.last_run_time = timezone.now()
        task.status = TaskStatus.ENABLED
        task.save()

        logger.info(f"Task {task.name} completed with {len(results)} executions")

        return {
            "task_id": str(task.id),
            "executions": len(results),
            "execution_ids": results
        }

    except InspectionTask.DoesNotExist:
        logger.error(f"Task {task_id} not found")
        return {"error": "Task not found"}

    except Exception as e:
        logger.exception(f"Task execution failed: {e}")
        # Retry on failure
        self.retry(exc=e)
        return {"error": str(e)}


@shared_task(bind=True)
def run_single_inspection(self, task_id: str, instance_name: str, task_type: str):
    """执行单个实例巡检

    Args:
        task_id: InspectionTask UUID string
        instance_name: Instance name to inspect
        task_type: Task type string

    Returns:
        str: TaskExecution UUID string
    """
    from scheduler.models.task import InspectionTask, TaskType
    from scheduler.models.execution import TaskExecution, ExecutionStatus
    from scheduler.services.history_service import HistoryService

    try:
        task = InspectionTask.objects.get(id=task_id)

        # Create execution record
        execution = TaskExecution.objects.create(
            task=task,
            instance_name=instance_name,
            celery_task_id=self.request.id,
            status=ExecutionStatus.RUNNING
        )

        logger.info(f"Starting inspection for {instance_name} (task: {task.name})")

        # Get diagnostic agent and run inspection
        result = _execute_diagnostic(instance_name, task_type)

        if result:
            # Update execution with results
            execution.end_time = timezone.now()
            execution.duration_seconds = (execution.end_time - execution.start_time).total_seconds()
            execution.status = ExecutionStatus.SUCCESS
            execution.overall_score = result.overall_score
            execution.overall_status = result.overall_status.value if hasattr(result.overall_status, 'value') else str(result.overall_status)
            execution.critical_count = len(result.critical_issues) if hasattr(result, 'critical_issues') else 0
            execution.warning_count = len(result.warnings) if hasattr(result, 'warnings') else 0

            # Store result data
            execution.result_data = {
                "overall_score": result.overall_score,
                "overall_status": execution.overall_status,
                "critical_issues": getattr(result, 'critical_issues', []),
                "warnings": getattr(result, 'warnings', []),
                "suggestions": getattr(result, 'suggestions', []),
            }

            # Save report
            report_path = _save_report(result)
            if report_path:
                execution.report_path = str(report_path)

            execution.save()

            # Update task success count
            task.success_count += 1
            task.save()

            # Trigger alert check and history record chain
            chain(
                check_alerts.si(str(execution.id), str(task.id)),
                record_health_history.si(str(execution.id))
            ).apply_async()

            logger.info(f"Inspection completed for {instance_name}: score={result.overall_score}")

        else:
            execution.status = ExecutionStatus.FAILURE
            execution.error_message = "Diagnostic agent did not return result"
            execution.end_time = timezone.now()
            execution.duration_seconds = (execution.end_time - execution.start_time).total_seconds()
            execution.save()

            task.failure_count += 1
            task.save()

        return str(execution.id)

    except Exception as e:
        logger.exception(f"Single inspection failed: {e}")

        # Update execution as failed
        execution.status = ExecutionStatus.FAILURE
        execution.error_message = str(e)
        execution.end_time = timezone.now()
        execution.duration_seconds = (execution.end_time - execution.start_time).total_seconds()
        execution.save()

        task = InspectionTask.objects.get(id=task_id)
        task.failure_count += 1
        task.save()

        raise


def _execute_diagnostic(instance_name: str, task_type: str):
    """Execute diagnostic agent"""
    from rds_agent.diagnostic import get_diagnostic_agent, DiagnosticType

    # Map task type to diagnostic type
    type_mapping = {
        TaskType.FULL_INSPECTION: DiagnosticType.FULL_INSPECTION,
        TaskType.QUICK_CHECK: DiagnosticType.QUICK_CHECK,
        TaskType.PERFORMANCE_DIAG: DiagnosticType.PERFORMANCE_DIAG,
        TaskType.CONNECTION_DIAG: DiagnosticType.CONNECTION_DIAG,
        TaskType.STORAGE_DIAG: DiagnosticType.STORAGE_DIAG,
        TaskType.PARAMETER_DIAG: DiagnosticType.PARAMETER_DIAG,
        TaskType.SECURITY_DIAG: DiagnosticType.SECURITY_DIAG,
    }

    diagnostic_type = type_mapping.get(task_type, DiagnosticType.FULL_INSPECTION)

    try:
        agent = get_diagnostic_agent()
        result = agent.run(instance_name, diagnostic_type)
        return result
    except Exception as e:
        logger.error(f"Diagnostic agent failed: {e}")
        return None


def _save_report(result):
    """Save diagnostic report"""
    from rds_agent.diagnostic.report_generator import get_report_generator

    try:
        report_generator = get_report_generator()
        report_path = report_generator.save_report(result, format="json")
        return report_path
    except Exception as e:
        logger.error(f"Report save failed: {e}")
        return None


@shared_task
def check_alerts(execution_id: str, task_id: str):
    """检查告警

    Args:
        execution_id: TaskExecution UUID string
        task_id: InspectionTask UUID string
    """
    from scheduler.services.alert_service import AlertService

    try:
        AlertService.check_and_trigger_alerts(execution_id, task_id)
    except Exception as e:
        logger.exception(f"Alert check failed: {e}")


@shared_task
def record_health_history(execution_id: str):
    """记录健康历史

    Args:
        execution_id: TaskExecution UUID string
    """
    from scheduler.services.history_service import HistoryService

    try:
        HistoryService.record_health(execution_id)
    except Exception as e:
        logger.exception(f"History record failed: {e}")