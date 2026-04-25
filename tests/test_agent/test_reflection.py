"""Agent 反思引擎测试。"""

import pytest
from unittest.mock import Mock, MagicMock

from rds_agent.agent.reflection import (
    ReflectionEngine,
    ReflectionResult,
    ReflectionType,
    ReflectionDepth,
    ReflectionPromptTemplate,
)


class TestReflectionEngine:
    """反思引擎测试"""

    @pytest.fixture
    def reflection_engine(self):
        """创建反思引擎"""
        return ReflectionEngine(depth=2)

    @pytest.fixture
    def mock_evaluation_low(self):
        """模拟低评分评估"""
        mock = Mock()
        mock.score = 0.4
        mock.details = {}
        return mock

    @pytest.fixture
    def mock_evaluation_medium(self):
        """模拟中等评分评估"""
        mock = Mock()
        mock.score = 0.65
        mock.details = {}
        return mock

    @pytest.fixture
    def mock_evaluation_high(self):
        """模拟高评分评估"""
        mock = Mock()
        mock.score = 0.85
        mock.details = {}
        return mock

    def test_reflection_engine_creation(self):
        """测试创建反思引擎"""
        engine = ReflectionEngine()
        assert engine.depth == 2
        assert engine.llm_client is None

    def test_reflection_engine_custom_depth(self):
        """测试自定义深度"""
        engine = ReflectionEngine(depth=3)
        assert engine.depth == 3

    def test_reflect_quality_type(self, reflection_engine, mock_evaluation_medium):
        """测试质量反思类型"""
        result = reflection_engine.reflect(
            query="CPU 使用率过高",
            response="这是一个简短的响应",
            evaluation=mock_evaluation_medium,
            iteration=1,
        )

        assert result.reflection_type == ReflectionType.QUALITY
        assert len(result.analysis) > 0

    def test_reflect_error_type(self, reflection_engine, mock_evaluation_low):
        """测试错误反思类型"""
        # 添加 error 属性到 mock
        mock_evaluation_low.error = "执行超时"
        result = reflection_engine.reflect(
            query="分析 CPU 问题",
            response="发生错误：执行失败",
            evaluation=mock_evaluation_low,
            iteration=1,
        )

        assert result.reflection_type == ReflectionType.ERROR

    def test_reflect_strategy_type(self, reflection_engine, mock_evaluation_high):
        """测试策略反思类型"""
        # 添加 tool_calls 属性到 mock
        mock_evaluation_high.tool_calls = ["get_cpu", "analyze_sql"]
        result = reflection_engine.reflect(
            query="诊断实例",
            response="详细的诊断响应...",
            evaluation=mock_evaluation_high,
            iteration=2,
        )

        assert result.reflection_type == ReflectionType.STRATEGY

    def test_reflect_short_response(self, reflection_engine, mock_evaluation_medium):
        """测试短响应反思"""
        result = reflection_engine.reflect(
            query="详细分析",
            response="短",  # 过短响应
            evaluation=mock_evaluation_medium,
            iteration=1,
        )

        assert "响应过短" in result.issues[0] or len(result.issues) > 0

    def test_reflect_error_keywords(self, reflection_engine, mock_evaluation_low):
        """测试错误关键词"""
        mock_evaluation_low.error = None
        result = reflection_engine.reflect(
            query="检查实例",
            response="执行过程中发生错误，无法完成",
            evaluation=mock_evaluation_low,
            iteration=1,
            context={"instance": "db-01"},  # 提供上下文
        )

        assert len(result.issues) > 0
        assert len(result.improvements) > 0

    def test_reflect_with_context(self, reflection_engine, mock_evaluation_medium):
        """测试带上下文反思"""
        context = {"instance_name": "db-prod-01", "region": "cn-east"}

        result = reflection_engine.reflect(
            query="分析 CPU",
            response="CPU 使用率为 85%",
            evaluation=mock_evaluation_medium,
            iteration=1,
            context=context,
        )

        assert result.updated_context == context

    def test_reflect_result_to_prompt(self):
        """测试反思结果转提示"""
        result = ReflectionResult(
            analysis="分析结果",
            issues=["问题1", "问题2"],
            improvements=["改进1", "改进2"],
            confidence=0.8,
        )

        prompt_context = result.to_prompt_context()
        assert "分析结果" in prompt_context
        assert "问题1" in prompt_context
        assert "改进1" in prompt_context

    def test_reflection_history(self, reflection_engine, mock_evaluation_medium):
        """测试反思历史"""
        reflection_engine.reflect(
            query="问题1",
            response="响应1",
            evaluation=mock_evaluation_medium,
            iteration=1,
        )
        reflection_engine.reflect(
            query="问题2",
            response="响应2",
            evaluation=mock_evaluation_medium,
            iteration=2,
        )

        history = reflection_engine.get_history()
        assert len(history) == 2

    def test_clear_history(self, reflection_engine, mock_evaluation_medium):
        """测试清空历史"""
        reflection_engine.reflect(
            query="问题",
            response="响应",
            evaluation=mock_evaluation_medium,
            iteration=1,
        )

        reflection_engine.clear_history()
        assert len(reflection_engine.get_history()) == 0


