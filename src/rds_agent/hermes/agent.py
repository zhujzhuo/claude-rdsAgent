"""Hermes Agent 主类 - 基于 Hermes Function Calling 的智能 Agent。

特点:
- 原生 Function Calling 支持 (不需要 LangGraph)
- 多轮工具调用自动处理
- 与 RDS 工具层无缝集成
- 支持流式输出
"""

from typing import Any, Callable, Dict, List, Optional
import json

from .client import HermesClient
from .function_schema import FunctionSchema, ToolRegistry, ToolDefinition
from rds_agent.utils.logger import get_logger

logger = get_logger("hermes_agent")


class HermesAgent:
    """Hermes Agent - 基于 Hermes 模型的 Function Calling Agent"""

    def __init__(
        self,
        model: str = "hermes3",
        client: Optional[HermesClient] = None,
        tool_registry: Optional[ToolRegistry] = None,
        max_iterations: int = 10,
    ):
        """
        初始化 Hermes Agent

        Args:
            model: Hermes 模型名称
            client: Hermes 客户端 (可选)
            tool_registry: 工具注册中心 (可选)
            max_iterations: 最大工具调用迭代次数
        """
        self.client = client or HermesClient(model=model)
        self.tool_registry = tool_registry or ToolRegistry()
        self.max_iterations = max_iterations
        self._conversation_history: List[Dict[str, Any]] = []

        logger.info(f"Hermes Agent initialized with model: {model}")

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        required: List[str],
        handler: Callable,
    ) -> None:
        """注册工具"""
        self.tool_registry.register_function(
            name=name,
            description=description,
            parameters=parameters,
            required=required,
            handler=handler,
        )
        logger.debug(f"Tool registered: {name}")

    def register_tool_schema(self, schema: FunctionSchema) -> None:
        """注册工具 Schema"""
        self.tool_registry.register(schema)
        logger.debug(f"Tool schema registered: {schema.name}")

    def get_available_tools(self) -> List[ToolDefinition]:
        """获取所有可用工具"""
        return self.tool_registry.get_all_schemas()

    def invoke(
        self,
        message: str,
        tools: Optional[List[ToolDefinition]] = None,
        auto_execute: bool = True,
    ) -> Dict[str, Any]:
        """
        执行 Agent

        Args:
            message: 用户消息
            tools: 使用的工具列表 (默认使用所有注册的工具)
            auto_execute: 是否自动执行工具调用

        Returns:
            包含响应内容和可能的工具调用结果
        """
        # 使用传入的工具或所有注册的工具
        active_tools = tools or self.get_available_tools()

        # 添加用户消息到历史
        messages = self._conversation_history + [
            {"role": "user", "content": message}
        ]

        if not active_tools:
            # 无工具，简单对话
            result = self.client.chat(messages)
            self._conversation_history = messages + [
                {"role": "assistant", "content": result["content"]}
            ]
            return {
                "response": result["content"],
                "tool_calls": None,
                "tool_results": None,
            }

        # 有工具，执行带工具调用的对话循环
        if auto_execute:
            response = self.client.chat_with_tool_loop(
                user_message=message,
                tools=active_tools,
                tool_registry=self.tool_registry,
                max_iterations=self.max_iterations,
            )
            return {
                "response": response,
                "tool_calls": None,  # 已执行
                "tool_results": None,  # 已执行
            }

        # 不自动执行，返回工具调用信息
        result = self.client.chat(messages, active_tools)
        return {
            "response": result["content"],
            "tool_calls": result["tool_calls"],
            "tool_results": None,  # 需要手动执行
        }

    def stream(
        self,
        message: str,
        tools: Optional[List[ToolDefinition]] = None,
    ):
        """流式执行"""
        active_tools = tools or self.get_available_tools()
        messages = [{"role": "user", "content": message}]

        for chunk in self.client.stream(messages, active_tools):
            yield chunk

    def chat(self, message: str) -> str:
        """简化的聊天接口"""
        result = self.invoke(message)
        return result["response"]

    def clear_history(self) -> None:
        """清空对话历史"""
        self._conversation_history = []
        logger.info("Conversation history cleared")

    def get_history(self) -> List[Dict[str, Any]]:
        """获取对话历史"""
        return self._conversation_history

    def execute_tool(self, name: str, **kwargs) -> Any:
        """手动执行工具"""
        return self.tool_registry.execute(name, **kwargs)

    def get_tool_count(self) -> int:
        """获取注册工具数量"""
        return self.tool_registry.count()


# 全局 Hermes Agent 实例
_hermes_agent: Optional[HermesAgent] = None


def get_hermes_agent(
    model: str = "hermes3",
    init_tools: bool = True,
) -> HermesAgent:
    """
    获取 Hermes Agent 实例

    Args:
        model: Hermes 模型名称
        init_tools: 是否初始化 RDS 工具
    """
    global _hermes_agent
    if _hermes_agent is None:
        _hermes_agent = HermesAgent(model=model)
        if init_tools:
            from .tools import register_rds_tools
            register_rds_tools(_hermes_agent.tool_registry)
    return _hermes_agent


def create_hermes_agent(
    model: str = "hermes3",
    tool_registry: Optional[ToolRegistry] = None,
) -> HermesAgent:
    """创建新的 Hermes Agent 实例"""
    agent = HermesAgent(model=model, tool_registry=tool_registry)
    from .tools import register_rds_tools
    register_rds_tools(agent.tool_registry)
    return agent