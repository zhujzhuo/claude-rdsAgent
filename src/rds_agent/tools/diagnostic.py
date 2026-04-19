"""诊断Agent工具 - 将诊断Agent集成到工具层。"""

import json
from typing import Optional

from langchain_core.tools import tool

from rds_agent.diagnostic import (
    get_diagnostic_agent,
    DiagnosticType,
    get_report_generator,
)
from rds_agent.diagnostic.parameter_optimizer import (
    analyze_parameter_optimization,
    get_parameter_recommendations,
)
from rds_agent.utils.logger import get_logger

logger = get_logger("diagnostic_tools")


@tool
def run_full_inspection(instance_name: str) -> str:
    """对MySQL实例执行完整的健康巡检。

    执行全面检查，包括：实例状态、资源使用、连接与会话、性能指标、
    存储引擎、日志监控、安全配置等。

    Args:
        instance_name: 实例名称或ID

    Returns:
        完整诊断报告（JSON格式）
    """
    try:
        logger.info(f"开始完整巡检: {instance_name}")

        agent = get_diagnostic_agent()
        result = agent.full_inspection(instance_name)

        if result:
            # 生成报告
            report_generator = get_report_generator()
            json_report = report_generator.generate_json_report(result)

            return json_report
        else:
            return f"错误: 诊断未能生成结果"

    except Exception as e:
        logger.error(f"完整巡检失败: {instance_name} - {e}")
        return f"错误: 完整巡检失败 - {str(e)}"


@tool
def run_quick_check(instance_name: str) -> str:
    """对MySQL实例执行快速健康检查。

    仅检查关键指标：实例状态、连接数、Buffer Pool命中率、慢查询。

    Args:
        instance_name: 实例名称或ID

    Returns:
        快速检查报告（JSON格式）
    """
    try:
        logger.info(f"开始快速检查: {instance_name}")

        agent = get_diagnostic_agent()
        result = agent.quick_check(instance_name)

        if result:
            report_generator = get_report_generator()
            json_report = report_generator.generate_json_report(result)

            return json_report
        else:
            return f"错误: 快速检查未能生成结果"

    except Exception as e:
        logger.error(f"快速检查失败: {instance_name} - {e}")
        return f"错误: 快速检查失败 - {str(e)}"


@tool
def run_performance_diagnosis(instance_name: str) -> str:
    """对MySQL实例执行性能诊断。

    重点检查性能相关指标：Buffer Pool命中率、慢查询、连接数、锁等待等。

    Args:
        instance_name: 实例名称或ID

    Returns:
        性能诊断报告（JSON格式）
    """
    try:
        logger.info(f"开始性能诊断: {instance_name}")

        agent = get_diagnostic_agent()
        result = agent.performance_diagnosis(instance_name)

        if result:
            report_generator = get_report_generator()
            json_report = report_generator.generate_json_report(result)

            # 添加性能专项分析
            report_data = json.loads(json_report)
            report_data["performance_analysis"] = _extract_performance_summary(result)

            return json.dumps(report_data, ensure_ascii=False, indent=2)
        else:
            return f"错误: 性能诊断未能生成结果"

    except Exception as e:
        logger.error(f"性能诊断失败: {instance_name} - {e}")
        return f"错误: 性能诊断失败 - {str(e)}"


def _extract_performance_summary(result) -> dict:
    """提取性能专项摘要"""
    from rds_agent.diagnostic import CheckCategory

    perf_items = [c for c in result.check_items if c.category == CheckCategory.PERFORMANCE_METRICS]

    summary = {
        "qps": None,
        "buffer_pool_hit_rate": None,
        "slow_query_count": None,
        "issues": [],
    }

    for item in perf_items:
        if item.name == "qps_check":
            summary["qps"] = item.value
        elif item.name == "buffer_pool_hit_rate":
            summary["buffer_pool_hit_rate"] = item.value
        elif item.name == "slow_query_count":
            summary["slow_query_count"] = item.value

        if item.status != "healthy":
            summary["issues"].append({
                "name": item.name,
                "status": item.status,
                "message": item.message,
            })

    return summary


