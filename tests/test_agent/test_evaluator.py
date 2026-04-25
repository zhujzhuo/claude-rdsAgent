"""Agent 评估器测试。"""

import pytest
from unittest.mock import Mock, MagicMock

from rds_agent.agent.evaluator import (
    ResultEvaluator,
    EvaluationResult,
    EvaluationCriteria,
    EvaluationCriterion,
    CriterionScore,
)


class TestResultEvaluator:
    """结果评估器测试"""

    @pytest.fixture
    def evaluator(self):
        """创建评估器"""
        return ResultEvaluator()

    @pytest.fixture
    def evaluator_strict(self):
        """创建严格评估器"""
        criteria = EvaluationCriteria(min_score=0.8)
        return ResultEvaluator(criteria=criteria)

    def test_evaluator_creation(self):
        """测试创建评估器"""
        evaluator = ResultEvaluator()
        assert evaluator.criteria.min_score == 0.7

    def test_evaluator_custom_criteria(self):
        """测试自定义标准"""
        criteria = EvaluationCriteria(
            min_score=0.9,
            target_score=0.95,
            error_penalty=0.5,
        )
        evaluator = ResultEvaluator(criteria=criteria)

        assert evaluator.criteria.min_score == 0.9
        assert evaluator.criteria.target_score == 0.95

    def test_evaluate_complete_response(self, evaluator):
        """测试评估完整响应"""
        response = """
        ## 分析结果

        实例 db-prod-01 的 CPU 使用率分析：

        - 当前 CPU 使用率：85%
        - 高峰时段：14:00-16:00
        - 主要原因：慢 SQL 执行

        ## 建议

        1. 优化慢 SQL
        2. 调整 Buffer Pool
        3. 增加连接池配置
        """

        result = evaluator.evaluate(
            response=response,
            query="分析 CPU 使用率",
            tool_results=[{"name": "get_cpu_monitoring", "result": "85%"}],
            iteration=1,
        )

        assert result.score >= 0.5
        assert len(result.criterion_scores) > 0

    def test_evaluate_short_response(self, evaluator):
        """测试评估短响应"""
        result = evaluator.evaluate(
            response="CPU 高",
            query="详细分析 CPU 使用率",
            iteration=1,
        )

        # 短响应应该得低分
        assert result.score < 0.7
        assert len(result.issues) > 0  # 应有问题描述

    def test_evaluate_error_response(self, evaluator):
        """测试评估错误响应"""
        result = evaluator.evaluate(
            response="执行失败，发生错误",
            query="分析实例",
            iteration=1,
        )

        assert result.score < 0.8
        assert len(result.issues) > 0

    def test_evaluate_with_tool_results(self, evaluator):
        """测试带工具结果评估"""
        tool_results = [
            {"name": "get_monitoring_data", "result": "CPU: 85%"},
            {"name": "get_slow_queries", "result": "SELECT * FROM users"},
        ]

        result = evaluator.evaluate(
            response="分析结果：CPU 使用率 85%，发现慢 SQL",
            query="诊断实例",
            tool_results=tool_results,
            iteration=1,
        )

        assert result.details.get("tool_calls", 0) == 2

    def test_evaluate_pass_threshold(self, evaluator):
        """测试通过阈值"""
        response = """
        ## 完整分析

        详细的诊断结果和优化建议...

        - 数据点 1: xxx
        - 数据点 2: xxx

        结论：需要优化 SQL
        """

        result = evaluator.evaluate(
            response=response,
            query="诊断实例",
            iteration=1,
        )

        assert result.passed == (result.score >= evaluator.criteria.min_score)

    def test_evaluate_statistics(self, evaluator):
        """测试评估统计"""
        evaluator.evaluate(response="响应1", query="问题1", iteration=1)
        evaluator.evaluate(response="响应2", query="问题2", iteration=2)

        stats = evaluator.get_statistics()
        assert stats["total_evaluations"] == 2
        assert "avg_score" in stats

    def test_clear_history(self, evaluator):
        """测试清空历史"""
        evaluator.evaluate(response="响应", query="问题", iteration=1)
        evaluator.clear_history()

        assert len(evaluator.get_history()) == 0


