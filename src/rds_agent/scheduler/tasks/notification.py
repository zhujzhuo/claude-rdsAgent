"""Celery Tasks for Notification.

Handles sending notifications through various channels.
"""

from celery import shared_task
import logging
import httpx
import json

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_notification(self, channel_id: str, alert_id: str, message_data: dict):
    """发送通知

    Args:
        channel_id: NotificationChannel UUID string
        alert_id: AlertEvent UUID string
        message_data: Message content dict

    Returns:
        dict: Send result
    """
    from scheduler.models.notification import NotificationChannel
    from scheduler.models.alert import AlertEvent
    from django.utils import timezone

    try:
        channel = NotificationChannel.objects.get(id=channel_id)
        alert = AlertEvent.objects.get(id=alert_id) if alert_id else None

        logger.info(f"Sending notification via {channel.type} to {channel.name}")

        result = _send_by_channel(channel, message_data)

        if result.get("success"):
            # Mark channel as used
            channel.last_used_at = timezone.now()
            channel.save()

            # Mark alert notification sent
            if alert:
                alert.notification_sent = True
                if alert.notification_channels:
                    alert.notification_channels.append(str(channel.id))
                else:
                    alert.notification_channels = [str(channel.id)]
                alert.save()

            logger.info(f"Notification sent successfully via {channel.type}")
            return {"success": True, "channel": channel.type}

        else:
            logger.error(f"Notification failed: {result.get('error')}")
            # Retry on failure
            self.retry(exc=Exception(result.get("error")))
            return result

    except NotificationChannel.DoesNotExist:
        logger.error(f"Channel {channel_id} not found")
        return {"success": False, "error": "Channel not found"}

    except Exception as e:
        logger.exception(f"Notification send failed: {e}")
        self.retry(exc=e)
        return {"success": False, "error": str(e)}


def _send_by_channel(channel, message_data: dict) -> dict:
    """Send notification through specific channel type"""
    from scheduler.models.notification import ChannelType

    config = channel.config

    if channel.type == ChannelType.DINGTALK:
        return _send_dingtalk(config, message_data)
    elif channel.type == ChannelType.EMAIL:
        return _send_email(config, message_data)
    elif channel.type == ChannelType.WECHAT:
        return _send_wechat(config, message_data)
    elif channel.type == ChannelType.WEBHOOK:
        return _send_webhook(config, message_data)
    else:
        return {"success": False, "error": f"Unknown channel type: {channel.type}"}


def _send_dingtalk(config: dict, message_data: dict) -> dict:
    """Send DingTalk notification"""
    webhook = config.get("webhook")
    secret = config.get("secret")

    if not webhook:
        return {"success": False, "error": "DingTalk webhook not configured"}

    try:
        # Build message
        content = message_data.get("message", "")
        title = message_data.get("title", "RDS Agent Alert")

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": content
            }
        }

        # Add signature if secret is configured
        url = webhook
        if secret:
            import time
            import hmac
            import hashlib
            import base64
            import urllib.parse

            timestamp = str(round(time.time() * 1000))
            string_to_sign = f"{timestamp}\n{secret}"
            hmac_code = hmac.new(
                secret.encode("utf-8"),
                string_to_sign.encode("utf-8"),
                digestmod=hashlib.sha256
            ).digest()
            sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
            url = f"{webhook}&timestamp={timestamp}&sign={sign}"

        # Send request
        with httpx.Client(timeout=30) as client:
            response = client.post(url, json=payload)

        if response.status_code == 200 and response.json().get("errcode") == 0:
            return {"success": True}
        else:
            return {"success": False, "error": response.text}

    except Exception as e:
        return {"success": False, "error": str(e)}


def _send_email(config: dict, message_data: dict) -> dict:
    """Send email notification (placeholder - requires SMTP setup)"""
    # Email sending requires proper SMTP configuration
    # This is a placeholder that logs the intent
    logger.info(f"Email notification would be sent: {message_data.get('title')}")
    return {"success": True, "note": "Email sending requires SMTP configuration"}


def _send_wechat(config: dict, message_data: dict) -> dict:
    """Send WeChat Work notification (placeholder)"""
    logger.info(f"WeChat notification would be sent: {message_data.get('title')}")
    return {"success": True, "note": "WeChat sending requires proper configuration"}


def _send_webhook(config: dict, message_data: dict) -> dict:
    """Send generic webhook notification"""
    url = config.get("url")
    headers = config.get("headers", {})

    if not url:
        return {"success": False, "error": "Webhook URL not configured"}

    try:
        payload = {
            "title": message_data.get("title", ""),
            "message": message_data.get("message", ""),
            "level": message_data.get("level", ""),
            "instance": message_data.get("instance_name", ""),
            "timestamp": message_data.get("timestamp", ""),
        }

        with httpx.Client(timeout=30) as client:
            response = client.post(url, json=payload, headers=headers)

        if response.status_code in [200, 201, 202]:
            return {"success": True}
        else:
            return {"success": False, "error": response.text}

    except Exception as e:
        return {"success": False, "error": str(e)}