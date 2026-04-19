"""Agent状态测试。"""

import pytest
from langchain_core.messages import HumanMessage, AIMessage

from rds_agent.core.state import (
    AgentState,
    IntentType,
    ConversationContext,
    ToolCallRecord,
)


class TestIntentType:
    """意图类型枚举测试"""

    def test_intent_types_exist(self):
        """测试所有意图类型存在"""
        assert IntentType.INSTANCE_QUERY == "instance_query"
        assert IntentType.PERFORMANCE_DIAG == "performance_diag"
        assert IntentType.SQL_DIAG == "sql_diag"
        assert IntentType.CONNECTION_DIAG == "connection_diag"
        assert IntentType.STORAGE_DIAG == "storage_diag"
        assert IntentType.PARAMETER_QUERY == "parameter_query"
        assert IntentType.KNOWLEDGE_QA == "knowledge_qa"
        assert IntentType.GENERAL_CHAT == "general_chat"
        assert IntentType.UNKNOWN == "unknown"

    def test_intent_type_string_conversion(self):
        """测试字符串转换"""
        intent = IntentType("performance_diag")
        assert intent == IntentType.PERFORMANCE_DIAG

    def test_intent_type_invalid(self):
        """测试无效意图类型"""
        with pytest.raises(ValueError):
            IntentType("invalid_intent")


class TestAgentState:
    """Agent状态测试"""

    def test_agent_state_creation(self):
        """测试创建Agent状态"""
        state: AgentState = {
            "messages": [HumanMessage(content="查询实例列表")],
            "intent": IntentType.INSTANCE_QUERY,
            "target_instance": None,
            "tool_calls": [],
            "tool_results": [],
            "context": {},
            "current_node": "",
            "needs_tool_call": True,
            "response": None,
            "error": None,
        }
        assert len(state["messages"]) == 1
        assert state["intent"] == IntentType.INSTANCE_QUERY

    def test_agent_state_messages_add(self):
        """测试消息添加"""
        state: AgentState = {
            "messages": [],
            "intent": IntentType.UNKNOWN,
            "target_instance": None,
            "tool_calls": [],
            "tool_results": [],
            "context": {},
            "current_node": "",
            "needs_tool_call": False,
            "response": None,
            "error": None,
        }

        # 添加消息
        state["messages"].append(HumanMessage(content="用户问题"))
        state["messages"].append(AIMessage(content="AI回答"))

        assert len(state["messages"]) == 2

    def test_agent_state_tool_calls(self):
        """测试工具调用记录"""
        state: AgentState = {
            "messages": [],
            "intent": IntentType.PERFORMANCE_DIAG,
            "target_instance": "db-prod-01",
            "tool_calls": [
                {"tool_name": "get_performance_metrics", "arguments": {"instance_name": "db-prod-01"}},
            ],
            "tool_results": ["性能指标数据"],
            "context": {},
            "current_node": "execute_tools",
            "needs_tool_call": False,
            "response": None,
            "error": None,
        }

        assert len(state["tool_calls"]) == 1
        assert state["tool_calls"][0]["tool_name"] == "get_performance_metrics"

    def test_agent_state_error(self):
        """测试错误状态"""
        state: AgentState = {
            "messages": [],
            "intent": IntentType.UNKNOWN,
            "target_instance": None,
            "tool_calls": [],
            "tool_results": [],
            "context": {},
            "current_node": "",
            "needs_tool_call": False,
            "response": None,
            "error": "连接失败",
        }

        assert state["error"] == "连接失败"


class TestConversationContext:
    """对话上下文测试"""

    def test_conversation_context_creation(self):
        """测试创建对话上下文"""
        context = ConversationContext(
            session_id="session-001",
            user_id="user-001",
            current_instance="db-prod-01",
        )
        assert context.session_id == "session-001"
        assert context.user_id == "user-001"
        assert context.current_instance == "db-prod-01"

    def test_conversation_context_defaults(self):
        """测试默认值"""
        context = ConversationContext()
        assert context.session_id == ""
        assert context.user_id is None
        assert context.current_instance is None
        assert context.mentioned_instances == []
        assert context.previous_intents == []
        assert context.turn_count == 0

    def test_conversation_context_mentioned_instances(self):
        """测试提及过的实例"""
        context = ConversationContext(
            mentioned_instances=["db-prod-01", "db-test-01"],
        )
        assert len(context.mentioned_instances) == 2

    def test_conversation_context_previous_intents(self):
        """测试之前的意图"""
        context = ConversationContext(
            previous_intents=[
                IntentType.INSTANCE_QUERY,
                IntentType.PERFORMANCE_DIAG,
            ],
        )
        assert len(context.previous_intents) == 2
        assert context.previous_intents[0] == IntentType.INSTANCE_QUERY


class TestToolCallRecord:
    """工具调用记录测试"""

    def test_tool_call_record_creation(self):
        """测试创建工具调用记录"""
        record = ToolCallRecord(
            tool_name="get_performance_metrics",
            arguments={"instance_name": "db-prod-01"},
            result="性能指标数据",
            success=True,
            timestamp="2024-01-01T10:00:00",
        )
        assert record.tool_name == "get_performance_metrics"
        assert record.arguments["instance_name"] == "db-prod-01"
        assert record.success

    def test_tool_call_record_defaults(self):
        """测试默认值"""
        record = ToolCallRecord(tool_name="test_tool")
        assert record.arguments == {}
        assert record.result is None
        assert record.success
        assert record.timestamp == ""

    def test_tool_call_record_failure(self):
        """测试失败记录"""
        record = ToolCallRecord(
            tool_name="get_instance_info",
            arguments={"instance_name": "nonexistent"},
            result="错误: 未找到实例",
            success=False,
        )
        assert not record.success