class TestEvaluationResult:
    """评估结果测试"""

    def test_evaluation_result_creation(self):
        """测试创建评估结果"""
        criterion_scores = [
            CriterionScore(
                criterion=EvaluationCriterion.COMPLETENESS,
                score=0.85,
                weight=0.3,
            ),
            CriterionScore(
                criterion=EvaluationCriterion.ACCURACY,
                score=0.90,
                weight=0.25,
            ),
        ]

        result = EvaluationResult(
            score=0.85,
            passed=True,
            criterion_scores=criterion_scores,
            issues=["问题1"],
            suggestions=["建议1"],
        )

        assert result.score == 0.85
        assert result.passed == True
        assert len(result.criterion_scores) == 2

    def test_get_criterion_score(self):
        """测试获取标准评分"""
        completeness_score = CriterionScore(
            criterion=EvaluationCriterion.COMPLETENESS,
            score=0.8,
            weight=0.3,
        )
        accuracy_score = CriterionScore(
            criterion=EvaluationCriterion.ACCURACY,
            score=0.9,
            weight=0.25,
        )

        result = EvaluationResult(
            score=0.85,
            passed=True,
            criterion_scores=[completeness_score, accuracy_score],
        )

        found = result.get_criterion_score(EvaluationCriterion.COMPLETENESS)
        assert found.score == 0.8

        not_found = result.get_criterion_score(EvaluationCriterion.EFFICIENCY)
        assert not_found is None

    def test_evaluation_result_summary(self):
        """测试评估结果摘要"""
        result = EvaluationResult(
            score=0.75,
            passed=True,
            criterion_scores=[
                CriterionScore(EvaluationCriterion.COMPLETENESS, 0.8, 0.3),
                CriterionScore(EvaluationCriterion.ACCURACY, 0.7, 0.25),
            ],
            issues=["问题1"],
        )

        summary = result.to_summary()
        assert "score=0.75" in summary
        assert "passed=True" in summary


class TestCriterionScore:
    """标准评分测试"""

    def test_criterion_score_creation(self):
        """测试创建标准评分"""
        score = CriterionScore(
            criterion=EvaluationCriterion.COMPLETENESS,
            score=0.85,
            weight=0.3,
            details={"response_length": 200},
        )

        assert score.criterion == EvaluationCriterion.COMPLETENESS
        assert score.score == 0.85
        assert score.weight == 0.3

    def test_weighted_score(self):
        """测试加权分数"""
        score = CriterionScore(
            criterion=EvaluationCriterion.COMPLETENESS,
            score=0.8,
            weight=0.3,
        )

        weighted = score.weighted_score()
        assert weighted == 0.24  # 0.8 * 0.3


class TestEvaluationCriteria:
    """评估标准配置测试"""

    def test_evaluation_criteria_defaults(self):
        """测试默认配置"""
        criteria = EvaluationCriteria()

        assert criteria.min_score == 0.7
        assert criteria.target_score == 0.9
        assert criteria.error_penalty == 0.3

    def test_evaluation_criteria_weights(self):
        """测试权重配置"""
        criteria = EvaluationCriteria()

        completeness_weight = criteria.get_weight(EvaluationCriterion.COMPLETENESS)
        assert completeness_weight == 0.3

        accuracy_weight = criteria.get_weight(EvaluationCriterion.ACCURACY)
        assert accuracy_weight == 0.25

    def test_evaluation_criteria_custom_weights(self):
        """测试自定义权重"""
        criteria = EvaluationCriteria(
            weights={
                EvaluationCriterion.COMPLETENESS: 0.4,
                EvaluationCriterion.ACCURACY: 0.3,
            }
        )

        assert criteria.get_weight(EvaluationCriterion.COMPLETENESS) == 0.4


class TestEvaluationCriterion:
    """评估标准枚举测试"""

    def test_evaluation_criterion_values(self):
        """测试评估标准值"""
        assert EvaluationCriterion.COMPLETENESS.value == "completeness"
        assert EvaluationCriterion.ACCURACY.value == "accuracy"
        assert EvaluationCriterion.READABILITY.value == "readability"
        assert EvaluationCriterion.EFFECTIVENESS.value == "effectiveness"
        assert EvaluationCriterion.EFFICIENCY.value == "efficiency"