"""诊断Agent测试。"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from rds_agent.diagnostic.agent import DiagnosticAgent, get_diagnostic_agent
from rds_agent.diagnostic.state import DiagnosticType, HealthStatus


class TestDiagnosticAgent:
    """诊断Agent测试"""

    @pytest.fixture
    def mock_platform_client(self):
        """Mock平台客户端"""
        client = MagicMock()
        client.search_instance_by_name.return_value = MagicMock(
            id="inst-001",
            name="db-prod-01",
            host="192.168.1.100",
        )
        client.get_instance_connection.return_value = MagicMock(
            host="192.168.1.100",
            port=3306,
            user="admin",
            password="test",
        )
        client.close.return_value = None
        return client

    @pytest.fixture
    def mock_mysql_client(self):
        """Mock MySQL客户端"""
        client = MagicMock()
        client.get_version.return_value = "8.0.32"
        client.get_status_variables.return_value = {
            "Uptime": "2592000",
            "Threads_connected": "100",
            "Threads_running": "10",
        }
        client.get_connection_status.return_value = MagicMock(
            max_connections=1000,
            current_connections=100,
            active_connections=10,
            connection_usage_ratio=10.0,
        )
        client.get_performance_metrics.return_value = MagicMock(
            qps=500,
            tps=50,
            buffer_pool_hit_rate=99.5,
        )
        client.get_slow_queries.return_value = []
        client.get_storage_usage.return_value = MagicMock(
            total_size_gb=50,
            used_size_gb=20,
        )
        client.get_table_stats.return_value = []
        client.get_system_variables.return_value = {
            "slow_query_log": "ON",
            "long_query_time": "2",
        }
        client.get_processlist.return_value = []
        client.get_lock_info.return_value = []
        client.close.return_value = None
        return client

    def test_agent_creation(self):
        """测试Agent创建"""
        agent = DiagnosticAgent()
        assert agent.graph is not None
        assert agent.app is not None

    def test_agent_graph_structure(self):
        """测试图结构"""
        agent = DiagnosticAgent()
        # 验证节点存在
        assert agent.graph is not None

    def test_run_full_inspection_mock(self, mock_platform_client, mock_mysql_client):
        """测试完整巡检"""
        with patch("rds_agent.diagnostic.nodes.get_platform_client", return_value=mock_platform_client):
            with patch("rds_agent.diagnostic.nodes.MySQLClient", return_value=mock_mysql_client):
                agent = DiagnosticAgent()
                result = agent.full_inspection("db-prod-01")

                assert result is not None
                assert result.instance_name == "db-prod-01"
                assert result.diagnostic_type == DiagnosticType.FULL_INSPECTION

    def test_run_quick_check_mock(self, mock_platform_client, mock_mysql_client):
        """测试快速检查"""
        with patch("rds_agent.diagnostic.nodes.get_platform_client", return_value=mock_platform_client):
            with patch("rds_agent.diagnostic.nodes.MySQLClient", return_value=mock_mysql_client):
                agent = DiagnosticAgent()
                result = agent.quick_check("db-prod-01")

                assert result is not None
                assert result.diagnostic_type == DiagnosticType.QUICK_CHECK

    def test_run_performance_diagnosis(self, mock_platform_client, mock_mysql_client):
        """测试性能诊断"""
        with patch("rds_agent.diagnostic.nodes.get_platform_client", return_value=mock_platform_client):
            with patch("rds_agent.diagnostic.nodes.MySQLClient", return_value=mock_mysql_client):
                agent = DiagnosticAgent()
                result = agent.performance_diagnosis("db-prod-01")

                assert result is not None
                assert result.diagnostic_type == DiagnosticType.PERFORMANCE_DIAG

    def test_run_instance_not_found(self):
        """测试实例不存在"""
        mock_client = MagicMock()
        mock_client.search_instance_by_name.return_value = None

        with patch("rds_agent.diagnostic.nodes.get_platform_client", return_value=mock_client):
            agent = DiagnosticAgent()
            result = agent.full_inspection("nonexistent")

            assert result is not None
            assert result.overall_status == HealthStatus.UNKNOWN
            assert "未找到" in result.summary

    def test_stream_execution(self, mock_platform_client, mock_mysql_client):
        """测试流式执行"""
        with patch("rds_agent.diagnostic.nodes.get_platform_client", return_value=mock_platform_client):
            with patch("rds_agent.diagnostic.nodes.MySQLClient", return_value=mock_mysql_client):
                agent = DiagnosticAgent()

                events = list(agent.stream("db-prod-01", DiagnosticType.QUICK_CHECK))
                # 应产生多个事件
                assert len(events) >= 1


class TestDiagnosticAgentRouting:
    """诊断Agent路由测试"""

    @pytest.fixture
    def agent(self):
        return DiagnosticAgent()

    def test_route_after_initialize_success(self, agent):
        """测试初始化成功路由"""
        from rds_agent.diagnostic.state import DiagnosticState

        state: DiagnosticState = {
            "target_instance": "db-prod-01",
            "diagnostic_type": DiagnosticType.FULL_INSPECTION,
            "current_phase": "",
            "check_results": [],
            "diagnostic_result": None,
            "progress": 0,
            "error": None,
            "context": {},
        }

        route = agent._route_after_initialize(state)
        assert route == "continue"

    def test_route_after_initialize_error(self, agent):
        """测试初始化错误路由"""
        from rds_agent.diagnostic.state import DiagnosticState

        state: DiagnosticState = {
            "target_instance": "db-prod-01",
            "diagnostic_type": DiagnosticType.FULL_INSPECTION,
            "current_phase": "",
            "check_results": [],
            "diagnostic_result": None,
            "progress": 0,
            "error": "配置错误",
            "context": {},
        }

        route = agent._route_after_initialize(state)
        assert route == "error"

    def test_route_after_connect_success(self, agent):
        """测试连接成功路由"""
        from rds_agent.diagnostic.state import DiagnosticState

        state: DiagnosticState = {
            "target_instance": "db-prod-01",
            "diagnostic_type": DiagnosticType.FULL_INSPECTION,
            "current_phase": "connect",
            "check_results": [],
            "diagnostic_result": None,
            "progress": 10,
            "error": None,
            "context": {"mysql_client": MagicMock()},
        }

        route = agent._route_after_connect(state)
        assert route == "success"

    def test_route_after_connect_error(self, agent):
        """测试连接错误路由"""
        from rds_agent.diagnostic.state import DiagnosticState

        state: DiagnosticState = {
            "target_instance": "db-prod-01",
            "diagnostic_type": DiagnosticType.FULL_INSPECTION,
            "current_phase": "connect",
            "check_results": [],
            "diagnostic_result": None,
            "progress": 0,
            "error": "连接失败",
            "context": {},
        }

        route = agent._route_after_connect(state)
        assert route == "error"


class TestGetDiagnosticAgent:
    """获取诊断Agent实例测试"""

    def test_get_agent_singleton(self):
        """测试单例"""
        import rds_agent.diagnostic.agent as agent_module
        agent_module._diagnostic_agent = None

        agent1 = get_diagnostic_agent()
        agent2 = get_diagnostic_agent()

        assert agent1 == agent2