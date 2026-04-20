"""RouterAgent - 双 Agent 自动路由选择器。"""

from enum import Enum
from typing import Optional, Dict, Any, List

from rds_agent.core.agent import RDSAgent, get_agent
from rds_agent.core.state import IntentType
from rds_agent.hermes.agent import HermesAgent, get_hermes_agent
from rds_agent.diagnostic.agent import DiagnosticAgent, get_diagnostic_agent
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

    LANGGRAPH = "langgraph"
    HERMES = "hermes"
    DIAGNOSTIC = "diagnostic"
    AUTO = "auto"  # 自动选择


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
    """双 Agent 路由选择器 - 根据任务复杂度自动选择 Agent"""

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
    ) -> AgentType:
        """
        选择合适的 Agent

        Args:
            message: 用户消息
            complexity: 已评估的复杂度（可选）
            intent: 已识别的意图（可选）

        Returns:
            推荐的 Agent 类型
        """
        # 配置优先模式
        if self.agent_type != AgentType.AUTO:
            logger.info(f"配置指定 Agent: {self.agent_type}")
            # 如果配置指定的是 hermes，但任务是复杂诊断，仍需使用 diagnostic
            if self.agent_type == AgentType.HERMES:
                temp_complexity = complexity or self.evaluate_complexity(message, intent)
                if temp_complexity == ComplexityLevel.COMPLEX:
                    logger.info("复杂任务强制使用 DiagnosticAgent")
                    return AgentType.DIAGNOSTIC
            return self.agent_type

        # Hermes 未启用时，默认使用 LangGraph
        if not self.enable_hermes:
            logger.info("Hermes 未启用，使用 LangGraph")
            temp_complexity = complexity or self.evaluate_complexity(message, intent)
            if temp_complexity == ComplexityLevel.COMPLEX:
                return AgentType.DIAGNOSTIC
            return AgentType.LANGGRAPH

        # 自动评估复杂度
        if complexity is None:
            complexity = self.evaluate_complexity(message, intent)

        # 根据复杂度选择 Agent
        agent_mapping = {
            ComplexityLevel.SIMPLE: AgentType.HERMES,      # 简单任务 -> Hermes（快速）
            ComplexityLevel.MEDIUM: AgentType.LANGGRAPH,   # 中等任务 -> LangGraph
            ComplexityLevel.COMPLEX: AgentType.DIAGNOSTIC,  # 复杂任务 -> Diagnostic
        }

        selected = agent_mapping[complexity]
        logger.info(f"自动选择 Agent: {selected} (complexity={complexity})")

        return selected

    def invoke(
        self,
        message: str,
        thread_id: Optional[str] = None,
        instance: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        执行请求（自动路由）

        Args:
            message: 用户消息
            thread_id: 会话 ID（仅 LangGraph 使用）
            instance: 目标实例

        Returns:
            执行结果，包含 response, agent_type, complexity 等字段
        """
        # 1. 评估复杂度并选择 Agent
        complexity = self.evaluate_complexity(message)
        agent_type = self.select_agent(message, complexity)

        # 2. 根据选择执行
        result: Dict[str, Any] = {
            "agent_type": agent_type.value,
            "complexity": complexity.value,
            "message": message,
        }

        try:
            if agent_type == AgentType.HERMES:
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
        complexity = self.evaluate_complexity(message)
        agent_type = self.select_agent(message, complexity)

        if agent_type == AgentType.HERMES:
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