"""工具层单元测试。"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from rds_agent.tools.instance import (
    get_instance_list,
    get_instance_info,
    get_mysql_version,
)
from rds_agent.tools.performance import (
    get_performance_metrics,
    get_innodb_status,
    _analyze_performance,
)
from rds_agent.tools.sql import (
    get_slow_queries,
    analyze_processlist,
    _analyze_slow_query,
)
from rds_agent.tools.connection import (
    get_connection_status,
    get_lock_info,
    _analyze_connection_status,
)
from rds_agent.tools.storage import (
    get_storage_usage,
    get_table_stats,
    get_index_usage,
    _analyze_storage,
    _analyze_table_stats,
)
from rds_agent.tools.parameters import (
    get_parameters,
    get_all_variables,
    _analyze_parameter,
    PARAMETER_RECOMMENDATIONS,
)
from rds_agent.tools.knowledge import search_knowledge
from rds_agent.tools.base import (
    ToolResult,
    BaseRDSTool,
    register_tool,
    get_tool,
    list_tools,
)


class TestInstanceTools:
    """实例信息工具测试"""

    def test_get_instance_list_success(self):
        """测试获取实例列表成功"""
        result = get_instance_list.invoke({})
        # 应返回JSON字符串
        assert isinstance(result, str)
        # 解析JSON
        data = json.loads(result)
        assert isinstance(data, list)
        # Mock客户端返回3个实例
        assert len(data) == 3

    def test_get_instance_list_structure(self):
        """测试实例列表数据结构"""
        result = get_instance_list.invoke({})
        data = json.loads(result)
        for instance in data:
            assert "id" in instance
            assert "name" in instance
            assert "host" in instance
            assert "port" in instance

    def test_get_instance_info_found(self):
        """测试获取实例详情-找到实例"""
        result = get_instance_info.invoke({"instance_name": "db-prod-01"})
        data = json.loads(result)
        assert data["name"] == "db-prod-01"
        assert data["host"] == "192.168.1.100"

    def test_get_instance_info_not_found(self):
        """测试获取实例详情-未找到"""
        result = get_instance_info.invoke({"instance_name": "nonexistent"})
        assert "错误" in result or "未找到" in result

    def test_get_instance_info_by_id(self):
        """测试通过ID获取实例"""
        result = get_instance_info.invoke({"instance_name": "inst-001"})
        data = json.loads(result)
        assert data["id"] == "inst-001"

    def test_get_mysql_version_mock(self):
        """测试获取MySQL版本"""
        # 由于需要真实MySQL连接，这里测试错误处理
        result = get_mysql_version.invoke({"instance_name": "db-prod-01"})
        # Mock环境下应该返回错误或模拟值
        assert isinstance(result, str)


class TestPerformanceTools:
    """性能监控工具测试"""

    def test_analyze_performance_buffer_pool_low(self):
        """测试Buffer Pool命中率低的分析"""
        from rds_agent.data.models import PerformanceMetrics

        metrics = PerformanceMetrics(
            buffer_pool_hit_rate=80.0,  # 低命中率
            thread_running=60,  # 高线程数
            qps=1000,
            tps=100,
        )
        analysis = _analyze_performance(metrics)
        assert analysis["status"] == "需要关注"
        assert len(analysis["warnings"]) >= 1
        assert "Buffer Pool命中率偏低" in analysis["warnings"][0]

    def test_analyze_performance_normal(self):
        """测试正常性能指标分析"""
        from rds_agent.data.models import PerformanceMetrics

        metrics = PerformanceMetrics(
            buffer_pool_hit_rate=99.0,
            thread_running=10,
            qps=1000,
            tps=100,
            disk_reads=100,
            innodb_reads=10000,
        )
        analysis = _analyze_performance(metrics)
        assert analysis["status"] == "正常"

    def test_get_performance_metrics_structure(self):
        """测试性能指标返回结构"""
        result = get_performance_metrics.invoke({"instance_name": "db-prod-01"})
        assert isinstance(result, str)


class TestSQLTools:
    """SQL诊断工具测试"""

    def test_analyze_slow_query_select(self):
        """测试SELECT类型慢查询分析"""
        from rds_agent.data.models import SlowQueryRecord

        query = SlowQueryRecord(
            sql_text="SELECT * FROM orders WHERE user_id = 123",
            query_time=5.0,
            rows_examined=10000,
            rows_sent=10,
        )
        analysis = _analyze_slow_query(query)
        assert analysis["type"] == "SELECT查询"
        # 扫描比例高应该有建议
        assert len(analysis["suggestions"]) >= 1

    def test_analyze_slow_query_update(self):
        """测试UPDATE类型慢查询分析"""
        from rds_agent.data.models import SlowQueryRecord

        query = SlowQueryRecord(
            sql_text="UPDATE orders SET status = 1 WHERE id = 100",
            query_time=2.0,
            rows_examined=100,
            rows_sent=0,
        )
        analysis = _analyze_slow_query(query)
        assert "UPDATE" in analysis["type"] or "DELETE" in analysis["type"]

    def test_analyze_slow_query_with_join(self):
        """测试带JOIN的慢查询分析"""
        from rds_agent.data.models import SlowQueryRecord

        query = SlowQueryRecord(
            sql_text="SELECT * FROM orders JOIN users ON orders.user_id = users.id",
            query_time=3.0,
            rows_examined=5000,
            rows_sent=50,
        )
        analysis = _analyze_slow_query(query)
        assert any("JOIN" in s for s in analysis["suggestions"])

    def test_get_slow_queries_parameters(self):
        """测试慢查询参数传递"""
        result = get_slow_queries.invoke({
            "instance_name": "db-prod-01",
            "limit": 5,
            "min_time": 2.0
        })
        assert isinstance(result, str)

    def test_analyze_processlist(self):
        """测试进程列表分析"""
        result = analyze_processlist.invoke({"instance_name": "db-prod-01"})
        assert isinstance(result, str)


class TestConnectionTools:
    """连接诊断工具测试"""

    def test_analyze_connection_status_high_usage(self):
        """测试高连接使用率分析"""
        from rds_agent.data.models import ConnectionStatus

        status = ConnectionStatus(
            max_connections=100,
            current_connections=85,
            active_connections=40,
            idle_connections=45,
            connection_errors=0,
            aborted_connections=0,
        )
        # 使用率85%
        analysis = _analyze_connection_status(status)
        assert analysis["status"] == "告警"
        assert "连接使用率过高" in analysis["warnings"][0]

    def test_analyze_connection_status_normal(self):
        """测试正常连接状态分析"""
        from rds_agent.data.models import ConnectionStatus

        status = ConnectionStatus(
            max_connections=100,
            current_connections=50,
            active_connections=20,
            idle_connections=30,
            connection_errors=0,
            aborted_connections=0,
        )
        analysis = _analyze_connection_status(status)
        assert analysis["status"] == "正常"

    def test_analyze_connection_status_errors(self):
        """测试连接错误分析"""
        from rds_agent.data.models import ConnectionStatus

        status = ConnectionStatus(
            max_connections=100,
            current_connections=50,
            active_connections=20,
            idle_connections=30,
            connection_errors=200,
            aborted_connections=100,
        )
        analysis = _analyze_connection_status(status)
        assert len(analysis["warnings"]) >= 2

    def test_connection_usage_ratio_property(self):
        """测试连接使用率计算"""
        from rds_agent.data.models import ConnectionStatus

        status = ConnectionStatus(
            max_connections=100,
            current_connections=75,
        )
        assert status.connection_usage_ratio == 75.0


class TestStorageTools:
    """存储分析工具测试"""

    def test_analyze_storage_large_table(self):
        """测试大表分析"""
        from rds_agent.data.models import StorageUsage

        storage = StorageUsage(
            total_size_gb=100,
            used_size_gb=80,
            table_count=500,
            database_count=5,
            largest_tables=[
                {"schema_name": "prod", "table_name": "orders", "total_size_mb": 5000},
                {"schema_name": "prod", "table_name": "users", "total_size_mb": 2000},
            ],
        )
        analysis = _analyze_storage(storage)
        # 大表超过1GB应该有警告
        assert len(analysis["warnings"]) >= 1

    def test_analyze_storage_many_tables(self):
        """测试表数量过多分析"""
        from rds_agent.data.models import StorageUsage

        storage = StorageUsage(
            total_size_gb=50,
            used_size_gb=40,
            table_count=2000,
            database_count=10,
            largest_tables=[],
        )
        analysis = _analyze_storage(storage)
        assert "表数量较多" in analysis["warnings"][0]

    def test_analyze_table_stats_fragmentation(self):
        """测试碎片分析"""
        from rds_agent.data.models import TableStats

        table_stats = [
            TableStats(
                schema_name="prod",
                table_name="orders",
                table_rows=100000,
                data_size_mb=500.0,
                index_size_mb=100.0,
                data_free_mb=200.0,  # 高碎片
                engine="InnoDB",
            ),
            TableStats(
                schema_name="prod",
                table_name="users",
                table_rows=50000,
                data_size_mb=200.0,
                index_size_mb=50.0,
                data_free_mb=10.0,  # 低碎片
                engine="InnoDB",
            ),
        ]
        analysis = _analyze_table_stats(table_stats)
        # 碎片超过100MB应该有建议
        assert len(analysis["suggestions"]) >= 1

    def test_get_storage_usage(self):
        """测试获取存储使用情况"""
        result = get_storage_usage.invoke({"instance_name": "db-prod-01"})
        assert isinstance(result, str)

    def test_get_table_stats_with_schema(self):
        """测试带schema参数的表统计"""
        result = get_table_stats.invoke({
            "instance_name": "db-prod-01",
            "schema_name": "prod"
        })
        assert isinstance(result, str)


class TestParameterTools:
    """参数查询工具测试"""

    def test_analyze_parameter_buffer_pool_small(self):
        """测试Buffer Pool过小分析"""
        analysis = _analyze_parameter("innodb_buffer_pool_size", "134217728")  # 128MB
        assert analysis["status"] == "需优化"
        assert "Buffer Pool过小" in analysis["suggestions"][0]

    def test_analyze_parameter_buffer_pool_normal(self):
        """测试Buffer Pool正常"""
        analysis = _analyze_parameter("innodb_buffer_pool_size", "8589934592")  # 8GB
        assert analysis["status"] == "正常"

    def test_analyze_parameter_slow_query_log_off(self):
        """测试慢查询日志关闭"""
        analysis = _analyze_parameter("slow_query_log", "OFF")
        assert analysis["status"] == "需优化"
        assert "开启慢查询日志" in analysis["suggestions"][0]

    def test_analyze_parameter_slow_query_log_on(self):
        """测试慢查询日志开启"""
        analysis = _analyze_parameter("slow_query_log", "ON")
        assert analysis["status"] == "正常"

    def test_analyze_parameter_long_query_time(self):
        """测试慢查询阈值分析"""
        analysis = _analyze_parameter("long_query_time", "10.0")
        assert len(analysis["suggestions"]) >= 1
        assert "阈值较高" in analysis["suggestions"][0]

    def test_parameter_recommendations_exist(self):
        """测试参数推荐配置存在"""
        assert "innodb_buffer_pool_size" in PARAMETER_RECOMMENDATIONS
        assert "max_connections" in PARAMETER_RECOMMENDATIONS
        assert "innodb_flush_log_at_trx_commit" in PARAMETER_RECOMMENDATIONS

    def test_get_parameters(self):
        """测试获取参数"""
        result = get_parameters.invoke({"instance_name": "db-prod-01"})
        assert isinstance(result, str)

    def test_get_parameters_with_names(self):
        """测试获取指定参数"""
        result = get_parameters.invoke({
            "instance_name": "db-prod-01",
            "param_names": "max_connections,innodb_buffer_pool_size"
        })
        assert isinstance(result, str)


class TestKnowledgeTools:
    """知识库检索工具测试"""

    @patch("rds_agent.tools.knowledge.get_knowledge_store")
    def test_search_knowledge_success(self, mock_store):
        """测试知识库检索成功"""
        from langchain_core.documents import Document

        mock_store.return_value.search.return_value = [
            Document(
                page_content="InnoDB Buffer Pool缓存数据和索引页",
                metadata={"source": "architecture.md"}
            )
        ]
        result = search_knowledge.invoke({"query": "Buffer Pool", "top_k": 3})
        assert isinstance(result, str)

    @patch("rds_agent.tools.knowledge.get_knowledge_store")
    def test_search_knowledge_empty(self, mock_store):
        """测试知识库检索无结果"""
        mock_store.return_value.search.return_value = []
        result = search_knowledge.invoke({"query": "unknown topic", "top_k": 3})
        assert "未找到" in result


class TestToolBase:
    """工具基类测试"""

    def test_tool_result_success(self):
        """测试工具执行结果-成功"""
        result = ToolResult(success=True, data={"key": "value"})
        assert result.success
        assert result.data == {"key": "value"}

    def test_tool_result_failure(self):
        """测试工具执行结果-失败"""
        result = ToolResult(success=False, error="Something went wrong")
        assert not result.success
        assert result.error == "Something went wrong"

    def test_register_tool(self):
        """测试工具注册"""
        class MockTool(BaseRDSTool):
            name = "mock_tool"
            description = "A mock tool"

            def run(self):
                return ToolResult(success=True, data="mock")

        tool = MockTool()
        register_tool(tool)

        assert "mock_tool" in list_tools()
        assert get_tool("mock_tool") == tool

    def test_list_tools(self):
        """测试列出工具"""
        tools = list_tools()
        assert isinstance(tools, list)

    def test_tool_to_langchain(self):
        """测试转换为LangChain工具"""
        class MockTool(BaseRDSTool):
            name = "test_tool"
            description = "Test tool"

            def run(self, arg1: str):
                return ToolResult(success=True, data=f"processed: {arg1}")

        tool = MockTool()
        lc_tool = tool.to_langchain_tool()
        assert lc_tool.name == "test_tool"
        assert lc_tool.description == "Test tool"