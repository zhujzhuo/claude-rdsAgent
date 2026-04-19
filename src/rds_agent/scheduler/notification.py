"""告警通知模块 - 支持多种通知渠道发送告警。"""

import json
import httpx
from datetime import datetime
from typing import Optional, Callable
from abc import ABC, abstractmethod

from rds_agent.scheduler.state import AlertEvent, AlertLevel, NotificationChannel
from rds_agent.utils.logger import get_logger

logger = get_logger("notification")


class NotificationSender(ABC):
    """通知发送器基类"""

    @abstractmethod
    def send(self, alert: AlertEvent, channel_config: dict) -> bool:
        """发送通知"""
        pass

    @abstractmethod
    def format_message(self, alert: AlertEvent) -> str:
        """格式化消息"""
        pass


class DingTalkSender(NotificationSender):
    """钉钉通知发送器"""

    def send(self, alert: AlertEvent, channel_config: dict) -> bool:
        """发送钉钉通知"""
        webhook_url = channel_config.get("webhook_url")
        secret = channel_config.get("secret")

        if not webhook_url:
            logger.warning("钉钉webhook未配置")
            return False

        # 构建消息
        message = self.format_message(alert)

        # 发送请求
        try:
            # 如果有签名，计算签名
            if secret:
                import hmac
                import hashlib
                import base64
                import time

                timestamp = str(round(time.time() * 1000))
                string_to_sign = f"{timestamp}\n{secret}"
                hmac_code = hmac.new(
                    secret.encode("utf-8"),
                    string_to_sign.encode("utf-8"),
                    digestmod=hashlib.sha256
                ).digest()
                sign = base64.b64encode(hmac_code).decode("utf-8")
                webhook_url = f"{webhook_url}&timestamp={timestamp}&sign={sign}"

            data = {
                "msgtype": "markdown",
                "markdown": {
                    "title": alert.title,
                    "text": message,
                }
            }

            with httpx.Client() as client:
                response = client.post(webhook_url, json=data, timeout=10)
                response.raise_for_status()

                result = response.json()
                if result.get("errcode") == 0:
                    logger.info(f"钉钉通知发送成功: {alert.id}")
                    return True
                else:
                    logger.warning(f"钉钉通知发送失败: {result}")
                    return False

        except Exception as e:
            logger.error(f"钉钉通知发送异常: {e}")
            return False

    def format_message(self, alert: AlertEvent) -> str:
        """格式化钉钉消息"""
        level_colors = {
            AlertLevel.INFO: "🟢",
            AlertLevel.WARNING: "🟡",
            AlertLevel.CRITICAL: "🔴",
            AlertLevel.EMERGENCY: "🔴🔴",
        }

        level_icon = level_colors.get(alert.level, "⚪")

        message = f"""
## {level_icon} RDS告警通知

**实例**: {alert.instance_name}
**级别**: {alert.level}
**指标**: {alert.metric_name}
**当前值**: {alert.metric_value:.2f}
**阈值**: {alert.threshold}
**触发时间**: {alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}

---

**告警内容**:
{alert.message}

**处理建议**:
{alert.suggestion or '请检查相关指标和配置'}

---
*来自 RDS Agent 智能运维助手*
"""
        return message


class EmailSender(NotificationSender):
    """邮件通知发送器"""

    def send(self, alert: AlertEvent, channel_config: dict) -> bool:
        """发送邮件通知"""
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        smtp_host = channel_config.get("smtp_host")
        smtp_port = channel_config.get("smtp_port", 25)
        smtp_user = channel_config.get("smtp_user")
        smtp_password = channel_config.get("smtp_password")
        from_addr = channel_config.get("from_addr")
        to_addr = channel_config.get("to_addr")

        if not all([smtp_host, from_addr, to_addr]):
            logger.warning("邮件配置不完整")
            return False

        try:
            # 创建邮件
            msg = MIMEMultipart("alternative")
            msg["Subject"] = alert.title
            msg["From"] = from_addr
            msg["To"] = to_addr

            # 文本内容
            text_content = self.format_message(alert)
            msg.attach(MIMEText(text_content, "plain", "utf-8"))

            # 发送
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if smtp_user and smtp_password:
                    server.login(smtp_user, smtp_password)
                server.sendmail(from_addr, to_addr, msg.as_string())

            logger.info(f"邮件通知发送成功: {alert.id}")
            return True

        except Exception as e:
            logger.error(f"邮件通知发送异常: {e}")
            return False

    def format_message(self, alert: AlertEvent) -> str:
        """格式化邮件消息"""
        message = f"""
RDS告警通知

实例: {alert.instance_name}
级别: {alert.level}
指标: {alert.metric_name}
当前值: {alert.metric_value:.2f}
阈值: {alert.threshold}
触发时间: {alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}

告警内容:
{alert.message}

处理建议:
{alert.suggestion or '请检查相关指标和配置'}

---
来自 RDS Agent 智能运维助手
"""
        return message


