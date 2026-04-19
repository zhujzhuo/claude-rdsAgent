"""Alert Service - Alert checking and triggering."""

import logging
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class AlertService:
    """Service for checking and triggering alerts"""

    # Default alert rules
    DEFAULT_RULES = [
        {
            "name": "健康分数过低",
            "metric_name": "overall_score",
            "operator": "<",
            "threshold": 60,
            "level": "critical",
            "description": "健康分数低于60分触发严重告警"
        },
        {
            "name": "健康分数偏低",
            "metric_name": "overall_score",
            "operator": "<",
            "threshold": 80,
            "level": "warning",
            "description": "健康分数低于80分触发警告"
        },
        {
            "name": "严重问题检测",
            "metric_name": "critical_count",
            "operator": ">",
            "threshold": 0,
            "level": "critical",
            "description": "检测到严重问题触发告警"
        },
        {
            "name": "警告数量过多",
            "metric_name": "warning_count",
            "operator": ">",
            "threshold": 5,
            "level": "warning",
            "description": "警告数量超过5个触发告警"
        },
    ]

    @staticmethod
    def check_and_trigger_alerts(execution_id: str, task_id: str):
        """Check execution results and trigger alerts if needed

        Args:
            execution_id: TaskExecution UUID string
            task_id: InspectionTask UUID string
        """
        from scheduler.models.execution import TaskExecution
        from scheduler.models.task import InspectionTask
        from scheduler.models.alert import AlertRule, AlertEvent, AlertLevel, AlertStatus

        try:
            execution = TaskExecution.objects.get(id=execution_id)
            task = InspectionTask.objects.get(id=task_id)

            if not task.alert_enabled:
                logger.info(f"Task {task.name} has alerts disabled")
                return

            # Get alert rules (default or custom)
            rules = AlertRule.objects.filter(enabled=True)
            if not rules.exists():
                # Create default rules if none exist
                AlertService._create_default_rules()

            # Check each rule
            alerts_triggered = []

            for rule in rules:
                if AlertService._should_trigger_alert(execution, rule):
                    # Check suppression
                    if not AlertService._is_suppressed(execution.instance_name, rule):
                        alert = AlertService._create_alert_event(execution, rule)
                        alerts_triggered.append({
                            "rule": rule.name,
                            "level": rule.level,
                            "alert_id": str(alert.id)
                        })

                        # Trigger notification
                        AlertService._trigger_notification(alert, task)

            # Update execution with triggered alerts
            execution.alerts_triggered = alerts_triggered
            execution.save()

            logger.info(f"Checked alerts for {execution.instance_name}: {len(alerts_triggered)} triggered")

        except Exception as e:
            logger.exception(f"Alert check failed: {e}")

    @staticmethod
    def _should_trigger_alert(execution, rule) -> bool:
        """Check if alert should be triggered based on execution results"""
        import operator as op

        # Get metric value from execution
        metric_value = getattr(execution, rule.metric_name, None)
        if metric_value is None:
            # Try from result_data
            if execution.result_data:
                metric_value = execution.result_data.get(rule.metric_name)

        if metric_value is None:
            return False

        # Compare with threshold
        ops = {
            ">": op.gt,
            "<": op.lt,
            ">=": op.ge,
            "<=": op.le,
            "==": op.eq,
            "!=": op.ne,
        }

        compare_func = ops.get(rule.operator, op.gt)
        return compare_func(metric_value, rule.threshold)

    @staticmethod
    def _is_suppressed(instance_name: str, rule) -> bool:
        """Check if alert should be suppressed"""
        from scheduler.models.alert import AlertEvent, AlertStatus

        # Check recent alerts for this instance and metric
        recent_alerts = AlertEvent.objects.filter(
            instance_name=instance_name,
            metric_name=rule.metric_name,
            status=AlertStatus.FIRING,
            triggered_at__gte=timezone.now() - timedelta(seconds=rule.suppress_duration)
        )

        return recent_alerts.exists()

    @staticmethod
    def _create_alert_event(execution, rule):
        """Create alert event"""
        from scheduler.models.alert import AlertEvent, AlertStatus

        metric_value = getattr(execution, rule.metric_name, 0)
        if execution.result_data:
            metric_value = execution.result_data.get(rule.metric_name, metric_value)

        alert = AlertEvent.objects.create(
            rule=rule,
            instance_name=execution.instance_name,
            level=rule.level,
            title=f"{rule.name}: {execution.instance_name}",
            message=f"{rule.description}\n当前值: {metric_value}\n阈值: {rule.threshold}",
            metric_name=rule.metric_name,
            metric_value=float(metric_value) if metric_value else 0.0,
            threshold=rule.threshold,
            status=AlertStatus.FIRING,
            execution=execution
        )

        logger.info(f"Created alert event: {alert.title}")
        return alert

    @staticmethod
    def _trigger_notification(alert, task):
        """Trigger notification for alert"""
        from scheduler.tasks.notification import send_notification
        from scheduler.models.notification import NotificationChannel

        # Get notification channels
        channels = NotificationChannel.objects.filter(enabled=True)

        if task.alert_channels:
            # Filter by task's specified channels
            channels = channels.filter(name__in=task.alert_channels)

        message_data = {
            "title": alert.title,
            "message": alert.message,
            "level": alert.level,
            "instance_name": alert.instance_name,
            "timestamp": str(alert.triggered_at)
        }

        for channel in channels:
            send_notification.delay(str(channel.id), str(alert.id), message_data)

    @staticmethod
    def _create_default_rules():
        """Create default alert rules"""
        from scheduler.models.alert import AlertRule, AlertLevel

        for rule_data in AlertService.DEFAULT_RULES:
            AlertRule.objects.create(
                name=rule_data["name"],
                description=rule_data["description"],
                metric_name=rule_data["metric_name"],
                operator=rule_data["operator"],
                threshold=rule_data["threshold"],
                level=rule_data["level"],
                enabled=True
            )

        logger.info("Created default alert rules")