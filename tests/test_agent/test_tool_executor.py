"""Agent 工具执行器测试。"""

import pytest
from unittest.mock import Mock, MagicMock

from rds_agent.agent.tool_executor import (
    ToolExecutor,
    ToolResult,
    ToolStatus,
    ToolConfig,
    ToolRegistry,
    HermesStyleToolExecutor,
)


class TestToolExecutor:
    """工具执行器测试"""

    @pytest.fixture
    def executor(self):
        """创建执行器"""
        return ToolExecutor()

    @pytest.fixture
    def registry(self):
        """创建注册表"""
        registry = ToolRegistry()

        # 注册测试工具
        def echo_tool(message: str) -> str:
            return f"Echo: {message}"

        def add_tool(a: int, b: int) -> int:
            return a + b

        registry.register(
            "echo",
            echo_tool,
            description="Echo message",
            parameters={"message": {"type": "string"}},
        )
        registry.register(
            "add",
            add_tool,
            description="Add numbers",
            parameters={"a": {"type": "int"}, "b": {"type": "int"}},
        )

        return registry

    def test_executor_creation(self):
        """测试创建执行器"""
        executor = ToolExecutor()
        assert executor.config is not None
        assert executor.registry is not None

    def test_execute_success(self, registry):
        """测试成功执行"""
        executor = ToolExecutor(registry=registry)
        result = executor.execute("echo", {"message": "test"}, iteration=1)

        assert result.status == ToolStatus.SUCCESS
        assert "Echo: test" in result.result

    def test_execute_tool_not_found(self, executor):
        """测试工具不存在"""
        result = executor.execute("nonexistent", {}, iteration=1)

        assert result.status == ToolStatus.FAILED
        assert "Tool not found" in result.error

    def test_execute_with_arguments(self, registry):
        """测试带参数执行"""
        executor = ToolExecutor(registry=registry)
        result = executor.execute("add", {"a": 5, "b": 3}, iteration=1)

        assert result.status == ToolStatus.SUCCESS
        assert result.result == 8

    def test_execute_batch(self, registry):
        """测试批量执行"""
        executor = ToolExecutor(registry=registry)

        tool_calls = [
            {"name": "echo", "arguments": {"message": "hello"}},
            {"name": "add", "arguments": {"a": 2, "b": 3}},
        ]

        results = executor.execute_batch(tool_calls, iteration=1)

        assert len(results) == 2
        assert all(r.status == ToolStatus.SUCCESS for r in results)

    def test_get_history(self, registry):
        """测试获取历史"""
        executor = ToolExecutor(registry=registry)
        executor.execute("echo", {"message": "test1"}, iteration=1)
        executor.execute("echo", {"message": "test2"}, iteration=2)

        history = executor.get_history()
        assert len(history) == 2

    def test_get_stats(self, registry):
        """测试获取统计"""
        executor = ToolExecutor(registry=registry)
        executor.execute("echo", {"message": "test"}, iteration=1)

        stats = executor.get_stats()
        assert stats["total_calls"] == 1
        assert stats["success_calls"] == 1

    def test_clear_history(self, registry):
        """测试清空历史"""
        executor = ToolExecutor(registry=registry)
        executor.execute("echo", {"message": "test"}, iteration=1)

        executor.clear_history()
        assert len(executor.get_history()) == 0


class TestToolResult:
    """工具结果测试"""

    def test_result_creation(self):
        """测试创建结果"""
        result = ToolResult(
            tool_name="echo",
            status=ToolStatus.SUCCESS,
            result="Echo: test",
            arguments={"message": "test"},
            execution_time_ms=50.0,
        )

        assert result.tool_name == "echo"
        assert result.status == ToolStatus.SUCCESS
        assert result.result == "Echo: test"

    def test_result_is_success(self):
        """测试是否成功"""
        success_result = ToolResult(tool_name="test", status=ToolStatus.SUCCESS)
        failed_result = ToolResult(tool_name="test", status=ToolStatus.FAILED)

        assert success_result.is_success() == True
        assert failed_result.is_success() == False

    def test_result_to_dict(self):
        """测试结果转字典"""
        result = ToolResult(
            tool_name="echo",
            status=ToolStatus.SUCCESS,
            result="test",
            arguments={"msg": "test"},
            execution_time_ms=50.0,
            iteration=1,
        )

        dict_result = result.to_dict()
        assert dict_result["tool_name"] == "echo"
        assert dict_result["status"] == "success"

    def test_result_to_context_string(self):
        """测试结果转上下文字符串"""
        success_result = ToolResult(
            tool_name="echo",
            status=ToolStatus.SUCCESS,
            result="Echo: test",
        )
        failed_result = ToolResult(
            tool_name="echo",
            status=ToolStatus.FAILED,
            error="Execution failed",
        )

        success_str = success_result.to_context_string()
        assert "succeeded" in success_str

        failed_str = failed_result.to_context_string()
        assert "failed" in failed_str


