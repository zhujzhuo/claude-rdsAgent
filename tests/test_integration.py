"""集成测试 - 测试完整的Agent执行流程。"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import json

from rds_agent.core.agent import RDSAgent
from rds_agent.core.state import IntentType


class TestAgentIntegration:
    """Agent完整流程集成测试"""

    @pytest.fixture
    def mock_platform_client(self):
        """Mock实例管理平台客户端"""
        client = MagicMock()
        client.list_instances.return_value = [
            MagicMock(id="inst-001", name="db-prod-01", host="192.168.1.100"),
            MagicMock(id="inst-002", name="db-test-01", host="192.168.2.100"),
        ]
        client.search_instance_by_name.return_value = MagicMock(
            id="inst-001",
            name="db-prod-01",
            host="192.168.1.100",
            port=3306,
        )
        return client

    @pytest.fixture
    def mock_mysql_client(self):
        """Mock MySQL客户端"""
        client = MagicMock()
        client.get_version.return_value = "8.0.32"
        client.get_connection_status.return_value = MagicMock(
            max_connections=1000,
            current_connections=500,
            active_connections=200,
            connection_usage_ratio=50.0,
        )
        client.get_performance_metrics.return_value = MagicMock(
            qps=1200,
            tps=350,
            buffer_pool_hit_rate=99.5,
        )
        client.get_slow_queries.return_value = []
        client.close.return_value = None
        return client

    def test_full_flow_instance_query(self, mock_platform_client):
        """测试实例查询完整流程"""
        with patch("rds_agent.core.nodes.get_platform_client", return_value=mock_platform_client):
            with patch("rds_agent.core.nodes.get_llm") as mock_llm:
                mock_llm.return_value = MagicMock(invoke=lambda x: "发现2个实例")

                agent = RDSAgent()
                result = agent.invoke("查看实例列表", thread_id="test-1")

                # 验证流程执行
                assert result is not None
                assert result["intent"] == IntentType.INSTANCE_QUERY

    def test_full_flow_performance_diag(self, mock_platform_client, mock_mysql_client):
        """测试性能诊断完整流程"""
        with patch("rds_agent.data.instance_platform.get_platform_client", return_value=mock_platform_client):
            with patch("rds_agent.tools.performance._get_mysql_client", return_value=(mock_mysql_client, "")):
                with patch("rds_agent.core.nodes.get_llm") as mock_llm:
                    mock_llm_instance = MagicMock()
                    mock_llm_instance.invoke.return_value = "性能正常，QPS=1200"
                    mock_llm.return_value = mock_llm_instance

                    agent = RDSAgent()
                    result = agent.invoke("db-prod-01的性能情况", thread_id="test-2")

                    assert result["intent"] == IntentType.PERFORMANCE_DIAG
                    assert result["target_instance"] == "db-prod-01"

    def test_full_flow_conversation_context(self):
        """测试对话上下文保持"""
        with patch("rds_agent.core.nodes.get_llm") as mock_llm:
            mock_llm_instance = MagicMock()
            mock_llm_instance.invoke.side_effect = [
                "有3个实例",
                "db-prod-01的性能正常",
            ]
            mock_llm.return_value = mock_llm_instance

            agent = RDSAgent()
            thread_id = "conversation-test"

            # 第一轮对话
            result1 = agent.invoke("查看实例列表", thread_id=thread_id)

            # 第二轮对话（应该有上下文）
            result2 = agent.invoke("db-prod-01的性能", thread_id=thread_id)

            # 两次调用应使用相同thread_id
            assert agent.app.invoke.call_count == 2


class TestCLIIntegration:
    """CLI集成测试"""

    def test_cli_session_creation(self):
        """测试CLI会话创建"""
        from rds_agent.cli import create_key_bindings

        kb = create_key_bindings()
        assert kb is not None

    def test_cli_welcome_print(self):
        """测试欢迎信息打印"""
        from rds_agent.cli import print_welcome
        from rich.console import Console

        console = Console()
        # 不应抛出异常
        print_welcome(console)


class TestAPIIntegration:
    """API集成测试"""

    @pytest.fixture
    def app(self):
        """获取FastAPI应用"""
        from rds_agent.api.app import app
        return app

    def test_api_root_endpoint(self, app):
        """测试根路径"""
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert data["name"] == "RDS Agent"

    def test_api_health_endpoint(self, app):
        """测试健康检查"""
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_api_config_endpoint(self, app):
        """测试配置接口"""
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/config")

        assert response.status_code == 200
        data = response.json()
        assert "ollama" in data
        assert "agent" in data

    def test_api_chat_endpoint(self, app):
        """测试聊天接口"""
        from fastapi.testclient import TestClient

        with patch("rds_agent.api.app.agent") as mock_agent:
            mock_agent.invoke.return_value = {
                "response": "测试响应",
                "intent": "instance_query",
                "target_instance": None,
            }

            client = TestClient(app)
            response = client.post(
                "/chat",
                json={"message": "查看实例列表"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["response"] == "测试响应"

    def test_api_chat_empty_message(self, app):
        """测试空消息"""
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post(
            "/chat",
            json={"message": ""},
        )

        assert response.status_code == 400

    def test_api_instances_endpoint(self, app):
        """测试实例列表接口"""
        from fastapi.testclient import TestClient

        with patch("rds_agent.api.app.get_instance_list") as mock_list:
            mock_list.invoke.return_value = json.dumps([{"id": "1", "name": "test"}])

            client = TestClient(app)
            response = client.get("/instances")

            assert response.status_code == 200

    def test_api_instance_info_endpoint(self, app):
        """测试实例详情接口"""
        from fastapi.testclient import TestClient

        with patch("rds_agent.api.app.get_instance_info") as mock_info:
            mock_info.invoke.return_value = json.dumps({"id": "1", "name": "test"})

            client = TestClient(app)
            response = client.get("/instances/db-test-01")

            assert response.status_code == 200


class TestToolIntegration:
    """工具集成测试"""

    def test_tool_chain_execution(self):
        """测试工具链式执行"""
        from rds_agent.tools import (
            get_instance_list,
            get_instance_info,
            get_performance_metrics,
        )

        # 1. 获取实例列表
        list_result = get_instance_list.invoke({})
        instances = json.loads(list_result)

        # 2. 获取第一个实例的详情
        if instances:
            first_instance = instances[0]["name"]
            info_result = get_instance_info.invoke({"instance_name": first_instance})
            info = json.loads(info_result)

            # 验证数据一致性
            assert info["name"] == first_instance

    def test_tool_error_propagation(self):
        """测试工具错误传播"""
        from rds_agent.tools import get_instance_info

        # 不存在的实例
        result = get_instance_info.invoke({"instance_name": "nonexistent-instance"})
        assert "错误" in result or "未找到" in result


class TestKnowledgeIntegration:
    """知识库集成测试"""

    def test_knowledge_search_integration(self):
        """测试知识库检索集成"""
        from rds_agent.tools.knowledge import search_knowledge

        with patch("rds_agent.tools.knowledge.get_knowledge_store") as mock_store:
            from langchain_core.documents import Document

            mock_store.return_value.search.return_value = [
                Document(
                    page_content="Buffer Pool缓存数据页和索引页",
                    metadata={"source": "architecture.md"}
                )
            ]

            result = search_knowledge.invoke({"query": "Buffer Pool", "top_k": 3})
            data = json.loads(result)

            assert "results" in data
            assert len(data["results"]) >= 1


class TestEndToEndScenarios:
    """端到端场景测试"""

    def test_scenario_check_all_instances(self):
        """场景：查看所有实例"""
        from rds_agent.tools import get_instance_list

        result = get_instance_list.invoke({})
        instances = json.loads(result)

        assert isinstance(instances, list)
        assert len(instances) > 0

    def test_scenario_diagnose_single_instance(self):
        """场景：诊断单个实例"""
        from rds_agent.tools import (
            get_instance_info,
            get_performance_metrics,
            get_connection_status,
        )

        instance_name = "db-prod-01"

        # 获取基本信息
        info = json.loads(get_instance_info.invoke({"instance_name": instance_name}))

        # 获取性能指标
        perf = json.loads(get_performance_metrics.invoke({"instance_name": instance_name}))

        # 获取连接状态
        conn = json.loads(get_connection_status.invoke({"instance_name": instance_name}))

        # 验证所有信息来自同一实例
        assert info.get("name") == instance_name
        assert perf.get("instance") == instance_name
        assert conn.get("instance") == instance_name

    def test_scenario_slow_query_analysis(self):
        """场景：慢查询分析"""
        from rds_agent.tools import get_slow_queries

        result = get_slow_queries.invoke({
            "instance_name": "db-prod-01",
            "limit": 10,
            "min_time": 1.0
        })
        data = json.loads(result)

        # 验证结构
        assert "instance" in data
        assert "queries" in data

    def test_scenario_storage_analysis(self):
        """场景：存储空间分析"""
        from rds_agent.tools import get_storage_usage, get_table_stats

        # 获取整体存储使用
        storage = json.loads(get_storage_usage.invoke({"instance_name": "db-prod-01"}))

        # 获取详细表统计
        tables = json.loads(get_table_stats.invoke({"instance_name": "db-prod-01"}))

        # 验证数据关联
        assert storage.get("instance") == "db-prod-01"
        assert tables.get("instance") == "db-prod-01"