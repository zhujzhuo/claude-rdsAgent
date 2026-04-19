"""告警规则引擎测试。"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from rds_agent.scheduler.alert_engine import AlertEngine, get_alert_engine, DEFAULT_ALERT_RULES
from rds_agent.scheduler.state import (
    AlertRule,
    AlertEvent,
    AlertLevel,
    InspectionTask,
    TaskExecution,
)


class TestAlertEngine:
    """告警引擎测试"""

    @pytest.fixture
    def engine(self):
        """创建告警引擎实例"""
        engine = AlertEngine()
        return engine

    def test_engine_initialization(self, engine):
        """测试引擎初始化"""
        assert len(engine.rules) == 0
        assert len(engine.events) == 0
        assert engine.notification_callback is None

    def test_add_rule(self, engine):
        """测试添加规则"""
        rule = AlertRule(
            name="测试规则",
            metric_name="overall_score",
            operator="<",
            threshold=60,
            level=AlertLevel.WARNING,
        )

        rule_id = engine.add_rule(rule)

        assert rule_id is not None
        assert rule.id == rule_id
        assert len(engine.rules) == 1
        assert engine.get_rule(rule_id) == rule

    def test_remove_rule(self, engine):
        """测试删除规则"""
        rule = AlertRule(
            name="测试规则",
            metric_name="overall_score",
            operator="<",
            threshold=60,
        )

        rule_id = engine.add_rule(rule)
        result = engine.remove_rule(rule_id)

        assert result == True
        assert len(engine.rules) == 0
        assert engine.get_rule(rule_id) is None

    def test_enable_disable_rule(self, engine):
        """测试启用/禁用规则"""
        rule = AlertRule(
            name="测试规则",
            metric_name="overall_score",
            operator="<",
            threshold=60,
        )

        rule_id = engine.add_rule(rule)

        # 禁用
        engine.disable_rule(rule_id)
        assert engine.get_rule(rule_id).enabled == False

        # 启用
        engine.enable_rule(rule_id)
        assert engine.get_rule(rule_id).enabled == True

    def test_list_rules(self, engine):
        """测试列出规则"""
        rule1 = AlertRule(name="规则1", metric_name="score", operator="<", threshold=60)
        rule2 = AlertRule(name="规则2", metric_name="count", operator=">", threshold=5)

        engine.add_rule(rule1)
        engine.add_rule(rule2)

        rules = engine.list_rules()

        assert len(rules) == 2
        assert any(r.name == "规则1" for r in rules)
        assert any(r.name == "规则2" for r in rules)

    def test_check_threshold(self, engine):
        """测试阈值检查"""
        # 大于
        assert engine._check_threshold(10, ">", 5) == True
        assert engine._check_threshold(5, ">", 5) == False

        # 小于
        assert engine._check_threshold(5, "<", 10) == True
        assert engine._check_threshold(10, "<", 5) == False

        # 大于等于
        assert engine._check_threshold(5, ">=", 5) == True
        assert engine._check_threshold(4, ">=", 5) == False

        # 小于等于
        assert engine._check_threshold(5, "<=", 5) == True
        assert engine._check_threshold(6, "<=", 5) == False

        # 等于
        assert engine._check_threshold(5, "==", 5) == True
        assert engine._check_threshold(6, "==", 5) == False

        # 不等于
        assert engine._check_threshold(6, "!=", 5) == True
        assert engine._check_threshold(5, "!=", 5) == False

    def test_get_metric_value(self, engine):
        """测试获取指标值"""
        execution = TaskExecution(
            task_id="task-001",
            instance_name="db-01",
            result_data={
                "overall_score": 85,
                "critical_count": 2,
                "warning_count": 5,
                "category_scores": {
                    "performance": 90,
                    "storage": 80,
                },
            },
        )

        # 测试常用指标
        assert engine._get_metric_value(execution, "overall_score") == 85.0
        assert engine._get_metric_value(execution, "critical_count") == 2.0
        assert engine._get_metric_value(execution, "warning_count") == 5.0

        # 测试分类指标
        assert engine._get_metric_value(execution, "performance") == 90.0
        assert engine._get_metric_value(execution, "category_performance") == 90.0

        # 测试不存在指标
        assert engine._get_metric_value(execution, "nonexistent") is None

    def test_check_alerts_trigger(self, engine):
        """测试触发告警"""
        # 添加规则
        rule = AlertRule(
            name="分数过低",
            metric_name="overall_score",
            operator="<",
            threshold=60,
            level=AlertLevel.CRITICAL,
        )
        engine.add_rule(rule)

        # 创建执行结果
        execution = TaskExecution(
            task_id="task-001",
            instance_name="db-01",
            overall_score=50,
            result_data={"overall_score": 50},
        )

        task = InspectionTask(
            name="测试任务",
            target_instances=["db-01"],
            alert_enabled=True,
            alert_levels=[AlertLevel.CRITICAL],
        )

        # 检查告警
        alerts = engine.check_alerts(execution, task)

        assert len(alerts) == 1
        assert alerts[0].level == AlertLevel.CRITICAL
        assert alerts[0].metric_value == 50.0
        assert alerts[0].instance_name == "db-01"

    def test_check_alerts_no_trigger(self, engine):
        """测试不触发告警"""
        rule = AlertRule(
            name="分数过低",
            metric_name="overall_score",
            operator="<",
            threshold=60,
        )
        engine.add_rule(rule)

        execution = TaskExecution(
            task_id="task-001",
            instance_name="db-01",
            overall_score=85,
            result_data={"overall_score": 85},
        )

        task = InspectionTask(
            name="测试任务",
            target_instances=["db-01"],
            alert_enabled=True,
        )

        alerts = engine.check_alerts(execution, task)

        assert len(alerts) == 0

    def test_suppression(self, engine):
        """测试告警抑制"""
        rule = AlertRule(
            name="分数过低",
            metric_name="overall_score",
            operator="<",
            threshold=60,
            suppress_duration=300,
        )
        engine.add_rule(rule)

        execution = TaskExecution(
            task_id="task-001",
            instance_name="db-01",
            overall_score=50,
            result_data={"overall_score": 50},
        )

        task = InspectionTask(name="测试任务", target_instances=["db-01"], alert_enabled=True)

        # 第一次触发
        alerts1 = engine.check_alerts(execution, task)
        assert len(alerts1) == 1

        # 立即再次检查，应该被抑制
        alerts2 = engine.check_alerts(execution, task)
        assert len(alerts2) == 0

    def test_hourly_limit(self, engine):
        """测试每小时限制"""
        rule = AlertRule(
            name="分数过低",
            metric_name="overall_score",
            operator="<",
            threshold=60,
            max_alerts_per_hour=2,
        )
        engine.add_rule(rule)

        execution = TaskExecution(
            task_id="task-001",
            instance_name="db-01",
            overall_score=50,
            result_data={"overall_score": 50},
        )

        task = InspectionTask(name="测试任务", target_instances=["db-01"], alert_enabled=True)

        # 触发两次
        engine.check_alerts(execution, task)
        engine.clear_instance_alert_state("db-01")  # 清除抑制状态
        engine.check_alerts(execution, task)
        engine.clear_instance_alert_state("db-01")

        # 第三次应该被限制
        alerts3 = engine.check_alerts(execution, task)
        assert len(alerts3) == 0

    def test_acknowledge_alert(self, engine):
        """测试确认告警"""
        alert = AlertEvent(
            rule_id="rule-001",
            instance_name="db-01",
            level=AlertLevel.WARNING,
            title="测试告警",
            message="测试",
            metric_name="score",
            metric_value=50,
            threshold=60,
        )
        engine.events[alert.id] = alert

        result = engine.acknowledge_alert(alert.id)

        assert result == True
        assert alert.status == "acknowledged"
        assert alert.acknowledged_at is not None

    def test_resolve_alert(self, engine):
        """测试恢复告警"""
        alert = AlertEvent(
            rule_id="rule-001",
            instance_name="db-01",
            level=AlertLevel.WARNING,
            title="测试告警",
            message="测试",
            metric_name="score",
            metric_value=50,
            threshold=60,
        )
        engine.events[alert.id] = alert

        result = engine.resolve_alert(alert.id)

        assert result == True
        assert alert.status == "resolved"
        assert alert.resolved_at is not None

    def test_get_active_alerts(self, engine):
        """测试获取活跃告警"""
        alert1 = AlertEvent(
            id="alert-001",
            rule_id="rule-001",
            instance_name="db-01",
            level=AlertLevel.WARNING,
            title="告警1",
            message="测试",
            metric_name="score",
            metric_value=50,
            threshold=60,
        )
        alert2 = AlertEvent(
            id="alert-002",
            rule_id="rule-001",
            instance_name="db-02",
            level=AlertLevel.CRITICAL,
            title="告警2",
            message="测试",
            metric_name="score",
            metric_value=30,
            threshold=60,
        )
        # 已恢复的告警
        alert3 = AlertEvent(
            id="alert-003",
            rule_id="rule-001",
            instance_name="db-03",
            level=AlertLevel.WARNING,
            title="告警3",
            message="测试",
            metric_name="score",
            metric_value=50,
            threshold=60,
        )
        alert3.status = "resolved"

        engine.events[alert1.id] = alert1
        engine.events[alert2.id] = alert2
        engine.events[alert3.id] = alert3

        # 获取所有活跃告警
        active = engine.get_active_alerts()
        assert len(active) == 2

        # 获取指定实例活跃告警
        active_db01 = engine.get_active_alerts("db-01")
        assert len(active_db01) == 1

    def test_notification_callback(self, engine):
        """测试通知回调"""
        callback = Mock()
        engine.set_notification_callback(callback)

        rule = AlertRule(
            name="分数过低",
            metric_name="overall_score",
            operator="<",
            threshold=60,
            notification_channels=["dingtalk"],
        )
        engine.add_rule(rule)

        execution = TaskExecution(
            task_id="task-001",
            instance_name="db-01",
            overall_score=50,
            result_data={"overall_score": 50},
        )

        task = InspectionTask(name="测试任务", target_instances=["db-01"], alert_enabled=True)

        engine.check_alerts(execution, task)

        # 验证回调被调用
        assert callback.called == True

    def test_generate_suggestion(self, engine):
        """测试生成建议"""
        rule = AlertRule(
            name="分数过低",
            metric_name="overall_score",
            operator="<",
            threshold=60,
        )

        suggestion = engine._generate_suggestion(rule, 50, "db-01")

        assert suggestion is not None
        assert "db-01" in suggestion or "检查" in suggestion

    def test_default_rules(self):
        """测试默认规则"""
        engine = get_alert_engine()

        # 默认规则应该已添加
        assert len(engine.rules) > 0
        assert any(r.metric_name == "overall_score" for r in engine.list_rules())


class TestDefaultAlertRules:
    """默认告警规则测试"""

    def test_default_rules_content(self):
        """测试默认规则内容"""
        assert len(DEFAULT_ALERT_RULES) == 4

        # 检查健康分数规则
        score_rules = [r for r in DEFAULT_ALERT_RULES if r.metric_name == "overall_score"]
        assert len(score_rules) == 2  # 低于60和低于80

        # 检查严重问题规则
        critical_rules = [r for r in DEFAULT_ALERT_RULES if r.metric_name == "critical_count"]
        assert len(critical_rules) == 1