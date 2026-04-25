"""Agent 模块 - 支持自我迭代的智能 Agent 框架。

核心特性：
- 自我反思机制（Reflection）
- 迭代改进循环（Iteration Loop）
- 结果评估器（Evaluator）
- Agent 记忆系统（Memory）

架构参考：NousResearch Hermes Agent
"""

from .base import (
    BaseAgent,
    AgentConfig,
    AgentResult,
    IterationStrategy,
    get_agent_config,
)
from .state import AgentState, AgentStatus
from .reflection import ReflectionEngine, ReflectionResult
from .iteration import (
    IterationLoop,
    IterationResult,
    IterationMetrics,
    TerminationReason,
    TerminationCheck,
    TerminationCheckResult,
)
from .evaluator import ResultEvaluator, EvaluationResult, EvaluationCriteria
from .memory import AgentMemory, MemoryType, MemoryEntry
from .tool_executor import ToolExecutor, ToolResult

__all__ = [
    # Base Agent
    "BaseAgent",
    "AgentConfig",
    "AgentResult",
    "IterationStrategy",
    "get_agent_config",
    # State
    "AgentState",
    "AgentStatus",
    # Reflection
    "ReflectionEngine",
    "ReflectionResult",
    # Iteration
    "IterationLoop",
    "IterationResult",
    "IterationMetrics",
    "TerminationReason",
    "TerminationCheck",
    "TerminationCheckResult",
    # Evaluator
    "ResultEvaluator",
    "EvaluationResult",
    "EvaluationCriteria",
    # Memory
    "AgentMemory",
    "MemoryType",
    "MemoryEntry",
    # Tool Executor
    "ToolExecutor",
    "ToolResult",
]