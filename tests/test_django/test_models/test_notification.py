"""Tests for NotificationChannel model."""

import pytest


pytestmark = pytest.mark.django_db


class TestNotificationChannelModel:
    """Test cases for NotificationChannel model."""

    def test_create_channel_with_defaults(self, notification_channel_factory):
        """Test creating notification channel with default values."""
        channel = notification_channel_factory()

        assert channel.name == "Test Channel"
        assert channel.type == "dingtalk"
        assert channel.enabled is True
        assert channel.config.get("webhook") is not None

    def test_create_channel_custom_values(self, notification_channel_factory):
        """Test creating channel with custom values."""
        channel = notification_channel_factory(
            name="Email Alert Channel",
            type="email",
            config={
                "smtp_host": "smtp.example.com",
                "smtp_port": 587,
                "recipients": ["admin@example.com"],
            },
        )

        assert channel.name == "Email Alert Channel"
        assert channel.type == "email"
        assert channel.config["smtp_host"] == "smtp.example.com"

    def test_channel_str_representation(self, notification_channel_factory):
        """Test channel string representation."""
        channel = notification_channel_factory(name="My Channel")
        assert str(channel) == "My Channel"

    def test_channel_uuid_primary_key(self, notification_channel_factory):
        """Test that channel uses UUID primary key."""
        from uuid import UUID

        channel = notification_channel_factory()
        assert channel.id is not None
        UUID(str(channel.id))

    def test_channel_type_choices(self, notification_channel_factory):
        """Test channel type enum choices."""
        from scheduler.models.notification import ChannelType

        channel_dingtalk = notification_channel_factory(type=ChannelType.DINGTALK)
        channel_email = notification_channel_factory(type=ChannelType.EMAIL)
        channel_wechat = notification_channel_factory(type=ChannelType.WECHAT)
        channel_webhook = notification_channel_factory(type=ChannelType.WEBHOOK)

        assert channel_dingtalk.type == ChannelType.DINGTALK
        assert channel_email.type == ChannelType.EMAIL
        assert channel_wechat.type == ChannelType.WECHAT
        assert channel_webhook.type == ChannelType.WEBHOOK

    def test_channel_config_json_field(self, notification_channel_factory):
        """Test channel config JSON field."""
        config = {
            "webhook": "https://oapi.dingtalk.com/robot/send?access_token=test",
            "secret": "SEC123abc",
        }
        channel = notification_channel_factory(config=config)

        assert channel.config == config
        # Test modification
        channel.config["timeout"] = 30
        channel.save()
        assert channel.config["timeout"] == 30

    def test_channel_last_used_at(self, notification_channel_factory):
        """Test channel last_used_at field."""
        from django.utils import timezone

        channel = notification_channel_factory()
        channel.last_used_at = timezone.now()
        channel.save()

        assert channel.last_used_at is not None

    def test_channel_disabled(self, notification_channel_factory):
        """Test disabling a channel."""
        channel = notification_channel_factory(enabled=False)
        assert channel.enabled is False