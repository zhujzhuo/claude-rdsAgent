"""诊断Agent状态和模型测试。"""

import pytest
from datetime import datetime

from rds_agent.diagnostic.state import (
    DiagnosticType,
    HealthStatus,
    CheckCategory,
    CheckItem,
    DiagnosticResult,
    DiagnosticState,
    InspectionTemplate,
    DEFAULT_INSPECTION_TEMPLATE,
    QUICK_CHECK_TEMPLATE,
)


class TestDiagnosticType:
    """诊断类型测试"""

    def test_diagnostic_types_exist(self):
        """测试所有诊断类型"""
        assert DiagnosticType.FULL_INSPECTION == "full_inspection"
        assert DiagnosticType.PERFORMANCE_DIAG == "performance_diag"
        assert DiagnosticType.CONNECTION_DIAG == "connection_diag"
        assert DiagnosticType.STORAGE_DIAG == "storage_diag"
        assert DiagnosticType.PARAMETER_DIAG == "parameter_diag"
        assert DiagnosticType.SECURITY_DIAG == "security_diag"
        assert DiagnosticType.LOG_DIAG == "log_diag"
        assert DiagnosticType.QUICK_CHECK == "quick_check"


class TestHealthStatus:
    """健康状态测试"""

    def test_health_status_values(self):
        """测试健康状态值"""
        assert HealthStatus.HEALTHY == "healthy"
        assert HealthStatus.WARNING == "warning"
        assert HealthStatus.CRITICAL == "critical"
        assert HealthStatus.UNKNOWN == "unknown"


class TestCheckCategory:
    """检查类别测试"""

    def test_check_categories_exist(self):
        """测试检查类别"""
        assert CheckCategory.INSTANCE_STATUS == "instance_status"
        assert CheckCategory.RESOURCE_USAGE == "resource_usage"
        assert CheckCategory.CONNECTION_SESSION == "connection_session"
        assert CheckCategory.PERFORMANCE_METRICS == "performance_metrics"
        assert CheckCategory.STORAGE_ENGINE == "storage_engine"
        assert CheckCategory.LOG_MONITOR == "log_monitor"
        assert CheckCategory.BACKUP_RECOVERY == "backup_recovery"
        assert CheckCategory.HIGH_AVAILABILITY == "high_availability"
        assert CheckCategory.SECURITY_CONFIG == "security_config"
        assert CheckCategory.SCHEMA_OBJECT == "schema_object"


class TestCheckItem:
    """检查项测试"""

    def test_check_item_creation(self):
        """测试创建检查项"""
        item = CheckItem(
            name="buffer_pool_hit_rate",
            category=CheckCategory.PERFORMANCE_METRICS,
            status=HealthStatus.HEALTHY,
            score=95,
            value=99.5,
            threshold=95,
            message="Buffer Pool命中率: 99.5%",
            suggestion="正常",
        )
        assert item.name == "buffer_pool_hit_rate"
        assert item.score == 95
        assert item.status == HealthStatus.HEALTHY

    def test_check_item_defaults(self):
        """测试默认值"""
        item = CheckItem(
            name="test_check",
            category=CheckCategory.INSTANCE_STATUS,
        )
        assert item.status == HealthStatus.UNKNOWN
        assert item.score == 0
        assert item.value is None
        assert item.message == ""
        assert item.details == {}

    def test_check_item_score_range(self):
        """测试分数范围"""
        # 有效分数
        item = CheckItem(name="test", category=CheckCategory.INSTANCE_STATUS, score=50)
        assert item.score == 50

        # 分数应限制在0-100
        with pytest.raises(Exception):
            CheckItem(name="test", category=CheckCategory.INSTANCE_STATUS, score=150)


class TestDiagnosticResult:
    """诊断结果测试"""

    def test_diagnostic_result_creation(self):
        """测试创建诊断结果"""
        result = DiagnosticResult(
            instance_name="db-prod-01",
            diagnostic_type=DiagnosticType.FULL_INSPECTION,
            overall_status=HealthStatus.HEALTHY,
            overall_score=90,
            summary="实例健康状态良好",
        )
        assert result.instance_name == "db-prod-01"
        assert result.overall_score == 90

    def test_diagnostic_result_with_check_items(self):
        """测试带检查项的结果"""
        check_items = [
            CheckItem(
                name="connection_count",
                category=CheckCategory.CONNECTION_SESSION,
                status=HealthStatus.HEALTHY,
                score=100,
            ),
            CheckItem(
                name="buffer_pool_hit_rate",
                category=CheckCategory.PERFORMANCE_METRICS,
                status=HealthStatus.WARNING,
                score=70,
            ),
        ]
        result = DiagnosticResult(
            instance_name="db-test-01",
            diagnostic_type=DiagnosticType.QUICK_CHECK,
            overall_status=HealthStatus.WARNING,
            overall_score=85,
            check_items=check_items,
        )
        assert len(result.check_items) == 2

    def test_diagnostic_result_issues(self):
        """测试问题列表"""
        result = DiagnosticResult(
            instance_name="db-prod-01",
            diagnostic_type=DiagnosticType.FULL_INSPECTION,
            overall_status=HealthStatus.CRITICAL,
            overall_score=40,
            critical_issues=["连接数过高", "Buffer Pool命中率过低"],
            warnings=["慢查询数量较多"],
            suggestions=["增大Buffer Pool", "优化慢查询"],
        )
        assert len(result.critical_issues) == 2
        assert len(result.warnings) == 1
        assert len(result.suggestions) == 2

    def test_diagnostic_result_times(self):
        """测试时间字段"""
        start = datetime.now()
        result = DiagnosticResult(
            instance_name="db-prod-01",
            diagnostic_type=DiagnosticType.FULL_INSPECTION,
            start_time=start,
        )
        assert result.start_time == start
        assert result.end_time is None


class TestDiagnosticState:
    """诊断状态测试"""

    def test_diagnostic_state_creation(self):
        """测试创建诊断状态"""
        state: DiagnosticState = {
            "target_instance": "db-prod-01",
            "diagnostic_type": DiagnosticType.FULL_INSPECTION,
            "current_phase": "initialize",
            "check_results": [],
            "diagnostic_result": None,
            "progress": 0,
            "error": None,
            "context": {},
        }
        assert state["target_instance"] == "db-prod-01"
        assert state["progress"] == 0


class TestInspectionTemplate:
    """巡检模板测试"""

    def test_default_template(self):
        """测试默认模板"""
        assert DEFAULT_INSPECTION_TEMPLATE.name == "标准MySQL实例巡检"
        assert len(DEFAULT_INSPECTION_TEMPLATE.categories) >= 5
        assert len(DEFAULT_INSPECTION_TEMPLATE.check_items) >= 10

    def test_quick_check_template(self):
        """测试快速检查模板"""
        assert QUICK_CHECK_TEMPLATE.name == "快速健康检查"
        assert len(QUICK_CHECK_TEMPLATE.check_items) < len(DEFAULT_INSPECTION_TEMPLATE.check_items)

    def test_custom_template(self):
        """测试自定义模板"""
        template = InspectionTemplate(
            name="自定义模板",
            description="测试模板",
            categories=[CheckCategory.PERFORMANCE_METRICS],
            check_items=["buffer_pool_hit_rate", "slow_query_count"],
            thresholds={"buffer_pool_hit_rate_min": 95},
        )
        assert template.name == "自定义模板"
        assert len(template.check_items) == 2
        assert template.thresholds["buffer_pool_hit_rate_min"] == 95