"""Hermes Agent 测试。"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestFunctionSchema:
    """测试 FunctionSchema 类"""

    def test_create_schema(self):
        """测试创建 Function Schema"""
        from rds_agent.hermes.function_schema import FunctionSchema

        schema = FunctionSchema(
            name="test_function",
            description="Test function",
            parameters={
                "param1": {"type": "string", "description": "First parameter"},
            },
            required=["param1"],
        )

        assert schema.name == "test_function"
        assert schema.description == "Test function"

    def test_to_openai_format(self):
        """测试转换为 OpenAI 格式"""
        from rds_agent.hermes.function_schema import FunctionSchema

        schema = FunctionSchema(
            name="get_weather",
            description="Get current weather",
            parameters={
                "location": {"type": "string", "description": "City name"},
            },
            required=["location"],
        )

        openai_format = schema.to_openai_format()

        assert openai_format["type"] == "function"
        assert openai_format["function"]["name"] == "get_weather"
        assert openai_format["function"]["parameters"]["required"] == ["location"]

    def test_schema_with_handler(self):
        """测试带 Handler 的 Schema"""
        from rds_agent.hermes.function_schema import FunctionSchema

        def my_handler(param1: str) -> str:
            return f"Result: {param1}"

        schema = FunctionSchema(
            name="test",
            description="Test",
            parameters={"param1": {"type": "string"}},
            required=["param1"],
            handler=my_handler,
        )

        result = schema.execute(param1="hello")
        assert result == "Result: hello"


class TestToolRegistry:
    """测试 ToolRegistry 类"""

    def test_register_tool(self):
        """测试注册工具"""
        from rds_agent.hermes.function_schema import ToolRegistry, FunctionSchema

        registry = ToolRegistry()
        schema = FunctionSchema(
            name="tool1",
            description="Tool 1",
            parameters={},
            required=[],
        )

        registry.register(schema)
        assert registry.count() == 1

    def test_get_tool(self):
        """测试获取工具"""
        from rds_agent.hermes.function_schema import ToolRegistry, FunctionSchema

        registry = ToolRegistry()
        schema = FunctionSchema(
            name="tool1",
            description="Tool 1",
            parameters={},
            required=[],
        )
        registry.register(schema)

        tool = registry.get("tool1")
        assert tool is not None
        assert tool.name == "tool1"

    def test_get_all_schemas(self):
        """测试获取所有 Schema"""
        from rds_agent.hermes.function_schema import ToolRegistry, FunctionSchema

        registry = ToolRegistry()
        for i in range(3):
            schema = FunctionSchema(
                name=f"tool{i}",
                description=f"Tool {i}",
                parameters={},
                required=[],
            )
            registry.register(schema)

        schemas = registry.get_all_schemas()
        assert len(schemas) == 3

    def test_execute_tool(self):
        """测试执行工具"""
        from rds_agent.hermes.function_schema import ToolRegistry, FunctionSchema

        def handler(value: str) -> str:
            return f"processed: {value}"

        registry = ToolRegistry()
        schema = FunctionSchema(
            name="process",
            description="Process value",
            parameters={"value": {"type": "string"}},
            required=["value"],
            handler=handler,
        )
        registry.register(schema)

        result = registry.execute("process", value="test")
        assert result == "processed: test"

    def test_execute_nonexistent_tool(self):
        """测试执行不存在的工具"""
        from rds_agent.hermes.function_schema import ToolRegistry

        registry = ToolRegistry()

        with pytest.raises(ValueError):
            registry.execute("nonexistent")


class TestHermesClient:
    """测试 HermesClient 类"""

    def test_resolve_model_name(self):
        """测试模型名称解析"""
        from rds_agent.hermes.client import HermesClient

        client = HermesClient(model="hermes2pro")
        assert client.model == "hermes2pro-llama3"

        client2 = HermesClient(model="hermes3")
        assert client2.model == "hermes3-llama3.1"

    def test_build_system_prompt(self):
        """测试系统提示词构建"""
        from rds_agent.hermes.client import HermesClient

        client = HermesClient()
        prompt = client._build_system_prompt()

        assert "Hermes" in prompt
        assert "function calling" in prompt.lower()

    def test_parse_tool_calls(self):
        """测试工具调用解析"""
        from rds_agent.hermes.client import HermesClient

        client = HermesClient()

        # 测试 JSON 格式的工具调用
        content = '{"tool_calls": [{"name": "get_info", "arguments": {"instance": "db-01"}}]}'
        calls = client._parse_tool_calls(content, {})
        assert calls is not None
        assert calls[0]["name"] == "get_info"

    def test_parse_single_tool_call(self):
        """测试单个工具调用格式"""
        from rds_agent.hermes.client import HermesClient

        client = HermesClient()

        content = '{"name": "get_info", "arguments": {"instance": "db-01"}}'
        calls = client._parse_tool_calls(content, {})
        assert calls is not None
        assert len(calls) == 1

    @patch("httpx.post")
    def test_chat_mock(self, mock_post):
        """测试 chat 方法 (mock)"""
        from rds_agent.hermes.client import HermesClient

        mock_response = Mock()
        mock_response.json.return_value = {
            "message": {"content": "Hello, how can I help you?"}
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        client = HermesClient()
        result = client.chat([{"role": "user", "content": "Hello"}])

        assert "content" in result


class TestHermesAgent:
    """测试 HermesAgent 类"""

    def test_create_agent(self):
        """测试创建 Agent"""
        from rds_agent.hermes.agent import HermesAgent

        agent = HermesAgent(model="hermes3")
        assert agent.model == "hermes3"
        assert agent.tool_registry is not None

    def test_register_tool(self):
        """测试注册工具"""
        from rds_agent.hermes.agent import HermesAgent

        agent = HermesAgent()

        agent.register_tool(
            name="test_tool",
            description="Test tool",
            parameters={"param": {"type": "string"}},
            required=["param"],
            handler=lambda param: f"result: {param}",
        )

        assert agent.get_tool_count() == 1

    def test_get_available_tools(self):
        """测试获取可用工具"""
        from rds_agent.hermes.agent import HermesAgent

        agent = HermesAgent()

        agent.register_tool(
            name="tool1",
            description="Tool 1",
            parameters={},
            required=[],
            handler=lambda: "ok",
        )

        tools = agent.get_available_tools()
        assert len(tools) == 1

    @patch("rds_agent.hermes.client.HermesClient.chat")
    def test_invoke_mock(self, mock_chat):
        """测试 invoke 方法 (mock)"""
        from rds_agent.hermes.agent import HermesAgent

        mock_chat.return_value = {
            "content": "Here is the answer",
            "tool_calls": None,
            "tool_results": None,
        }

        agent = HermesAgent()
        result = agent.invoke("What is the status?")

        assert "response" in result

    def test_clear_history(self):
        """测试清空历史"""
        from rds_agent.hermes.agent import HermesAgent

        agent = HermesAgent()
        agent.clear_history()

        assert len(agent.get_history()) == 0

    def test_execute_tool(self):
        """测试手动执行工具"""
        from rds_agent.hermes.agent import HermesAgent

        agent = HermesAgent()
        agent.register_tool(
            name="echo",
            description="Echo tool",
            parameters={"text": {"type": "string"}},
            required=["text"],
            handler=lambda text: text,
        )

        result = agent.execute_tool("echo", text="hello")
        assert result == "hello"


class TestRDSTools:
    """测试 RDS 工具注册"""

    def test_register_rds_tools(self):
        """测试注册 RDS 工具"""
        from rds_agent.hermes.tools import register_rds_tools, RDS_TOOL_SCHEMAS
        from rds_agent.hermes.function_schema import ToolRegistry

        registry = ToolRegistry()
        register_rds_tools(registry)

        # 应注册 8 个工具
        assert registry.count() == 8

    def test_tool_names(self):
        """测试工具名称"""
        from rds_agent.hermes.tools import RDS_TOOL_SCHEMAS

        expected_names = [
            "get_instance_info",
            "get_performance_metrics",
            "analyze_sql",
            "check_connections",
            "analyze_storage",
            "get_parameters",
            "search_knowledge",
            "run_diagnostic",
        ]

        actual_names = [schema.name for schema in RDS_TOOL_SCHEMAS]
        assert set(actual_names) == set(expected_names)

    def test_tool_has_handler(self):
        """测试工具是否有 Handler"""
        from rds_agent.hermes.tools import RDS_TOOL_SCHEMAS

        for schema in RDS_TOOL_SCHEMAS:
            assert schema.handler is not None

    def test_get_rds_tool_registry(self):
        """测试获取 RDS 工具注册中心"""
        from rds_agent.hermes.tools import get_rds_tool_registry

        registry = get_rds_tool_registry()
        assert registry.count() == 8


class TestHermesIntegration:
    """Hermes Agent 集成测试"""

    @patch("rds_agent.tools.instance.get_instance_info_tool")
    def test_tool_execution_mock(self, mock_tool):
        """测试工具执行 (mock)"""
        from rds_agent.hermes.tools import _get_instance_info

        mock_tool.invoke.return_value = {
            "name": "db-prod-01",
            "version": "8.0.32",
        }

        result = _get_instance_info("db-prod-01")
        assert result["success"] is True

    @patch("rds_agent.diagnostic.agent.get_diagnostic_agent")
    def test_diagnostic_tool_mock(self, mock_agent_getter):
        """测试诊断工具执行 (mock)"""
        from rds_agent.hermes.tools import _run_diagnostic

        mock_agent = Mock()
        mock_result = Mock()
        mock_result.overall_score = 85
        mock_result.overall_status = Mock(value="healthy")
        mock_result.critical_issues = []
        mock_result.warnings = []
        mock_result.suggestions = ["No issues"]
        mock_agent.run.return_value = mock_result
        mock_agent_getter.return_value = mock_agent

        result = _run_diagnostic("db-01", "quick_check")
        assert result["success"] is True
        assert result["data"]["overall_score"] == 85