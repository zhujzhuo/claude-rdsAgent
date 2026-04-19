"""Agent节点函数测试。"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage

from rds_agent.core.nodes import (
    classify_intent,
    check_instance,
    select_tools,
    execute_tools,
    generate_response,
    handle_error,
    extract_instance_name,
    get_llm,
    INTENT_KEYWORDS,
)
from rds_agent.core.state import AgentState, IntentType


class TestExtractInstanceName:
    """实例名称提取测试"""

    def test_extract_instance_name_db_pattern(self):
        """测试db-模式"""
        message = "查询db-prod-01的性能"
        result = extract_instance_name(message)
        assert result == "db-prod-01"

    def test_extract_instance_name_inst_pattern(self):
        """测试inst-模式"""
        message = "inst-003实例状态如何"
        result = extract_instance_name(message)
        assert result == "inst-003"

    def test_extract_instance_name_quoted(self):
        """测试引号模式"""
        message = "查看实例\"db-test\"的信息"
        result = extract_instance_name(message)
        assert result == "db-test"

    def test_extract_instance_name_suffix(self):
        """测试后缀模式"""
        message = "prod01实例的性能情况"
        result = extract_instance_name(message)
        assert result == "prod01"

    def test_extract_instance_name_not_found(self):
        """测试未找到实例名"""
        message = "查看所有实例列表"
        result = extract_instance_name(message)
        assert result is None

    def test_extract_instance_name_multiple(self):
        """测试多个实例名（返回第一个）"""
        message = "db-prod-01和db-prod-02的对比"
        result = extract_instance_name(message)
        assert result == "db-prod-01"


class TestClassifyIntent:
    """意图识别节点测试"""

    @pytest.fixture
    def base_state(self):
        """基础状态"""
        return {
            "messages": [HumanMessage(content="测试消息")],
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

    def test_classify_intent_instance_query(self, base_state):
        """测试实例查询意图"""
        base_state["messages"] = [HumanMessage(content="查看实例列表")]
        result = classify_intent(base_state)

        assert result["intent"] == IntentType.INSTANCE_QUERY
        assert result["current_node"] == "classify"

    def test_classify_intent_performance_diag(self, base_state):
        """测试性能诊断意图"""
        base_state["messages"] = [HumanMessage(content="db-prod-01的性能情况")]
        result = classify_intent(base_state)

        assert result["intent"] == IntentType.PERFORMANCE_DIAG
        assert result["target_instance"] == "db-prod-01"
        assert result["needs_tool_call"]

    def test_classify_intent_sql_diag(self, base_state):
        """测试SQL诊断意图"""
        base_state["messages"] = [HumanMessage(content="获取慢SQL列表")]
        result = classify_intent(base_state)

        assert result["intent"] == IntentType.SQL_DIAG

    def test_classify_intent_connection_diag(self, base_state):
        """测试连接诊断意图"""
        base_state["messages"] = [HumanMessage(content="检查连接数")]
        result = classify_intent(base_state)

        assert result["intent"] == IntentType.CONNECTION_DIAG

    def test_classify_intent_storage_diag(self, base_state):
        """测试存储分析意图"""
        base_state["messages"] = [HumanMessage(content="空间使用情况")]
        result = classify_intent(base_state)

        assert result["intent"] == IntentType.STORAGE_DIAG

    def test_classify_intent_parameter_query(self, base_state):
        """测试参数查询意图"""
        base_state["messages"] = [HumanMessage(content="查看参数配置")]
        result = classify_intent(base_state)

        assert result["intent"] == IntentType.PARAMETER_QUERY

    def test_classify_intent_knowledge_qa(self, base_state):
        """测试知识问答意图"""
        base_state["messages"] = [HumanMessage(content="如何优化慢查询")]
        result = classify_intent(base_state)

        assert result["intent"] == IntentType.KNOWLEDGE_QA

    def test_classify_intent_general_chat(self, base_state):
        """测试通用聊天意图"""
        base_state["messages"] = [HumanMessage(content="你好")]
        result = classify_intent(base_state)

        # 如果关键词匹配不到，会尝试LLM或返回GENERAL_CHAT
        assert result["intent"] in [IntentType.GENERAL_CHAT, IntentType.KNOWLEDGE_QA]

    def test_classify_intent_with_instance_extraction(self, base_state):
        """测试意图识别时提取实例"""
        base_state["messages"] = [HumanMessage(content="db-prod-01的慢查询")]
        result = classify_intent(base_state)

        assert result["target_instance"] == "db-prod-01"


class TestCheckInstance:
    """实例检查节点测试"""

    @pytest.fixture
    def base_state(self):
        return {
            "messages": [],
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

    def test_check_instance_has_instance(self, base_state):
        """测试已指定实例"""
        base_state["target_instance"] = "db-prod-01"
        base_state["intent"] = IntentType.PERFORMANCE_DIAG

        result = check_instance(base_state)
        assert result["target_instance"] == "db-prod-01"

    def test_check_instance_knowledge_qa_no_instance_needed(self, base_state):
        """测试知识问答不需要实例"""
        base_state["intent"] = IntentType.KNOWLEDGE_QA
        base_state["target_instance"] = None

        result = check_instance(base_state)
        # 知识问答不需要实例检查
        assert result["current_node"] == "check_instance"

    def test_check_instance_no_instance_single_available(self, base_state):
        """测试只有一个实例时自动选择"""
        base_state["target_instance"] = None
        base_state["intent"] = IntentType.PERFORMANCE_DIAG

        with patch("rds_agent.core.nodes.get_instance_list") as mock_list:
            import json
            mock_list.invoke.return_value = json.dumps([{"name": "db-only-01"}])

            result = check_instance(base_state)
            # 单实例自动选择
            assert result["target_instance"] == "db-only-01"


class TestSelectTools:
    """工具选择节点测试"""

    @pytest.fixture
    def base_state(self):
        return {
            "messages": [],
            "intent": IntentType.PERFORMANCE_DIAG,
            "target_instance": "db-prod-01",
            "tool_calls": [],
            "tool_results": [],
            "context": {},
            "current_node": "",
            "needs_tool_call": True,
            "response": None,
            "error": None,
        }

    def test_select_tools_performance_diag(self, base_state):
        """测试性能诊断工具选择"""
        result = select_tools(base_state)

        assert len(result["tool_calls"]) >= 1
        tool_names = [tc["tool_name"] for tc in result["tool_calls"]]
        assert "get_performance_metrics" in tool_names

    def test_select_tools_sql_diag(self, base_state):
        """测试SQL诊断工具选择"""
        base_state["intent"] = IntentType.SQL_DIAG

        result = select_tools(base_state)
        tool_names = [tc["tool_name"] for tc in result["tool_calls"]]
        assert "get_slow_queries" in tool_names

    def test_select_tools_connection_diag(self, base_state):
        """测试连接诊断工具选择"""
        base_state["intent"] = IntentType.CONNECTION_DIAG

        result = select_tools(base_state)
        tool_names = [tc["tool_name"] for tc in result["tool_calls"]]
        assert "get_connection_status" in tool_names

    def test_select_tools_storage_diag(self, base_state):
        """测试存储分析工具选择"""
        base_state["intent"] = IntentType.STORAGE_DIAG

        result = select_tools(base_state)
        tool_names = [tc["tool_name"] for tc in result["tool_calls"]]
        assert "get_storage_usage" in tool_names

    def test_select_tools_with_instance_arg(self, base_state):
        """测试工具参数包含实例"""
        result = select_tools(base_state)

        for tc in result["tool_calls"]:
            if "instance_name" in tc.get("arguments", {}):
                assert tc["arguments"]["instance_name"] == "db-prod-01"


class TestExecuteTools:
    """工具执行节点测试"""

    @pytest.fixture
    def base_state(self):
        return {
            "messages": [],
            "intent": IntentType.INSTANCE_QUERY,
            "target_instance": "db-prod-01",
            "tool_calls": [
                {"tool_name": "get_instance_list", "arguments": {}, "timestamp": ""},
            ],
            "tool_results": [],
            "context": {},
            "current_node": "",
            "needs_tool_call": True,
            "response": None,
            "error": None,
        }

    def test_execute_tools_success(self, base_state):
        """测试工具执行成功"""
        with patch("rds_agent.core.nodes.get_all_langchain_tools") as mock_tools:
            mock_tool = MagicMock()
            mock_tool.name = "get_instance_list"
            mock_tool.invoke.return_value = '{"id": "1", "name": "test"}'
            mock_tools.return_value = [mock_tool]

            result = execute_tools(base_state)

            assert len(result["tool_results"]) == 1
            assert result["tool_calls"][0]["success"]

    def test_execute_tools_multiple(self, base_state):
        """测试执行多个工具"""
        base_state["tool_calls"] = [
            {"tool_name": "get_performance_metrics", "arguments": {"instance_name": "db-prod-01"}},
            {"tool_name": "get_slow_queries", "arguments": {"instance_name": "db-prod-01"}},
        ]

        with patch("rds_agent.core.nodes.get_all_langchain_tools") as mock_tools:
            mock_perf = MagicMock()
            mock_perf.name = "get_performance_metrics"
            mock_perf.invoke.return_value = '{"qps": 1000}'

            mock_slow = MagicMock()
            mock_slow.name = "get_slow_queries"
            mock_slow.invoke.return_value = '{"queries": []}'

            mock_tools.return_value = [mock_perf, mock_slow]

            result = execute_tools(base_state)

            assert len(result["tool_results"]) == 2

    def test_execute_tools_failure(self, base_state):
        """测试工具执行失败"""
        base_state["tool_calls"] = [
            {"tool_name": "nonexistent_tool", "arguments": {}},
        ]

        with patch("rds_agent.core.nodes.get_all_langchain_tools") as mock_tools:
            mock_tools.return_value = []

            result = execute_tools(base_state)

            assert "错误" in result["tool_results"][0]
            assert not result["tool_calls"][0]["success"]


class TestGenerateResponse:
    """响应生成节点测试"""

    @pytest.fixture
    def base_state(self):
        return {
            "messages": [HumanMessage(content="查询实例列表")],
            "intent": IntentType.INSTANCE_QUERY,
            "target_instance": None,
            "tool_calls": [],
            "tool_results": ['{"instances": [{"name": "db-01"}]}'],
            "context": {},
            "current_node": "",
            "needs_tool_call": True,
            "response": None,
            "error": None,
        }

    def test_generate_response_with_tool_results(self, base_state):
        """测试有工具结果时生成响应"""
        with patch("rds_agent.core.nodes.get_llm") as mock_llm:
            mock_llm_instance = MagicMock()
            mock_llm_instance.invoke.return_value = "当前有1个实例: db-01"
            mock_llm.return_value = mock_llm_instance

            result = generate_response(base_state)

            assert result["response"] is not None
            assert result["current_node"] == "respond"
            assert len(result["messages"]) == 2  # 原始消息 + AI响应

    def test_generate_response_adds_ai_message(self, base_state):
        """测试添加AI消息到历史"""
        with patch("rds_agent.core.nodes.get_llm") as mock_llm:
            mock_llm_instance = MagicMock()
            mock_llm_instance.invoke.return_value = "AI回答"
            mock_llm.return_value = mock_llm_instance

            result = generate_response(base_state)

            # 检查最后一条消息是AIMessage
            last_msg = result["messages"][-1]
            assert isinstance(last_msg, AIMessage)


class TestHandleError:
    """错误处理节点测试"""

    def test_handle_error_basic(self):
        """测试基本错误处理"""
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
            "error": "连接超时",
        }

        result = handle_error(state)

        assert result["response"] is not None
        assert "连接超时" in result["response"]
        assert result["current_node"] == "error"


class TestGetLLM:
    """获取LLM测试"""

    def test_get_llm(self):
        """测试获取LLM实例"""
        with patch("rds_agent.core.nodes.settings") as mock_settings:
            mock_settings.ollama.model = "qwen2.5:14b"
            mock_settings.ollama.host = "http://localhost:11434"

            with patch("rds_agent.core.nodes.Ollama") as mock_ollama:
                llm = get_llm()
                mock_ollama.assert_called_once()