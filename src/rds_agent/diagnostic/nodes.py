"""诊断Agent节点实现。"""

import json
from datetime import datetime
from typing import Optional

from langchain_core.messages import HumanMessage, AIMessage

from rds_agent.diagnostic.state import (
    DiagnosticState,
    DiagnosticResult,
    DiagnosticType,
    HealthStatus,
    CheckItem,
    CheckCategory,
    DEFAULT_INSPECTION_TEMPLATE,
    QUICK_CHECK_TEMPLATE,
)
from rds_agent.diagnostic.checks import get_check_class, BaseCheck
from rds_agent.data import get_platform_client, MySQLClient, InstanceInfo, ConnectionConfig
from rds_agent.utils.logger import get_logger

logger = get_logger("diagnostic_nodes")


def initialize_diagnostic(state: DiagnosticState) -> DiagnosticState:
    """初始化诊断"""
    logger.info("初始化诊断流程")

    state["current_phase"] = "initialize"
    state["progress"] = 0
    state["check_results"] = []
    state["error"] = None

    # 根据诊断类型选择模板
    diagnostic_type = state.get("diagnostic_type", DiagnosticType.FULL_INSPECTION)

    if diagnostic_type == DiagnosticType.QUICK_CHECK:
        template = QUICK_CHECK_TEMPLATE
    else:
        template = DEFAULT_INSPECTION_TEMPLATE

    state["context"]["template"] = template
    state["context"]["check_items_to_run"] = template.check_items.copy()
    state["context"]["thresholds"] = template.thresholds.copy()

    return state


def connect_instance(state: DiagnosticState) -> DiagnosticState:
    """连接目标实例"""
    logger.info(f"连接实例: {state['target_instance']}")

    state["current_phase"] = "connect"

    try:
        platform_client = get_platform_client()
        instance = platform_client.search_instance_by_name(state["target_instance"])

        if not instance:
            state["error"] = f"未找到实例: {state['target_instance']}"
            state["progress"] = 0
            return state

        # 获取连接配置
        conn_config = platform_client.get_instance_connection(instance.id)
        platform_client.close()

        if not conn_config:
            state["error"] = f"无法获取实例连接配置: {state['target_instance']}"
            state["progress"] = 0
            return state

        # 创建MySQL客户端
        mysql_client = MySQLClient(conn_config)

        state["context"]["instance_info"] = instance
        state["context"]["mysql_client"] = mysql_client
        state["progress"] = 10

    except Exception as e:
        logger.error(f"连接实例失败: {e}")
        state["error"] = str(e)

    return state


def run_checks(state: DiagnosticState) -> DiagnosticState:
    """执行所有检查项"""
    logger.info("执行诊断检查")

    state["current_phase"] = "checks"

    mysql_client = state["context"].get("mysql_client")
    instance_info = state["context"].get("instance_info")
    check_items_to_run = state["context"].get("check_items_to_run", [])
    thresholds = state["context"].get("thresholds", {})

    if not mysql_client:
        state["error"] = "MySQL客户端未初始化"
        return state

    check_results: list[CheckItem] = []

    total_checks = len(check_items_to_run)
    completed = 0

    for check_name in check_items_to_run:
        try:
            check_class = get_check_class(check_name)

            if check_class:
                check = check_class(mysql_client, instance_info)

                # 设置阈值
                if check_name in thresholds:
                    check.set_threshold(thresholds[check_name])

                # 执行检查
                result = check.run()
                check_results.append(result)

                logger.info(f"检查 {check_name}: {result.status} - {result.message}")
            else:
                logger.warning(f"未知的检查项: {check_name}")

            completed += 1
            state["progress"] = 10 + int(80 * completed / total_checks)

        except Exception as e:
            logger.error(f"检查 {check_name} 失败: {e}")
            check_results.append(CheckItem(
                name=check_name,
                category=CheckCategory.INSTANCE_STATUS,
                status=HealthStatus.UNKNOWN,
                score=0,
                message=f"检查失败: {str(e)}",
            ))

    state["check_results"] = check_results
    state["progress"] = 90

    return state


