"""RouterAgent - 三层问题分类路由选择器，支持自我迭代改进。"""

from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
import time

from rds_agent.core.agent import RDSAgent, get_agent
from rds_agent.core.state import IntentType
from rds_agent.hermes.agent import HermesAgent, get_hermes_agent
from rds_agent.diagnostic.agent import DiagnosticAgent, get_diagnostic_agent
from rds_agent.router.classifier import (
    QuestionCategory,
    QuestionClassifier,
    get_classifier,
)
from rds_agent.skills.base import SkillType, SkillState
from rds_agent.skills.executor import SkillExecutor, get_skill_executor
from rds_agent.utils.config import settings
from rds_agent.utils.logger import get_logger

# Agent 自我迭代组件
from rds_agent.agent import (
    IterationStrategy,
    IterationLoop,
    IterationResult,
    TerminationReason,
    ReflectionEngine,
    ReflectionResult,
    ResultEvaluator,
    EvaluationResult,
    AgentMemory,
    ToolExecutor,
    ToolResult,
)

logger = get_logger("router_agent")


class ComplexityLevel(str, Enum):
    """任务复杂度级别"""

    SIMPLE = "simple"      # 单工具调用，快速响应
    MEDIUM = "medium"      # 多工具调用，需组合分析
    COMPLEX = "complex"    # 完整诊断流程，13+检查项


class AgentType(str, Enum):
    """Agent 类型"""

    LANGGRAPH = "langgraph"   # LangGraph Agent 自主规划
    HERMES = "hermes"         # Hermes Agent 快速响应
    DIAGNOSTIC = "diagnostic" # Diagnostic Agent 完整巡检
    SKILL = "skill"           # Skills/SOP 标准化流程
    AUTO = "auto"             # 自动选择


# 意图关键词映射（从 core/nodes.py 复制）
INTENT_KEYWORDS: Dict[IntentType, List[str]] = {
    IntentType.INSTANCE_QUERY: [
        "实例", "列表", "规格", "版本", "架构", "部署",
        "有哪些", "查看实例", "实例信息",
    ],
    IntentType.PERFORMANCE_DIAG: [
        "性能", "QPS", "TPS", "慢", "延迟", "响应",
        "慢查询", "慢SQL", "Buffer", "命中率",
        "性能问题", "性能情况", "运行状态",
    ],
    IntentType.SQL_DIAG: [
        "SQL", "慢SQL", "慢查询", "语句", "查询分析",
        "执行", "processlist", "正在执行",
    ],
    IntentType.CONNECTION_DIAG: [
        "连接", "会话", "连接数", "活跃", "锁", "等待",
        "连接池", "超时", "中断",
    ],
    IntentType.STORAGE_DIAG: [
        "空间", "存储", "容量", "大小", "表大小",
        "索引", "碎片", "磁盘", "数据量",
    ],
    IntentType.PARAMETER_QUERY: [
        "参数", "配置", "设置", "innodb", "max_connections",
        "参数值", "优化建议",
    ],
    IntentType.KNOWLEDGE_QA: [
        "为什么", "怎么", "如何", "是什么", "解释",
        "原理", "区别", "优化方法", "最佳实践",
    ],
}


