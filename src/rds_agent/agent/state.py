"""Agent 状态管理 - 跟踪 Agent 执行过程中的状态变化"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from typing_extensions import TypedDict

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    """Agent 执行状态"""

    IDLE = "idle"                    # 空闲，等待输入
    INITIALIZING = "initializing"    # 初始化
    EXECUTING = "executing"          # 执行中
    TOOL_CALLING = "tool_calling"    # 工具调用中
    EVALUATING = "evaluating"        # 评估中
    REFLECTING = "reflecting"        # 反思中
    ITERATING = "iterating"          # 迭代中
    COMPLETED = "completed"          # 完成
    FAILED = "failed"                # 失败
    TIMEOUT = "timeout"              # 超时


class IterationPhase(str, Enum):
    """迭代阶段"""

    EXECUTE = "execute"              # 执行阶段
    EVALUATE = "evaluate"            # 评估阶段
    REFLECT = "reflect"              # 反思阶段
    IMPROVE = "improve"              # 改进阶段
    TERMINATE = "terminate"          # 终止阶段


class ToolCallRecord(TypedDict):
    """工具调用记录"""

    name: str
    arguments: Dict[str, Any]
    result: Optional[Any]
    error: Optional[str]
    timestamp: datetime
    iteration: int


class ReflectionRecord(TypedDict):
    """反思记录"""

    iteration: int
    analysis: str
    issues: List[str]
    improvements: List[str]
    timestamp: datetime


class EvaluationRecord(TypedDict):
    """评估记录"""

    iteration: int
    score: float
    passed: bool
    criteria: Dict[str, float]
    details: Dict[str, Any]
    timestamp: datetime


class IterationRecord(TypedDict):
    """迭代记录"""

    iteration: int
    phase: IterationPhase
    status: AgentStatus
    response: str
    tool_calls: List[ToolCallRecord]
    evaluation: Optional[EvaluationRecord]
    reflection: Optional[ReflectionRecord]
    duration_ms: float
    timestamp: datetime


class AgentState(BaseModel):
    """Agent 状态 - 完整的状态管理

    跟踪 Agent 执行过程中的所有状态变化：
    - 基本信息
    - 执行状态
    - 工具调用
    - 迭代记录
    - 评估结果
    - 反思内容
    """

    # 基本信息
    agent_id: str = Field(default="", description="Agent ID")
    agent_type: str = Field(default="", description="Agent 类型")
    query: str = Field(default="", description="用户查询")

    # 执行状态
    status: AgentStatus = Field(default=AgentStatus.IDLE, description="当前状态")
    current_iteration: int = Field(default=0, description="当前迭代次数")
    current_phase: IterationPhase = Field(default=IterationPhase.EXECUTE, description="当前阶段")

    # 上下文
    context: Dict[str, Any] = Field(default_factory=dict, description="执行上下文")

    # 工具调用
    tool_calls: List[ToolCallRecord] = Field(default_factory=list, description="工具调用记录")
    pending_tools: List[str] = Field(default_factory=list, description="待执行工具")

    # 迭代记录
    iterations: List[IterationRecord] = Field(default_factory=list, description="迭代历史")

    # 评估
    evaluation: Optional[EvaluationRecord] = Field(default=None, description="最新评估")
    quality_score: float = Field(default=0.0, description="质量评分")

    # 反思
    reflection: Optional[ReflectionRecord] = Field(default=None, description="最新反思")
    pending_improvements: List[str] = Field(default_factory=list, description="待应用改进")

    # 结果
    response: str = Field(default="", description="当前响应")
    best_response: str = Field(default="", description="最佳响应")
    best_score: float = Field(default=0.0, description="最佳评分")

    # 错误
    error: Optional[str] = Field(default=None, description="错误信息")
    error_history: List[str] = Field(default_factory=list, description="错误历史")

    # 时间
    start_time: Optional[datetime] = Field(default=None, description="开始时间")
    end_time: Optional[datetime] = Field(default=None, description="结束时间")
    duration_ms: float = Field(default=0.0, description="总时长(ms)")

    def initialize(self, query: str, context: Optional[Dict] = None) -> None:
        """初始化状态"""
        self.query = query
        self.status = AgentStatus.INITIALIZING
        self.context = context or {}
        self.start_time = datetime.now()

    def start_iteration(self, iteration: int) -> None:
        """开始迭代"""
        self.current_iteration = iteration
        self.status = AgentStatus.EXECUTING
        self.current_phase = IterationPhase.EXECUTE

    def record_tool_call(self, record: ToolCallRecord) -> None:
        """记录工具调用"""
        record["timestamp"] = datetime.now()
        record["iteration"] = self.current_iteration
        self.tool_calls.append(record)

    def update_evaluation(self, evaluation: EvaluationRecord) -> None:
        """更新评估"""
        evaluation["timestamp"] = datetime.now()
        evaluation["iteration"] = self.current_iteration
        self.evaluation = evaluation
        self.quality_score = evaluation["score"]

        # 更新最佳结果
        if evaluation["score"] > self.best_score:
            self.best_score = evaluation["score"]
            self.best_response = self.response

    def update_reflection(self, reflection: ReflectionRecord) -> None:
        """更新反思"""
        reflection["timestamp"] = datetime.now()
        reflection["iteration"] = self.current_iteration
        self.reflection = reflection
        self.pending_improvements = reflection.get("improvements", [])

    def record_iteration(self, record: IterationRecord) -> None:
        """记录迭代"""
        record["timestamp"] = datetime.now()
        record["iteration"] = self.current_iteration
        self.iterations.append(record)

    def mark_completed(self, reason: str = "success") -> None:
        """标记完成"""
        self.status = AgentStatus.COMPLETED
        self.end_time = datetime.now()
        if self.start_time:
            self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000

    def mark_failed(self, error: str) -> None:
        """标记失败"""
        self.status = AgentStatus.FAILED
        self.error = error
        self.error_history.append(error)
        self.end_time = datetime.now()
        if self.start_time:
            self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000

    def apply_improvements(self) -> None:
        """应用改进"""
        for improvement in self.pending_improvements:
            self.context["improvement"] = improvement
        self.pending_improvements = []

    def get_summary(self) -> Dict[str, Any]:
        """获取状态摘要"""
        return {
            "agent_id": self.agent_id,
            "status": self.status.value,
            "iterations": len(self.iterations),
            "quality_score": self.quality_score,
            "tool_calls": len(self.tool_calls),
            "error": self.error,
            "duration_ms": self.duration_ms,
        }

    def is_terminal(self) -> bool:
        """是否已终止"""
        return self.status in [
            AgentStatus.COMPLETED,
            AgentStatus.FAILED,
            AgentStatus.TIMEOUT,
        ]

    def should_continue(self, max_iterations: int, min_score: float) -> bool:
        """是否应继续迭代"""
        if self.is_terminal():
            return False

        if self.current_iteration >= max_iterations:
            return False

        if self.quality_score >= min_score:
            return False

        return True


class StateManager:
    """状态管理器 - 管理多个 Agent 的状态"""

    def __init__(self):
        """初始化状态管理器"""
        self._states: Dict[str, AgentState] = {}

    def create_state(self, agent_id: str, query: str, context: Optional[Dict] = None) -> AgentState:
        """创建状态"""
        state = AgentState(agent_id=agent_id)
        state.initialize(query, context)
        self._states[agent_id] = state
        return state

    def get_state(self, agent_id: str) -> Optional[AgentState]:
        """获取状态"""
        return self._states.get(agent_id)

    def update_state(self, agent_id: str, updates: Dict[str, Any]) -> None:
        """更新状态"""
        state = self.get_state(agent_id)
        if state:
            for key, value in updates.items():
                if hasattr(state, key):
                    setattr(state, key, value)

    def remove_state(self, agent_id: str) -> None:
        """移除状态"""
        if agent_id in self._states:
            del self._states[agent_id]

    def list_states(self) -> List[str]:
        """列出所有状态 ID"""
        return list(self._states.keys())

    def clear_all(self) -> None:
        """清空所有状态"""
        self._states.clear()


# 全局状态管理器
_state_manager: Optional[StateManager] = None


def get_state_manager() -> StateManager:
    """获取状态管理器单例"""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager