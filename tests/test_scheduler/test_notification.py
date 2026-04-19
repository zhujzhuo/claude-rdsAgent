"""告警通知模块测试。"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import httpx

from rds_agent.scheduler.notification import (
    NotificationSender,
    DingTalkSender,
    EmailSender,
    WeChatSender,
    WebhookSender,
    NotificationManager,
    get_notification_manager,
)
from rds_agent.scheduler.state import AlertEvent, AlertLevel, NotificationChannel


class TestDingTalkSender:
    """钉钉通知发送器测试"""

    @pytest.fixture
    def sender(self):
        """创建发送器实例"""
        return DingTalkSender()

    @pytest.fixture
    def alert(self):
        """创建告警事件"""
        return AlertEvent(
            id="alert-001",
            rule_id="rule-001",
            instance_name="db-01",
            level=AlertLevel.CRITICAL,
            title="测试告警",
            message="健康分数过低",
            metric_name="overall_score",
            metric_value=50.0,
            threshold=80,
            triggered_at=datetime.now(),
        )

    def test_format_message(self, sender, alert):
        """测试格式化消息"""
        message = sender.format_message(alert)

        assert "RDS告警通知" in message
        assert alert.instance_name in message
        assert alert.level in message
        assert str(alert.metric_value) in message

    def test_send_success(self, sender, alert):
        """测试发送成功"""
        config = {
            "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=test"
        }

        with patch("httpx.Client") as mock_client:
            mock_response = Mock()
            mock_response.json.return_value = {"errcode": 0}
            mock_response.raise_for_status = Mock()

            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = sender.send(alert, config)

            assert result == True

    def test_send_failure(self, sender, alert):
        """测试发送失败"""
        config = {
            "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=test"
        }

        with patch("httpx.Client") as mock_client:
            mock_response = Mock()
            mock_response.json.return_value = {"errcode": 1, "errmsg": "失败"}

            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = sender.send(alert, config)

            assert result == False

    def test_send_no_webhook(self, sender, alert):
        """测试未配置webhook"""
        config = {}

        result = sender.send(alert, config)

        assert result == False

    def test_send_with_signature(self, sender, alert):
        """测试带签名发送"""
        config = {
            "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=test",
            "secret": "test_secret",
        }

        with patch("httpx.Client") as mock_client:
            mock_response = Mock()
            mock_response.json.return_value = {"errcode": 0}

            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = sender.send(alert, config)

            # 验证URL包含签名参数
            call_args = mock_client.return_value.__enter__.return_value.post.call_args
            assert "timestamp=" in str(call_args)


class TestEmailSender:
    """邮件通知发送器测试"""

    @pytest.fixture
    def sender(self):
        """创建发送器实例"""
        return EmailSender()

    @pytest.fixture
    def alert(self):
        """创建告警事件"""
        return AlertEvent(
            id="alert-001",
            rule_id="rule-001",
            instance_name="db-01",
            level=AlertLevel.WARNING,
            title="测试告警",
            message="连接数过高",
            metric_name="connection_usage",
            metric_value=85.0,
            threshold=80,
            triggered_at=datetime.now(),
        )

    def test_format_message(self, sender, alert):
        """测试格式化消息"""
        message = sender.format_message(alert)

        assert "RDS告警通知" in message
        assert alert.instance_name in message
        assert alert.metric_name in message

    def test_send_success(self, sender, alert):
        """测试发送成功"""
        config = {
            "smtp_host": "smtp.example.com",
            "smtp_port": 25,
            "from_addr": "alert@example.com",
            "to_addr": "dba@example.com",
        }

        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = Mock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            result = sender.send(alert, config)

            assert result == True
            mock_server.sendmail.assert_called_once()

    def test_send_with_auth(self, sender, alert):
        """测试带认证发送"""
        config = {
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_user": "user@example.com",
            "smtp_password": "password",
            "from_addr": "alert@example.com",
            "to_addr": "dba@example.com",
        }

        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = Mock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            result = sender.send(alert, config)

            assert result == True
            mock_server.login.assert_called_once()

    def test_send_config_missing(self, sender, alert):
        """测试配置缺失"""
        config = {"smtp_host": "smtp.example.com"}  # 缺少其他必要配置

        result = sender.send(alert, config)

        assert result == False


class TestWeChatSender:
    """企业微信通知发送器测试"""

    @pytest.fixture
    def sender(self):
        """创建发送器实例"""
        return WeChatSender()

    @pytest.fixture
    def alert(self):
        """创建告警事件"""
        return AlertEvent(
            id="alert-001",
            rule_id="rule-001",
            instance_name="db-01",
            level=AlertLevel.CRITICAL,
            title="测试告警",
            message="严重问题",
            metric_name="critical_count",
            metric_value=5.0,
            threshold=0,
            triggered_at=datetime.now(),
        )

    def test_format_message(self, sender, alert):
        """测试格式化消息"""
        message = sender.format_message(alert)

        assert "RDS告警通知" in message
        assert alert.instance_name in message

    def test_send_success(self, sender, alert):
        """测试发送成功"""
        config = {"webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test"}

        with patch("httpx.Client") as mock_client:
            mock_response = Mock()
            mock_response.json.return_value = {"errcode": 0}

            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = sender.send(alert, config)

            assert result == True

    def test_send_no_webhook(self, sender, alert):
        """测试未配置webhook"""
        config = {}

        result = sender.send(alert, config)

        assert result == False


class TestWebhookSender:
    """通用Webhook发送器测试"""

    @pytest.fixture
    def sender(self):
        """创建发送器实例"""
        return WebhookSender()

    @pytest.fixture
    def alert(self):
        """创建告警事件"""
        return AlertEvent(
            id="alert-001",
            rule_id="rule-001",
            instance_name="db-01",
            level=AlertLevel.INFO,
            title="测试告警",
            message="测试消息",
            metric_name="test_metric",
            metric_value=10.0,
            threshold=5,
            triggered_at=datetime.now(),
            suggestion="测试建议",
        )

    def test_format_message(self, sender, alert):
        """测试格式化消息"""
        message = sender.format_message(alert)

        import json
        data = json.loads(message)
        assert data["alert_id"] == alert.id
        assert data["instance"] == alert.instance_name

    def test_send_success(self, sender, alert):
        """测试发送成功"""
        config = {
            "url": "https://example.com/webhook",
            "headers": {"Authorization": "Bearer token"},
        }

        with patch("httpx.Client") as mock_client:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()

            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = sender.send(alert, config)

            assert result == True

            # 验证调用参数
            call_args = mock_client.return_value.__enter__.return_value.post.call_args
            assert call_args[0][0] == config["url"]
            assert "Authorization" in call_args[1]["headers"]

    def test_send_no_url(self, sender, alert):
        """测试未配置URL"""
        config = {}

        result = sender.send(alert, config)

        assert result == False


class TestNotificationManager:
    """通知管理器测试"""

    @pytest.fixture
    def manager(self):
        """创建管理器实例"""
        manager = NotificationManager()
        return manager

    @pytest.fixture
    def alert(self):
        """创建告警事件"""
        return AlertEvent(
            id="alert-001",
            rule_id="rule-001",
            instance_name="db-01",
            level=AlertLevel.WARNING,
            title="测试告警",
            message="测试消息",
            metric_name="overall_score",
            metric_value=75.0,
            threshold=80,
            triggered_at=datetime.now(),
        )

    def test_manager_initialization(self, manager):
        """测试管理器初始化"""
        assert len(manager.channels) == 0
        assert len(manager.senders) == 4  # dingtalk, email, wechat, webhook

    def test_add_channel(self, manager):
        """测试添加渠道"""
        channel = NotificationChannel(
            name="钉钉告警",
            type="dingtalk",
            config={"webhook_url": "https://test.com"},
        )

        channel_id = manager.add_channel(channel)

        assert channel_id is not None
        assert len(manager.channels) == 1
        assert manager.get_channel(channel_id) == channel

    def test_remove_channel(self, manager):
        """测试删除渠道"""
        channel = NotificationChannel(
            name="钉钉告警",
            type="dingtalk",
            config={"webhook_url": "https://test.com"},
        )

        channel_id = manager.add_channel(channel)
        result = manager.remove_channel(channel_id)

        assert result == True
        assert len(manager.channels) == 0

    def test_list_channels(self, manager):
        """测试列出渠道"""
        channel1 = NotificationChannel(name="渠道1", type="dingtalk", config={})
        channel2 = NotificationChannel(name="渠道2", type="email", config={})

        manager.add_channel(channel1)
        manager.add_channel(channel2)

        channels = manager.list_channels()

        assert len(channels) == 2
        assert any(c.name == "渠道1" for c in channels)
        assert any(c.name == "渠道2" for c in channels)

    def test_send_alert(self, manager, alert):
        """测试发送告警"""
        # 添加渠道
        channel = NotificationChannel(
            name="测试渠道",
            type="dingtalk",
            config={"webhook_url": "https://test.com"},
            enabled=True,
        )
        manager.add_channel(channel)

        with patch.object(manager.senders["dingtalk"], "send", return_value=True):
            results = manager.send_alert(alert, ["测试渠道"])

            assert results["测试渠道"] == True
            assert alert.notification_sent == True
            assert "测试渠道" in alert.notification_channels

    def test_send_alert_disabled_channel(self, manager, alert):
        """测试发送到已禁用渠道"""
        channel = NotificationChannel(
            name="测试渠道",
            type="dingtalk",
            config={"webhook_url": "https://test.com"},
            enabled=False,
        )
        manager.add_channel(channel)

        results = manager.send_alert(alert, ["测试渠道"])

        assert results["测试渠道"] == False

    def test_send_alert_unknown_channel(self, manager, alert):
        """测试发送到未知渠道"""
        results = manager.send_alert(alert, ["未知渠道"])

        assert results["未知渠道"] == False

    def test_send_batch_alerts(self, manager):
        """测试批量发送告警"""
        # 添加渠道
        channel = NotificationChannel(
            name="测试渠道",
            type="webhook",
            config={"url": "https://test.com"},
            enabled=True,
        )
        manager.add_channel(channel)

        alerts = [
            AlertEvent(
                id="alert-1",
                rule_id="rule-1",
                instance_name="db-01",
                level=AlertLevel.WARNING,
                title="告警1",
                message="消息1",
                metric_name="score",
                metric_value=70,
                threshold=80,
                triggered_at=datetime.now(),
            ),
            AlertEvent(
                id="alert-2",
                rule_id="rule-1",
                instance_name="db-02",
                level=AlertLevel.CRITICAL,
                title="告警2",
                message="消息2",
                metric_name="score",
                metric_value=50,
                threshold=80,
                triggered_at=datetime.now(),
            ),
        ]

        with patch.object(manager.senders["webhook"], "send", return_value=True):
            results = manager.send_batch_alerts(alerts, ["测试渠道"])

            assert len(results) == 2
            assert all(v["测试渠道"] == True for v in results.values())


class TestGetNotificationManager:
    """获取通知管理器实例测试"""

    def test_get_manager_singleton(self):
        """测试单例模式"""
        import rds_agent.scheduler.notification as module
        module._notification_manager = None

        manager1 = get_notification_manager()
        manager2 = get_notification_manager()

        assert manager1 == manager2

        # 清理
        module._notification_manager = None