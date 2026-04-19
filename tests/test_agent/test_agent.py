"""Agent主类测试。"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from langchain_core.messages import HumanMessage

from rds_agent.core.agent import RDSAgent, get_agent
from rds_agent.core.state import AgentState, IntentType


class TestRDSAgent:
    """RDS Agent主类测试"""

    @pytest.fixture
    def mock_checkpointer(self):
        """Mock检查点"""
        return MagicMock()

    @pytest.fixture
    def agent(self, mock_checkpointer):
        """Agent fixture"""
        with patch("rds_agent.core.agent.RDSAgent._build_graph"):
            agent = RDSAgent(checkpointer=mock_checkpointer)
            agent.graph = MagicMock()
            agent.app = MagicMock()
            return agent

    def test_agent_creation(self, mock_checkpointer):
        """测试Agent创建"""
        agent = RDSAgent(checkpointer=mock_checkpointer)
        assert agent.checkpointer == mock_checkpointer
        assert agent.graph is not None

    def test_agent_creation_default_checkpointer(self):
        """测试默认检查点"""
        with patch("rds_agent.core.agent.RDSAgent._build_graph"):
            from langgraph.checkpoint.memory import MemorySaver
            agent = RDSAgent()
            assert isinstance(agent.checkpointer, MemorySaver)

    def test_build_graph_structure(self, mock_checkpointer):
        """测试构建图结构"""
        from langgraph.graph import StateGraph

        agent = RDSAgent(checkpointer=mock_checkpointer)

        # 检查图是StateGraph
        assert isinstance(agent.graph, StateGraph)

    def test_invoke(self, agent):
        """测试invoke方法"""
        mock_result = {
            "response": "测试响应",
            "intent": IntentType.INSTANCE_QUERY,
        }
        agent.app.invoke.return_value = mock_result

        result = agent.invoke("查看实例列表", thread_id="test-thread")

        assert result["response"] == "测试响应"
        agent.app.invoke.assert_called_once()

    def test_invoke_with_messages(self, agent):
        """测试带消息的invoke"""
        messages = [HumanMessage(content="历史消息")]
        agent.app.invoke.return_value = {"response": "响应"}

        result = agent.invoke("新消息", thread_id="test", messages=messages)

        # 应使用提供的消息
        call_args = agent.app.invoke.call_args[0][0]
        assert len(call_args["messages"]) >= 1

    def test_stream(self, agent):
        """测试流式执行"""
        agent.app.stream.return_value = [
            {"classify": {"intent": IntentType.INSTANCE_QUERY}},
            {"respond": {"response": "响应"}},
        ]

        events = list(agent.stream("查询实例", thread_id="test"))

        assert len(events) == 2
        agent.app.stream.assert_called_once()

    def test_chat(self, agent):
        """测试chat方法"""
        agent.invoke.return_value = {
            "response": "这是回答",
            "intent": IntentType.INSTANCE_QUERY,
        }

        response = agent.chat("查看实例列表", thread_id="test")

        assert response == "这是回答"

    def test_chat_error_handling(self, agent):
        """测试chat错误处理"""
        agent.invoke.return_value = {
            "response": None,
            "error": "处理失败",
        }

        response = agent.chat("无效问题")
        assert "无法生成响应" in response or response is None

    def test_get_state(self, agent):
        """测试获取状态"""
        mock_state = {"messages": [], "intent": IntentType.UNKNOWN}
        agent.app.get_state.return_value = mock_state

        state = agent.get_state("test-thread")
        assert state == mock_state

    def test_get_state_not_found(self, agent):
        """测试获取不存在线程的状态"""
        agent.app.get_state.side_effect = Exception("Not found")

        state = agent.get_state("nonexistent")
        assert state is None

    def test_reset(self, agent):
        """测试重置会话"""
        agent.reset("test-thread")
        agent.app.update_state.assert_called_once()

    def test_reset_error(self, agent):
        """测试重置失败"""
        agent.app.update_state.side_effect = Exception("Reset failed")

        # 不应抛出异常
        agent.reset("test-thread")


class TestRDSAgentRouting:
    """Agent路由测试"""

    @pytest.fixture
    def agent(self):
        """Agent fixture"""
        agent = RDSAgent()
        return agent

    def test_route_after_classify_need_instance(self, agent):
        """测试需要实例的路由"""
        state: AgentState = {
            "intent": IntentType.PERFORMANCE_DIAG,
            "target_instance": None,
            "needs_tool_call": True,
            "error": None,
        }

        route = agent._route_after_classify(state)
        assert route == "need_instance"

    def test_route_after_classify_need_tools(self, agent):
        """测试需要工具的路由"""
        state: AgentState = {
            "intent": IntentType.KNOWLEDGE_QA,
            "target_instance": None,
            "needs_tool_call": True,
            "error": None,
        }

        route = agent._route_after_classify(state)
        assert route == "need_tools"

    def test_route_after_classify_error(self, agent):
        """测试错误路由"""
        state: AgentState = {
            "intent": IntentType.UNKNOWN,
            "target_instance": None,
            "needs_tool_call": False,
            "error": "发生错误",
        }

        route = agent._route_after_classify(state)
        assert route == "error"

    def test_route_after_classify_respond(self, agent):
        """测试直接响应路由"""
        state: AgentState = {
            "intent": IntentType.GENERAL_CHAT,
            "target_instance": None,
            "needs_tool_call": False,
            "error": None,
        }

        route = agent._route_after_classify(state)
        assert route == "respond_directly"

    def test_route_after_check_instance_need_tools(self, agent):
        """测试实例检查后需要工具"""
        state: AgentState = {
            "intent": IntentType.PERFORMANCE_DIAG,
            "target_instance": "db-prod-01",
            "needs_tool_call": True,
            "error": None,
        }

        route = agent._route_after_check_instance(state)
        assert route == "need_tools"

    def test_route_after_check_instance_respond(self, agent):
        """测试实例检查后直接响应"""
        state: AgentState = {
            "intent": IntentType.INSTANCE_QUERY,
            "target_instance": None,
            "needs_tool_call": False,
            "response": "请指定实例",
            "error": None,
        }

        route = agent._route_after_check_instance(state)
        assert route == "respond_directly"

    def test_route_after_check_instance_error(self, agent):
        """测试实例检查后错误"""
        state: AgentState = {
            "intent": IntentType.PERFORMANCE_DIAG,
            "target_instance": None,
            "needs_tool_call": True,
            "error": "无法获取实例",
        }

        route = agent._route_after_check_instance(state)
        assert route == "error"


class TestGetAgent:
    """获取Agent实例测试"""

    def test_get_agent_singleton(self):
        """测试单例模式"""
        # 清除全局实例
        import rds_agent.core.agent as agent_module
        agent_module._agent = None

        with patch("rds_agent.core.agent.RDSAgent") as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent

            agent1 = get_agent()
            agent2 = get_agent()

            assert agent1 == agent2
            mock_agent_class.assert_called_once()

    def test_get_agent_existing(self):
        """测试已有实例"""
        import rds_agent.core.agent as agent_module
        mock_agent = MagicMock()
        agent_module._agent = mock_agent

        agent = get_agent()
        assert agent == mock_agent