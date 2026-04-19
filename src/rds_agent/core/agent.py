"""LangGraph Agent主类。"""

from typing import Optional, Sequence

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from rds_agent.core.state import AgentState, IntentType
from rds_agent.core.nodes import (
    classify_intent,
    check_instance,
    select_tools,
    execute_tools,
    generate_response,
    handle_error,
)
from rds_agent.utils.logger import get_logger

logger = get_logger("agent")


class RDSAgent:
    """RDS智能助手Agent"""

    def __init__(self, checkpointer: Optional[MemorySaver] = None):
        """初始化Agent"""
        self.checkpointer = checkpointer or MemorySaver()
        self.graph = self._build_graph()
        self.app = self.graph.compile(checkpointer=self.checkpointer)
        logger.info("RDS Agent初始化完成")

    def _build_graph(self) -> StateGraph:
        """构建状态图"""
        # 创建状态图
        graph = StateGraph(AgentState)

        # 添加节点
        graph.add_node("classify", classify_intent)
        graph.add_node("check_instance", check_instance)
        graph.add_node("select_tools", select_tools)
        graph.add_node("execute_tools", execute_tools)
        graph.add_node("respond", generate_response)
        graph.add_node("error", handle_error)

        # 设置入口点
        graph.set_entry_point("classify")

        # 添加边（条件路由）
        graph.add_conditional_edges(
            "classify",
            self._route_after_classify,
            {
                "need_instance": "check_instance",
                "need_tools": "select_tools",
                "respond_directly": "respond",
                "error": "error",
            }
        )

        graph.add_conditional_edges(
            "check_instance",
            self._route_after_check_instance,
            {
                "need_tools": "select_tools",
                "respond_directly": "respond",
                "error": "error",
            }
        )

        graph.add_edge("select_tools", "execute_tools")
        graph.add_edge("execute_tools", "respond")

        graph.add_edge("respond", END)
        graph.add_edge("error", END)

        return graph

    def _route_after_classify(self, state: AgentState) -> str:
        """意图识别后的路由"""
        intent = state.get("intent")
        needs_tool = state.get("needs_tool_call", False)
        error = state.get("error")

        if error:
            return "error"

        if intent in [IntentType.KNOWLEDGE_QA, IntentType.GENERAL_CHAT]:
            # 知识问答或聊天，可以直接调用知识库工具
            state["target_instance"] = None
            return "need_tools"

        if needs_tool:
            # 需要调用工具，先检查实例
            return "need_instance"

        return "respond_directly"

    def _route_after_check_instance(self, state: AgentState) -> str:
        """实例检查后的路由"""
        error = state.get("error")
        needs_tool = state.get("needs_tool_call", True)

        if error:
            return "error"

        if not needs_tool:
            return "respond_directly"

        return "need_tools"

    def invoke(
        self,
        input_message: str,
        thread_id: Optional[str] = None,
        messages: Optional[Sequence[BaseMessage]] = None,
    ) -> AgentState:
        """执行Agent"""
        logger.info(f"接收输入: {input_message[:50]}...")

        # 构建初始状态
        initial_state: AgentState = {
            "messages": messages or [HumanMessage(content=input_message)],
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

        # 配置
        config = {"configurable": {"thread_id": thread_id or "default"}}

        # 执行
        result = self.app.invoke(initial_state, config)

        return result

    def stream(
        self,
        input_message: str,
        thread_id: Optional[str] = None,
    ):
        """流式执行Agent"""
        logger.info(f"流式接收输入: {input_message[:50]}...")

        initial_state: AgentState = {
            "messages": [HumanMessage(content=input_message)],
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

        config = {"configurable": {"thread_id": thread_id or "default"}}

        for event in self.app.stream(initial_state, config):
            yield event

    def chat(self, message: str, thread_id: Optional[str] = None) -> str:
        """简化的聊天接口"""
        result = self.invoke(message, thread_id)
        return result.get("response", "无法生成响应")

    def get_state(self, thread_id: str) -> Optional[AgentState]:
        """获取指定线程的状态"""
        config = {"configurable": {"thread_id": thread_id}}
        try:
            return self.app.get_state(config)
        except Exception:
            return None

    def reset(self, thread_id: str) -> None:
        """重置指定线程的状态"""
        config = {"configurable": {"thread_id": thread_id}}
        try:
            self.app.update_state(config, None)
        except Exception as e:
            logger.warning(f"重置状态失败: {e}")


# 全局Agent实例
_agent: Optional[RDSAgent] = None


def get_agent() -> RDSAgent:
    """获取Agent实例"""
    global _agent
    if _agent is None:
        _agent = RDSAgent()
    return _agent