def analyze_results(state: DiagnosticState) -> DiagnosticState:
    """分析检查结果"""
    logger.info("分析诊断结果")

    state["current_phase"] = "analyze"

    check_results = state.get("check_results", [])

    # 计算总分
    total_score = 0
    critical_issues: list[str] = []
    warnings: list[str] = []
    suggestions: list[str] = []

    # 按类别分组统计
    category_scores = {}

    for check in check_results:
        total_score += check.score

        if check.status == HealthStatus.CRITICAL:
            critical_issues.append(f"{check.name}: {check.message}")
            if check.suggestion:
                suggestions.append(check.suggestion)

        elif check.status == HealthStatus.WARNING:
            warnings.append(f"{check.name}: {check.message}")
            if check.suggestion:
                suggestions.append(check.suggestion)

        # 按类别累计
        cat = check.category.value
        if cat not in category_scores:
            category_scores[cat] = []
        category_scores[cat].append(check.score)

    # 平均分
    avg_score = total_score / len(check_results) if check_results else 0

    # 确定整体状态
    if len(critical_issues) > 0:
        overall_status = HealthStatus.CRITICAL
    elif len(warnings) > 0:
        overall_status = HealthStatus.WARNING
    else:
        overall_status = HealthStatus.HEALTHY

    # 生成摘要
    summary = f"健康检查完成，整体状态: {overall_status}, 平均分数: {avg_score:.0f}/100"
    if critical_issues:
        summary += f", 发现{len(critical_issues)}个严重问题"
    if warnings:
        summary += f", {len(warnings)}个警告"

    # 构建诊断结果
    diagnostic_result = DiagnosticResult(
        instance_name=state["target_instance"],
        diagnostic_type=state["diagnostic_type"],
        start_time=datetime.now(),
        overall_status=overall_status,
        overall_score=int(avg_score),
        check_items=check_results,
        summary=summary,
        critical_issues=critical_issues,
        warnings=warnings,
        suggestions=suggestions,
        metadata={
            "category_scores": {k: sum(v)/len(v) for k, v in category_scores.items()},
            "total_checks": len(check_results),
        }
    )

    state["diagnostic_result"] = diagnostic_result
    state["progress"] = 95

    return state


def generate_report(state: DiagnosticState) -> DiagnosticState:
    """生成诊断报告"""
    logger.info("生成诊断报告")

    state["current_phase"] = "report"

    diagnostic_result = state.get("diagnostic_result")

    if not diagnostic_result:
        state["error"] = "诊断结果未生成"
        return state

    # 完成时间
    diagnostic_result.end_time = datetime.now()

    # 在这里可以生成详细报告（后续实现）
    state["context"]["report"] = diagnostic_result.model_dump()

    state["progress"] = 100
    state["current_phase"] = "complete"

    return state


def cleanup(state: DiagnosticState) -> DiagnosticState:
    """清理资源"""
    logger.info("清理诊断资源")

    mysql_client = state["context"].get("mysql_client")

    if mysql_client:
        try:
            mysql_client.close()
        except Exception as e:
            logger.warning(f"关闭MySQL客户端失败: {e}")

    state["context"]["mysql_client"] = None

    return state


def handle_diagnostic_error(state: DiagnosticState) -> DiagnosticState:
    """处理诊断错误"""
    logger.error(f"诊断错误: {state.get('error')}")

    error = state.get("error", "未知错误")

    diagnostic_result = DiagnosticResult(
        instance_name=state["target_instance"],
        diagnostic_type=state["diagnostic_type"],
        start_time=datetime.now(),
        end_time=datetime.now(),
        overall_status=HealthStatus.UNKNOWN,
        overall_score=0,
        summary=f"诊断失败: {error}",
        critical_issues=[error],
        metadata={"error": error},
    )

    state["diagnostic_result"] = diagnostic_result
    state["progress"] = 100

    return state