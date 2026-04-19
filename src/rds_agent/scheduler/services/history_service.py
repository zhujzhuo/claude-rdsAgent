"""History Service - Health history recording and trend analysis."""

import logging
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class HistoryService:
    """Service for recording and analyzing health history"""

    @staticmethod
    def record_health(execution_id: str):
        """Record health history from execution result

        Args:
            execution_id: TaskExecution UUID string
        """
        from scheduler.models.execution import TaskExecution
        from scheduler.models.history import HealthHistory, TrendType

        try:
            execution = TaskExecution.objects.get(id=execution_id)

            if not execution.result_data:
                logger.warning(f"Execution {execution_id} has no result data")
                return

            # Create health history record
            history = HealthHistory.objects.create(
                instance_name=execution.instance_name,
                overall_score=execution.overall_score or 0,
                overall_status=execution.overall_status or "unknown",
                category_scores=execution.result_data.get("category_scores", {}),
                critical_count=execution.critical_count,
                warning_count=execution.warning_count,
                execution=execution
            )

            # Calculate trend
            HistoryService._calculate_trend(history)

            logger.info(f"Recorded health history for {execution.instance_name}: score={history.overall_score}")

        except Exception as e:
            logger.exception(f"Health history record failed: {e}")

    @staticmethod
    def _calculate_trend(history):
        """Calculate trend by comparing with previous records"""
        from scheduler.models.history import HealthHistory, TrendType

        # Get previous records for this instance
        previous_records = HealthHistory.objects.filter(
            instance_name=history.instance_name,
            recorded_at__lt=history.recorded_at
        ).order_by("-recorded_at")[:1]

        if previous_records.exists():
            previous = previous_records[0]
            history.score_change = float(history.overall_score - previous.overall_score)

            if history.score_change > 5:
                history.trend = TrendType.IMPROVING
            elif history.score_change < -5:
                history.trend = TrendType.DEGADING
            else:
                history.trend = TrendType.STABLE

            history.save()

    @staticmethod
    def get_instance_history(instance_name: str, days: int = 7):
        """Get health history for an instance

        Args:
            instance_name: Instance name
            days: Number of days to look back

        Returns:
            list: HealthHistory records
        """
        from scheduler.models.history import HealthHistory

        start_date = timezone.now() - timedelta(days=days)
        return HealthHistory.objects.filter(
            instance_name=instance_name,
            recorded_at__gte=start_date
        ).order_by("-recorded_at")

    @staticmethod
    def get_last_health(instance_name: str):
        """Get last health record for an instance

        Args:
            instance_name: Instance name

        Returns:
            HealthHistory or None
        """
        from scheduler.models.history import HealthHistory

        return HealthHistory.objects.filter(
            instance_name=instance_name
        ).order_by("-recorded_at").first()

    @staticmethod
    def get_health_trend(instance_name: str, days: int = 7):
        """Get health trend analysis for an instance

        Args:
            instance_name: Instance name
            days: Number of days to analyze

        Returns:
            dict: Trend analysis result
        """
        from scheduler.models.history import HealthHistory, TrendType

        records = HistoryService.get_instance_history(instance_name, days)

        if records.count() < 2:
            return {
                "instance_name": instance_name,
                "current_score": records[0].overall_score if records.exists() else None,
                "trend": None,
                "records_count": records.count()
            }

        latest = records[0]
        oldest = records[records.count() - 1]
        total_change = latest.overall_score - oldest.overall_score
        avg_change = total_change / (records.count() - 1)

        # Determine overall trend
        if avg_change > 2:
            overall_trend = TrendType.IMPROVING
        elif avg_change < -2:
            overall_trend = TrendType.DEGADING
        else:
            overall_trend = TrendType.STABLE

        return {
            "instance_name": instance_name,
            "current_score": latest.overall_score,
            "previous_score": oldest.overall_score,
            "total_change": total_change,
            "avg_change": round(avg_change, 2),
            "overall_trend": overall_trend,
            "trend_display": dict(TrendType.choices).get(overall_trend, ""),
            "records_count": records.count(),
            "days_analyzed": days
        }

    @staticmethod
    def get_all_instances_trends(days: int = 7):
        """Get trends for all instances

        Args:
            days: Number of days to analyze

        Returns:
            list: Trend analysis for each instance
        """
        from scheduler.models.history import HealthHistory

        start_date = timezone.now() - timedelta(days=days)

        instances = HealthHistory.objects.filter(
            recorded_at__gte=start_date
        ).values_list("instance_name", flat=True).distinct()

        trends = []
        for instance in instances:
            trend = HistoryService.get_health_trend(instance, days)
            trends.append(trend)

        return trends