"""调度器状态模型测试。"""

import pytest
from datetime import datetime

from rds_agent.scheduler.state import (
    InspectionTask,
    TaskExecution,
    AlertRule,
    AlertEvent,
    HealthHistory,
    NotificationChannel,
    TaskStatus,
    ScheduleType,
    TaskType,
    AlertLevel,
)


class TestInspectionTask:
    """巡检任务模型测试"""

    def test_create_task_with_defaults(self):
        """测试创建任务（默认值）"""
        task = InspectionTask(
            name="测试任务",
            target_instances=["db-prod-01"],
        )

        assert task.name == "测试任务"
        assert task.target_instances == ["db-prod-01"]
        assert task.task_type == TaskType.FULL_INSPECTION
        assert task.schedule_type == ScheduleType.INTERVAL
        assert task.status == TaskStatus.DISABLED
        assert task.alert_enabled == True
        assert task.run_count == 0

    def test_create_cron_task(self):
        """测试创建Cron任务"""
        task = InspectionTask(
            name="每日巡检",
            target_instances=["db-prod-01"],
            schedule_type=ScheduleType.CRON,
            cron_expression="0 9 * * *",
        )

        assert task.schedule_type == ScheduleType.CRON
        assert task.cron_expression == "0 9 * * *"

    def test_create_interval_task(self):
        """测试创建间隔任务"""
        task = InspectionTask(
            name="每小时巡检",
            target_instances=["db-prod-01"],
            schedule_type=ScheduleType.INTERVAL,
            interval_seconds=3600,
        )

        assert task.schedule_type == ScheduleType.INTERVAL
        assert task.interval_seconds == 3600

    def test_task_status_values(self):
        """测试任务状态枚举值"""
        assert TaskStatus.DISABLED == "disabled"
        assert TaskStatus.ENABLED == "enabled"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.PAUSED == "paused"

    def test_schedule_type_values(self):
        """测试调度类型枚举值"""
        assert ScheduleType.CRON == "cron"
        assert ScheduleType.INTERVAL == "interval"
        assert ScheduleType.ONCE == "once"

    def test_task_type_values(self):
        """测试任务类型枚举值"""
        assert TaskType.FULL_INSPECTION == "full_inspection"
        assert TaskType.QUICK_CHECK == "quick_check"
        assert TaskType.PERFORMANCE_DIAG == "performance_diag"


class TestTaskExecution:
    """任务执行记录测试"""

    def test_create_execution(self):
        """测试创建执行记录"""
        execution = TaskExecution(
            task_id="task-001",
            instance_name="db-prod-01",
        )

        assert execution.task_id == "task-001"
        assert execution.instance_name == "db-prod-01"
        assert execution.status == "running"
        assert execution.critical_count == 0
        assert execution.warning_count == 0

    def test_execution_with_result(self):
        """测试执行记录包含结果"""
        execution = TaskExecution(
            task_id="task-001",
            instance_name="db-prod-01",
            overall_score=85,
            overall_status="healthy",
            critical_count=0,
            warning_count=3,
        )

        assert execution.overall_score == 85
        assert execution.overall_status == "healthy"
        assert execution.warning_count == 3


class TestAlertRule:
    """告警规则测试"""

    def test_create_rule(self):
        """测试创建告警规则"""
        rule = AlertRule(
            name="健康分数过低",
            metric_name="overall_score",
            operator="<",
            threshold=60,
            level=AlertLevel.CRITICAL,
        )

        assert rule.name == "健康分数过低"
        assert rule.metric_name == "overall_score"
        assert rule.operator == "<"
        assert rule.threshold == 60
        assert rule.level == AlertLevel.CRITICAL
        assert rule.enabled == True

    def test_rule_suppression_settings(self):
        """测试规则抑制设置"""
        rule = AlertRule(
            name="测试规则",
            metric_name="test_metric",
            operator=">",
            threshold=10,
            suppress_duration=600,
            max_alerts_per_hour=5,
        )

        assert rule.suppress_duration == 600
        assert rule.max_alerts_per_hour == 5

    def test_alert_level_values(self):
        """测试告警级别枚举值"""
        assert AlertLevel.INFO == "info"
        assert AlertLevel.WARNING == "warning"
        assert AlertLevel.CRITICAL == "critical"
        assert AlertLevel.EMERGENCY == "emergency"


class TestAlertEvent:
    """告警事件测试"""

    def test_create_alert_event(self):
        """测试创建告警事件"""
        alert = AlertEvent(
            rule_id="rule-001",
            instance_name="db-prod-01",
            level=AlertLevel.WARNING,
            title="测试告警",
            message="健康分数偏低",
            metric_name="overall_score",
            metric_value=75.0,
            threshold=80,
        )

        assert alert.rule_id == "rule-001"
        assert alert.instance_name == "db-prod-01"
        assert alert.level == AlertLevel.WARNING
        assert alert.status == "firing"
        assert alert.notification_sent == False


class TestHealthHistory:
    """健康历史测试"""

    def test_create_health_history(self):
        """测试创建健康历史记录"""
        history = HealthHistory(
            instance_name="db-prod-01",
            overall_score=85,
            overall_status="healthy",
            critical_count=0,
            warning_count=3,
        )

        assert history.instance_name == "db-prod-01"
        assert history.overall_score == 85
        assert history.overall_status == "healthy"
        # trend defaults to None, not "stable"
        assert history.trend is None

    def test_health_trend_calculation(self):
        """测试健康趋势计算"""
        # 改善趋势
        improving = HealthHistory(
            instance_name="db-prod-01",
            overall_score=90,
            overall_status="healthy",
            score_change=10,
            trend="improving",
        )
        assert improving.trend == "improving"

        # 恶化趋势
        degrading = HealthHistory(
            instance_name="db-prod-01",
            overall_score=70,
            overall_status="warning",
            score_change=-15,
            trend="degrading",
        )
        assert degrading.trend == "degrading"


class TestNotificationChannel:
    """通知渠道测试"""

    def test_create_dingtalk_channel(self):
        """测试创建钉钉渠道"""
        channel = NotificationChannel(
            name="钉钉告警",
            type="dingtalk",
            config={"webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=xxx"},
        )

        assert channel.name == "钉钉告警"
        assert channel.type == "dingtalk"
        assert channel.enabled == True

    def test_create_email_channel(self):
        """测试创建邮件渠道"""
        channel = NotificationChannel(
            name="邮件告警",
            type="email",
            config={
                "smtp_host": "smtp.example.com",
                "smtp_port": 25,
                "from_addr": "alert@example.com",
                "to_addr": "dba@example.com",
            },
        )

        assert channel.name == "邮件告警"
        assert channel.type == "email"
        assert channel.config["smtp_host"] == "smtp.example.com"