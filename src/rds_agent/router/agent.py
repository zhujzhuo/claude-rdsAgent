"""RouterAgent - 三层问题分类路由选择器。"""

from enum import Enum
from typing import Optional, Dict, Any, List, Tuple

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