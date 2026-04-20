"""Router Agent 模块 - 双 Agent 自动路由选择器。

该模块提供根据任务复杂度自动选择合适 Agent 的功能：
- 简单任务（单工具调用） -> Hermes Agent（快速响应）
- 中等任务（多工具调用） -> LangGraph Agent（状态机编排）
- 复杂任务（完整诊断） -> DiagnosticAgent（13项检查）
"""

from .agent import (
    RouterAgent,
    AgentType,
    ComplexityLevel,
    get_router_agent,
    create_router_agent,
)

__all__ = [
    "RouterAgent",
    "AgentType",
    "ComplexityLevel",
    "get_router_agent",
    "create_router_agent",
]