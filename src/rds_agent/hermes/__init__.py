"""Hermes Agent 模块 - NousResearch Hermes 模型的 Function Calling 支持。

Hermes 模型系列 (Hermes 2 Pro, Hermes 3) 原生支持 OpenAI 格式的 Function Calling，
非常适合 Agent 应用场景。

支持的模型:
- Hermes-2-Pro-Llama-3 (7B)
- Hermes-3-Llama-3.1 (8B/70B)

特点:
- 原生 Function Calling 支持
- OpenAI 兼容的函数调用格式
- 本地部署 (通过 Ollama)
- 多轮对话工具调用
"""

from .agent import HermesAgent, get_hermes_agent
from .function_schema import FunctionSchema, ToolRegistry
from .client import HermesClient
from .tools import register_rds_tools, get_rds_tool_registry

__all__ = [
    "HermesAgent",
    "get_hermes_agent",
    "FunctionSchema",
    "ToolRegistry",
    "HermesClient",
    "register_rds_tools",
    "get_rds_tool_registry",
]