"""反思引擎 - Agent 自我反思和改进机制

反思机制让 Agent 能够：
1. 分析自己的输出质量
2. 识别问题和不足
3. 制定改进策略
4. 优化后续执行

参考 Hermes Agent 的反思架构设计
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from rds_agent.utils.logger import get_logger

logger = get_logger("agent_reflection")


class ReflectionType(str, Enum):
    """反思类型"""

    QUALITY = "quality"          # 质量反思
    ERROR = "error"              # 错误反思
    STRATEGY = "strategy"        # 策略反思
    TOOL = "tool"                # 工具反思
    CONTEXT = "context"          # 上下文反思
    SELF = "self"                # 自我反思


class ReflectionDepth(str, Enum):
    """反思深度"""

    SURFACE = "surface"          # 表层反思：仅分析输出
    MODERATE = "moderate"        # 中层反思：分析过程和输出
    DEEP = "deep"                # 深层反思：分析根因和策略


@dataclass
class ReflectionResult:
    """反思结果"""

    # 分析
    analysis: str                                          # 总体分析
    issues: List[str] = field(default_factory=list)        # 发现的问题
    strengths: List[str] = field(default_factory=list)     # 发现的优点

    # 改进
    improvements: List[str] = field(default_factory=list)  # 改进建议
    priority_improvements: List[str] = field(default_factory=list)  # 优先改进

    # 上下文更新
    updated_context: Dict[str, Any] = field(default_factory=dict)  # 更新的上下文

    # 新工具
    new_tools: List[str] = field(default_factory=list)     # 建议添加的工具

    # 策略调整
    strategy_adjustment: Optional[str] = None              # 策略调整建议

    # 元数据
    reflection_type: ReflectionType = ReflectionType.QUALITY
    confidence: float = 0.8                                # 反思置信度
    timestamp: datetime = field(default_factory=datetime.now)

    def to_prompt_context(self) -> str:
        """转换为可注入到 LLM 的上下文"""
        lines = [
            "## 反思分析",
            f"总体分析: {self.analysis}",
        ]

        if self.issues:
            lines.append("\n发现的问题:")
            for issue in self.issues:
                lines.append(f"- {issue}")

        if self.improvements:
            lines.append("\n改进建议:")
            for imp in self.improvements:
                lines.append(f"- {imp}")

        if self.strategy_adjustment:
            lines.append(f"\n策略调整: {self.strategy_adjustment}")

        return "\n".join(lines)


class ReflectionPromptTemplate:
    """反思提示词模板"""

    QUALITY_REFLECTION = """
请对以下 Agent 响应进行质量反思：

**用户查询**: {query}
**Agent 响应**: {response}
**质量评分**: {score}
**评估详情**: {details}

请分析：
1. 响应是否完整解决了用户的问题？
2. 响应的准确性和可靠性如何？
3. 响应的结构和表达是否清晰？
4. 有哪些可以改进的地方？

请输出 JSON 格式的反思结果：
```json
{
  "analysis": "总体分析",
  "issues": ["问题1", "问题2"],
  "improvements": ["改进1", "改进2"],
  "confidence": 0.8
}
```
"""

    ERROR_REFLECTION = """
请对以下执行错误进行反思：

**用户查询**: {query}
**执行阶段**: {phase}
**错误信息**: {error}
**上下文**: {context}

请分析：
1. 错误的根本原因是什么？
2. 是否是工具调用问题？参数问题？
3. 如何避免类似的错误？
4. 有哪些替代方案？

请输出 JSON 格式的反思结果：
```json
{
  "analysis": "错误分析",
  "root_cause": "根本原因",
  "issues": ["问题列表"],
  "improvements": ["改进方案"],
  "alternative_approaches": ["替代方案"]
}
```
"""

    STRATEGY_REFLECTION = """
请对以下执行策略进行反思：

**用户查询**: {query}
**迭代次数**: {iteration}
**执行结果**: {response}
**工具调用**: {tool_calls}
**质量评分**: {score}

请分析：
1. 当前策略是否有效？
2. 工具调用是否合理？
3. 是否需要调整执行顺序？
4. 是否需要增加或减少工具？

