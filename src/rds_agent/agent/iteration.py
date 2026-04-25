"""迭代循环 - Agent 自我迭代执行的核心控制

迭代循环管理 Agent 的执行-评估-反思-改进循环：
1. 执行任务
2. 评估结果
3. 反思分析
4. 应用改进
5. 重新执行
6. 检查终止条件

参考 Hermes Agent 的迭代架构设计
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from rds_agent.agent.base import IterationStrategy
from rds_agent.agent.evaluator import EvaluationResult
from rds_agent.utils.logger import get_logger

logger = get_logger("agent_iteration")


class TerminationReason(str, Enum):
    """终止原因"""

    SUCCESS = "success"                  # 成功完成
    QUALITY_THRESHOLD = "quality_threshold"  # 达到质量阈值
    MAX_ITERATIONS = "max_iterations"    # 达到最大迭代次数
    NO_IMPROVEMENT = "no_improvement"    # 无改进
    CONVERGENCE = "convergence"          # 收敛（连续迭代无变化）
    ERROR = "error"                      # 错误终止
    TIMEOUT = "timeout"                  # 超时
    USER_CANCEL = "user_cancel"          # 用户取消


@dataclass
class TerminationCheck:
    """终止检查结果"""

    should_terminate: bool
    reason: TerminationReason
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TerminationCheckResult:
    """终止检查结果（简化版）"""

    should_terminate: bool
    reason: TerminationReason
    score: float = 0.0
    iteration: int = 0


@dataclass
class IterationMetrics:
    """迭代指标"""

    iteration: int
    quality_score: float
    improvement_delta: float  # 相比上次的改进量
    total_time_ms: float
    avg_time_per_iteration: float
    tool_calls_count: int
    reflection_count: int


@dataclass
class IterationResult:
    """迭代结果"""

    # 基本信息
    total_iterations: int
    termination_reason: TerminationReason

    # 最佳结果
    best_response: str
    best_score: float
    best_iteration: int

    # 指标
    metrics: IterationMetrics

    # 历史
    iteration_history: List[Dict[str, Any]] = field(default_factory=list)

    # 时间
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    total_duration_ms: float = 0.0

    def mark_completed(self) -> None:
        """标记完成"""
        self.end_time = datetime.now()
        if self.start_time:
            self.total_duration_ms = (self.end_time - self.start_time).total_seconds() * 1000

    def to_summary(self) -> str:
        """生成摘要"""
        lines = [
            f"Iteration Result Summary",
            f"- Total Iterations: {self.total_iterations}",
            f"- Best Score: {self.best_score:.2f} (iteration {self.best_iteration})",
            f"- Termination: {self.termination_reason.value}",
            f"- Duration: {self.total_duration_ms:.0f}ms",
            f"- Avg Time/Iteration: {self.metrics.avg_time_per_iteration:.0f}ms",
        ]
        return "\n".join(lines)


class IterationConfig(BaseModel):
    """迭代配置"""

    # 迭代限制
    max_iterations: int = Field(default=5, description="最大迭代次数")
    min_iterations: int = Field(default=1, description="最小迭代次数")

    # 质量阈值
    min_quality_score: float = Field(default=0.7, description="最低质量阈值")
    target_quality_score: float = Field(default=0.9, description="目标质量阈值")

    # 改进检测
    min_improvement_delta: float = Field(default=0.05, description="最小改进量")
    convergence_threshold: int = Field(default=3, description="收敛阈值（连续无改进次数）")

    # 时间限制
    max_total_time_ms: float = Field(default=300000, description="最大总时间(ms)")
    max_iteration_time_ms: float = Field(default=60000, description="最大单次迭代时间(ms)")

    # 策略
    strategy: IterationStrategy = Field(default=IterationStrategy.BALANCED, description="迭代策略")


class IterationLoop:
    """迭代循环 - 控制 Agent 的自我迭代

    核心功能：
    1. 管理迭代流程
    2. 检查终止条件
    3. 跟踪迭代指标
    4. 选择最佳结果

    支持多种迭代策略：
    - NONE: 不迭代，单次执行
    - CONSERVATIVE: 仅当评估不合格时迭代
    - AGGRESSIVE: 总是尝试迭代改进
    - BALANCED: 根据评估结果动态决定
    - SKILL_BASED: SOP/Skill 驱动迭代
    """

    def __init__(
        self,
        max_iterations: int = 5,
        strategy: IterationStrategy = IterationStrategy.BALANCED,
        min_quality_score: float = 0.7,
        config: Optional[IterationConfig] = None,
    ):
        """初始化迭代循环

        Args:
            max_iterations: 最大迭代次数
            strategy: 迭代策略
            min_quality_score: 最低质量阈值
            config: 完整配置
        """
        self.config = config or IterationConfig(
            max_iterations=max_iterations,
            strategy=strategy,
            min_quality_score=min_quality_score,
        )

        # 迭代状态
        self.current_iteration: int = 0
        self.iteration_scores: List[float] = []
        self.iteration_responses: List[str] = []
        self.iteration_times: List[float] = []

        # 最佳结果跟踪
        self.best_score: float = 0.0
        self.best_response: str = ""
        self.best_iteration: int = 0

        # 收敛检测
        self.no_improvement_count: int = 0

        # 开始时间
        self.start_time: datetime = datetime.now()

        logger.info(
            f"IterationLoop initialized: strategy={strategy}, "
            f"max_iterations={max_iterations}, min_score={min_quality_score}"
        )

    def should_iterate(self, evaluation: EvaluationResult) -> bool:
        """检查是否应该继续迭代

        Args:
            evaluation: 当前评估结果

        Returns:
            是否继续迭代
        """
        if self.current_iteration >= self.config.max_iterations:
            return False

        # 根据策略决定
        if self.config.strategy == IterationStrategy.NONE:
            return False

        if self.config.strategy == IterationStrategy.CONSERVATIVE:
            # 仅当不合格时迭代
            return not evaluation.passed

        if self.config.strategy == IterationStrategy.AGGRESSIVE:
            # 总是迭代（除非达到最大次数或阈值）
            if evaluation.score >= self.config.target_quality_score:
                return False
            return self.current_iteration < self.config.max_iterations - 1

        if self.config.strategy == IterationStrategy.BALANCED:
            # 平衡策略：评估结果动态决定
            if evaluation.score >= self.config.min_quality_score:
                # 已达标，检查是否值得继续改进
                improvement_potential = self._estimate_improvement_potential(evaluation)
                return improvement_potential > self.config.min_improvement_delta
            return True

        if self.config.strategy == IterationStrategy.SKILL_BASED:
            # SOP 驱动：根据 SOP 步骤决定
            return self.current_iteration < self.config.max_iterations

        return False

    def check_termination(
        self,
        iteration: int,
        evaluation: EvaluationResult,
    ) -> TerminationCheck:
        """检查终止条件

        Args:
            iteration: 当前迭代次数
            evaluation: 评估结果

        Returns:
            TerminationCheck 终止检查结果
        """
        # 1. 成功终止
        if evaluation.score >= self.config.target_quality_score:
            return TerminationCheck(
                should_terminate=True,
                reason=TerminationReason.SUCCESS,
                details={"score": evaluation.score},
            )

        # 2. 达到质量阈值
        if evaluation.score >= self.config.min_quality_score and self.config.strategy != IterationStrategy.AGGRESSIVE:
            return TerminationCheck(
                should_terminate=True,
                reason=TerminationReason.QUALITY_THRESHOLD,
                details={
                    "score": evaluation.score,
                    "threshold": self.config.min_quality_score,
                },
            )

        # 3. 达到最大迭代次数
        if iteration >= self.config.max_iterations:
            return TerminationCheck(
                should_terminate=True,
                reason=TerminationReason.MAX_ITERATIONS,
                details={
                    "iterations": iteration,
                    "max": self.config.max_iterations,
                },
            )

        # 4. 无改进（收敛）
        if self.no_improvement_count >= self.config.convergence_threshold:
            return TerminationCheck(
                should_terminate=True,
                reason=TerminationReason.CONVERGENCE,
                details={
                    "no_improvement_count": self.no_improvement_count,
                    "threshold": self.config.convergence_threshold,
                },
            )

        # 5. 超时
        elapsed_ms = (datetime.now() - self.start_time).total_seconds() * 1000
        if elapsed_ms > self.config.max_total_time_ms:
            return TerminationCheck(
                should_terminate=True,
                reason=TerminationReason.TIMEOUT,
                details={
                    "elapsed_ms": elapsed_ms,
                    "max_ms": self.config.max_total_time_ms,
                },
            )

        # 继续迭代
        return TerminationCheck(
            should_terminate=False,
            reason=TerminationReason.SUCCESS,  # 暂时使用，后续更新
            details={},
        )

    def check_termination_result(
        self,
        iteration: int,
        evaluation: EvaluationResult,
    ) -> TerminationCheckResult:
        """检查终止条件（简化版）

        Args:
            iteration: 当前迭代次数
            evaluation: 评估结果

        Returns:
            TerminationCheckResult 终止检查结果
        """
        check = self.check_termination(iteration, evaluation)
        return TerminationCheckResult(
            should_terminate=check.should_terminate,
            reason=check.reason,
            score=evaluation.score,
            iteration=iteration,
        )

    def record_iteration(
        self,
        iteration: int,
        score: float,
        response: str,
        time_ms: float,
    ) -> None:
        """记录迭代结果

        Args:
            iteration: 迭代次数
            score: 质量评分
            response: 响应内容
            time_ms: 执行时间
        """
        self.current_iteration = iteration
        self.iteration_scores.append(score)
        self.iteration_responses.append(response)
        self.iteration_times.append(time_ms)

        # 更新最佳结果
        if score > self.best_score:
            self.best_score = score
            self.best_response = response
            self.best_iteration = iteration
            self.no_improvement_count = 0
        else:
            # 检查改进量
            if len(self.iteration_scores) >= 2:
                delta = score - self.iteration_scores[-2]
                if delta < self.config.min_improvement_delta:
                    self.no_improvement_count += 1

        logger.debug(
            f"Iteration {iteration}: score={score:.2f}, "
            f"best={self.best_score:.2f}, no_improvement={self.no_improvement_count}"
        )

    def get_metrics(self) -> IterationMetrics:
        """获取迭代指标"""
        total_time = sum(self.iteration_times) if self.iteration_times else 0

        # 计算改进量
        improvement_delta = 0.0
        if len(self.iteration_scores) >= 2:
            improvement_delta = self.iteration_scores[-1] - self.iteration_scores[0]

        return IterationMetrics(
            iteration=self.current_iteration,
            quality_score=self.best_score,
            improvement_delta=improvement_delta,
            total_time_ms=total_time,
            avg_time_per_iteration=total_time / len(self.iteration_times) if self.iteration_times else 0,
            tool_calls_count=0,  # 需要从外部传入
            reflection_count=len(self.iteration_scores) - 1 if len(self.iteration_scores) > 1 else 0,
        )

    def get_result(self, termination_reason: TerminationReason) -> IterationResult:
        """获取最终结果"""
        metrics = self.get_metrics()

        result = IterationResult(
            total_iterations=self.current_iteration + 1,
            termination_reason=termination_reason,
            best_response=self.best_response,
            best_score=self.best_score,
            best_iteration=self.best_iteration,
            metrics=metrics,
            iteration_history=[
                {
                    "iteration": i,
                    "score": self.iteration_scores[i],
                    "time_ms": self.iteration_times[i],
                    "response_preview": self.iteration_responses[i][:100],
                }
                for i in range(len(self.iteration_scores))
            ],
            start_time=self.start_time,
        )

        result.mark_completed()
        return result

    def _estimate_improvement_potential(self, evaluation: EvaluationResult) -> float:
        """估计改进潜力"""
        # 基于历史趋势估计
        if len(self.iteration_scores) >= 2:
            # 计算平均改进率
            deltas = []
            for i in range(1, len(self.iteration_scores)):
                deltas.append(self.iteration_scores[i] - self.iteration_scores[i-1])

            avg_delta = sum(deltas) / len(deltas) if deltas else 0

            # 如果改进趋势正向，估计潜力
            if avg_delta > 0:
                remaining_iterations = self.config.max_iterations - self.current_iteration
                return avg_delta * remaining_iterations

        # 默认估计
        gap_to_target = self.config.target_quality_score - evaluation.score
        return min(gap_to_target * 0.3, 0.1)  # 估计能达到目标的30%

    def reset(self) -> None:
        """重置迭代循环"""
        self.current_iteration = 0
        self.iteration_scores = []
        self.iteration_responses = []
        self.iteration_times = []
        self.best_score = 0.0
        self.best_response = ""
        self.best_iteration = 0
        self.no_improvement_count = 0
        self.start_time = datetime.now()

        logger.info("IterationLoop reset")

    def should_continue_iterate(self, iteration: int, evaluation: EvaluationResult) -> bool:
        """检查是否应该继续迭代（基于当前迭代次数和评估）

        Args:
            iteration: 当前迭代次数
            evaluation: 当前评估结果

        Returns:
            是否继续迭代
        """
        # 更新当前迭代次数
        self.current_iteration = iteration

        # 使用 should_iterate 方法
        return self.should_iterate(evaluation)


class IterationController:
    """迭代控制器 - 高层迭代控制

    提供迭代循环的高级控制接口
    """

    def __init__(self, config: Optional[IterationConfig] = None):
        """初始化控制器"""
        self.config = config or IterationConfig()
        self._loops: Dict[str, IterationLoop] = {}

    def create_loop(self, loop_id: str) -> IterationLoop:
        """创建迭代循环"""
        loop = IterationLoop(config=self.config)
        self._loops[loop_id] = loop
        return loop

    def get_loop(self, loop_id: str) -> Optional[IterationLoop]:
        """获取迭代循环"""
        return self._loops.get(loop_id)

    def remove_loop(self, loop_id: str) -> None:
        """移除迭代循环"""
        if loop_id in self._loops:
            del self._loops[loop_id]

    def list_loops(self) -> List[str]:
        """列出所有循环"""
        return list(self._loops.keys())


# 全局控制器
_iteration_controller: Optional[IterationController] = None


def get_iteration_controller(config: Optional[IterationConfig] = None) -> IterationController:
    """获取迭代控制器单例"""
    global _iteration_controller
    if _iteration_controller is None:
        _iteration_controller = IterationController(config)
    return _iteration_controller


def create_iteration_loop(
    max_iterations: int = 5,
    strategy: IterationStrategy = IterationStrategy.BALANCED,
    min_quality_score: float = 0.7,
) -> IterationLoop:
    """创建迭代循环"""
    return IterationLoop(
        max_iterations=max_iterations,
        strategy=strategy,
        min_quality_score=min_quality_score,
    )