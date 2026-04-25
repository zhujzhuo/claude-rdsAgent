"""Router Agent 模块 - 三层问题分类路由。

该模块提供根据问题类型自动选择执行路径的功能：
- 简单常识问答 (SIMPLE_QA) -> Hermes Agent + 知识库
- 专业垂直类问题 (SOP_SKILL) -> Skills/SOP 标准化流程
- 泛化问题 (GENERAL) -> LangGraph Agent 自主规划

支持自我迭代改进（IterativeRouterAgent）
"""

from .agent import (
    RouterAgent,
    IterativeRouterAgent,
    IterationConfig,
    AgentType,
    ComplexityLevel,
    get_router_agent,
    create_router_agent,
    get_iterative_router_agent,
    create_iterative_router_agent,
)
from .classifier import (
    QuestionCategory,
    QuestionClassifier,
    get_classifier,
    classify_question,
)

__all__ = [
    # RouterAgent
    "RouterAgent",
    "IterativeRouterAgent",
    "IterationConfig",
    "AgentType",
    "ComplexityLevel",
    "get_router_agent",
    "create_router_agent",
    "get_iterative_router_agent",
    "create_iterative_router_agent",
    # Classifier
    "QuestionCategory",
    "QuestionClassifier",
    "get_classifier",
    "classify_question",
]