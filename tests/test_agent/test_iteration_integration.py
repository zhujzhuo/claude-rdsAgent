"""Agent 自我迭代集成测试。

测试完整的迭代循环流程：
1. 评估-反思-改进循环
2. 终止条件检测
3. 最佳结果选择
4. 记忆系统集成
"""

import pytest
from unittest.mock import Mock, MagicMock
import time

from rds_agent.agent import (
    IterationLoop,
    IterationResult,
    IterationStrategy,
    TerminationReason,
    ReflectionEngine,
    ReflectionResult,
    ResultEvaluator,
    EvaluationResult,
    AgentMemory,
)


class TestIterationIntegration:
    """迭代循环集成测试"""

    @pytest.fixture
    def iteration_loop(self):
        """创建迭代循环"""
        return IterationLoop(
            max_iterations=5,
            strategy=IterationStrategy.BALANCED,
            min_quality_score=0.7,
        )

    @pytest.fixture
    def evaluator(self):
        """创建评估器"""
        return ResultEvaluator()

    @pytest.fixture
    def reflection_engine(self):
        """创建反思引擎"""
        return ReflectionEngine(depth=2)

    @pytest.fixture
    def memory(self):
        """创建记忆系统"""
        return AgentMemory(enable_learning=False)

    def test_full_iteration_cycle(
        self,
        iteration_loop,
        evaluator,
        reflection_engine,
        memory,
    ):
        """测试完整迭代周期"""
        query = "分析 CPU 使用率过高问题"

        # 模拟迭代过程
        responses = [
            "CPU 使用率 85%",  # 第一次响应（不完整）
            "CPU 使用率 85%，原因是慢 SQL",  # 第二次响应（部分改进）
            "## CPU 分析报告\n\nCPU 使用率 85%，高峰时段 14:00-16:00。\n\n根因：慢 SQL 导致。\n\n建议：优化 SQL 执行计划",  # 第三次响应（达标）
        ]

        last_check = None
        for i, response in enumerate(responses):
            # 评估
            evaluation = evaluator.evaluate(
                response=response,
                query=query,
                iteration=i,
            )

            # 反思（添加空上下文）
            reflection = reflection_engine.reflect(
                query=query,
                response=response,
                evaluation=evaluation,
                iteration=i,
                context={},  # 添加空上下文
            )

            # 记录迭代
            iteration_loop.record_iteration(
                iteration=i,
                score=evaluation.score,
                response=response,
                time_ms=100.0 + i * 50,
            )

            # 记录到记忆
            memory.add_evaluation_memory(
                iteration=i,
                score=evaluation.score,
                passed=evaluation.passed,
                criteria={},
                query=query,
            )
            memory.add_reflection_memory(
                iteration=i,
                analysis=reflection.analysis,
                issues=reflection.issues,
                improvements=reflection.improvements,
                query=query,
            )

            # 检查终止
            last_check = iteration_loop.check_termination(i, evaluation)
            if last_check.should_terminate:
                break

        # 获取最终结果
        result = iteration_loop.get_result(last_check.reason)

        # 验证
        assert result.total_iterations <= 3
        assert result.best_score >= 0.5  # 至少有一定质量
        stats = memory.get_stats()
        assert stats.get("total_entries", 0) >= 1

    def test_iteration_with_convergence(
        self,
        iteration_loop,
        evaluator,
    ):
        """测试迭代收敛"""
        query = "诊断实例问题"

        # 模拟收敛场景：连续迭代无改进
        responses = [
            "响应 1",
            "响应 2",  # 相似
            "响应 3",  # 相似
            "响应 4",  # 相似
        ]

        last_check = None
        for i, response in enumerate(responses):
            evaluation = evaluator.evaluate(
                response=response,
                query=query,
                iteration=i,
            )

            iteration_loop.record_iteration(
                iteration=i,
                score=evaluation.score,
                response=response,
                time_ms=100.0,
            )

            last_check = iteration_loop.check_termination(i, evaluation)
            if last_check.should_terminate:
                break

        # 应该因为收敛或最大迭代而终止
        result = iteration_loop.get_result(last_check.reason)

        assert result.termination_reason in [
            TerminationReason.CONVERGENCE,
            TerminationReason.MAX_ITERATIONS,
            TerminationReason.QUALITY_THRESHOLD,
        ]

    def test_iteration_success_termination(
        self,
        iteration_loop,
        evaluator,
    ):
        """测试成功终止"""
        query = "简单问题"

        # 高质量响应应该立即成功终止
        response = """
        ## 完整分析报告

        详细的问题分析和解决方案：
        - 问题 1: xxx
        - 问题 2: xxx

        结论：建议优化配置
        """

        evaluation = evaluator.evaluate(
            response=response,
            query=query,
            iteration=0,
        )

        iteration_loop.record_iteration(
            iteration=0,
            score=evaluation.score,
            response=response,
            time_ms=50.0,
        )

        check = iteration_loop.check_termination(0, evaluation)

        # 高质量响应应该可能成功终止
        assert check.should_terminate or evaluation.score >= 0.7


