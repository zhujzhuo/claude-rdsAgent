"""结果评估器 - 评估 Agent 执行结果的质量

评估维度：
1. 完整性：是否完整解决了用户问题
2. 准确性：响应内容是否准确可靠
3. 可读性：响应结构和表达是否清晰
4. 有效性：是否使用了合适的工具
5. 效率性：执行时间和资源消耗

参考 Hermes Agent 的评估架构
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field

from rds_agent.utils.logger import get_logger

logger = get_logger("agent_evaluator")


class EvaluationCriterion(str, Enum):
    """评估标准"""

    COMPLETENESS = "completeness"      # 完整性
    ACCURACY = "accuracy"              # 准确性
    READABILITY = "readability"        # 可读性
    EFFECTIVENESS = "effectiveness"     # 有效性
    EFFICIENCY = "efficiency"          # 效率性
    ERROR_FREE = "error_free"          # 无错误
    RELEVANCE = "relevance"            # 相关性
    ACTIONABLE = "actionable"          # 可操作性


class EvaluationCriteria(BaseModel):
    """评估标准配置"""

    # 权重配置
    weights: Dict[EvaluationCriterion, float] = Field(
        default_factory=lambda: {
            EvaluationCriterion.COMPLETENESS: 0.3,
            EvaluationCriterion.ACCURACY: 0.25,
            EvaluationCriterion.READABILITY: 0.15,
            EvaluationCriterion.EFFECTIVENESS: 0.15,
            EvaluationCriterion.ERROR_FREE: 0.15,
        },
        description="各标准权重"
    )

    # 最低阈值
    min_score: float = Field(default=0.7, description="最低合格分数")
    target_score: float = Field(default=0.9, description="目标分数")

    # 特殊规则
    error_penalty: float = Field(default=0.3, description="错误扣分")
    empty_response_penalty: float = Field(default=0.5, description="空响应扣分")
    short_response_penalty: float = Field(default=0.2, description="短响应扣分")
    short_response_threshold: int = Field(default=50, description="短响应阈值")

    def get_weight(self, criterion: EvaluationCriterion) -> float:
        """获取权重"""
        return self.weights.get(criterion, 0.1)


@dataclass
class CriterionScore:
    """单项标准评分"""

    criterion: EvaluationCriterion
    score: float
    weight: float
    details: Dict[str, Any] = field(default_factory=dict)

    def weighted_score(self) -> float:
        """加权分数"""
        return self.score * self.weight


@dataclass
class EvaluationResult:
    """评估结果"""

    # 总分
    score: float
    passed: bool

    # 各项评分
    criterion_scores: List[CriterionScore] = field(default_factory=list)

    # 详情
    details: Dict[str, Any] = field(default_factory=dict)

    # 问题
    issues: List[str] = field(default_factory=list)

    # 建议
    suggestions: List[str] = field(default_factory=list)

    # 元数据
    timestamp: datetime = field(default_factory=datetime.now)
    iteration: int = 0

    def get_criterion_score(self, criterion: EvaluationCriterion) -> Optional[CriterionScore]:
        """获取特定标准的评分"""
        for cs in self.criterion_scores:
            if cs.criterion == criterion:
                return cs
        return None

    def to_summary(self) -> str:
        """生成摘要"""
        lines = [
            f"Evaluation Result: score={self.score:.2f}, passed={self.passed}",
            f"Details:",
        ]

        for cs in self.criterion_scores:
            lines.append(f"  - {cs.criterion.value}: {cs.score:.2f} (weight={cs.weight})")

        if self.issues:
            lines.append(f"Issues: {', '.join(self.issues[:3])}")

        return "\n".join(lines)


class ResultEvaluator:
    """结果评估器 - 评估 Agent 输出质量

    支持多种评估方式：
    1. 规则评估：基于预设规则的自动评估
    2. LLM 评估：使用 LLM 进行智能评估
    3. 混合评估：结合规则和 LLM

    可配置评估标准和权重
    """

    def __init__(
        self,
        criteria: Optional[EvaluationCriteria] = None,
        llm_client: Optional[Any] = None,
    ):
        """初始化评估器

        Args:
            criteria: 评估标准配置
            llm_client: LLM 客户端（用于智能评估）
        """
        self.criteria = criteria or EvaluationCriteria()
        self.llm_client = llm_client

        # 评估历史
        self._evaluation_history: List[EvaluationResult] = []

        logger.info(
            f"ResultEvaluator initialized: min_score={self.criteria.min_score}"
        )

    def evaluate(
        self,
        response: str,
        query: str,
        tool_results: Optional[List[Dict[str, Any]]] = None,
        iteration: int = 0,
    ) -> EvaluationResult:
        """评估 Agent 响应

        Args:
            response: Agent 响应
            query: 用户查询
            tool_results: 工具执行结果
            iteration: 当前迭代次数

        Returns:
            EvaluationResult 评估结果
        """
        criterion_scores = []
        issues = []
        suggestions = []

        # 1. 完整性评估
        completeness_score = self._evaluate_completeness(response, query)
        criterion_scores.append(CriterionScore(
            criterion=EvaluationCriterion.COMPLETENESS,
            score=completeness_score,
            weight=self.criteria.get_weight(EvaluationCriterion.COMPLETENESS),
            details={"response_length": len(response)},
        ))
        if completeness_score < 0.5:
            issues.append("响应不完整")

        # 2. 准确性评估
        accuracy_score = self._evaluate_accuracy(response, tool_results)
        criterion_scores.append(CriterionScore(
            criterion=EvaluationCriterion.ACCURACY,
            score=accuracy_score,
            weight=self.criteria.get_weight(EvaluationCriterion.ACCURACY),
            details={"has_tool_results": tool_results is not None},
        ))
        if accuracy_score < 0.5:
            issues.append("响应准确性不足")

        # 3. 可读性评估
        readability_score = self._evaluate_readability(response)
        criterion_scores.append(CriterionScore(
            criterion=EvaluationCriterion.READABILITY,
            score=readability_score,
            weight=self.criteria.get_weight(EvaluationCriterion.READABILITY),
            details={"structure_detected": self._has_structure(response)},
        ))
        if readability_score < 0.5:
            suggestions.append("优化响应结构，提高可读性")

        # 4. 有效性评估
        effectiveness_score = self._evaluate_effectiveness(response, tool_results, query)
        criterion_scores.append(CriterionScore(
            criterion=EvaluationCriterion.EFFECTIVENESS,
            score=effectiveness_score,
            weight=self.criteria.get_weight(EvaluationCriterion.EFFECTIVENESS),
            details={"tool_calls_count": len(tool_results) if tool_results else 0},
        ))
        if effectiveness_score < 0.5:
            issues.append("工具使用效率不足")

        # 5. 无错误评估
        error_free_score = self._evaluate_error_free(response, tool_results)
        criterion_scores.append(CriterionScore(
            criterion=EvaluationCriterion.ERROR_FREE,
            score=error_free_score,
            weight=self.criteria.get_weight(EvaluationCriterion.ERROR_FREE),
            details={"has_errors": error_free_score < 1.0},
        ))
        if error_free_score < 0.7:
            issues.append("存在执行错误")

        # 计算总分
        total_score = sum(cs.weighted_score() for cs in criterion_scores)

        # 应用惩罚
        if not response or len(response) < self.criteria.short_response_threshold:
            total_score -= self.criteria.short_response_penalty
            issues.append("响应过短")

        if self._has_error_keywords(response):
            total_score -= self.criteria.error_penalty
            issues.append("包含错误关键词")

        # 确保分数在 0-1 范围内
        total_score = max(0.0, min(1.0, total_score))

        # 判断是否通过
        passed = total_score >= self.criteria.min_score

        # 构建结果
        result = EvaluationResult(
            score=total_score,
            passed=passed,
            criterion_scores=criterion_scores,
            details={
                "response_length": len(response),
                "tool_calls": len(tool_results) if tool_results else 0,
                "iteration": iteration,
            },
            issues=issues,
            suggestions=suggestions,
            iteration=iteration,
            timestamp=datetime.now(),
        )

        # 记录历史
        self._evaluation_history.append(result)

        logger.info(
            f"Evaluation completed: score={total_score:.2f}, passed={passed}, "
            f"issues={len(issues)}"
        )

        return result

    def _evaluate_completeness(self, response: str, query: str) -> float:
        """评估完整性"""
        score = 1.0

        # 检查响应长度
        if len(response) < 50:
            score -= 0.3

        if len(response) < 100:
            score -= 0.2

        # 检查是否包含关键信息
        # 基于查询关键词检查
        query_keywords = self._extract_keywords(query)
        matched_keywords = sum(1 for kw in query_keywords if kw.lower() in response.lower())

        if matched_keywords < len(query_keywords) * 0.5:
            score -= 0.2

        # 检查是否有结论性内容
        if not any(word in response for word in ["结果", "结论", "建议", "分析", "完成"]):
            score -= 0.1

        return max(0.0, score)

    def _evaluate_accuracy(self, response: str, tool_results: Optional[List[Dict]]) -> float:
        """评估准确性"""
        score = 1.0

        # 如果有工具结果，检查是否引用了
        if tool_results:
            # 检查响应是否基于工具结果
            for result in tool_results:
                result_str = str(result.get("result", ""))
                if result_str and result_str[:50] not in response:
                    score -= 0.1
                    break

        # 检查是否有不确定的表述
        uncertain_phrases = ["不确定", "可能", "大概", "猜测", "估计"]
        for phrase in uncertain_phrases:
            if phrase in response:
                score -= 0.05

        # 检查是否有具体的数值或事实
        if not self._has_specific_data(response):
            score -= 0.1

        return max(0.0, score)

    def _evaluate_readability(self, response: str) -> float:
        """评估可读性"""
        score = 1.0

        # 检查结构
        if not self._has_structure(response):
            score -= 0.2

        # 检查段落划分
        paragraphs = response.split("\n\n")
        if len(paragraphs) < 2:
            score -= 0.1

        # 检查是否有过度冗长的段落
        for para in paragraphs:
            if len(para) > 500:
                score -= 0.05

        # 检查是否有列表或要点
        if not ("-" in response or "*" in response or "•" in response or "1." in response):
            score -= 0.1

        return max(0.0, score)

    def _evaluate_effectiveness(
        self,
        response: str,
        tool_results: Optional[List[Dict]],
        query: str,
    ) -> float:
        """评估有效性"""
        score = 1.0

        # 检查是否使用了工具
        if not tool_results:
            # 没有工具调用，可能不适合复杂问题
            if self._is_complex_query(query):
                score -= 0.3
        else:
            # 有工具调用，检查是否合理
            tool_count = len(tool_results)

            # 过多工具调用可能效率低
            if tool_count > 10:
                score -= 0.1

            # 检查工具是否相关
            for result in tool_results:
                if result.get("error"):
                    score -= 0.1

        return max(0.0, score)

    def _evaluate_error_free(
        self,
        response: str,
        tool_results: Optional[List[Dict]],
    ) -> float:
        """评估无错误"""
        score = 1.0

        # 检查响应中的错误关键词
        error_keywords = ["错误", "失败", "异常", "timeout", "error", "failed"]
        for keyword in error_keywords:
            if keyword.lower() in response.lower():
                score -= 0.2

        # 检查工具结果中的错误
        if tool_results:
            for result in tool_results:
                if result.get("error"):
                    score -= 0.2

        return max(0.0, score)

    def _extract_keywords(self, text: str) -> Set[str]:
        """提取关键词"""
        # 简化版本：提取中文词语
        import re
        keywords = set()

        # 提取中文词
        chinese_words = re.findall(r'[a-zA-Z0-9\-]+|[\u4e00-\u9fa5]{2,}', text)
        keywords.update(chinese_words)

        return keywords

    def _has_structure(self, response: str) -> bool:
        """检查是否有结构"""
        structure_indicators = ["##", "###", "- ", "* ", "1.", "2.", "结论", "建议", "分析"]
        return any(indicator in response for indicator in structure_indicators)

    def _has_specific_data(self, response: str) -> bool:
        """检查是否有具体数据"""
        import re
        # 数字
        if re.search(r'\d+[%\.\d]', response):
            return True
        # 实例名
        if re.search(r'db-[a-zA-Z0-9\-]+', response):
            return True
        return False

    def _is_complex_query(self, query: str) -> bool:
        """检查是否是复杂查询"""
        complex_indicators = ["诊断", "分析", "检查", "优化", "巡检", "详细"]
        return any(indicator in query for indicator in complex_indicators)

    def _has_error_keywords(self, response: str) -> bool:
        """检查是否有错误关键词"""
        error_keywords = ["失败", "错误", "异常", "无法", "timeout"]
        return any(kw in response for kw in error_keywords)

    def get_history(self) -> List[EvaluationResult]:
        """获取评估历史"""
        return self._evaluation_history

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计数据"""
        if not self._evaluation_history:
            return {}

        scores = [r.score for r in self._evaluation_history]

        return {
            "total_evaluations": len(self._evaluation_history),
            "avg_score": sum(scores) / len(scores),
            "max_score": max(scores),
            "min_score": min(scores),
            "pass_rate": sum(1 for r in self._evaluation_history if r.passed) / len(self._evaluation_history),
        }

    def clear_history(self) -> None:
        """清空历史"""
        self._evaluation_history.clear()


def create_evaluator(
    min_score: float = 0.7,
    llm_client: Optional[Any] = None,
) -> ResultEvaluator:
    """创建评估器"""
    criteria = EvaluationCriteria(min_score=min_score)
    return ResultEvaluator(criteria=criteria, llm_client=llm_client)