class TestReflectionResult:
    """反思结果测试"""

    def test_reflection_result_creation(self):
        """测试创建反思结果"""
        result = ReflectionResult(
            analysis="总体分析",
            issues=["问题1", "问题2"],
            improvements=["改进1", "改进2"],
            confidence=0.85,
        )

        assert result.analysis == "总体分析"
        assert len(result.issues) == 2
        assert len(result.improvements) == 2
        assert result.confidence == 0.85

    def test_reflection_result_with_strategy(self):
        """测试带策略调整的反思结果"""
        result = ReflectionResult(
            analysis="策略分析",
            strategy_adjustment="建议使用更激进的工具调用策略",
        )

        assert result.strategy_adjustment == "建议使用更激进的工具调用策略"

    def test_reflection_result_to_prompt_context(self):
        """测试转换为提示上下文"""
        result = ReflectionResult(
            analysis="质量未达标",
            issues=["响应过短", "缺少关键信息"],
            improvements=["提供更详细响应", "补充实例信息"],
            strategy_adjustment="调整执行策略",
        )

        context = result.to_prompt_context()

        assert "质量未达标" in context
        assert "响应过短" in context
        assert "提供更详细响应" in context
        assert "策略调整" in context


class TestReflectionType:
    """反思类型测试"""

    def test_reflection_types(self):
        """测试反思类型枚举"""
        assert ReflectionType.QUALITY.value == "quality"
        assert ReflectionType.ERROR.value == "error"
        assert ReflectionType.STRATEGY.value == "strategy"
        assert ReflectionType.TOOL.value == "tool"
        assert ReflectionType.SELF.value == "self"


class TestReflectionDepth:
    """反思深度测试"""

    def test_reflection_depths(self):
        """测试反思深度枚举"""
        assert ReflectionDepth.SURFACE.value == "surface"
        assert ReflectionDepth.MODERATE.value == "moderate"
        assert ReflectionDepth.DEEP.value == "deep"


class TestReflectionPromptTemplate:
    """反思提示模板测试"""

    def test_quality_reflection_template(self):
        """测试质量反思模板"""
        template = ReflectionPromptTemplate.QUALITY_REFLECTION

        assert "质量反思" in template
        assert "{query}" in template
        assert "{response}" in template
        assert "{score}" in template

    def test_error_reflection_template(self):
        """测试错误反思模板"""
        template = ReflectionPromptTemplate.ERROR_REFLECTION

        assert "执行错误" in template
        assert "{error}" in template
        assert "{context}" in template

    def test_strategy_reflection_template(self):
        """测试策略反思模板"""
        template = ReflectionPromptTemplate.STRATEGY_REFLECTION

        assert "执行策略" in template
        assert "{iteration}" in template
        assert "{tool_calls}" in template