请输出 JSON 格式的反思结果：
```json
{
  "analysis": "策略分析",
  "strategy_effectiveness": "有效性评估",
  "tool_evaluation": {"tool_name": "评估"},
  "strategy_adjustment": "调整建议",
  "recommended_tools": ["工具列表"]
}
```
"""

    SELF_REFLECTION = """
请进行自我反思，评估当前迭代的表现：

**迭代次数**: {iteration}
**历史响应**: {history_responses}
**质量变化**: {quality_trend}
**工具使用**: {tool_usage}

请分析：
1. 迭代是否有效改进了结果？
2. 哪些改进措施最有效？
3. 是否陷入无效循环？
4. 何时应该终止迭代？

请输出 JSON 格式的反思结果：
```json
{
  "analysis": "自我评估",
  "iteration_effectiveness": "有效性",
  "effective_improvements": ["有效改进"],
  "ineffective_attempts": ["无效尝试"],
  "should_terminate": true/false,
  "termination_reason": "原因"
}
```
"""


class ReflectionEngine:
    """反思引擎 - Agent 自我反思的核心组件

    支持多种反思类型：
    - 质量反思：分析输出质量
    - 错误反思：分析执行错误
    - 策略反思：分析执行策略
    - 工具反思：分析工具使用
    - 自我反思：评估迭代效果

    反思深度可配置：
    - 表层：仅分析输出
    - 中层：分析过程和输出
    - 深层：分析根因和策略
    """

    def __init__(
        self,
        depth: int = 2,
        llm_client: Optional[Any] = None,
    ):
        """初始化反思引擎

        Args:
            depth: 反思深度（1=表层, 2=中层, 3=深层）
            llm_client: LLM 客户端（用于智能反思）
        """
        self.depth = depth
        self.llm_client = llm_client
        self.templates = ReflectionPromptTemplate()

        # 反思历史
        self._reflection_history: List[ReflectionResult] = []

        logger.info(f"ReflectionEngine initialized: depth={depth}")

    def reflect(
        self,
        query: str,
        response: str,
        evaluation: Any,
        iteration: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> ReflectionResult:
        """执行反思

        Args:
            query: 用户查询
            response: Agent 响应
            evaluation: 评估结果
            iteration: 当前迭代次数
            context: 执行上下文

        Returns:
            ReflectionResult 反思结果
        """
        # 根据评估结果选择反思类型
        if hasattr(evaluation, 'score') and evaluation.score < 0.5:
            reflection_type = ReflectionType.ERROR
        elif hasattr(evaluation, 'score') and evaluation.score < 0.7:
            reflection_type = ReflectionType.QUALITY
        else:
            reflection_type = ReflectionType.STRATEGY

        # 执行对应类型的反思
        if reflection_type == ReflectionType.ERROR:
            result = self._reflect_error(query, response, evaluation, context)
        elif reflection_type == ReflectionType.QUALITY:
            result = self._reflect_quality(query, response, evaluation, context)
        elif reflection_type == ReflectionType.STRATEGY:
            result = self._reflect_strategy(query, response, evaluation, iteration, context)
        else:
            result = self._reflect_default(query, response, evaluation)

        # 添加元数据
        result.reflection_type = reflection_type
        result.timestamp = datetime.now()

        # 记录历史
        self._reflection_history.append(result)

        logger.info(
            f"Reflection completed: type={reflection_type}, "
            f"issues={len(result.issues)}, improvements={len(result.improvements)}"
        )

        return result

    def _reflect_quality(
        self,
        query: str,
        response: str,
        evaluation: Any,
        context: Optional[Dict[str, Any]],
    ) -> ReflectionResult:
        """质量反思"""
        score = getattr(evaluation, 'score', 0.0)
        details = getattr(evaluation, 'details', {})

        # 如果有 LLM，执行智能反思
        if self.llm_client and self.depth >= 2:
            return self._llm_reflect(
                ReflectionType.QUALITY,
                query=query,
                response=response,
                score=score,
                details=details,
            )

        # 默认规则反思
        issues = []
        improvements = []

        # 分析常见问题
        if len(response) < 50:
            issues.append("响应过短，可能未完整解决问题")
            improvements.append("提供更详细和完整的响应")

        if "错误" in response or "失败" in response:
            issues.append("响应包含错误信息")
            improvements.append("检查工具调用参数，确保正确执行")

        if score < 0.5:
            issues.append(f"质量评分过低: {score}")
            improvements.append("重新分析问题，选择合适的工具")

        if score < 0.7:
            issues.append(f"质量评分未达标: {score}")
            improvements.append("优化响应结构和内容")

        # 根据深度添加更多分析
        if self.depth >= 2:
            if not details.get("has_tool_calls"):
                issues.append("未使用任何工具")
                improvements.append("分析是否需要工具辅助")

            if details.get("error"):
                issues.append(f"存在错误: {details.get('error')}")
                improvements.append("修复错误后重新执行")

        # 深层反思
        if self.depth >= 3:
            if context and not context.get("instance_name"):
                issues.append("缺少关键上下文信息")
                improvements.append("补充实例名称等关键信息")

        analysis = "响应质量未达到预期标准，需要改进"

        return ReflectionResult(
            analysis=analysis,
            issues=issues,
            improvements=improvements,
            updated_context=context or {},
            confidence=0.7,
        )

    def _reflect_error(
        self,
        query: str,
        response: str,
        evaluation: Any,
        context: Optional[Dict[str, Any]],
    ) -> ReflectionResult:
        """错误反思"""
        error = getattr(evaluation, 'error', None) or context.get("error", "")

        if self.llm_client and self.depth >= 2:
            return self._llm_reflect(
                ReflectionType.ERROR,
                query=query,
                response=response,
                error=error,
                context=context,
            )

        # 分析常见错误
        issues = []
        improvements = []

        if "timeout" in error.lower():
            issues.append("执行超时")
            improvements.append("优化工具调用，减少不必要的步骤")

        if "not found" in error.lower() or "不存在" in error.lower():
            issues.append("工具或参数不存在")
            improvements.append("检查工具名称和参数是否正确")

        if "connection" in error.lower():
            issues.append("连接问题")
            improvements.append("检查实例连接状态")

        if "permission" in error.lower():
            issues.append("权限问题")
            improvements.append("检查用户权限配置")

        # 默认改进
        if not improvements:
            issues.append(f"未知错误: {error}")
            improvements.append("重新执行，尝试不同的策略")

        analysis = f"执行过程中发生错误: {error}"

        return ReflectionResult(
            analysis=analysis,
            issues=issues,
            improvements=improvements,
            updated_context=context or {},
            confidence=0.8,
        )

    def _reflect_strategy(
        self,
        query: str,
        response: str,
        evaluation: Any,
        iteration: int,
        context: Optional[Dict[str, Any]],
    ) -> ReflectionResult:
        """策略反思"""
        score = getattr(evaluation, 'score', 0.0)
        tool_calls = getattr(evaluation, 'tool_calls', [])

        if self.llm_client and self.depth >= 2:
            return self._llm_reflect(
                ReflectionType.STRATEGY,
                query=query,
                response=response,
                iteration=iteration,
                score=score,
                tool_calls=tool_calls,
            )

        # 分析策略有效性
        issues = []
        improvements = []
        new_tools = []

        # 检查迭代效果
        if iteration >= 2 and score < 0.8:
            issues.append(f"迭代 {iteration} 次后质量仍未达标")
            improvements.append("考虑调整迭代策略或终止迭代")

        # 检查工具使用
        if not tool_calls:
            issues.append("未调用任何工具")
            improvements.append("分析问题，选择合适的工具")
            new_tools.append("knowledge_search")  # 建议使用知识库

        if len(tool_calls) > 5:
            issues.append("工具调用过多")
            improvements.append("优化工具调用顺序，减少冗余")

        # 深层策略分析
        if self.depth >= 3:
            # 分析历史反思
            if len(self._reflection_history) >= 2:
                prev_reflections = self._reflection_history[-2:]
                same_issues = self._check_repeated_issues(prev_reflections)
                if same_issues:
                    issues.append(f"重复问题: {same_issues}")
                    improvements.append("尝试完全不同的策略")

        analysis = "当前执行策略需要优化"

        strategy_adjustment = None
        if score < 0.7:
            strategy_adjustment = "建议使用更激进的工具调用策略"

        return ReflectionResult(
            analysis=analysis,
            issues=issues,
            improvements=improvements,
            new_tools=new_tools,
            strategy_adjustment=strategy_adjustment,
            updated_context=context or {},
            confidence=0.7,
        )

    def _reflect_default(
        self,
        query: str,
        response: str,
        evaluation: Any,
    ) -> ReflectionResult:
        """默认反思"""
        return ReflectionResult(
            analysis="基本反思：响应生成完成",
            improvements=["继续优化响应质量"],
            confidence=0.5,
        )

    def _llm_reflect(
        self,
        reflection_type: ReflectionType,
        **kwargs,
    ) -> ReflectionResult:
        """使用 LLM 进行智能反思"""
        try:
            # 选择模板
            if reflection_type == ReflectionType.QUALITY:
                prompt = self.templates.QUALITY_REFLECTION.format(**kwargs)
            elif reflection_type == ReflectionType.ERROR:
                prompt = self.templates.ERROR_REFLECTION.format(**kwargs)
            elif reflection_type == ReflectionType.STRATEGY:
                prompt = self.templates.STRATEGY_REFLECTION.format(**kwargs)
            else:
                prompt = self.templates.SELF_REFLECTION.format(**kwargs)

            # 调用 LLM
            if hasattr(self.llm_client, 'invoke'):
                llm_response = self.llm_client.invoke(prompt)
            elif hasattr(self.llm_client, 'chat'):
                llm_response = self.llm_client.chat([{"role": "user", "content": prompt}])
                llm_response = llm_response.get("content", "")
            else:
                # 无法调用 LLM，使用默认反思
                return self._reflect_default(kwargs.get("query", ""), kwargs.get("response", ""), None)

            # 解析 LLM 响应
            return self._parse_llm_reflection(llm_response, reflection_type)

        except Exception as e:
            logger.warning(f"LLM reflection failed: {e}")
            return self._reflect_default(kwargs.get("query", ""), kwargs.get("response", ""), None)

    def _parse_llm_reflection(self, response: str, reflection_type: ReflectionType) -> ReflectionResult:
        """解析 LLM 反思响应"""
        import json
        import re

        try:
            # 提取 JSON
            json_match = re.search(r'\{[^{}]*\}', response)
            if json_match:
                parsed = json.loads(json_match.group())

                return ReflectionResult(
                    analysis=parsed.get("analysis", ""),
                    issues=parsed.get("issues", []),
                    improvements=parsed.get("improvements", []),
                    strategy_adjustment=parsed.get("strategy_adjustment"),
                    new_tools=parsed.get("recommended_tools", []),
                    confidence=parsed.get("confidence", 0.8),
                )
        except (json.JSONDecodeError, Exception) as e:
            logger.debug(f"Failed to parse LLM reflection: {e}")

        # 解析失败，返回默认
        return ReflectionResult(
            analysis=response[:200],
            improvements=["根据 LLM 建议改进"],
            confidence=0.6,
        )

    def _check_repeated_issues(self, reflections: List[ReflectionResult]) -> Optional[str]:
        """检查重复问题"""
        issue_counts = {}
        for r in reflections:
            for issue in r.issues:
                issue_counts[issue] = issue_counts.get(issue, 0) + 1

        for issue, count in issue_counts.items():
            if count >= 2:
                return issue

        return None

    def get_history(self) -> List[ReflectionResult]:
        """获取反思历史"""
        return self._reflection_history

    def clear_history(self) -> None:
        """清空反思历史"""
        self._reflection_history.clear()


def create_reflection_engine(
    depth: int = 2,
    llm_client: Optional[Any] = None,
) -> ReflectionEngine:
    """创建反思引擎"""
    return ReflectionEngine(depth=depth, llm_client=llm_client)