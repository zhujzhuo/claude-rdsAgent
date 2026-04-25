"""Agent 迭代模块测试。"""

import pytest
from unittest.mock import Mock, MagicMock

from rds_agent.agent.iteration import (
    IterationLoop,
    IterationConfig,
    IterationResult,
    IterationMetrics,
    TerminationReason,
    TerminationCheck,
    TerminationCheckResult,
)
from rds_agent.agent.base import IterationStrategy
from rds_agent.agent.evaluator import EvaluationResult


class TestIterationLoop:
    """迭代循环测试"""

    @pytest.fixture
    def iteration_loop(self):
        """创建迭代循环"""
        return IterationLoop(
            max_iterations=5,
            strategy=IterationStrategy.BALANCED,
            min_quality_score=0.7,
        )

    @pytest.fixture
    def mock_evaluation_passed(self):
        """模拟通过的评估"""
        return EvaluationResult(
            score=0.85,
            passed=True,
            criterion_scores=[],
            details={},
            issues=[],
            suggestions=[],
        )

    @pytest.fixture
    def mock_evaluation_failed(self):
        """模拟失败的评估"""
        return EvaluationResult(
            score=0.5,
            passed=False,
            criterion_scores=[],
            details={},
            issues=["响应不完整"],
            suggestions=["提供更多细节"],
        )

    def test_iteration_loop_creation(self):
        """测试创建迭代循环"""
        loop = IterationLoop()
        assert loop.current_iteration == 0
        assert loop.best_score == 0.0
        assert loop.no_improvement_count == 0

    def test_should_iterate_none_strategy(self):
        """测试 NONE 策略不迭代"""
        loop = IterationLoop(strategy=IterationStrategy.NONE)
        eval_result = EvaluationResult(score=0.5, passed=False)

        assert loop.should_iterate(eval_result) == False

    def test_should_iterate_conservative_strategy(self):
        """测试 CONSERVATIVE 策略"""
        loop = IterationLoop(strategy=IterationStrategy.CONSERVATIVE)

        # 不合格的评估应该迭代
        eval_failed = EvaluationResult(score=0.5, passed=False)
        assert loop.should_iterate(eval_failed) == True

        # 合格的评估不迭代
        eval_passed = EvaluationResult(score=0.8, passed=True)
        assert loop.should_iterate(eval_passed) == False

    def test_should_iterate_aggressive_strategy(self):
        """测试 AGGRESSIVE 策略"""
        loop = IterationLoop(strategy=IterationStrategy.AGGRESSIVE, max_iterations=5)

        # 未达到目标分数，应该迭代
        eval_result = EvaluationResult(score=0.85, passed=True)
        loop.current_iteration = 2
        assert loop.should_iterate(eval_result) == True

        # 达到目标分数，不迭代
        eval_target = EvaluationResult(score=0.95, passed=True)
        assert loop.should_iterate(eval_target) == False

    def test_should_iterate_max_iterations(self, iteration_loop):
        """测试达到最大迭代次数"""
        iteration_loop.current_iteration = 5
        eval_result = EvaluationResult(score=0.5, passed=False)

        assert iteration_loop.should_iterate(eval_result) == False

    def test_record_iteration(self, iteration_loop):
        """测试记录迭代"""
        iteration_loop.record_iteration(0, 0.5, "response 1", 100.0)
        iteration_loop.record_iteration(1, 0.7, "response 2", 150.0)
        iteration_loop.record_iteration(2, 0.85, "response 3", 200.0)

        assert iteration_loop.current_iteration == 2
        assert len(iteration_loop.iteration_scores) == 3
        assert iteration_loop.best_score == 0.85
        assert iteration_loop.best_iteration == 2
        assert iteration_loop.best_response == "response 3"

    def test_record_iteration_no_improvement(self, iteration_loop):
        """测试记录无改进迭代"""
        iteration_loop.record_iteration(0, 0.5, "response 1", 100.0)
        iteration_loop.record_iteration(1, 0.55, "response 2", 150.0)  # 小改进
        iteration_loop.record_iteration(2, 0.52, "response 3", 200.0)  # 退步

        # 应该增加无改进计数
        assert iteration_loop.no_improvement_count > 0

    def test_check_termination_success(self, iteration_loop):
        """测试成功终止"""
        eval_result = EvaluationResult(score=0.95, passed=True)
        check = iteration_loop.check_termination(2, eval_result)

        assert check.should_terminate == True
        assert check.reason == TerminationReason.SUCCESS

    def test_check_termination_quality_threshold(self, iteration_loop):
        """测试质量阈值终止"""
        eval_result = EvaluationResult(score=0.75, passed=True)
        check = iteration_loop.check_termination(2, eval_result)

        assert check.should_terminate == True
        assert check.reason == TerminationReason.QUALITY_THRESHOLD

    def test_check_termination_max_iterations(self, iteration_loop):
        """测试最大迭代终止"""
        eval_result = EvaluationResult(score=0.5, passed=False)
        check = iteration_loop.check_termination(5, eval_result)

        assert check.should_terminate == True
        assert check.reason == TerminationReason.MAX_ITERATIONS

    def test_check_termination_convergence(self, iteration_loop):
        """测试收敛终止"""
        iteration_loop.no_improvement_count = 3
        eval_result = EvaluationResult(score=0.6, passed=False)
        check = iteration_loop.check_termination(2, eval_result)

        assert check.should_terminate == True
        assert check.reason == TerminationReason.CONVERGENCE

    def test_check_termination_continue(self, iteration_loop):
        """测试继续迭代"""
        eval_result = EvaluationResult(score=0.5, passed=False)
        check = iteration_loop.check_termination(1, eval_result)

        assert check.should_terminate == False

    def test_get_metrics(self, iteration_loop):
        """测试获取指标"""
        iteration_loop.record_iteration(0, 0.5, "response 1", 100.0)
        iteration_loop.record_iteration(1, 0.7, "response 2", 150.0)

        metrics = iteration_loop.get_metrics()

        assert metrics.iteration == 1
        assert metrics.quality_score == 0.7
        assert abs(metrics.improvement_delta - 0.2) < 0.01  # 浮点数精度
        assert metrics.total_time_ms == 250.0

    def test_get_result(self, iteration_loop):
        """测试获取结果"""
        iteration_loop.record_iteration(0, 0.5, "response 1", 100.0)
        iteration_loop.record_iteration(1, 0.85, "response 2", 150.0)

        result = iteration_loop.get_result(TerminationReason.SUCCESS)

        assert result.total_iterations == 2
        assert result.termination_reason == TerminationReason.SUCCESS
        assert result.best_score == 0.85
        assert result.best_response == "response 2"
        assert len(result.iteration_history) == 2

    def test_reset(self, iteration_loop):
        """测试重置"""
        iteration_loop.record_iteration(0, 0.5, "response 1", 100.0)
        iteration_loop.record_iteration(1, 0.7, "response 2", 150.0)

        iteration_loop.reset()

        assert iteration_loop.current_iteration == 0
        assert iteration_loop.iteration_scores == []
        assert iteration_loop.best_score == 0.0


