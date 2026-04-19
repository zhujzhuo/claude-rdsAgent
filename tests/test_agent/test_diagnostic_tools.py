"""诊断工具测试。"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import json

from rds_agent.tools.diagnostic import (
    run_full_inspection,
    run_quick_check,
    run_performance_diagnosis,
    run_connection_diagnosis,
    run_storage_diagnosis,
    get_health_score,
    generate_diagnostic_report,
)


class TestDiagnosticTools:
    """诊断工具测试"""

    @pytest.fixture
    def mock_diagnostic_agent(self):
        """Mock诊断Agent"""
        agent = MagicMock()

        # 创建模拟诊断结果
        from rds_agent.diagnostic.state import DiagnosticResult, HealthStatus

        result = DiagnosticResult(
            instance_name="db-prod-01",
            diagnostic_type="full_inspection",
            overall_status=HealthStatus.HEALTHY,
            overall_score=95,
            summary="实例状态良好",
            critical_issues=[],
            warnings=["慢查询阈值偏高"],
            suggestions=["降低慢查询阈值到1-3秒"],
        )

        agent.full_inspection.return_value = result
        agent.quick_check.return_value = result
        agent.performance_diagnosis.return_value = result
        agent.run.return_value = result

        return agent, result

    def test_run_full_inspection(self, mock_diagnostic_agent):
        """测试完整巡检工具"""
        agent, result = mock_diagnostic_agent

        with patch("rds_agent.tools.diagnostic.get_diagnostic_agent", return_value=agent):
            output = run_full_inspection.invoke({"instance_name": "db-prod-01"})
            data = json.loads(output)

            assert data["instance_name"] == "db-prod-01"
            assert data["overall_score"] == 95

    def test_run_quick_check(self, mock_diagnostic_agent):
        """测试快速检查工具"""
        agent, result = mock_diagnostic_agent

        with patch("rds_agent.tools.diagnostic.get_diagnostic_agent", return_value=agent):
            output = run_quick_check.invoke({"instance_name": "db-prod-01"})
            data = json.loads(output)

            assert data is not None

    def test_run_performance_diagnosis(self, mock_diagnostic_agent):
        """测试性能诊断工具"""
        agent, result = mock_diagnostic_agent

        # 添加性能检查项
        from rds_agent.diagnostic.state import CheckItem, CheckCategory

        result.check_items = [
            CheckItem(
                name="buffer_pool_hit_rate",
                category=CheckCategory.PERFORMANCE_METRICS,
                status="healthy",
                score=100,
                value=99.5,
            ),
            CheckItem(
                name="slow_query_count",
                category=CheckCategory.PERFORMANCE_METRICS,
                status="healthy",
                score=100,
                value=0,
            ),
        ]

        with patch("rds_agent.tools.diagnostic.get_diagnostic_agent", return_value=agent):
            output = run_performance_diagnosis.invoke({"instance_name": "db-prod-01"})
            data = json.loads(output)

            assert "performance_analysis" in data

    def test_run_connection_diagnosis(self, mock_diagnostic_agent):
        """测试连接诊断工具"""
        agent, result = mock_diagnostic_agent

        with patch("rds_agent.tools.diagnostic.get_diagnostic_agent", return_value=agent):
            output = run_connection_diagnosis.invoke({"instance_name": "db-prod-01"})
            data = json.loads(output)

            assert data["instance_name"] == "db-prod-01"

    def test_run_storage_diagnosis(self, mock_diagnostic_agent):
        """测试存储诊断工具"""
        agent, result = mock_diagnostic_agent

        # 添加存储检查项
        from rds_agent.diagnostic.state import CheckItem, CheckCategory

        result.check_items = [
            CheckItem(
                name="storage_capacity",
                category=CheckCategory.STORAGE_ENGINE,
                status="healthy",
                score=100,
                value={"used_gb": 20, "quota_gb": 100},
            ),
        ]

        with patch("rds_agent.tools.diagnostic.get_diagnostic_agent", return_value=agent):
            output = run_storage_diagnosis.invoke({"instance_name": "db-prod-01"})
            data = json.loads(output)

            assert "storage_analysis" in data

    def test_get_health_score(self, mock_diagnostic_agent):
        """测试健康分数工具"""
        agent, result = mock_diagnostic_agent

        with patch("rds_agent.tools.diagnostic.get_diagnostic_agent", return_value=agent):
            output = get_health_score.invoke({"instance_name": "db-prod-01"})
            data = json.loads(output)

            assert data["overall_score"] == 95
            assert data["overall_status"] == "healthy"

    def test_generate_diagnostic_report(self, mock_diagnostic_agent):
        """测试生成报告工具"""
        agent, result = mock_diagnostic_agent

        mock_report_generator = MagicMock()
        mock_report_generator.save_report.return_value = "/tmp/test_report.txt"

        with patch("rds_agent.tools.diagnostic.get_diagnostic_agent", return_value=agent):
            with patch("rds_agent.tools.diagnostic.get_report_generator", return_value=mock_report_generator):
                output = generate_diagnostic_report.invoke({
                    "instance_name": "db-prod-01",
                    "format": "txt"
                })
                data = json.loads(output)

                assert "report_path" in data

    def test_diagnostic_instance_not_found(self):
        """测试实例不存在"""
        agent = MagicMock()
        agent.full_inspection.return_value = None

        with patch("rds_agent.tools.diagnostic.get_diagnostic_agent", return_value=agent):
            output = run_full_inspection.invoke({"instance_name": "nonexistent"})
            assert "错误" in output


class TestParameterOptimizerTools:
    """参数优化工具测试"""

    def test_analyze_parameter_optimization_mock(self):
        """测试参数优化分析"""
        mock_platform_client = MagicMock()
        mock_platform_client.search_instance_by_name.return_value = MagicMock(
            id="inst-001",
            name="db-prod-01",
        )
        mock_platform_client.get_instance_connection.return_value = MagicMock(
            host="192.168.1.100",
            port=3306,
            user="admin",
        )

        mock_mysql_client = MagicMock()
        mock_mysql_client.get_system_variables.return_value = {
            "innodb_buffer_pool_size": "8589934592",
            "max_connections": "500",
            "slow_query_log": "ON",
        }
        mock_mysql_client.get_status_variables.return_value = {}

        from rds_agent.diagnostic.parameter_optimizer import analyze_parameter_optimization

        with patch("rds_agent.diagnostic.parameter_optimizer.get_platform_client", return_value=mock_platform_client):
            with patch("rds_agent.diagnostic.parameter_optimizer.MySQLClient", return_value=mock_mysql_client):
                output = analyze_parameter_optimization.invoke({"instance_name": "db-prod-01"})
                data = json.loads(output)

                assert "parameters" in data
                assert "overall_score" in data

    def test_get_parameter_recommendations_mock(self):
        """测试参数推荐"""
        mock_platform_client = MagicMock()
        mock_platform_client.search_instance_by_name.return_value = MagicMock(
            id="inst-001",
            name="db-prod-01",
        )
        mock_platform_client.get_instance_connection.return_value = MagicMock()

        mock_mysql_client = MagicMock()
        mock_mysql_client.get_system_variables.return_value = {
            "max_connections": "500",
            "innodb_buffer_pool_size": "8589934592",
        }

        from rds_agent.diagnostic.parameter_optimizer import get_parameter_recommendations

        with patch("rds_agent.diagnostic.parameter_optimizer.get_platform_client", return_value=mock_platform_client):
            with patch("rds_agent.diagnostic.parameter_optimizer.MySQLClient", return_value=mock_mysql_client):
                output = get_parameter_recommendations.invoke({
                    "instance_name": "db-prod-01",
                    "param_names": "max_connections"
                })
                data = json.loads(output)

                assert "recommendations" in data
                assert len(data["recommendations"]) == 1