"""诊断Agent主类 - 自动化诊断流程。"""

from typing import Optional

from langgraph.graph import END, StateGraph

from rds_agent.diagnostic.state import (
    DiagnosticState,
    DiagnosticType,
    DiagnosticResult,
)
from rds_agent.diagnostic.nodes import (
    initialize_diagnostic,
    connect_instance,
    run_checks,
    analyze_results,
    generate_report,
    cleanup,
    handle_diagnostic_error,
)
from rds_agent.utils.logger import get_logger

logger = get_logger("diagnostic_agent")


class DiagnosticAgent:
    """诊断Agent - 执行自动化诊断流程"""

    def __init__(self):
        """初始化诊断Agent"""
        self.graph = self._build_graph()
        self.app = self.graph.compile()
        logger.info("诊断Agent初始化完成")

    def _build_graph(self) -> StateGraph:
        """构建诊断流程图"""
        graph = StateGraph(DiagnosticState)

        # 添加节点
        graph.add_node("initialize", initialize_diagnostic)
        graph.add_node("connect", connect_instance)
        graph.add_node("checks", run_checks)
        graph.add_node("analyze", analyze_results)
        graph.add_node("report", generate_report)
        graph.add_node("cleanup", cleanup)
        graph.add_node("error", handle_diagnostic_error)

        # 设置入口点
        graph.set_entry_point("initialize")

        # 添加边
        graph.add_conditional_edges(
            "initialize",
            self._route_after_initialize,
            {
                "continue": "connect",
                "error": "error",
            }
        )

        graph.add_conditional_edges(
            "connect",
            self._route_after_connect,
            {
                "success": "checks",
                "error": "error",
            }
        )

        graph.add_edge("checks", "analyze")
        graph.add_edge("analyze", "report")

        graph.add_conditional_edges(
            "report",
            self._route_after_report,
            {
                "success": "cleanup",
                "error": "cleanup",
            }
        )

        graph.add_edge("cleanup", END)
        graph.add_edge("error", END)

        return graph

    def _route_after_initialize(self, state: DiagnosticState) -> str:
        """初始化后的路由"""
        if state.get("error"):
            return "error"
        return "continue"

    def _route_after_connect(self, state: DiagnosticState) -> str:
        """连接后的路由"""
        if state.get("error"):
            return "error"
        return "success"

    def _route_after_report(self, state: DiagnosticState) -> str:
        """报告生成后的路由"""
        # 无论成功失败都清理资源
        return "success"

    def run(
        self,
        instance_name: str,
        diagnostic_type: DiagnosticType = DiagnosticType.FULL_INSPECTION,
    ) -> DiagnosticResult:
        """执行诊断"""
        logger.info(f"开始诊断实例: {instance_name}, 类型: {diagnostic_type}")

        initial_state: DiagnosticState = {
            "target_instance": instance_name,
            "diagnostic_type": diagnostic_type,
            "current_phase": "",
            "check_results": [],
            "diagnostic_result": None,
            "progress": 0,
            "error": None,
            "context": {},
        }

        # 执行流程
        final_state = self.app.invoke(initial_state)

        result = final_state.get("diagnostic_result")

        if result:
            logger.info(f"诊断完成: {result.overall_status}, 分数: {result.overall_score}")
        else:
            logger.error("诊断未能生成结果")

        return result

    def quick_check(self, instance_name: str) -> DiagnosticResult:
        """快速检查"""
        return self.run(instance_name, DiagnosticType.QUICK_CHECK)

    def full_inspection(self, instance_name: str) -> DiagnosticResult:
        """完整巡检"""
        return self.run(instance_name, DiagnosticType.FULL_INSPECTION)

    def performance_diagnosis(self, instance_name: str) -> DiagnosticResult:
        """性能诊断"""
        return self.run(instance_name, DiagnosticType.PERFORMANCE_DIAG)

    def stream(
        self,
        instance_name: str,
        diagnostic_type: DiagnosticType = DiagnosticType.FULL_INSPECTION,
    ):
        """流式执行诊断"""
        logger.info(f"流式诊断: {instance_name}")

        initial_state: DiagnosticState = {
            "target_instance": instance_name,
            "diagnostic_type": diagnostic_type,
            "current_phase": "",
            "check_results": [],
            "diagnostic_result": None,
            "progress": 0,
            "error": None,
            "context": {},
        }

        for event in self.app.stream(initial_state):
            yield event


# 全局诊断Agent实例
_diagnostic_agent: Optional[DiagnosticAgent] = None


def get_diagnostic_agent() -> DiagnosticAgent:
    """获取诊断Agent实例"""
    global _diagnostic_agent
    if _diagnostic_agent is None:
        _diagnostic_agent = DiagnosticAgent()
    return _diagnostic_agent