class WeChatSender(NotificationSender):
    """企业微信通知发送器"""

    def send(self, alert: AlertEvent, channel_config: dict) -> bool:
        """发送企业微信通知"""
        webhook_url = channel_config.get("webhook_url")

        if not webhook_url:
            logger.warning("企业微信webhook未配置")
            return False

        message = self.format_message(alert)

        try:
            data = {
                "msgtype": "markdown",
                "markdown": {
                    "content": message,
                }
            }

            with httpx.Client() as client:
                response = client.post(webhook_url, json=data, timeout=10)
                response.raise_for_status()

                result = response.json()
                if result.get("errcode") == 0:
                    logger.info(f"企业微信通知发送成功: {alert.id}")
                    return True
                else:
                    logger.warning(f"企业微信通知发送失败: {result}")
                    return False

        except Exception as e:
            logger.error(f"企业微信通知发送异常: {e}")
            return False

    def format_message(self, alert: AlertEvent) -> str:
        """格式化企业微信消息"""
        level_colors = {
            AlertLevel.INFO: "<font color=\"info\">INFO</font>",
            AlertLevel.WARNING: "<font color=\"warning\">WARNING</font>",
            AlertLevel.CRITICAL: "<font color=\"warning\">CRITICAL</font>",
            AlertLevel.EMERGENCY: "<font color=\"warning\">EMERGENCY</font>",
        }

        level_text = level_colors.get(alert.level, alert.level)

        message = f"""
**RDS告警通知**

> 实例: **{alert.instance_name}**
> 级别: {level_text}
> 指标: {alert.metric_name}
> 当前值: {alert.metric_value:.2f}
> 阈值: {alert.threshold}

**告警内容**:
{alert.message}

**处理建议**:
{alert.suggestion or '请检查相关指标和配置'}

触发时间: {alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}
"""
        return message


class WebhookSender(NotificationSender):
    """通用Webhook通知发送器"""

    def send(self, alert: AlertEvent, channel_config: dict) -> bool:
        """发送Webhook通知"""
        webhook_url = channel_config.get("url")
        headers = channel_config.get("headers", {})

        if not webhook_url:
            logger.warning("Webhook URL未配置")
            return False

        # 构建JSON数据
        data = {
            "alert_id": alert.id,
            "instance": alert.instance_name,
            "level": alert.level,
            "title": alert.title,
            "message": alert.message,
            "metric_name": alert.metric_name,
            "metric_value": alert.metric_value,
            "threshold": alert.threshold,
            "triggered_at": alert.triggered_at.isoformat(),
            "suggestion": alert.suggestion,
        }

        try:
            with httpx.Client() as client:
                response = client.post(
                    webhook_url,
                    json=data,
                    headers=headers,
                    timeout=10
                )
                response.raise_for_status()

                logger.info(f"Webhook通知发送成功: {alert.id}")
                return True

        except Exception as e:
            logger.error(f"Webhook通知发送异常: {e}")
            return False

    def format_message(self, alert: AlertEvent) -> str:
        """格式化消息"""
        return json.dumps({
            "alert_id": alert.id,
            "instance": alert.instance_name,
            "level": alert.level,
            "message": alert.message,
        }, ensure_ascii=False)


class NotificationManager:
    """通知管理器"""

    def __init__(self):
        """初始化通知管理器"""
        # 通知渠道配置
        self.channels: dict[str, NotificationChannel] = {}

        # 发送器映射
        self.senders: dict[str, NotificationSender] = {
            "dingtalk": DingTalkSender(),
            "email": EmailSender(),
            "wechat": WeChatSender(),
            "webhook": WebhookSender(),
        }

        logger.info("通知管理器初始化完成")

    def add_channel(self, channel: NotificationChannel) -> str:
        """添加通知渠道"""
        channel.id = channel.id or f"{channel.type}_{len(self.channels)}"
        channel.created_at = datetime.now()

        self.channels[channel.id] = channel
        logger.info(f"添加通知渠道: {channel.name} ({channel.type})")
        return channel.id

    def remove_channel(self, channel_id: str) -> bool:
        """移除通知渠道"""
        if channel_id in self.channels:
            del self.channels[channel_id]
            logger.info(f"移除通知渠道: {channel_id}")
            return True
        return False

    def get_channel(self, channel_id: str) -> Optional[NotificationChannel]:
        """获取通知渠道"""
        return self.channels.get(channel_id)

    def list_channels(self) -> list[NotificationChannel]:
        """列出所有通知渠道"""
        return list(self.channels.values())

    def send_alert(self, alert: AlertEvent, channel_names: list[str]) -> dict:
        """发送告警通知"""
        results = {}

        for channel_name in channel_names:
            # 查找渠道配置
            channel = None
            for c in self.channels.values():
                if c.name == channel_name or c.id == channel_name:
                    channel = c
                    break

            if not channel or not channel.enabled:
                logger.warning(f"通知渠道未找到或已禁用: {channel_name}")
                results[channel_name] = False
                continue

            # 获取发送器
            sender = self.senders.get(channel.type)

            if not sender:
                logger.warning(f"不支持的渠道类型: {channel.type}")
                results[channel_name] = False
                continue

            # 发送通知
            success = sender.send(alert, channel.config)
            results[channel_name] = success

            if success:
                channel.last_used_at = datetime.now()
                alert.notification_sent = True
                alert.notification_channels.append(channel_name)

        # 统计结果
        success_count = sum(1 for v in results.values() if v)
        logger.info(f"通知发送完成: {success_count}/{len(channel_names)} 成功")

        return results

    def send_batch_alerts(self, alerts: list[AlertEvent], channel_names: list[str]) -> dict:
        """批量发送告警"""
        results = {}

        for alert in alerts:
            results[alert.id] = self.send_alert(alert, channel_names)

        return results


# 全局通知管理器
_notification_manager: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    """获取通知管理器实例"""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager


def send_alert_notification(alert: AlertEvent, channels: list[str]) -> dict:
    """发送告警通知（便捷函数）"""
    manager = get_notification_manager()
    return manager.send_alert(alert, channels)