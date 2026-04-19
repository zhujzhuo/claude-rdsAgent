"""诊断检查项测试。"""

import pytest
from unittest.mock import MagicMock, patch

from rds_agent.diagnostic.checks import (
    BaseCheck,
    InstanceRunningCheck,
    UptimeCheck,
    ConnectionCountCheck,
    ActiveSessionsCheck,
    LockWaitCheck,
    BufferPoolHitRateCheck,
    SlowQueryCountCheck,
    StorageCapacityCheck,
    FragmentationCheck,
    CHECK_REGISTRY,
    get_check_class,
)
from rds_agent.diagnostic.state import HealthStatus, CheckCategory


class TestBaseCheck:
    """检查项基类测试"""

    def test_base_check_creation(self):
        """测试创建检查项"""
        mock_client = MagicMock()
        check = BaseCheck(mock_client)
        assert check.mysql_client == mock_client

    def test_set_threshold(self):
        """测试设置阈值"""
        mock_client = MagicMock()
        check = BaseCheck(mock_client)
        check.set_threshold(80)
        assert check.threshold == 80


class TestInstanceRunningCheck:
    """实例运行状态检查测试"""

    def test_check_running(self):
        """测试实例运行"""
        mock_client = MagicMock()
        mock_client.get_version.return_value = "8.0.32"

        check = InstanceRunningCheck(mock_client)
        result = check.run()

        assert result.status == HealthStatus.HEALTHY
        assert result.score == 100
        assert "8.0.32" in result.message

    def test_check_not_running(self):
        """测试实例不运行"""
        mock_client = MagicMock()
        mock_client.get_version.return_value = None

        check = InstanceRunningCheck(mock_client)
        result = check.run()

        assert result.status == HealthStatus.CRITICAL
        assert result.score == 0

    def test_check_error(self):
        """测试检查错误"""
        mock_client = MagicMock()
        mock_client.get_version.side_effect = Exception("Connection error")

        check = InstanceRunningCheck(mock_client)
        result = check.run()

        assert result.status == HealthStatus.CRITICAL
        assert "Connection error" in result.message


class TestUptimeCheck:
    """运行时间检查测试"""

    def test_check_long_uptime(self):
        """测试长时间运行"""
        mock_client = MagicMock()
        mock_client.get_status_variables.return_value = {"Uptime": "2592000"}  # 30天

        check = UptimeCheck(mock_client)
        result = check.run()

        assert result.status == HealthStatus.HEALTHY
        assert result.score == 100

    def test_check_short_uptime(self):
        """测试短时间运行"""
        mock_client = MagicMock()
        mock_client.get_status_variables.return_value = {"Uptime": "3600"}  # 1小时

        check = UptimeCheck(mock_client)
        result = check.run()

        assert result.status == HealthStatus.WARNING


class TestConnectionCountCheck:
    """连接数检查测试"""

    def test_check_normal(self):
        """测试正常连接数"""
        from rds_agent.data.models import ConnectionStatus

        mock_client = MagicMock()
        mock_client.get_connection_status.return_value = ConnectionStatus(
            max_connections=1000,
            current_connections=500,
            active_connections=200,
        )

        check = ConnectionCountCheck(mock_client)
        result = check.run()

        assert result.status == HealthStatus.HEALTHY
        assert result.score == 100

    def test_check_high_usage(self):
        """测试高连接使用率"""
        from rds_agent.data.models import ConnectionStatus

        mock_client = MagicMock()
        mock_client.get_connection_status.return_value = ConnectionStatus(
            max_connections=100,
            current_connections=90,
        )

        check = ConnectionCountCheck(mock_client)
        check.set_threshold(80)
        result = check.run()

        assert result.status == HealthStatus.CRITICAL
        assert result.score < 50

    def test_check_warning_level(self):
        """测试警告级别"""
        from rds_agent.data.models import ConnectionStatus

        mock_client = MagicMock()
        mock_client.get_connection_status.return_value = ConnectionStatus(
            max_connections=100,
            current_connections=70,
        )

        check = ConnectionCountCheck(mock_client)
        check.set_threshold(80)
        result = check.run()

        assert result.status == HealthStatus.WARNING


class TestBufferPoolHitRateCheck:
    """Buffer Pool命中率检查测试"""

    def test_check_high_hit_rate(self):
        """测试高命中率"""
        from rds_agent.data.models import PerformanceMetrics

        mock_client = MagicMock()
        mock_client.get_performance_metrics.return_value = PerformanceMetrics(
            buffer_pool_hit_rate=99.5,
        )

        check = BufferPoolHitRateCheck(mock_client)
        result = check.run()

        assert result.status == HealthStatus.HEALTHY
        assert result.value == 99.5

    def test_check_low_hit_rate(self):
        """测试低命中率"""
        from rds_agent.data.models import PerformanceMetrics

        mock_client = MagicMock()
        mock_client.get_performance_metrics.return_value = PerformanceMetrics(
            buffer_pool_hit_rate=80.0,
        )

        check = BufferPoolHitRateCheck(mock_client)
        check.set_threshold(95)
        result = check.run()

        assert result.status == HealthStatus.CRITICAL
        assert len(result.suggestion) > 0


