"""RouterAgent 单元测试"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from rds_agent.router.agent import (
    RouterAgent,
    AgentType,
    ComplexityLevel,
    get_router_agent,
    create_router_agent,
)
from rds_agent.core.state import IntentType


class TestRouterAgentInit:
    """RouterAgent 初始化测试"""

    def test_init_default_config(self):
        """测试默认配置初始化"""
        with patch("rds_agent.router.agent.settings") as mock_settings:
            mock_settings.agent.type = "auto"
            mock_settings.hermes.enabled = True

            agent = RouterAgent()
            assert agent.agent_type == AgentType.AUTO
            assert agent.enable_hermes == True

    def test_init_override_agent_type(self):
        """测试配置覆盖 Agent 类型"""
        agent = RouterAgent(agent_type=AgentType.HERMES)
        assert agent.agent_type == AgentType.HERMES

    def test_init_override_hermes_disabled(self):
        """测试配置覆盖 Hermes 禁用"""
        agent = RouterAgent(enable_hermes=False)
        assert agent.enable_hermes == False


class TestComplexityEvaluation:
    """复杂度评估测试"""

    def test_complexity_simple_instance_query(self):
        """测试简单任务 - 实例查询"""
        agent = RouterAgent()
        complexity = agent.evaluate_complexity("查看实例列表")
        assert complexity == ComplexityLevel.SIMPLE

    def test_complexity_simple_parameter(self):
        """测试简单任务 - 参数查询"""
        agent = RouterAgent()
        complexity = agent.evaluate_complexity("查看innodb参数配置")
        assert complexity == ComplexityLevel.SIMPLE

    def test_complexity_simple_knowledge(self):
        """测试简单任务 - 知识问答"""
        agent = RouterAgent()
        complexity = agent.evaluate_complexity("为什么MySQL会产生慢查询")
        assert complexity == ComplexityLevel.SIMPLE

    def test_complexity_medium_performance(self):
        """测试中等任务 - 性能诊断"""
        agent = RouterAgent()
        complexity = agent.evaluate_complexity("db-01的性能情况")
        assert complexity == ComplexityLevel.MEDIUM

    def test_complexity_medium_sql(self):
        """测试中等任务 - SQL诊断"""
        agent = RouterAgent()
        complexity = agent.evaluate_complexity("分析慢SQL")
        assert complexity == ComplexityLevel.MEDIUM

    def test_complexity_medium_connection(self):
        """测试中等任务 - 连接诊断"""
        agent = RouterAgent()
        complexity = agent.evaluate_complexity("检查连接数和锁等待")
        assert complexity == ComplexityLevel.MEDIUM

    def test_complexity_complex_full_inspection(self):
        """测试复杂任务 - 完整巡检"""
        agent = RouterAgent()
        complexity = agent.evaluate_complexity("对db-01做完整巡检")
        assert complexity == ComplexityLevel.COMPLEX

    def test_complexity_complex_health_check(self):
        """测试复杂任务 - 健康检查"""
        agent = RouterAgent()
        complexity = agent.evaluate_complexity("完整检查db-prod-01")
        assert complexity == ComplexityLevel.COMPLEX

    def test_complexity_complex_deep_analysis(self):
        """测试复杂任务 - 深度分析关键词"""
        agent = RouterAgent()
        # 中等意图 + 深度分析关键词 → COMPLEX
        complexity = agent.evaluate_complexity("详细分析db-01的性能问题")
        assert complexity == ComplexityLevel.COMPLEX


class TestAgentSelection:
    """Agent 选择测试"""

    def test_select_agent_simple_to_hermes(self):
        """测试简单任务选择 Hermes"""
        agent = RouterAgent(enable_hermes=True)
        selected = agent.select_agent("查看实例信息")
        assert selected == AgentType.HERMES

    def test_select_agent_medium_to_langgraph(self):
        """测试中等任务选择 LangGraph"""
        agent = RouterAgent(enable_hermes=True)
        selected = agent.select_agent("db-01的性能情况")
        assert selected == AgentType.LANGGRAPH

    def test_select_agent_complex_to_diagnostic(self):
        """测试复杂任务选择 Diagnostic"""
        agent = RouterAgent(enable_hermes=True)
        selected = agent.select_agent("完整巡检db-01")
        assert selected == AgentType.DIAGNOSTIC

    def test_select_agent_hermes_disabled_fallback(self):
        """测试 Hermes 禁用时回退到 LangGraph"""
        agent = RouterAgent(enable_hermes=False)
        selected = agent.select_agent("查看实例信息")
        assert selected == AgentType.LANGGRAPH

    def test_select_agent_hermes_disabled_complex_to_diagnostic(self):
        """测试 Hermes 禁用时复杂任务仍使用 Diagnostic"""
        agent = RouterAgent(enable_hermes=False)
        selected = agent.select_agent("完整巡检db-01")
        assert selected == AgentType.DIAGNOSTIC

    def test_select_agent_config_override_hermes(self):
        """测试配置强制指定 Hermes"""
        agent = RouterAgent(agent_type=AgentType.HERMES, enable_hermes=True)
        # 简单任务仍使用 Hermes
        selected = agent.select_agent("查看实例信息")
        assert selected == AgentType.HERMES

    def test_select_agent_config_override_hermes_complex(self):
        """测试配置指定 Hermes 但复杂任务强制使用 Diagnostic"""
        agent = RouterAgent(agent_type=AgentType.HERMES, enable_hermes=True)
        # 复杂任务强制使用 Diagnostic
        selected = agent.select_agent("完整巡检db-01")
        assert selected == AgentType.DIAGNOSTIC

    def test_select_agent_config_override_langgraph(self):
        """测试配置强制指定 LangGraph"""
        agent = RouterAgent(agent_type=AgentType.LANGGRAPH)
        # 所有任务使用 LangGraph
        selected = agent.select_agent("查看实例信息")
        assert selected == AgentType.LANGGRAPH


class TestQuickIntentClassify:
    """快速意图识别测试"""

    def test_intent_instance(self):
        """测试实例意图识别"""
        agent = RouterAgent()
        intent = agent._quick_intent_classify("查看db-prod实例的规格")
        assert intent == IntentType.INSTANCE_QUERY

    def test_intent_performance(self):
        """测试性能意图识别"""
        agent = RouterAgent()
        intent = agent._quick_intent_classify("检查QPS和TPS")
        assert intent == IntentType.PERFORMANCE_DIAG

    def test_intent_sql(self):
        """测试SQL意图识别"""
        agent = RouterAgent()
        intent = agent._quick_intent_classify("分析慢SQL语句")
        assert intent == IntentType.SQL_DIAG

    def test_intent_connection(self):
        """测试连接意图识别"""
        agent = RouterAgent()
        intent = agent._quick_intent_classify("查看连接数")
        assert intent == IntentType.CONNECTION_DIAG

    def test_intent_storage(self):
        """测试存储意图识别"""
        agent = RouterAgent()
        intent = agent._quick_intent_classify("检查存储空间")
        assert intent == IntentType.STORAGE_DIAG

    def test_intent_parameter(self):
        """测试参数意图识别"""
        agent = RouterAgent()
        intent = agent._quick_intent_classify("查看innodb配置")
        assert intent == IntentType.PARAMETER_QUERY

    def test_intent_knowledge(self):
        """测试知识意图识别"""
        agent = RouterAgent()
        intent = agent._quick_intent_classify("如何优化MySQL性能")
        assert intent == IntentType.KNOWLEDGE_QA

    def test_intent_general_no_match(self):
        """测试无匹配时返回通用意图"""
        agent = RouterAgent()
        intent = agent._quick_intent_classify("你好")
        assert intent == IntentType.GENERAL_CHAT


class TestInstanceExtraction:
    """实例名称提取测试"""

    def test_extract_db_pattern(self):
        """测试 db-xxx 模式"""
        agent = RouterAgent()
        instance = agent._extract_instance("查看db-prod-01的信息")
        assert instance == "db-prod-01"

    def test_extract_inst_pattern(self):
        """测试 inst-xxx 模式"""
        agent = RouterAgent()
        instance = agent._extract_instance("检查inst-test-01的状态")
        assert instance == "inst-test-01"

    def test_extract_chinese_pattern(self):
        """测试中文描述模式"""
        agent = RouterAgent()
        instance = agent._extract_instance("对实例 prod-01 做诊断")
        assert instance == "prod-01"

    def test_extract_no_instance(self):
        """测试无实例名称"""
        agent = RouterAgent()
        instance = agent._extract_instance("查看所有实例列表")
        assert instance is None


class TestInvoke:
    """invoke 执行测试"""

    @patch("rds_agent.router.agent.HermesAgent")
    def test_invoke_hermes(self, mock_hermes_class):
        """测试 Hermes Agent 执行"""
        mock_hermes = MagicMock()
        mock_hermes.invoke.return_value = {"response": "test result", "tool_calls": []}
        mock_hermes_class.return_value = mock_hermes

        agent = RouterAgent(enable_hermes=True)
        agent._hermes_agent = mock_hermes

        result = agent.invoke("查看实例列表")

        assert result["agent_type"] == AgentType.HERMES.value
        assert result["complexity"] == ComplexityLevel.SIMPLE.value
        assert result["response"] == "test result"

    @patch("rds_agent.router.agent.RDSAgent")
    def test_invoke_langgraph(self, mock_langgraph_class):
        """测试 LangGraph Agent 执行"""
        mock_langgraph = MagicMock()
        mock_langgraph.invoke.return_value = {"response": "test response", "intent": "performance_diag"}
        mock_langgraph_class.return_value = mock_langgraph

        agent = RouterAgent(enable_hermes=False)
        agent._langgraph_agent = mock_langgraph

        result = agent.invoke("db-01性能情况", thread_id="test-thread")

        assert result["agent_type"] == AgentType.LANGGRAPH.value
        assert result["complexity"] == ComplexityLevel.MEDIUM.value
        assert result["response"] == "test response"

    @patch("rds_agent.router.agent.DiagnosticAgent")
    def test_invoke_diagnostic(self, mock_diagnostic_class):
        """测试 Diagnostic Agent 执行"""
        mock_diagnostic = MagicMock()
        mock_result = Mock(
            instance_name="db-01",
            overall_status=Mock(value="healthy"),
            overall_score=85,
            critical_issues=[],
            warnings=["test warning"],
            suggestions=["test suggestion"],
            start_time="2024-01-01",
            end_time="2024-01-01",
        )
        mock_diagnostic.full_inspection.return_value = mock_result
        mock_diagnostic_class.return_value = mock_diagnostic

        agent = RouterAgent(enable_hermes=True)
        agent._diagnostic_agent = mock_diagnostic

        result = agent.invoke("完整巡检db-01")

        assert result["agent_type"] == AgentType.DIAGNOSTIC.value
        assert result["complexity"] == ComplexityLevel.COMPLEX.value
        assert "诊断报告" in result["response"]


class TestChat:
    """chat 简化接口测试"""

    def test_chat_returns_response(self):
        """测试 chat 返回响应字符串"""
        agent = RouterAgent(enable_hermes=True)

        with patch.object(agent, "invoke") as mock_invoke:
            mock_invoke.return_value = {"response": "test response", "agent_type": "hermes"}

            response = agent.chat("测试消息")

            assert response == "test response"
            mock_invoke.assert_called_once_with("测试消息", None)

    def test_chat_with_thread_id(self):
        """测试 chat 携带 thread_id"""
        agent = RouterAgent(enable_hermes=True)

        with patch.object(agent, "invoke") as mock_invoke:
            mock_invoke.return_value = {"response": "test response"}

            response = agent.chat("测试消息", thread_id="test-thread")

            assert response == "test response"
            mock_invoke.assert_called_once_with("测试消息", "test-thread")


class TestGetRouterAgent:
    """get_router_agent 函数测试"""

    def test_get_router_agent_singleton(self):
        """测试单例模式"""
        # 重置全局实例
        import rds_agent.router.agent as router_module
        router_module._router_agent = None

        agent1 = get_router_agent()
        agent2 = get_router_agent()

        assert agent1 is agent2

    def test_create_router_agent_new_instance(self):
        """测试创建新实例"""
        agent1 = create_router_agent()
        agent2 = create_router_agent()

        assert agent1 is not agent2


class TestReset:
    """reset 测试"""

    def test_reset_clears_sessions(self):
        """测试重置会话"""
        agent = RouterAgent()

        mock_langgraph = MagicMock()
        mock_hermes = MagicMock()
        agent._langgraph_agent = mock_langgraph
        agent._hermes_agent = mock_hermes

        agent.reset("test-thread")

        mock_langgraph.reset.assert_called_once_with("test-thread")
        mock_hermes.clear_history.assert_called_once()