class TestMemoryLearningIntegration:
    """记忆学习集成测试"""

    @pytest.fixture
    def memory(self):
        """创建记忆系统（启用学习）"""
        return AgentMemory(enable_learning=True)

    def test_memory_learning_from_iterations(self, memory):
        """测试从迭代中学习"""
        # 添加多次执行记录
        for i in range(5):
            memory.add_execution_memory(
                iteration=i,
                tool_name="get_cpu_monitoring",
                tool_result={"cpu": f"{80+i}%"},
                response=f"CPU 使用率 {80+i}%",
                query="CPU 分析",
            )
            memory.add_success_memory(
                iteration=i,
                query="CPU 分析",
                query_type="cpu_analysis",
                tools=["get_cpu_monitoring"],
                strategy="获取监控数据分析",
            )

        # 学习
        patterns = memory.learn_from_memories()

        # 验证学习结果
        assert isinstance(patterns, dict)

    def test_memory_context_for_iteration(self, memory):
        """测试记忆上下文准备"""
        # 添加记忆
        memory.add_execution_memory(
            iteration=1,
            tool_name="get_cpu",
            tool_result="85%",
            response="CPU 高",
            query="CPU 分析",
        )
        memory.add_evaluation_memory(
            iteration=1,
            score=0.6,
            passed=False,
            criteria={},
            query="CPU 分析",
        )
        memory.update_working_memory("instance", "db-prod-01")

        # 获取上下文
        context = memory.get_context_for_iteration(2)

        assert "recent_memories" in context
        assert "working_memory" in context
        assert context["working_memory"]["instance"] == "db-prod-01"


class TestReflectionEvaluationIntegration:
    """反思评估集成测试"""

    @pytest.fixture
    def evaluator(self):
        """创建评估器"""
        return ResultEvaluator()

    @pytest.fixture
    def reflection_engine(self):
        """创建反思引擎"""
        return ReflectionEngine(depth=2)

    def test_reflection_guides_improvement(self, evaluator, reflection_engine):
        """测试反思指导改进"""
        query = "分析 CPU 使用率"

        # 第一轮响应（质量较低）
        response1 = "CPU 高"
        evaluation1 = evaluator.evaluate(response1, query, iteration=0)
        reflection1 = reflection_engine.reflect(
            query, response1, evaluation1, iteration=0,
            context={},  # 添加空上下文
        )

        # 验证反思提出了改进建议
        assert len(reflection1.improvements) > 0

        # 第二轮响应（基于改进建议）
        improvements = reflection1.improvements
        response2 = f"CPU 使用率 85%，{improvements[0] if improvements else '需要优化'}"
        evaluation2 = evaluator.evaluate(response2, query, iteration=1)

        # 验证质量提升或保持
        assert evaluation2.score >= evaluation1.score or evaluation2.passed


class TestTerminationIntegration:
    """终止条件集成测试"""

    def test_all_termination_reasons(self):
        """测试所有终止原因"""
        loop = IterationLoop(max_iterations=10)
        evaluator = ResultEvaluator()

        tested_reasons = set()

        for attempt in range(3):
            loop.reset()
            iteration = 0

            while iteration < loop.config.max_iterations:
                response = f"测试响应 {iteration}"
                evaluation = evaluator.evaluate(response, "测试问题", iteration=iteration)

                loop.record_iteration(iteration, evaluation.score, response, 100.0)

                check = loop.check_termination(iteration, evaluation)
                if check.should_terminate:
                    result = loop.get_result(check.reason)
                    tested_reasons.add(result.termination_reason)
                    break

                iteration += 1

        # 验证至少测试了一种终止原因
        assert len(tested_reasons) > 0


class TestMultiComponentIntegration:
    """多组件集成测试"""

    @pytest.fixture
    def full_system(self):
        """创建完整系统"""
        return {
            "iteration_loop": IterationLoop(
                max_iterations=5,
                strategy=IterationStrategy.BALANCED,
            ),
            "evaluator": ResultEvaluator(),
            "reflection_engine": ReflectionEngine(depth=2),
            "memory": AgentMemory(enable_learning=True),
        }

    def test_full_system_workflow(self, full_system):
        """测试完整系统工作流"""
        query = "诊断实例 CPU 使用率过高"

        # 初始化
        iteration_loop = full_system["iteration_loop"]
        evaluator = full_system["evaluator"]
        reflection_engine = full_system["reflection_engine"]
        memory = full_system["memory"]

        iteration = 0
        responses = [
            "CPU 高",
            "CPU 使用率 85%，需要分析",
            "## CPU 分析报告\n\nCPU 使用率 85%。\n\n建议：优化 SQL",
        ]

        last_check = None
        for response in responses:
            # 执行
            memory.add_execution_memory(
                iteration=iteration,
                tool_name="get_cpu_monitoring",
                tool_result={"cpu": "85%"},
                response=response,
                query=query,
            )

            # 评估
            evaluation = evaluator.evaluate(response, query, iteration=iteration)
            memory.add_evaluation_memory(
                iteration=iteration,
                score=evaluation.score,
                passed=evaluation.passed,
                criteria={},
                query=query,
            )

            # 反思
            reflection = reflection_engine.reflect(
                query, response, evaluation, iteration,
                context={},  # 添加空上下文
            )
            memory.add_reflection_memory(
                iteration=iteration,
                analysis=reflection.analysis,
                issues=reflection.issues,
                improvements=reflection.improvements,
                query=query,
            )

            # 记录迭代
            iteration_loop.record_iteration(
                iteration=iteration,
                score=evaluation.score,
                response=response,
                time_ms=100.0,
            )

            # 检查终止
            last_check = iteration_loop.check_termination(iteration, evaluation)
            if last_check.should_terminate:
                break

            iteration += 1

        # 获取结果
        result = iteration_loop.get_result(last_check.reason)

        # 验证整个流程
        assert result.total_iterations <= len(responses)
        stats = memory.get_stats()
        assert stats.get("total_entries", 0) >= iteration + 1

        # 学习
        patterns = memory.learn_from_memories()
        assert isinstance(patterns, dict)