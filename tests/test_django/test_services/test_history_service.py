"""Tests for History Service."""

import pytest
from unittest.mock import Mock, patch


pytestmark = pytest.mark.django_db


class TestHistoryService:
    """Test cases for HistoryService."""

    def test_record_health_creates_history(self, task_factory):
        """Test record_health creates HealthHistory record."""
        from scheduler.services.history_service import HistoryService
        from scheduler.models.history import HealthHistory
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
            overall_score=85,
            overall_status="healthy",
            critical_count=0,
            warning_count=2,
            result_data={"category_scores": {"performance": 90, "security": 80}},
        )

        HistoryService.record_health(str(execution.id))

        # Should create history record
        history = HealthHistory.objects.filter(instance_name="db-01").first()
        assert history is not None
        assert history.overall_score == 85
        assert history.overall_status == "healthy"

    def test_record_health_no_result_data(self, task_factory):
        """Test record_health when execution has no result data."""
        from scheduler.services.history_service import HistoryService
        from scheduler.models.history import HealthHistory
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
            result_data=None,
        )

        HistoryService.record_health(str(execution.id))

        # Should not create history when no data
        history_count = HealthHistory.objects.filter(instance_name="db-01").count()
        assert history_count == 0

    def test_get_instance_history(self, task_factory):
        """Test get_instance_history returns records."""
        from scheduler.services.history_service import HistoryService
        from scheduler.models.history import HealthHistory
        from scheduler.models.execution import TaskExecution

        task = task_factory()

        for i in range(5):
            execution = TaskExecution.objects.create(
                task=task,
                instance_name="db-01",
            )
            HealthHistory.objects.create(
                instance_name="db-01",
                overall_score=80 + i,
                execution=execution,
            )

        histories = HistoryService.get_instance_history("db-01", days=7)

        assert histories.count() == 5

    def test_get_last_health(self, task_factory):
        """Test get_last_health returns most recent."""
        from scheduler.services.history_service import HistoryService
        from scheduler.models.history import HealthHistory
        from scheduler.models.execution import TaskExecution

        task = task_factory()

        execution1 = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )
        HealthHistory.objects.create(
            instance_name="db-01",
            overall_score=80,
            execution=execution1,
        )

        execution2 = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )
        HistoryService.record_health  # This is a method, not calling it here
        latest = HealthHistory.objects.create(
            instance_name="db-01",
            overall_score=85,
            execution=execution2,
        )

        result = HistoryService.get_last_health("db-01")

        assert result == latest

    def test_get_health_trend_improving(self, task_factory):
        """Test get_health_trend with improving trend."""
        from scheduler.services.history_service import HistoryService
        from scheduler.models.history import HealthHistory, TrendType
        from scheduler.models.execution import TaskExecution

        task = task_factory()

        # Create records showing improvement
        scores = [70, 75, 80, 85, 90]
        for score in scores:
            execution = TaskExecution.objects.create(
                task=task,
                instance_name="db-01",
            )
            HealthHistory.objects.create(
                instance_name="db-01",
                overall_score=score,
                execution=execution,
            )

        trend = HistoryService.get_health_trend("db-01", days=7)

        assert trend["current_score"] == 90
        assert trend["overall_trend"] == TrendType.IMPROVING
        assert trend["records_count"] == 5

    def test_get_health_trend_degrading(self, task_factory):
        """Test get_health_trend with degrading trend."""
        from scheduler.services.history_service import HistoryService
        from scheduler.models.history import HealthHistory, TrendType
        from scheduler.models.execution import TaskExecution

        task = task_factory()

        # Create records showing degradation
        scores = [90, 85, 80, 75, 70]
        for score in scores:
            execution = TaskExecution.objects.create(
                task=task,
                instance_name="db-01",
            )
            HealthHistory.objects.create(
                instance_name="db-01",
                overall_score=score,
                execution=execution,
            )

        trend = HistoryService.get_health_trend("db-01", days=7)

        assert trend["current_score"] == 70
        assert trend["overall_trend"] == TrendType.DEGADING

    def test_get_health_trend_stable(self, task_factory):
        """Test get_health_trend with stable trend."""
        from scheduler.services.history_service import HistoryService
        from scheduler.models.history import HealthHistory, TrendType
        from scheduler.models.execution import TaskExecution

        task = task_factory()

        # Create records showing stability
        scores = [80, 81, 80, 82, 80]
        for score in scores:
            execution = TaskExecution.objects.create(
                task=task,
                instance_name="db-01",
            )
            HealthHistory.objects.create(
                instance_name="db-01",
                overall_score=score,
                execution=execution,
            )

        trend = HistoryService.get_health_trend("db-01", days=7)

        assert trend["overall_trend"] == TrendType.STABLE

    def test_get_health_trend_insufficient_records(self, task_factory):
        """Test get_health_trend with insufficient records."""
        from scheduler.services.history_service import HistoryService
        from scheduler.models.history import HealthHistory
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )
        HealthHistory.objects.create(
            instance_name="db-01",
            overall_score=80,
            execution=execution,
        )

        trend = HistoryService.get_health_trend("db-01", days=7)

        # Only 1 record, cannot determine trend
        assert trend["trend"] is None
        assert trend["records_count"] == 1

    def test_get_all_instances_trends(self, task_factory):
        """Test get_all_instances_trends returns trends for all."""
        from scheduler.services.history_service import HistoryService
        from scheduler.models.history import HealthHistory
        from scheduler.models.execution import TaskExecution

        task = task_factory()

        # Create histories for multiple instances
        for instance in ["db-01", "db-02", "db-03"]:
            execution = TaskExecution.objects.create(
                task=task,
                instance_name=instance,
            )
            HealthHistory.objects.create(
                instance_name=instance,
                overall_score=85,
                execution=execution,
            )

        trends = HistoryService.get_all_instances_trends(days=7)

        assert len(trends) == 3

        instance_names = [t["instance_name"] for t in trends]
        assert "db-01" in instance_names
        assert "db-02" in instance_names
        assert "db-03" in instance_names