class TestToolRegistry:
    """工具注册表测试"""

    def test_registry_creation(self):
        """测试创建注册表"""
        registry = ToolRegistry()
        assert len(registry.list_tools()) == 0

    def test_register_tool(self):
        """测试注册工具"""
        registry = ToolRegistry()

        def test_func(x: int) -> int:
            return x * 2

        registry.register(
            "double",
            test_func,
            description="Double a number",
            parameters={"x": {"type": "int"}},
        )

        assert "double" in registry.list_tools()

    def test_get_tool(self):
        """测试获取工具"""
        registry = ToolRegistry()

        def test_func():
            return "test"

        registry.register("test", test_func)

        func = registry.get("test")
        assert func() == "test"

    def test_get_tool_info(self):
        """测试获取工具信息"""
        registry = ToolRegistry()

        registry.register(
            "echo",
            lambda x: x,
            description="Echo function",
            parameters={"x": {"type": "string"}},
        )

        info = registry.get_info("echo")
        assert info["description"] == "Echo function"

    def test_unregister_tool(self):
        """测试注销工具"""
        registry = ToolRegistry()
        registry.register("test", lambda: "test")

        registry.unregister("test")
        assert "test" not in registry.list_tools()

    def test_get_tool_definitions(self):
        """测试获取工具定义"""
        registry = ToolRegistry()

        registry.register(
            "add",
            lambda a, b: a + b,
            description="Add two numbers",
            parameters={"a": {"type": "int"}, "b": {"type": "int"}},
        )

        definitions = registry.get_tool_definitions()
        assert len(definitions) == 1
        assert definitions[0]["name"] == "add"


class TestToolConfig:
    """工具配置测试"""

    def test_config_defaults(self):
        """测试默认配置"""
        config = ToolConfig()

        assert config.default_timeout_ms == 30000
        assert config.max_retries == 3
        assert config.max_concurrent_calls == 5

    def test_config_custom(self):
        """测试自定义配置"""
        config = ToolConfig(
            max_retries=5,
            default_timeout_ms=60000,
            log_tool_calls=False,
        )

        assert config.max_retries == 5
        assert config.default_timeout_ms == 60000
        assert config.log_tool_calls == False


class TestHermesStyleToolExecutor:
    """Hermes 风格工具执行器测试"""

    @pytest.fixture
    def executor(self):
        """创建 Hermes 风格执行器"""
        return HermesStyleToolExecutor()

    def test_hermes_executor_creation(self):
        """测试创建 Hermes 执行器"""
        executor = HermesStyleToolExecutor()
        assert executor is not None

    def test_format_for_llm(self):
        """测试格式化供 LLM 使用"""
        executor = HermesStyleToolExecutor()

        results = [
            ToolResult(tool_name="get_cpu", status=ToolStatus.SUCCESS, result="85%"),
            ToolResult(tool_name="get_mem", status=ToolStatus.FAILED, error="timeout"),
        ]

        formatted = executor.format_for_llm(results)
        assert "get_cpu" in formatted
        assert "succeeded" in formatted.lower() or "success" in formatted.lower()
        assert "failed" in formatted.lower()


class TestToolStatus:
    """工具状态枚举测试"""

    def test_tool_status_values(self):
        """测试工具状态值"""
        assert ToolStatus.SUCCESS.value == "success"
        assert ToolStatus.FAILED.value == "failed"
        assert ToolStatus.TIMEOUT.value == "timeout"
        assert ToolStatus.PENDING.value == "pending"
        assert ToolStatus.RUNNING.value == "running"