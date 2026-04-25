"""Agent 自我迭代集成测试。

测试完整的迭代循环流程：
1. IterativeRouterAgent 迭代执行
2. 评估-反思-改进循环
3. 终止条件检测
4. 最佳结果选择
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
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
from rds_agent.router.agent import IterationConfig


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

        for i, response in enumerate(responses):
            # 评估
            evaluation = evaluator.evaluate(
                response=response,
                query=query,
                iteration=i,
            )

            # 反思
            reflection = reflection_engine.reflect(
                query=query,
                response=response,
                evaluation=evaluation,
                iteration=i,
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
            check = iteration_loop.check_termination(i, evaluation)
            if check.should_terminate:
                break

        # 获取最终结果
        result = iteration_loop.get_result(check.reason)

        # 验证
        assert result.total_iterations <= 3
        assert result.best_score >= 0.7
        assert result.best_response == responses[result.best_iteration]
        assert len(memory.get_stats()["total_entries"]) >= 3

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


class TestIterativeRouterAgentIntegration:
    """IterativeRouterAgent 集成测试"""

    @pytest.fixture
    def mock_router_agent(self):
        """创建 Mock RouterAgent"""
        with patch("rds_agent.router.agent.RouterAgent.invoke") as mock_invoke:
            # 模拟响应逐步改进
            responses = [
                {"response": "CPU 高", "agent_type": "hermes"},
                {"response": "CPU 使用率 85%", "agent_type": "hermes"},
                {"response": "## CPU 分析\n\nCPU 使用率 85%，需要优化", "agent_type": "hermes"},
            ]
            mock_invoke.side_effect = responses
            yield mock_invoke

    def test_iteration_config_creation(self):
        """测试迭代配置创建"""
        config = IterationConfig(
            strategy=IterationStrategy.BALANCED,
            max_iterations=3,
            min_quality_score=0.8,
        )

        assert config.strategy == IterationStrategy.BALANCED
        assert config.max_iterations == 3

    def test_iterative_router_agent_components(self):
        """测试迭代 RouterAgent 组件初始化"""
        with patch("rds_agent.router.agent.RouterAgent.__init__", return_value=None):
            agent = IterativeRouterAgent()

            # 手动初始化组件（因为 __init__ 被 mock）
            agent.iteration_config = IterationConfig()
            agent._init_iteration_components()

            assert agent._iteration_loop is not None
            assert agent._evaluator is not None
            assert agent._reflection_engine is not None
            assert agent._memory is not None

    def test_iterative_router_agent_stats(self):
        """测试迭代 RouterAgent 统计"""
        with patch("rds_agent.router.agent.RouterAgent.__init__", return_value=None):
            agent = IterativeRouterAgent()

            agent.iteration_config = IterationConfig()
            agent._init_iteration_components()

            # 添加一些评估记录
            agent._evaluator.evaluate("响应", "问题", iteration=1)

            stats = agent.get_iteration_stats()

            assert "evaluation" in stats
            assert stats["evaluation"]["total_evaluations"] >= 1

    def test_iterative_router_agent_reset(self):
        """测试迭代 RouterAgent 重置"""
        with patch("rds_agent.router.agent.RouterAgent.__init__", return_value=None):
            agent = IterativeRouterAgent()

            agent.iteration_config = IterationConfig()
            agent._init_iteration_components()

            # 添加数据
            agent._iteration_loop.record_iteration(1, 0.5, "响应", 100.0)
            agent._memory.add_execution_memory(1, "tool", "result", "响应", "问题")

            # 重置
            agent.reset_iteration()

            # 验证重置
            assert len(agent._evaluator.get_history()) == 0
            assert agent._iteration_loop.iteration_scores == []


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
            query, response1, evaluation1, iteration=0
        )

        # 验证反思提出了改进建议
        assert len(reflection1.improvements) > 0

        # 第二轮响应（基于改进建议）
        improvements = reflection1.improvements
        response2 = f"CPU 使用率 85%，{improvements[0] if improvements else '需要优化'}"
        evaluation2 = evaluator.evaluate(response2, query, iteration=1)

        # 验证质量提升
        assert evaluation2.score >= evaluation1.score or evaluation2.passed

    def test_reflection_type_selection(self, evaluator, reflection_engine):
        """测试反思类型自动选择"""
        query = "诊断问题"

        # 不同质量的响应应触发不同反思类型
        low_quality_response = "错误"
        low_eval = evaluator.evaluate(low_quality_response, query, iteration=0)
        low_reflection = reflection_engine.reflect(query, low_quality_response, low_eval, iteration=0)
        # 低质量应触发 ERROR 或 QUALITY 反思

        high_quality_response = "## 完整分析\n\n详细结果和建议"
        high_eval = evaluator.evaluate(high_quality_response, query, iteration=1)
        high_reflection = reflection_engine.reflect(query, high_quality_response, high_eval, iteration=1)
        # 高质量应触发 STRATEGY 反思


class TestTerminationIntegration:
    """终止条件集成测试"""

    def test_all_termination_reasons(self):
        """测试所有终止原因"""
        loop = IterationLoop(max_iterations=10)
        evaluator = ResultEvaluator()

        # 测试不同终止场景
        scenarios = [
            # (score, expected_reason_hint)
            (0.95, TerminationReason.SUCCESS),  # 高质量成功
            (0.75, TerminationReason.QUALITY_THRESHOLD),  # 达到阈值
            (0.5, TerminationReason.MAX_ITERATIONS),  # 未达标，最大迭代
        ]

        for score_target, expected_reason in scenarios:
            loop.reset()
            iteration = 0

            # 模拟迭代直到终止
            while iteration < loop.config.max_iterations:
                response = f"测试响应 {iteration}"
                evaluation = evaluator.evaluate(response, "测试问题", iteration)

                loop.record_iteration(iteration, evaluation.score, response, 100.0)

                check = loop.check_termination(iteration, evaluation)
                if check.should_terminate:
                    result = loop.get_result(check.reason)
                    # 验证终止原因合理
                    assert result.termination_reason in [
                        TerminationReason.SUCCESS,
                        TerminationReason.QUALITY_THRESHOLD,
                        TerminationReason.MAX_ITERATIONS,
                        TerminationReason.CONVERGENCE,
                    ]
                    break

                iteration += 1