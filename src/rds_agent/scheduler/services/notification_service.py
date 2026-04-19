"""Notification Service - Notification management."""

import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing notifications"""

    @staticmethod
    def send_to_channels(alert, channels: list):
        """Send notification to specified channels

        Args:
            alert: AlertEvent instance
            channels: List of NotificationChannel instances or names
        """
        from scheduler.models.notification import NotificationChannel
        from scheduler.tasks.notification import send_notification

        message_data = {
            "title": alert.title,
            "message": alert.message,
            "level": alert.level,
            "instance_name": alert.instance_name,
            "timestamp": str(alert.triggered_at)
        }

        for channel in channels:
            if isinstance(channel, str):
                # Channel is a name, get the actual channel
                try:
                    channel = NotificationChannel.objects.get(name=channel, enabled=True)
                except NotificationChannel.DoesNotExist:
                    logger.warning(f"Channel {channel} not found or disabled")
                    continue

            if not channel.enabled:
                continue

            # Trigger async notification task
            send_notification.delay(str(channel.id), str(alert.id), message_data)

    @staticmethod
    def test_channel(channel_id: str):
        """Test notification channel

        Args:
            channel_id: NotificationChannel UUID string

        Returns:
            dict: Test result
        """
        from scheduler.models.notification import NotificationChannel
        from scheduler.tasks.notification import _send_by_channel

        try:
            channel = NotificationChannel.objects.get(id=channel_id)

            test_message = {
                "title": "RDS Agent - Channel Test",
                "message": "This is a test notification from RDS Agent.",
                "level": "info",
                "instance_name": "test",
                "timestamp": str(timezone.now())
            }

            result = _send_by_channel(channel, test_message)

            if result.get("success"):
                channel.last_used_at = timezone.now()
                channel.save()

            return result

        except NotificationChannel.DoesNotExist:
            return {"success": False, "error": "Channel not found"}

        except Exception as e:
            return {"success": False, "error": str(e)}