@tool
def run_connection_diagnosis(instance_name: str) -> str:
    """对MySQL实例执行连接诊断。

    检查连接数、活跃会话、锁等待等连接相关问题。

    Args:
        instance_name: 实例名称或ID

    Returns:
        连接诊断报告
    """
    try:
        logger.info(f"开始连接诊断: {instance_name}")

        agent = get_diagnostic_agent()
        result = agent.run(instance_name, DiagnosticType.CONNECTION_DIAG)

        if result:
            report_generator = get_report_generator()
            return report_generator.generate_json_report(result)
        else:
            return f"错误: 连接诊断未能生成结果"

    except Exception as e:
        logger.error(f"连接诊断失败: {instance_name} - {e}")
        return f"错误: 连接诊断失败 - {str(e)}"


@tool
def run_storage_diagnosis(instance_name: str) -> str:
    """对MySQL实例执行存储诊断。

    检查存储容量、表碎片、索引使用等存储相关问题。

    Args:
        instance_name: 实例名称或ID

    Returns:
        存储诊断报告
    """
    try:
        logger.info(f"开始存储诊断: {instance_name}")

        agent = get_diagnostic_agent()
        result = agent.run(instance_name, DiagnosticType.STORAGE_DIAG)

        if result:
            report_generator = get_report_generator()
            json_report = report_generator.generate_json_report(result)

            # 添加存储专项分析
            report_data = json.loads(json_report)
            report_data["storage_analysis"] = _extract_storage_summary(result)

            return json.dumps(report_data, ensure_ascii=False, indent=2)
        else:
            return f"错误: 存储诊断未能生成结果"

    except Exception as e:
        logger.error(f"存储诊断失败: {instance_name} - {e}")
        return f"错误: 存储诊断失败 - {str(e)}"


def _extract_storage_summary(result) -> dict:
    """提取存储专项摘要"""
    from rds_agent.diagnostic import CheckCategory

    storage_items = [c for c in result.check_items if c.category == CheckCategory.STORAGE_ENGINE]

    summary = {
        "storage_used_gb": None,
        "fragmentation_mb": None,
        "fragmented_tables": None,
        "issues": [],
    }

    for item in storage_items:
        if item.name == "storage_capacity":
            if isinstance(item.value, dict):
                summary["storage_used_gb"] = item.value.get("used_gb")
        elif item.name == "fragmentation":
            if isinstance(item.value, dict):
                summary["fragmentation_mb"] = item.value.get("total_fragmentation_mb")
                summary["fragmented_tables"] = item.value.get("fragmented_tables")

        if item.status != "healthy":
            summary["issues"].append({
                "name": item.name,
                "status": item.status,
                "message": item.message,
            })

    return summary


@tool
def get_health_score(instance_name: str) -> str:
    """获取MySQL实例的健康分数。

    快速检查并返回整体健康分数和简要状态。

    Args:
        instance_name: 实例名称或ID

    Returns:
        健康分数和状态摘要
    """
    try:
        agent = get_diagnostic_agent()
        result = agent.quick_check(instance_name)

        if result:
            return json.dumps({
                "instance": instance_name,
                "overall_score": result.overall_score,
                "overall_status": result.overall_status,
                "critical_count": len(result.critical_issues),
                "warning_count": len(result.warnings),
                "summary": result.summary,
            }, ensure_ascii=False, indent=2)
        else:
            return f"错误: 无法获取健康分数"

    except Exception as e:
        return f"错误: {str(e)}"


@tool
def generate_diagnostic_report(instance_name: str, format: str = "txt") -> str:
    """生成MySQL实例的诊断报告文件。

    Args:
        instance_name: 实例名称
        format: 报告格式，txt或json

    Returns:
        报告文件路径
    """
    try:
        agent = get_diagnostic_agent()
        result = agent.full_inspection(instance_name)

        if result:
            report_generator = get_report_generator()
            filepath = report_generator.save_report(result, format=format)

            return json.dumps({
                "instance": instance_name,
                "report_path": str(filepath),
                "format": format,
                "overall_score": result.overall_score,
            }, ensure_ascii=False, indent=2)
        else:
            return f"错误: 无法生成报告"

    except Exception as e:
        return f"错误: {str(e)}"