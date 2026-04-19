"""Tests for Alert API endpoints."""

import pytest
from rest_framework.test import APIClient
from rest_framework import status


pytestmark = pytest.mark.django_db


class TestAlertRuleAPI:
    """Test cases for AlertRule API endpoints."""

    def test_list_rules_empty(self):
        """Test listing alert rules when empty."""
        client = APIClient()
        response = client.get("/api/scheduler/alerts/rules/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

    def test_list_rules(self, alert_rule_factory):
        """Test listing alert rules."""
        alert_rule_factory(name="Rule 1")
        alert_rule_factory(name="Rule 2")

        client = APIClient()
        response = client.get("/api/scheduler/alerts/rules/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_create_rule(self):
        """Test creating a new alert rule."""
        client = APIClient()
        data = {
            "name": "Score Alert",
            "description": "Health score alert",
            "metric_name": "overall_score",
            "operator": "<",
            "threshold": 60,
            "level": "critical",
        }

        response = client.post("/api/scheduler/alerts/rules/", data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Score Alert"

    def test_retrieve_rule(self, alert_rule_factory):
        """Test retrieving a single rule."""
        rule = alert_rule_factory(name="Detail Rule")

        client = APIClient()
        response = client.get(f"/api/scheduler/alerts/rules/{rule.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Detail Rule"

    def test_update_rule(self, alert_rule_factory):
        """Test updating an alert rule."""
        rule = alert_rule_factory(threshold=60)

        client = APIClient()
        data = {"threshold": 70}
        response = client.patch(f"/api/scheduler/alerts/rules/{rule.id}/", data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["threshold"] == 70

    def test_delete_rule(self, alert_rule_factory):
        """Test deleting an alert rule."""
        rule = alert_rule_factory(name="Delete Rule")

        client = APIClient()
        response = client.delete(f"/api/scheduler/alerts/rules/{rule.id}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_filter_rules_by_level(self, alert_rule_factory):
        """Test filtering rules by level."""
        alert_rule_factory(name="Critical 1", level="critical")
        alert_rule_factory(name="Warning", level="warning")
        alert_rule_factory(name="Critical 2", level="critical")

        client = APIClient()
        response = client.get("/api/scheduler/alerts/rules/?level=critical")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2


class TestAlertEventAPI:
    """Test cases for AlertEvent API endpoints."""

    def test_list_events_empty(self):
        """Test listing alert events when empty."""
        client = APIClient()
        response = client.get("/api/scheduler/alerts/events/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

    def test_list_events(self, task_factory, alert_rule_factory):
        """Test listing alert events."""
        from scheduler.models.alert import AlertEvent
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        rule = alert_rule_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )

        AlertEvent.objects.create(
            rule=rule,
            instance_name="db-01",
            level="critical",
            title="Alert 1",
            execution=execution,
        )
        AlertEvent.objects.create(
            rule=rule,
            instance_name="db-02",
            level="warning",
            title="Alert 2",
            execution=execution,
        )

        client = APIClient()
        response = client.get("/api/scheduler/alerts/events/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_retrieve_event(self, task_factory, alert_rule_factory):
        """Test retrieving a single event."""
        from scheduler.models.alert import AlertEvent
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        rule = alert_rule_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )

        event = AlertEvent.objects.create(
            rule=rule,
            instance_name="db-01",
            level="critical",
            title="Detail Alert",
            execution=execution,
        )

        client = APIClient()
        response = client.get(f"/api/scheduler/alerts/events/{event.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "Detail Alert"

    def test_filter_events_by_status(self, task_factory, alert_rule_factory):
        """Test filtering events by status."""
        from scheduler.models.alert import AlertEvent, AlertStatus
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        rule = alert_rule_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )

        AlertEvent.objects.create(
            rule=rule,
            instance_name="db-01",
            status=AlertStatus.FIRING,
            execution=execution,
        )
        AlertEvent.objects.create(
            rule=rule,
            instance_name="db-02",
            status=AlertStatus.RESOLVED,
            execution=execution,
        )

        client = APIClient()
        response = client.get("/api/scheduler/alerts/events/?status=firing")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_filter_events_by_instance(self, task_factory, alert_rule_factory):
        """Test filtering events by instance name."""
        from scheduler.models.alert import AlertEvent
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        rule = alert_rule_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )

        AlertEvent.objects.create(
            rule=rule,
            instance_name="db-master",
            title="Master Alert",
            execution=execution,
        )
        AlertEvent.objects.create(
            rule=rule,
            instance_name="db-slave",
            title="Slave Alert",
            execution=execution,
        )

        client = APIClient()
        response = client.get("/api/scheduler/alerts/events/?instance_name=db-master")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1