class TestSlowQueryCountCheck:
    """慢查询数量检查测试"""

    def test_check_no_slow_queries(self):
        """测试无慢查询"""
        mock_client = MagicMock()
        mock_client.get_slow_queries.return_value = []
        mock_client.get_system_variables.return_value = {
            "slow_query_log": "ON",
            "long_query_time": "2",
        }

        check = SlowQueryCountCheck(mock_client)
        result = check.run()

        assert result.status == HealthStatus.HEALTHY
        assert result.value == 0

    def test_check_many_slow_queries(self):
        """测试大量慢查询"""
        from rds_agent.data.models import SlowQueryRecord

        mock_client = MagicMock()
        mock_client.get_slow_queries.return_value = [
            SlowQueryRecord(sql_text="SELECT * FROM test", query_time=2.0)
            for _ in range(15)
        ]
        mock_client.get_system_variables.return_value = {
            "slow_query_log": "ON",
            "long_query_time": "2",
        }

        check = SlowQueryCountCheck(mock_client)
        check.set_threshold(10)
        result = check.run()

        assert result.status == HealthStatus.CRITICAL
        assert len(result.suggestion) > 0

    def test_check_slow_log_disabled(self):
        """测试慢日志未开启"""
        mock_client = MagicMock()
        mock_client.get_slow_queries.return_value = []
        mock_client.get_system_variables.return_value = {
            "slow_query_log": "OFF",
            "long_query_time": "10",
        }

        check = SlowQueryCountCheck(mock_client)
        result = check.run()

        assert "开启慢查询日志" in result.suggestion


class TestStorageCapacityCheck:
    """存储容量检查测试"""

    def test_check_normal(self):
        """测试正常存储"""
        from rds_agent.data.models import StorageUsage

        mock_client = MagicMock()
        mock_client.get_storage_usage.return_value = StorageUsage(
            total_size_gb=100,
            used_size_gb=40,
        )

        mock_instance = MagicMock()
        mock_instance.storage_size = 100

        check = StorageCapacityCheck(mock_client, mock_instance)
        result = check.run()

        assert result.value["usage_ratio"] == 40.0

    def test_check_high_usage(self):
        """测试高存储使用"""
        from rds_agent.data.models import StorageUsage

        mock_client = MagicMock()
        mock_client.get_storage_usage.return_value = StorageUsage(
            total_size_gb=100,
            used_size_gb=90,
        )

        mock_instance = MagicMock()
        mock_instance.storage_size = 100

        check = StorageCapacityCheck(mock_client, mock_instance)
        check.set_threshold(85)
        result = check.run()

        assert result.status == HealthStatus.CRITICAL


class TestFragmentationCheck:
    """碎片检查测试"""

    def test_check_no_fragmentation(self):
        """测试无碎片"""
        from rds_agent.data.models import TableStats

        mock_client = MagicMock()
        mock_client.get_table_stats.return_value = [
            TableStats(schema_name="test", table_name="t1", data_free_mb=10),
            TableStats(schema_name="test", table_name="t2", data_free_mb=5),
        ]

        check = FragmentationCheck(mock_client)
        check.set_threshold(100)
        result = check.run()

        assert result.status == HealthStatus.HEALTHY

    def test_check_high_fragmentation(self):
        """测试高碎片"""
        from rds_agent.data.models import TableStats

        mock_client = MagicMock()
        mock_client.get_table_stats.return_value = [
            TableStats(schema_name="test", table_name="t1", data_free_mb=500),
            TableStats(schema_name="test", table_name="t2", data_free_mb=300),
        ]

        check = FragmentationCheck(mock_client)
        check.set_threshold(100)
        result = check.run()

        assert result.status == HealthStatus.CRITICAL
        assert len(result.details["fragmented_tables"]) == 2


class TestCheckRegistry:
    """检查项注册表测试"""

    def test_registry_has_checks(self):
        """测试注册表有检查项"""
        assert len(CHECK_REGISTRY) > 0
        assert "instance_running" in CHECK_REGISTRY
        assert "connection_count" in CHECK_REGISTRY
        assert "buffer_pool_hit_rate" in CHECK_REGISTRY

    def test_get_check_class(self):
        """测试获取检查类"""
        check_class = get_check_class("instance_running")
        assert check_class == InstanceRunningCheck

        check_class = get_check_class("connection_count")
        assert check_class == ConnectionCountCheck

    def test_get_unknown_check(self):
        """测试获取未知检查"""
        check_class = get_check_class("unknown_check")
        assert check_class is None