class TestTerminationCheck:
    """终止检查测试"""

    def test_termination_check_creation(self):
        """测试创建终止检查"""
        check = TerminationCheck(
            should_terminate=True,
            reason=TerminationReason.SUCCESS,
            details={"score": 0.9},
        )

        assert check.should_terminate == True
        assert check.reason == TerminationReason.SUCCESS
        assert check.details["score"] == 0.9

    def test_termination_check_result(self):
        """测试终止检查结果"""
        result = TerminationCheckResult(
            should_terminate=True,
            reason=TerminationReason.SUCCESS,
            score=0.9,
            iteration=3,
        )

        assert result.should_terminate == True
        assert result.reason == TerminationReason.SUCCESS
        assert result.score == 0.9
        assert result.iteration == 3


class TestIterationConfig:
    """迭代配置测试"""

    def test_iteration_config_defaults(self):
        """测试默认配置"""
        config = IterationConfig()

        assert config.max_iterations == 5
        assert config.min_iterations == 1
        assert config.min_quality_score == 0.7
        assert config.target_quality_score == 0.9
        assert config.strategy == IterationStrategy.BALANCED

    def test_iteration_config_custom(self):
        """测试自定义配置"""
        config = IterationConfig(
            max_iterations=10,
            min_quality_score=0.6,
            strategy=IterationStrategy.AGGRESSIVE,
        )

        assert config.max_iterations == 10
        assert config.min_quality_score == 0.6
        assert config.strategy == IterationStrategy.AGGRESSIVE


class TestIterationResult:
    """迭代结果测试"""

    def test_iteration_result_creation(self):
        """测试创建迭代结果"""
        metrics = IterationMetrics(
            iteration=3,
            quality_score=0.85,
            improvement_delta=0.35,
            total_time_ms=500.0,
            avg_time_per_iteration=166.67,
            tool_calls_count=5,
            reflection_count=2,
        )

        result = IterationResult(
            total_iterations=3,
            termination_reason=TerminationReason.SUCCESS,
            best_response="最佳响应",
            best_score=0.85,
            best_iteration=2,
            metrics=metrics,
        )

        assert result.total_iterations == 3
        assert result.termination_reason == TerminationReason.SUCCESS
        assert result.best_score == 0.85

    def test_iteration_result_summary(self):
        """测试迭代结果摘要"""
        metrics = IterationMetrics(
            iteration=3,
            quality_score=0.85,
            improvement_delta=0.35,
            total_time_ms=500.0,
            avg_time_per_iteration=166.67,
            tool_calls_count=5,
            reflection_count=2,
        )

        result = IterationResult(
            total_iterations=3,
            termination_reason=TerminationReason.SUCCESS,
            best_response="最佳响应",
            best_score=0.85,
            best_iteration=2,
            metrics=metrics,
        )

        summary = result.to_summary()
        assert "Iteration Result Summary" in summary
        assert "Best Score: 0.85" in summary
        assert "success" in summary  # 检查小写形式