class RouterAgent:
    """三层问题分类路由选择器 - 根据问题类型自动选择执行路径"""

    # 意图复杂度映射
    INTENT_COMPLEXITY_MAP: Dict[IntentType, ComplexityLevel] = {
        IntentType.INSTANCE_QUERY: ComplexityLevel.SIMPLE,
        IntentType.PARAMETER_QUERY: ComplexityLevel.SIMPLE,
        IntentType.KNOWLEDGE_QA: ComplexityLevel.SIMPLE,
        IntentType.GENERAL_CHAT: ComplexityLevel.SIMPLE,
        IntentType.UNKNOWN: ComplexityLevel.SIMPLE,
        IntentType.PERFORMANCE_DIAG: ComplexityLevel.MEDIUM,
        IntentType.SQL_DIAG: ComplexityLevel.MEDIUM,
        IntentType.CONNECTION_DIAG: ComplexityLevel.MEDIUM,
        IntentType.STORAGE_DIAG: ComplexityLevel.MEDIUM,
    }

    # 完整诊断关键词
    FULL_INSPECTION_KEYWORDS = [
        "完整巡检", "全面检查", "健康巡检", "完整诊断",
        "巡检报告", "检查报告", "全面诊断", "全部检查",
        "13项检查", "完整检查", "系统巡检", "健康检查",
    ]

    # 深度分析关键词
    DEEP_ANALYSIS_KEYWORDS = [
        "详细分析", "深度诊断", "根因分析", "深入分析",
        "全面分析", "彻底检查", "详细检查",
    ]

    def __init__(
        self,
        agent_type: Optional[AgentType] = None,
        enable_hermes: Optional[bool] = None,
    ):
        """
        初始化 RouterAgent

        Args:
            agent_type: 指定 Agent 类型（覆盖配置）
            enable_hermes: 是否启用 Hermes（覆盖配置）
        """
        # 配置优先级：参数 > 环境变量 > 默认值
        self.agent_type = agent_type or AgentType(settings.agent.type)
        self.enable_hermes = enable_hermes if enable_hermes is not None else settings.hermes.enabled

        # 初始化各 Agent 实例（懒加载）
        self._langgraph_agent: Optional[RDSAgent] = None
        self._hermes_agent: Optional[HermesAgent] = None
        self._diagnostic_agent: Optional[DiagnosticAgent] = None
        self._skill_executor: Optional[SkillExecutor] = None
        self._classifier: Optional[QuestionClassifier] = None

        logger.info(
            f"RouterAgent 初始化完成: type={self.agent_type}, "
            f"hermes_enabled={self.enable_hermes}"
        )

    def _get_langgraph_agent(self) -> RDSAgent:
        """获取 LangGraph Agent（懒加载）"""
        if self._langgraph_agent is None:
            self._langgraph_agent = get_agent()
        return self._langgraph_agent

    def _get_hermes_agent(self) -> HermesAgent:
        """获取 Hermes Agent（懒加载）"""
        if self._hermes_agent is None:
            self._hermes_agent = get_hermes_agent()
        return self._hermes_agent

    def _get_diagnostic_agent(self) -> DiagnosticAgent:
        """获取 Diagnostic Agent（懒加载）"""
        if self._diagnostic_agent is None:
            self._diagnostic_agent = get_diagnostic_agent()
        return self._diagnostic_agent

    def _get_skill_executor(self) -> SkillExecutor:
        """获取 Skill 执行器（懒加载）"""
        if self._skill_executor is None:
            self._skill_executor = get_skill_executor()
        return self._skill_executor

    def _get_classifier(self) -> QuestionClassifier:
        """获取问题分类器（懒加载）"""
        if self._classifier is None:
            self._classifier = get_classifier()
        return self._classifier

    def evaluate_complexity(
        self,
        message: str,
        intent: Optional[IntentType] = None,
    ) -> ComplexityLevel:
        """
        评估任务复杂度

        Args:
            message: 用户输入消息
            intent: 已识别的意图（可选）

        Returns:
            复杂度级别
        """
        message_lower = message.lower()

        # 1. 检查是否需要完整巡检
        for keyword in self.FULL_INSPECTION_KEYWORDS:
            if keyword in message_lower:
                logger.info(f"检测到完整巡检关键词: {keyword}")
                return ComplexityLevel.COMPLEX

        # 2. 如果意图未识别，进行快速意图识别
        if intent is None:
            intent = self._quick_intent_classify(message)

        # 3. 根据意图映射复杂度
        base_complexity = self.INTENT_COMPLEXITY_MAP.get(
            intent, ComplexityLevel.SIMPLE
        )

        # 4. 根据额外特征调整复杂度
        if base_complexity == ComplexityLevel.MEDIUM:
            # 检查是否需要深度分析
            for kw in self.DEEP_ANALYSIS_KEYWORDS:
                if kw in message_lower:
                    logger.info(f"检测到深度分析关键词: {kw}")
                    return ComplexityLevel.COMPLEX

        logger.info(f"复杂度评估: intent={intent}, complexity={base_complexity}")
        return base_complexity

    def _quick_intent_classify(self, message: str) -> IntentType:
        """快速意图分类（仅关键词匹配）"""
        message_lower = message.lower()
        max_score = 0
        best_intent = IntentType.GENERAL_CHAT

        for intent_type, keywords in INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in message_lower)
            if score > max_score:
                max_score = score
                best_intent = intent_type

        logger.info(f"快速意图识别: intent={best_intent}, score={max_score}")
        return best_intent

    def select_agent(
        self,
        message: str,
        complexity: Optional[ComplexityLevel] = None,
        intent: Optional[IntentType] = None,
    ) -> Tuple[AgentType, Optional[SkillType]]:
        """
        选择合适的 Agent（三层路由）

        Args:
            message: 用户消息
            complexity: 已评估的复杂度（可选）
            intent: 已识别的意图（可选）

        Returns:
            Tuple[AgentType, Optional[SkillType]]
            - Agent 类型
            - 如果是 SKILL，返回对应的 SkillType
        """
        # Step 1: 三层问题分类
        classifier = self._get_classifier()
        question_category, skill_type = classifier.classify(message)

        logger.info(
            f"问题分类: category={question_category.value}, "
            f"skill_type={skill_type.value if skill_type else None}"
        )

        # Step 2: 根据问题分类选择执行路径
        # SIMPLE_QA -> Hermes + Knowledge
        if question_category == QuestionCategory.SIMPLE_QA:
            if self.enable_hermes:
                logger.info("SIMPLE_QA -> Hermes")
                return AgentType.HERMES, None
            else:
                logger.info("SIMPLE_QA -> LangGraph (Hermes 禁用)")
                return AgentType.LANGGRAPH, None

        # SOP_SKILL -> Skills/SOP 执行
        if question_category == QuestionCategory.SOP_SKILL:
            logger.info(f"SOP_SKILL -> Skill: {skill_type.value}")
            return AgentType.SKILL, skill_type

        # GENERAL -> 根据复杂度决定
        # 复杂度评估
        if complexity is None:
            complexity = self.evaluate_complexity(message, intent)

        # 检查完整巡检
        if complexity == ComplexityLevel.COMPLEX:
            logger.info("GENERAL -> Diagnostic (复杂任务)")
            return AgentType.DIAGNOSTIC, None

        # 默认使用 LangGraph 自主规划
        logger.info("GENERAL -> LangGraph")
        return AgentType.LANGGRAPH, None

    def invoke(
        self,
        message: str,
        thread_id: Optional[str] = None,
        instance: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        执行请求（三层路由）

        Args:
            message: 用户消息
            thread_id: 会话 ID（仅 LangGraph 使用）
            instance: 目标实例

        Returns:
            执行结果，包含 response, agent_type, question_category 等字段
        """
        # 1. 三层问题分类
        classifier = self._get_classifier()
        question_category, skill_type = classifier.classify(message)

        # 2. 选择 Agent
        complexity = self.evaluate_complexity(message)
        agent_type, resolved_skill_type = self.select_agent(message, complexity)

        # 使用分类结果的 skill_type
        if resolved_skill_type is None and skill_type is not None:
            resolved_skill_type = skill_type

        # 3. 初始化结果
        result: Dict[str, Any] = {
            "agent_type": agent_type.value,
            "question_category": question_category.value,
            "complexity": complexity.value,
            "message": message,
        }

        # 4. 根据选择执行
        try:
            if agent_type == AgentType.SKILL:
                # Skills/SOP 执行
                skill_result = self._execute_skill(
                    message, resolved_skill_type, instance
                )
                result["response"] = self._format_skill_report(skill_result)
                result["skill_result"] = {
                    "skill_type": resolved_skill_type.value if resolved_skill_type else "",
                    "root_cause": skill_result.get("root_cause"),
                    "progress": skill_result.get("progress"),
                }

            elif agent_type == AgentType.HERMES:
                # Hermes Agent 执行
                agent = self._get_hermes_agent()
                response = agent.invoke(message)
                result["response"] = response.get("response", "")
                result["tool_calls"] = response.get("tool_calls", [])

            elif agent_type == AgentType.DIAGNOSTIC:
                # DiagnosticAgent 执行
                agent = self._get_diagnostic_agent()
                # 提取实例名称
                instance_name = instance or self._extract_instance(message)
                if instance_name:
                    diag_result = agent.full_inspection(instance_name)
                    result["response"] = self._format_diagnostic_report(diag_result)
                    result["diagnostic_result"] = {
                        "instance_name": diag_result.instance_name,
                        "overall_status": diag_result.overall_status.value,
                        "overall_score": diag_result.overall_score,
                        "critical_count": len(diag_result.critical_issues),
                        "warning_count": len(diag_result.warnings),
                    }
                else:
                    # 没有实例名称，回退到 LangGraph
                    logger.warning("复杂诊断缺少实例名称，回退到 LangGraph")
                    agent = self._get_langgraph_agent()
                    state = agent.invoke(message, thread_id)
                    result["agent_type"] = AgentType.LANGGRAPH.value
                    result["response"] = state.get("response", "")

            else:  # LANGGRAPH
                # LangGraph Agent 执行
                agent = self._get_langgraph_agent()
                state = agent.invoke(message, thread_id)
                result["response"] = state.get("response", "")
                result["intent"] = state.get("intent", "").value if state.get("intent") else ""
                result["target_instance"] = state.get("target_instance", "")
                result["thread_id"] = thread_id

        except Exception as e:
            logger.error(f"Agent 执行失败: {e}")
            result["error"] = str(e)
            result["response"] = f"处理请求时发生错误: {str(e)}"

        return result

    def _execute_skill(
        self,
        message: str,
        skill_type: Optional[SkillType],
        instance: Optional[str] = None,
    ) -> SkillState:
        """执行 Skill

        Args:
            message: 用户消息
            skill_type: Skill 类型
            instance: 目标实例

        Returns:
            SkillState 执行结果
        """
        if skill_type is None:
            logger.warning("Skill 类型未识别，回退到 LangGraph")
            agent = self._get_langgraph_agent()
            state = agent.invoke(message)
            # 转换为 SkillState 格式
            return {
                "skill_type": "",
                "sop_name": "",
                "instance_name": "",
                "context": {},
                "step_results": [],
                "current_step": 0,
                "progress": 0,
                "conclusion": state.get("response", ""),
                "root_cause": None,
                "key_findings": [],
                "recommendations": [],
                "error": None,
            }

        # 提取实例名称
        instance_name = instance or self._extract_instance(message)
        if not instance_name:
            logger.warning("Skill 缺少实例名称")
            return {
                "skill_type": skill_type.value,
                "sop_name": "",
                "instance_name": "",
                "context": {},
                "step_results": [],
                "current_step": 0,
                "progress": 0,
                "conclusion": "请指定实例名称",
                "root_cause": None,
                "key_findings": [],
                "recommendations": [],
                "error": "缺少实例名称",
            }

        # 执行 Skill
        executor = self._get_skill_executor()
        result = executor.execute(skill_type, instance_name)

        return result

    def _format_skill_report(self, skill_result: SkillState) -> str:
        """格式化 Skill 报告"""
        if skill_result is None:
            return "Skill 执行未能生成结果"

        # 使用 conclusion 或生成默认报告
        if skill_result.get("conclusion"):
            return skill_result["conclusion"]

        lines = [
            f"## Skill 分析报告: {skill_result.get('skill_type', '')}",
            f"- 实例: {skill_result.get('instance_name', '')}",
            f"- SOP: {skill_result.get('sop_name', '')}",
            f"- 进度: {skill_result.get('progress', 0)}%",
            "",
        ]

        # 根因
        root_cause = skill_result.get("root_cause")
        if root_cause:
            lines.append("### 根因定位")
            lines.append(root_cause)
            lines.append("")

        # 关键发现
        key_findings = skill_result.get("key_findings", [])
        if key_findings:
            lines.append("### 关键发现")
            for finding in key_findings:
                lines.append(finding)
            lines.append("")

        # 优化建议
        recommendations = skill_result.get("recommendations", [])
        if recommendations:
            lines.append("### 优化建议")
            for rec in recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        # 错误
        error = skill_result.get("error")
        if error:
            lines.append("### 错误")
            lines.append(error)

        return "\n".join(lines)

    def chat(self, message: str, thread_id: Optional[str] = None) -> str:
        """
        简化的聊天接口

        Args:
            message: 用户消息
            thread_id: 会话 ID

        Returns:
            响应字符串
        """
        result = self.invoke(message, thread_id)
        return result.get("response", "无法生成响应")

    def stream(self, message: str, thread_id: Optional[str] = None):
        """
        流式执行

        Args:
            message: 用户消息
            thread_id: 会话 ID
        """
        # 三层分类
        classifier = self._get_classifier()
        question_category, skill_type = classifier.classify(message)

        # 选择 Agent
        complexity = self.evaluate_complexity(message)
        agent_type, resolved_skill_type = self.select_agent(message, complexity)

        if resolved_skill_type is None and skill_type is not None:
            resolved_skill_type = skill_type

        if agent_type == AgentType.SKILL:
            # Skill 执行（不支持流式，直接返回结果）
            skill_result = self._execute_skill(message, resolved_skill_type)
            yield {"agent": "skill", "result": skill_result}

        elif agent_type == AgentType.HERMES:
            agent = self._get_hermes_agent()
            for chunk in agent.stream(message):
                yield {"agent": "hermes", "chunk": chunk}

        elif agent_type == AgentType.DIAGNOSTIC:
            agent = self._get_diagnostic_agent()
            instance_name = self._extract_instance(message)
            if instance_name:
                for event in agent.stream(instance_name):
                    yield {"agent": "diagnostic", "event": event}
            else:
                # 回退
                agent = self._get_langgraph_agent()
                for event in agent.stream(message, thread_id):
                    yield {"agent": "langgraph", "event": event}

        else:  # LANGGRAPH
            agent = self._get_langgraph_agent()
            for event in agent.stream(message, thread_id):
                yield {"agent": "langgraph", "event": event}

    def reset(self, thread_id: str) -> None:
        """
        重置会话状态

        Args:
            thread_id: 会话 ID
        """
        # LangGraph Agent 重置
        if self._langgraph_agent:
            self._langgraph_agent.reset(thread_id)

        # Hermes Agent 清空历史
        if self._hermes_agent:
            self._hermes_agent.clear_history()

        logger.info(f"会话已重置: {thread_id}")

    def _extract_instance(self, message: str) -> Optional[str]:
        """从消息中提取实例名称"""
        import re

        # 匹配模式：db-xxx, inst-xxx, 或 "实例xxx"
        patterns = [
            r"(db-[a-zA-Z0-9_-]+)",
            r"(inst-[a-zA-Z0-9_-]+)",
            r"实例\s*[\"']?([a-zA-Z0-9_-]+)[\"']?",
            r"([a-zA-Z0-9_-]+)\s*实例",
        ]

        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                return match.group(1)

        return None

    def _format_diagnostic_report(self, result) -> str:
        """格式化诊断报告"""
        if result is None:
            return "诊断未能生成结果"

        lines = [
            f"## 诊断报告: {result.instance_name}",
            f"- 整体状态: {result.overall_status.value}",
            f"- 健康分数: {result.overall_score}/100",
            "",
            "### 严重问题:",
        ]

        for issue in result.critical_issues:
            lines.append(f"- {issue}")

        lines.append("")
        lines.append("### 警告:")
        for warning in result.warnings:
            lines.append(f"- {warning}")

        lines.append("")
        lines.append("### 优化建议:")
        for suggestion in result.suggestions:
            lines.append(f"- {suggestion}")

        return "\n".join(lines)


# 全局 RouterAgent 实例
_router_agent: Optional[RouterAgent] = None


def get_router_agent(
    agent_type: Optional[AgentType] = None,
    enable_hermes: Optional[bool] = None,
) -> RouterAgent:
    """
    获取 RouterAgent 实例（全局单例）

    Args:
        agent_type: 指定 Agent 类型
        enable_hermes: 是否启用 Hermes

    Returns:
        RouterAgent 实例
    """
    global _router_agent
    if _router_agent is None:
        _router_agent = RouterAgent(agent_type=agent_type, enable_hermes=enable_hermes)
    return _router_agent


def create_router_agent(
    agent_type: AgentType = AgentType.AUTO,
    enable_hermes: bool = True,
) -> RouterAgent:
    """
    创建新的 RouterAgent 实例

    Args:
        agent_type: Agent 类型
        enable_hermes: 是否启用 Hermes

    Returns:
        新的 RouterAgent 实例
    """
    return RouterAgent(agent_type=agent_type, enable_hermes=enable_hermes)


class IterationConfig:
    """迭代配置"""

    def __init__(
        self,
        strategy: IterationStrategy = IterationStrategy.BALANCED,
        max_iterations: int = 5,
        min_quality_score: float = 0.7,
        target_quality_score: float = 0.9,
        enable_reflection: bool = True,
        enable_memory: bool = True,
        reflection_depth: int = 2,
    ):
        """初始化迭代配置"""
        self.strategy = strategy
        self.max_iterations = max_iterations
        self.min_quality_score = min_quality_score
        self.target_quality_score = target_quality_score
        self.enable_reflection = enable_reflection
        self.enable_memory = enable_memory
        self.reflection_depth = reflection_depth


class IterativeRouterAgent(RouterAgent):
    """支持自我迭代的 RouterAgent

    在 RouterAgent 三层路由基础上，增加自我迭代改进机制：
    1. 执行 Agent（Hermes/LangGraph/Diagnostic/Skill）
    2. 评估执行结果（ResultEvaluator）
    3. 反思分析（ReflectionEngine）
    4. 应用改进建议
    5. 迭代执行直到达到质量阈值或满足终止条件

    特点：
    - 支持多种迭代策略（NONE/CONSERVATIVE/AGGRESSIVE/BALANCED）
    - 记忆系统存储执行历史和学习
    - 反思机制分析问题和改进方向
    """

    def __init__(
        self,
        agent_type: Optional[AgentType] = None,
        enable_hermes: Optional[bool] = None,
        iteration_config: Optional[IterationConfig] = None,
    ):
        """初始化迭代 RouterAgent

        Args:
            agent_type: Agent 类型
            enable_hermes: 是否启用 Hermes
            iteration_config: 迭代配置
        """
        super().__init__(agent_type=agent_type, enable_hermes=enable_hermes)

        # 迭代配置
        self.iteration_config = iteration_config or IterationConfig()

        # 迭代组件
        self._iteration_loop: Optional[IterationLoop] = None
        self._evaluator: Optional[ResultEvaluator] = None
        self._reflection_engine: Optional[ReflectionEngine] = None
        self._memory: Optional[AgentMemory] = None

        # 初始化迭代组件
        self._init_iteration_components()

        logger.info(
            f"IterativeRouterAgent initialized: "
            f"strategy={self.iteration_config.strategy}, "
            f"max_iterations={self.iteration_config.max_iterations}"
        )

    def _init_iteration_components(self) -> None:
        """初始化迭代组件"""
        # 迭代循环
        self._iteration_loop = IterationLoop(
            max_iterations=self.iteration_config.max_iterations,
            strategy=self.iteration_config.strategy,
            min_quality_score=self.iteration_config.min_quality_score,
        )

        # 评估器
        self._evaluator = ResultEvaluator()

        # 反思引擎
        if self.iteration_config.enable_reflection:
            self._reflection_engine = ReflectionEngine(
                depth=self.iteration_config.reflection_depth
            )

        # 记忆系统
        if self.iteration_config.enable_memory:
            self._memory = AgentMemory(enable_learning=True)

    def invoke_with_iteration(
        self,
        message: str,
        thread_id: Optional[str] = None,
        instance: Optional[str] = None,
    ) -> Dict[str, Any]:
        """带自我迭代的执行

        执行流程：
        1. 初始化迭代循环
        2. 执行 Agent
        3. 评估结果
        4. 反思分析
        5. 检查终止条件
        6. 应用改进（如果继续）
        7. 返回最佳结果

        Args:
            message: 用户消息
            thread_id: 会话 ID
            instance: 目标实例

        Returns:
            包含迭代过程的执行结果
        """
        # 重置迭代循环
        self._iteration_loop.reset()

        # 初始化结果
        result: Dict[str, Any] = {
            "message": message,
            "iteration_enabled": True,
            "iterations": [],
        }

        # 执行迭代
        iteration = 0
        last_response = ""
        last_evaluation: Optional[EvaluationResult] = None
        last_reflection: Optional[ReflectionResult] = None

        while True:
            iteration_start_time = time.time()

            # 1. 准备上下文（包含反思建议）
            context = {}
            if iteration > 0 and last_reflection:
                context["reflection"] = last_reflection.to_prompt_context()
                context["improvements"] = last_reflection.improvements
            if self.iteration_config.enable_memory and iteration > 0:
                context["memory"] = self._memory.get_context_for_iteration(iteration)

            # 2. 执行 Agent
            agent_result = self.invoke(message, thread_id, instance)
            response = agent_result.get("response", "")
            agent_type = agent_result.get("agent_type", "")

            # 3. 评估结果
            evaluation = self._evaluator.evaluate(
                response=response,
                query=message,
                tool_results=agent_result.get("tool_calls"),
                iteration=iteration,
            )

            # 记录评估到记忆
            if self.iteration_config.enable_memory:
                self._memory.add_evaluation_memory(
                    iteration=iteration,
                    score=evaluation.score,
                    passed=evaluation.passed,
                    criteria={cs.criterion.value: cs.score for cs in evaluation.criterion_scores},
                    query=message,
                )

            # 4. 反思分析
            if self.iteration_config.enable_reflection:
                reflection = self._reflection_engine.reflect(
                    query=message,
                    response=response,
                    evaluation=evaluation,
                    iteration=iteration,
                    context=context,
                )

                # 记录反思到记忆
                if self.iteration_config.enable_memory:
                    self._memory.add_reflection_memory(
                        iteration=iteration,
                        analysis=reflection.analysis,
                        issues=reflection.issues,
                        improvements=reflection.improvements,
                        query=message,
                    )

                last_reflection = reflection

            # 5. 记录迭代
            iteration_time_ms = (time.time() - iteration_start_time) * 1000
            self._iteration_loop.record_iteration(
                iteration=iteration,
                score=evaluation.score,
                response=response,
                time_ms=iteration_time_ms,
            )

            # 记录迭代历史
            result["iterations"].append({
                "iteration": iteration,
                "agent_type": agent_type,
                "score": evaluation.score,
                "passed": evaluation.passed,
                "time_ms": iteration_time_ms,
                "response_preview": response[:200] if response else "",
                "issues": evaluation.issues[:3] if evaluation.issues else [],
                "improvements": last_reflection.improvements[:3] if last_reflection else [],
            })

            # 更新变量
            last_response = response
            last_evaluation = evaluation

            # 6. 检查终止条件
            termination_check = self._iteration_loop.check_termination(
                iteration=iteration,
                evaluation=evaluation,
            )

            if termination_check.should_terminate:
                logger.info(
                    f"Iteration terminated: reason={termination_check.reason.value}, "
                    f"iteration={iteration}, score={evaluation.score:.2f}"
                )
                break

            # 7. 检查是否继续迭代
            if not self._iteration_loop.should_iterate(evaluation):
                break

            iteration += 1

        # 获取迭代结果
        iteration_result = self._iteration_loop.get_result(
            termination_check.reason
        )

        # 构建最终结果
        result["response"] = iteration_result.best_response
        result["best_score"] = iteration_result.best_score
        result["best_iteration"] = iteration_result.best_iteration
        result["total_iterations"] = iteration_result.total_iterations
        result["termination_reason"] = iteration_result.termination_reason.value
        result["total_duration_ms"] = iteration_result.total_duration_ms

        # 如果最后一次迭代是最好的，使用完整的 agent_result
        if iteration_result.best_iteration == iteration:
            result["agent_type"] = agent_result.get("agent_type")
            result["question_category"] = agent_result.get("question_category")
            result["complexity"] = agent_result.get("complexity")
        else:
            # 重新执行获取最佳迭代的完整结果
            # 这里简化处理，使用最后一次的 agent 类型
            result["agent_type"] = agent_result.get("agent_type")
            result["question_category"] = agent_result.get("question_category")
            result["complexity"] = agent_result.get("complexity")

        # 学习（可选）
        if self.iteration_config.enable_memory and iteration > 0:
            patterns = self._memory.learn_from_memories()
            result["learned_patterns"] = patterns

        return result

    def invoke(
        self,
        message: str,
        thread_id: Optional[str] = None,
        instance: Optional[str] = None,
        enable_iteration: bool = False,
    ) -> Dict[str, Any]:
        """执行请求（支持可选迭代）

        Args:
            message: 用户消息
            thread_id: 会话 ID
            instance: 目标实例
            enable_iteration: 是否启用迭代改进

        Returns:
            执行结果
        """
        if enable_iteration:
            return self.invoke_with_iteration(message, thread_id, instance)
        else:
            return super().invoke(message, thread_id, instance)

    def get_iteration_stats(self) -> Dict[str, Any]:
        """获取迭代统计"""
        stats = {}
        if self._evaluator:
            stats["evaluation"] = self._evaluator.get_statistics()
        if self._memory:
            stats["memory"] = self._memory.get_stats()
        return stats

    def reset_iteration(self) -> None:
        """重置迭代状态"""
        if self._iteration_loop:
            self._iteration_loop.reset()
        if self._memory:
            self._memory.reset()
        if self._evaluator:
            self._evaluator.clear_history()
        if self._reflection_engine:
            self._reflection_engine.clear_history()


# 全局 IterativeRouterAgent 实例
_iterative_router_agent: Optional[IterativeRouterAgent] = None


def get_iterative_router_agent(
    agent_type: Optional[AgentType] = None,
    enable_hermes: Optional[bool] = None,
    iteration_config: Optional[IterationConfig] = None,
) -> IterativeRouterAgent:
    """获取迭代 RouterAgent 实例（全局单例）"""
    global _iterative_router_agent
    if _iterative_router_agent is None:
        _iterative_router_agent = IterativeRouterAgent(
            agent_type=agent_type,
            enable_hermes=enable_hermes,
            iteration_config=iteration_config,
        )
    return _iterative_router_agent


def create_iterative_router_agent(
    strategy: IterationStrategy = IterationStrategy.BALANCED,
    max_iterations: int = 5,
    min_quality_score: float = 0.7,
) -> IterativeRouterAgent:
    """创建新的迭代 RouterAgent 实例"""
    config = IterationConfig(
        strategy=strategy,
        max_iterations=max_iterations,
        min_quality_score=min_quality_score,
    )
    return IterativeRouterAgent(iteration_config=config)