"""Tests for Notification Service."""

import pytest
from unittest.mock import Mock, patch


pytestmark = pytest.mark.django_db


class TestNotificationService:
    """Test cases for NotificationService."""

    def test_send_to_channels_success(self, notification_channel_factory, task_factory):
        """Test send_to_channels sends to enabled channels."""
        from scheduler.services.notification_service import NotificationService
        from scheduler.models.alert import AlertEvent
        from scheduler.models.execution import TaskExecution

        channel1 = notification_channel_factory(name="DingTalk", enabled=True)
        channel2 = notification_channel_factory(name="Email", enabled=True)

        task = task_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )

        alert = AlertEvent.objects.create(
            instance_name="db-01",
            level="critical",
            title="Test Alert",
            message="Test message",
        )

        with patch("scheduler.tasks.notification.send_notification.delay") as mock_delay:
            mock_delay.return_value = Mock(id="task-123")

            NotificationService.send_to_channels(alert, [channel1, channel2])

            # Should send to both channels
            assert mock_delay.call_count == 2

    def test_send_to_channels_disabled_channel(self, notification_channel_factory, task_factory):
        """Test send_to_channels skips disabled channels."""
        from scheduler.services.notification_service import NotificationService
        from scheduler.models.alert import AlertEvent
        from scheduler.models.execution import TaskExecution

        channel_enabled = notification_channel_factory(name="Enabled", enabled=True)
        channel_disabled = notification_channel_factory(name="Disabled", enabled=False)

        task = task_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )

        alert = AlertEvent.objects.create(
            instance_name="db-01",
            level="critical",
            title="Test Alert",
        )

        with patch("scheduler.tasks.notification.send_notification.delay") as mock_delay:
            NotificationService.send_to_channels(alert, [channel_enabled, channel_disabled])

            # Should only send to enabled channel
            assert mock_delay.call_count == 1

    def test_send_to_channels_by_name(self, notification_channel_factory, task_factory):
        """Test send_to_channels with channel names."""
        from scheduler.services.notification_service import NotificationService
        from scheduler.models.alert import AlertEvent
        from scheduler.models.execution import TaskExecution

        channel = notification_channel_factory(name="DingTalk", enabled=True)

        task = task_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )

        alert = AlertEvent.objects.create(
            instance_name="db-01",
            level="critical",
            title="Test Alert",
        )

        with patch("scheduler.tasks.notification.send_notification.delay") as mock_delay:
            NotificationService.send_to_channels(alert, ["DingTalk"])

            # Should send to channel by name
            mock_delay.assert_called_once()

    def test_send_to_channels_nonexistent_name(self, task_factory):
        """Test send_to_channels with nonexistent channel name."""
        from scheduler.services.notification_service import NotificationService
        from scheduler.models.alert import AlertEvent
        from scheduler.models.execution import TaskExecution

        task = task_factory()
        execution = TaskExecution.objects.create(
            task=task,
            instance_name="db-01",
        )

        alert = AlertEvent.objects.create(
            instance_name="db-01",
            level="critical",
            title="Test Alert",
        )

        with patch("scheduler.tasks.notification.send_notification.delay") as mock_delay:
            NotificationService.send_to_channels(alert, ["Nonexistent"])

            # Should not send to nonexistent channel
            mock_delay.assert_not_called()

    def test_test_channel_success(self, notification_channel_factory):
        """Test test_channel returns success."""
        from scheduler.services.notification_service import NotificationService

        channel = notification_channel_factory(type="webhook")

        with patch("scheduler.tasks.notification._send_by_channel") as mock_send:
            mock_send.return_value = {"success": True}

            result = NotificationService.test_channel(str(channel.id))

            assert result.get("success") is True

    def test_test_channel_not_found(self):
        """Test test_channel when channel not found."""
        from scheduler.services.notification_service import NotificationService

        result = NotificationService.test_channel("nonexistent-id")

        assert result.get("success") is False
        assert "error" in result

    def test_test_channel_updates_last_used(self, notification_channel_factory):
        """Test test_channel updates last_used_at on success."""
        from scheduler.services.notification_service import NotificationService

        channel = notification_channel_factory()

        with patch("scheduler.tasks.notification._send_by_channel") as mock_send:
            mock_send.return_value = {"success": True}

            NotificationService.test_channel(str(channel.id))

            channel.refresh_from_db()
            assert channel.last_used_at is not None