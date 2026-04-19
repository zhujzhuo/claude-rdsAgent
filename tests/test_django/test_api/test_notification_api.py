"""Tests for NotificationChannel API endpoints."""

import pytest
from rest_framework.test import APIClient
from rest_framework import status


pytestmark = pytest.mark.django_db


class TestNotificationChannelAPI:
    """Test cases for NotificationChannel API endpoints."""

    def test_list_channels_empty(self):
        """Test listing channels when empty."""
        client = APIClient()
        response = client.get("/api/scheduler/notifications/channels/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

    def test_list_channels(self, notification_channel_factory):
        """Test listing notification channels."""
        notification_channel_factory(name="DingTalk")
        notification_channel_factory(name="Email")

        client = APIClient()
        response = client.get("/api/scheduler/notifications/channels/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_create_dingtalk_channel(self):
        """Test creating a DingTalk channel."""
        client = APIClient()
        data = {
            "name": "DingTalk Alert",
            "type": "dingtalk",
            "config": {
                "webhook": "https://oapi.dingtalk.com/robot/send?access_token=test",
                "secret": "SEC123",
            },
        }

        response = client.post("/api/scheduler/notifications/channels/", data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "DingTalk Alert"
        assert response.data["type"] == "dingtalk"

    def test_create_webhook_channel(self):
        """Test creating a webhook channel."""
        client = APIClient()
        data = {
            "name": "Custom Webhook",
            "type": "webhook",
            "config": {
                "url": "https://example.com/webhook",
                "headers": {"Authorization": "Bearer token"},
            },
        }

        response = client.post("/api/scheduler/notifications/channels/", data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["type"] == "webhook"

    def test_retrieve_channel(self, notification_channel_factory):
        """Test retrieving a single channel."""
        channel = notification_channel_factory(name="Detail Channel")

        client = APIClient()
        response = client.get(f"/api/scheduler/notifications/channels/{channel.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Detail Channel"

    def test_update_channel(self, notification_channel_factory):
        """Test updating a channel."""
        channel = notification_channel_factory(name="Original")

        client = APIClient()
        data = {"name": "Updated"}
        response = client.patch(f"/api/scheduler/notifications/channels/{channel.id}/", data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Updated"

    def test_delete_channel(self, notification_channel_factory):
        """Test deleting a channel."""
        channel = notification_channel_factory(name="Delete Channel")

        client = APIClient()
        response = client.delete(f"/api/scheduler/notifications/channels/{channel.id}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_test_channel_action(self, notification_channel_factory):
        """Test test action on channel."""
        channel = notification_channel_factory(name="Test Channel")

        client = APIClient()
        response = client.post(f"/api/scheduler/notifications/channels/{channel.id}/test/")

        assert response.status_code == status.HTTP_200_OK
        # Response should contain test result
        assert "success" in response.data

    def test_filter_channels_by_type(self, notification_channel_factory):
        """Test filtering channels by type."""
        notification_channel_factory(name="DingTalk", type="dingtalk")
        notification_channel_factory(name="Email", type="email")
        notification_channel_factory(name="Another DingTalk", type="dingtalk")

        client = APIClient()
        response = client.get("/api/scheduler/notifications/channels/?type=dingtalk")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_filter_enabled_channels(self, notification_channel_factory):
        """Test filtering by enabled status."""
        notification_channel_factory(name="Enabled 1", enabled=True)
        notification_channel_factory(name="Enabled 2", enabled=True)
        notification_channel_factory(name="Disabled", enabled=False)

        client = APIClient()
        response = client.get("/api/scheduler/notifications/channels/?enabled=true")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2


class TestHealthHistoryAPI:
    """Test cases for HealthHistory API endpoints."""

    def test_list_history_empty(self):
        """Test listing health history when empty."""
        client = APIClient()
        response = client.get("/api/scheduler/history/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

    def test_list_history(self, task_factory):
        """Test listing health history."""
        from scheduler.models.history import HealthHistory
        from scheduler.models.execution import TaskExecution

        task = task_factory()

        for i in range(3):
            execution = TaskExecution.objects.create(
                task=task,
                instance_name=f"db-{i}",
            )
            HealthHistory.objects.create(
                instance_name=f"db-{i}",
                overall_score=80 + i * 5,
                execution=execution,
            )

        client = APIClient()
        response = client.get("/api/scheduler/history/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3

    def test_filter_history_by_instance(self, task_factory):
        """Test filtering history by instance."""
        from scheduler.models.history import HealthHistory
        from scheduler.models.execution import TaskExecution

        task = task_factory()

        execution1 = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )
        HealthHistory.objects.create(
            instance_name="db-01",
            overall_score=85,
            execution=execution1,
        )

        execution2 = TaskExecution.objects.create(
            task=task,
            instance_name="db-02",
        )
        HealthHistory.objects.create(
            instance_name="db-02",
            overall_score=90,
            execution=execution2,
        )

        client = APIClient()
        response = client.get("/api/scheduler/history/?instance_name=db-01")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["instance_name"] == "db-01"