"""告警规则引擎 - 检测和触发告警。"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, Callable
from collections import defaultdict

from rds_agent.scheduler.state import (
    AlertRule,
    AlertEvent,
    AlertLevel,
    TaskExecution,
    InspectionTask,
)
from rds_agent.utils.logger import get_logger

logger = get_logger("alert_engine")


class AlertEngine:
    """告警规则引擎"""

    def __init__(self):
        """初始化告警引擎"""
        # 告警规则
        self.rules: dict[str, AlertRule] = {}

        # 告警事件
        self.events: dict[str, AlertEvent] = {}

        # 实例告警状态（用于抑制）
        self.instance_alerts: dict[str, dict] = defaultdict(dict)

        # 告警计数（每小时限制）
        self.hourly_counts: dict[str, int] = defaultdict(int)

        # 通知回调
        self.notification_callback: Optional[Callable] = None

        logger.info("告警引擎初始化完成")

    def add_rule(self, rule: AlertRule) -> str:
        """添加告警规则"""
        rule.id = rule.id or str(uuid.uuid4())
        rule.created_at = datetime.now()

        self.rules[rule.id] = rule
        logger.info(f"添加告警规则: {rule.name} ({rule.level})")
        return rule.id

    def remove_rule(self, rule_id: str) -> bool:
        """移除告警规则"""
        if rule_id in self.rules:
            del self.rules[rule_id]
            logger.info(f"移除告警规则: {rule_id}")
            return True
        return False

    def enable_rule(self, rule_id: str) -> bool:
        """启用规则"""
        rule = self.rules.get(rule_id)
        if rule:
            rule.enabled = True
            return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        """禁用规则"""
        rule = self.rules.get(rule_id)
        if rule:
            rule.enabled = False
            return True
        return False

    def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """获取规则"""
        return self.rules.get(rule_id)

    def list_rules(self) -> list[AlertRule]:
        """列出规则"""
        return list(self.rules.values())

    def check_alerts(self, execution: TaskExecution, task: InspectionTask) -> list[AlertEvent]:
        """检查执行结果，触发告警"""
        triggered_alerts = []

        if not execution.result_data:
            return triggered_alerts

        instance = execution.instance_name

        # 检查每个告警规则
        for rule in self.rules.values():
            if not rule.enabled:
                continue

            # 检查任务配置的告警级别是否包含此规则的级别
            if task.alert_levels and rule.level not in task.alert_levels:
                continue

            # 检查指标
            metric_value = self._get_metric_value(execution, rule.metric_name)

            if metric_value is None:
                continue

            # 判断是否触发
            if self._check_threshold(metric_value, rule.operator, rule.threshold):
                # 检查抑制条件
                if self._should_suppress(instance, rule):
                    continue

                # 检查每小时限制
                if self._check_hourly_limit(rule):
                    continue

                # 创建告警事件
                alert = self._create_alert_event(rule, instance, metric_value, execution.id)

                # 添加建议
                suggestion = self._generate_suggestion(rule, metric_value, instance)
                alert.suggestion = suggestion

                # 存储事件
                self.events[alert.id] = alert

                # 记录实例告警状态（用于抑制）
                self.instance_alerts[instance][rule.metric_name] = {
                    "alert_id": alert.id,
                    "triggered_at": alert.triggered_at,
                    "suppress_duration": rule.suppress_duration,
                }

                # 更新计数
                self.hourly_counts[rule.id] += 1

                # 发送通知
                if self.notification_callback:
                    self.notification_callback(alert, rule.notification_channels)

                triggered_alerts.append(alert)

                # 记录到执行结果
                execution.alerts_triggered.append({
                    "alert_id": alert.id,
                    "rule_name": rule.name,
                    "level": rule.level,
                    "message": alert.message,
                })

        logger.info(f"检查告警: {instance}, 触发 {len(triggered_alerts)} 个告警")
        return triggered_alerts

    def _get_metric_value(self, execution: TaskExecution, metric_name: str) -> Optional[float]:
        """获取指标值"""
        result_data = execution.result_data

        if not result_data:
            return None

        # 常用指标映射
        metric_mapping = {
            "overall_score": result_data.get("overall_score"),
            "critical_count": result_data.get("critical_count") or len(result_data.get("critical_issues", [])),
            "warning_count": result_data.get("warning_count") or len(result_data.get("warnings", [])),
        }

        # 直接映射
        if metric_name in metric_mapping:
            return float(metric_mapping[metric_name])

        # 检查分类分数
        category_scores = result_data.get("category_scores", {})
        if metric_name in category_scores:
            return float(category_scores[metric_name])

        # 检查分类分数（带前缀）
        if metric_name.startswith("category_"):
            category = metric_name.replace("category_", "")
            if category in category_scores:
                return float(category_scores[category])

        return None

    def _check_threshold(self, value: float, operator: str, threshold: float) -> bool:
        """检查阈值"""
        operators = {
            ">": lambda v, t: v > t,
            "<": lambda v, t: v < t,
            ">=": lambda v, t: v >= t,
            "<=": lambda v, t: v <= t,
            "==": lambda v, t: v == t,
            "!=": lambda v, t: v != t,
        }

        check_func = operators.get(operator)
        if check_func:
            return check_func(value, threshold)

        return False

    def _should_suppress(self, instance: str, rule: AlertRule) -> bool:
        """检查是否抑制"""
        instance_state = self.instance_alerts.get(instance, {})
        metric_state = instance_state.get(rule.metric_name)

        if not metric_state:
            return False

        # 检查抑制时间是否已过
        triggered_at = metric_state.get("triggered_at")
        suppress_duration = metric_state.get("suppress_duration", rule.suppress_duration)

        if triggered_at:
            elapsed = (datetime.now() - triggered_at).total_seconds()
            if elapsed < suppress_duration:
                logger.debug(f"告警抑制: {instance} - {rule.metric_name}")
                return True

        return False

    def _check_hourly_limit(self, rule: AlertRule) -> bool:
        """检查每小时限制"""
        # 每小时重置计数（简化实现）
        count = self.hourly_counts.get(rule.id, 0)
        if count >= rule.max_alerts_per_hour:
            logger.warning(f"告警达到每小时限制: {rule.name}")
            return True

        return False

    def _create_alert_event(
        self,
        rule: AlertRule,
        instance: str,
        metric_value: float,
        execution_id: str
    ) -> AlertEvent:
        """创建告警事件"""
        alert_id = str(uuid.uuid4())

        # 构建告警内容
        title = f"[{rule.level}] {instance} - {rule.metric_name} 告警"
        message = f"指标 {rule.metric_name} 当前值 {metric_value:.2f}，阈值 {rule.threshold} ({rule.operator})，规则: {rule.name}"

        alert = AlertEvent(
            id=alert_id,
            rule_id=rule.id,
            instance_name=instance,
            level=rule.level,
            title=title,
            message=message,
            metric_name=rule.metric_name,
            metric_value=metric_value,
            threshold=rule.threshold,
            execution_id=execution_id,
            notification_channels=rule.notification_channels,
        )

        return alert

    def _generate_suggestion(self, rule: AlertRule, metric_value: float, instance: str) -> str:
        """生成处理建议"""
        suggestions = {
            "overall_score": f"建议检查实例 {instance} 的各项指标，找出低分项并优化",
            "critical_count": f"发现严重问题，建议立即处理",
            "warning_count": f"存在多个警告，建议逐一排查",
            "buffer_pool_hit_rate": f"Buffer Pool命中率低，建议增大 innodb_buffer_pool_size",
            "connection_usage": f"连接数过高，建议增大 max_connections 或优化应用连接池",
            "slow_query_count": f"慢查询较多，建议分析和优化慢SQL",
            "storage_usage": f"存储使用率高，建议清理数据或扩容",
            "fragmentation": f"表碎片较多，建议执行 OPTIMIZE TABLE",
        }

        metric_name = rule.metric_name
        suggestion = suggestions.get(metric_name)

        if not suggestion:
            suggestion = f"建议检查 {metric_name} 相关配置和指标"

        return suggestion

    def acknowledge_alert(self, alert_id: str) -> bool:
        """确认告警"""
        alert = self.events.get(alert_id)
        if alert:
            alert.status = "acknowledged"
            alert.acknowledged_at = datetime.now()
            logger.info(f"告警已确认: {alert_id}")
            return True
        return False

    def resolve_alert(self, alert_id: str) -> bool:
        """恢复告警"""
        alert = self.events.get(alert_id)
        if alert:
            alert.status = "resolved"
            alert.resolved_at = datetime.now()
            logger.info(f"告警已恢复: {alert_id}")
            return True
        return False

    def get_active_alerts(self, instance: Optional[str] = None) -> list[AlertEvent]:
        """获取活跃告警"""
        alerts = [a for a in self.events.values() if a.status == "firing"]
        if instance:
            alerts = [a for a in alerts if a.instance_name == instance]
        return sorted(alerts, key=lambda a: a.triggered_at, reverse=True)

    def get_alert_history(
        self,
        instance: Optional[str] = None,
        level: Optional[AlertLevel] = None,
        limit: int = 50
    ) -> list[AlertEvent]:
        """获取告警历史"""
        alerts = list(self.events.values())

        if instance:
            alerts = [a for a in alerts if a.instance_name == instance]

        if level:
            alerts = [a for a in alerts if a.level == level]

        return sorted(alerts, key=lambda a: a.triggered_at, reverse=True)[:limit]

    def set_notification_callback(self, callback: Callable) -> None:
        """设置通知回调"""
        self.notification_callback = callback

    def reset_hourly_counts(self) -> None:
        """重置每小时计数"""
        self.hourly_counts.clear()
        logger.info("告警计数已重置")

    def clear_instance_alert_state(self, instance: str) -> None:
        """清除实例告警状态"""
        if instance in self.instance_alerts:
            del self.instance_alerts[instance]


# 预定义告警规则
DEFAULT_ALERT_RULES = [
    AlertRule(
        name="健康分数过低",
        metric_name="overall_score",
        operator="<",
        threshold=60,
        level=AlertLevel.CRITICAL,
        notification_channels=["dingtalk"],
        suppress_duration=600,
        max_alerts_per_hour=3,
    ),
    AlertRule(
        name="健康分数偏低",
        metric_name="overall_score",
        operator="<",
        threshold=80,
        level=AlertLevel.WARNING,
        notification_channels=["dingtalk"],
        suppress_duration=900,
        max_alerts_per_hour=5,
    ),
    AlertRule(
        name="严重问题检测",
        metric_name="critical_count",
        operator=">",
        threshold=0,
        level=AlertLevel.CRITICAL,
        notification_channels=["dingtalk", "email"],
        suppress_duration=300,
        max_alerts_per_hour=10,
    ),
    AlertRule(
        name="警告数量过多",
        metric_name="warning_count",
        operator=">",
        threshold=5,
        level=AlertLevel.WARNING,
        notification_channels=["dingtalk"],
        suppress_duration=600,
        max_alerts_per_hour=5,
    ),
]


# 全局告警引擎
_alert_engine: Optional[AlertEngine] = None


def get_alert_engine() -> AlertEngine:
    """获取告警引擎实例"""
    global _alert_engine
    if _alert_engine is None:
        _alert_engine = AlertEngine()
        # 添加默认规则
        for rule in DEFAULT_ALERT_RULES:
            _alert_engine.add_rule(rule)
    return _alert_engine