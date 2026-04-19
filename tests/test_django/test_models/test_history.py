"""Tests for HealthHistory model."""

import pytest
from django.utils import timezone


pytestmark = pytest.mark.django_db


class TestHealthHistoryModel:
    """Test cases for HealthHistory model."""

    def test_create_health_history(self, task_factory):
        """Test creating health history record."""
        from scheduler.models.history import HealthHistory
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
            overall_score=85,
            overall_status="healthy",
        )

        history = HealthHistory.objects.create(
            instance_name="db-01",
            overall_score=85,
            overall_status="healthy",
            category_scores={
                "performance": 90,
                "security": 80,
            },
            critical_count=0,
            warning_count=2,
            execution=execution,
        )

        assert history.instance_name == "db-01"
        assert history.overall_score == 85
        assert history.overall_status == "healthy"
        assert history.category_scores["performance"] == 90

    def test_health_history_trend_choices(self, task_factory):
        """Test health history trend choices."""
        from scheduler.models.history import HealthHistory, TrendType
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )

        history_improving = HealthHistory.objects.create(
            instance_name="db-01",
            overall_score=85,
            trend=TrendType.IMPROVING,
            score_change=10,
        )
        history_degrading = HealthHistory.objects.create(
            instance_name="db-01",
            overall_score=75,
            trend=TrendType.DEGADING,
            score_change=-10,
        )
        history_stable = HealthHistory.objects.create(
            instance_name="db-01",
            overall_score=80,
            trend=TrendType.STABLE,
            score_change=0,
        )

        assert history_improving.trend == TrendType.IMPROVING
        assert history_degrading.trend == TrendType.DEGADING
        assert history_stable.trend == TrendType.STABLE

    def test_health_history_score_change(self, task_factory):
        """Test health history score change calculation."""
        from scheduler.models.history import HealthHistory
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )

        history = HealthHistory.objects.create(
            instance_name="db-01",
            overall_score=75,
            score_change=-5.0,
            execution=execution,
        )

        assert history.score_change == -5.0

    def test_health_history_uuid_primary_key(self, task_factory):
        """Test that health history uses UUID primary key."""
        from scheduler.models.history import HealthHistory
        from scheduler.models.execution import TaskExecution
        from uuid import UUID

        task = task_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )

        history = HealthHistory.objects.create(
            instance_name="db-01",
            overall_score=85,
            execution=execution,
        )

        assert history.id is not None
        UUID(str(history.id))

    def test_health_history_filter_by_instance(self, task_factory):
        """Test filtering health history by instance."""
        from scheduler.models.history import HealthHistory
        from scheduler.models.execution import TaskExecution

        task = task_factory()

        # Create multiple histories for different instances
        for instance in ["db-01", "db-02", "db-01"]:
            execution = TaskExecution.objects.create(
                task=task,
                instance_name=instance,
            )
            HealthHistory.objects.create(
                instance_name=instance,
                overall_score=80,
                execution=execution,
            )

        # Filter by instance
        db01_histories = HealthHistory.objects.filter(instance_name="db-01")
        db02_histories = HealthHistory.objects.filter(instance_name="db-02")

        assert db01_histories.count() == 2
        assert db02_histories.count() == 1

    def test_health_history_ordering(self, task_factory):
        """Test health history ordering by recorded_at."""
        from scheduler.models.history import HealthHistory
        from scheduler.models.execution import TaskExecution

        task = task_factory()

        # Create histories with different times
        execution1 = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )
        history1 = HealthHistory.objects.create(
            instance_name="db-01",
            overall_score=80,
            execution=execution1,
        )

        execution2 = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )
        history2 = HealthHistory.objects.create(
            instance_name="db-01",
            overall_score=85,
            execution=execution2,
        )

        # Should be ordered by recorded_at descending (most recent first)
        histories = HealthHistory.objects.filter(instance_name="db-01").order_by("-recorded_at")
        assert histories.first() == history2