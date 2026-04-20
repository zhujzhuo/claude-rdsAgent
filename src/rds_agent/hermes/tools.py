"""RDS 工具注册 - 将 RDS Agent 的工具转换为 Hermes Function Calling 格式。

注册的工具包括:
- 实例信息查询
- 性能监控
- SQL 诊断
- 连接诊断
- 存储分析
- 参数查询
- 知识检索
- 诊断执行
"""

from typing import Any, Dict, Optional
import json

from .function_schema import FunctionSchema, ToolRegistry, get_global_registry
from rds_agent.utils.logger import get_logger

logger = get_logger("hermes_tools")


# ============================================================
# 工具 Handler 实现
# ============================================================

def _get_instance_info(instance_name: str) -> Dict[str, Any]:
    """获取实例信息"""
    from rds_agent.tools.instance import get_instance_info_tool
    try:
        result = get_instance_info_tool.invoke({"instance_name": instance_name})
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _get_performance_metrics(instance_name: str, metric_type: str = "all") -> Dict[str, Any]:
    """获取性能指标"""
    from rds_agent.tools.performance import get_performance_tool
    try:
        result = get_performance_tool.invoke({
            "instance_name": instance_name,
            "metric_type": metric_type,
        })
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _analyze_sql(instance_name: str, sql_text: Optional[str] = None) -> Dict[str, Any]:
    """分析 SQL"""
    from rds_agent.tools.sql import get_sql_tool
    try:
        result = get_sql_tool.invoke({
            "instance_name": instance_name,
            "sql_text": sql_text,
        })
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _check_connections(instance_name: str) -> Dict[str, Any]:
    """检查连接状态"""
    from rds_agent.tools.connection import get_connection_tool
    try:
        result = get_connection_tool.invoke({"instance_name": instance_name})
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _analyze_storage(instance_name: str, analyze_type: str = "overview") -> Dict[str, Any]:
    """分析存储空间"""
    from rds_agent.tools.storage import get_storage_tool
    try:
        result = get_storage_tool.invoke({
            "instance_name": instance_name,
            "analyze_type": analyze_type,
        })
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _get_parameters(instance_name: str, parameter_name: Optional[str] = None) -> Dict[str, Any]:
    """获取参数配置"""
    from rds_agent.tools.parameters import get_parameters_tool
    try:
        result = get_parameters_tool.invoke({
            "instance_name": instance_name,
            "parameter_name": parameter_name,
        })
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _search_knowledge(query: str, top_k: int = 3) -> Dict[str, Any]:
    """搜索知识库"""
    from rds_agent.tools.knowledge import get_knowledge_tool
    try:
        result = get_knowledge_tool.invoke({
            "query": query,
            "top_k": top_k,
        })
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _run_diagnostic(instance_name: str, diagnostic_type: str = "quick_check") -> Dict[str, Any]:
    """执行诊断"""
    from rds_agent.diagnostic.agent import get_diagnostic_agent, DiagnosticType
    try:
        agent = get_diagnostic_agent()
        type_mapping = {
            "quick_check": DiagnosticType.QUICK_CHECK,
            "full_inspection": DiagnosticType.FULL_INSPECTION,
            "performance_diag": DiagnosticType.PERFORMANCE_DIAG,
        }
        diag_type = type_mapping.get(diagnostic_type, DiagnosticType.QUICK_CHECK)
        result = agent.run(instance_name, diag_type)
        if result:
            return {
                "success": True,
                "data": {
                    "overall_score": result.overall_score,
                    "overall_status": result.overall_status.value if hasattr(result.overall_status, 'value') else result.overall_status,
                    "critical_issues": result.critical_issues,
                    "warnings": result.warnings,
                    "suggestions": result.suggestions,
                }
            }
        return {"success": False, "error": "诊断未能生成结果"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# 工具 Schema 定义 (Hermes/OpenAI 格式)
# ============================================================

RDS_TOOL_SCHEMAS: list[FunctionSchema] = [
    FunctionSchema(
        name="get_instance_info",
        description="获取 MySQL 实例的基本信息，包括版本、规格、部署架构等",
        parameters={
            "instance_name": {
                "type": "string",
                "description": "实例名称，如 db-prod-01",
            }
        },
        required=["instance_name"],
        handler=_get_instance_info,
    ),

    FunctionSchema(
        name="get_performance_metrics",
        description="获取 MySQL 实例的性能监控指标，包括 QPS、连接数、慢查询等",
        parameters={
            "instance_name": {
                "type": "string",
                "description": "实例名称",
            },
            "metric_type": {
                "type": "string",
                "description": "指标类型: all, qps, connections, slow_queries, io",
                "enum": ["all", "qps", "connections", "slow_queries", "io"],
            }
        },
        required=["instance_name"],
        handler=_get_performance_metrics,
    ),

    FunctionSchema(
        name="analyze_sql",
        description="分析 MySQL 实例的 SQL 执行情况，包括慢 SQL、执行计划分析",
        parameters={
            "instance_name": {
                "type": "string",
                "description": "实例名称",
            },
            "sql_text": {
                "type": "string",
                "description": "要分析的 SQL 文本 (可选，不提供则分析实例上的慢 SQL)",
            }
        },
        required=["instance_name"],
        handler=_analyze_sql,
    ),

    FunctionSchema(
        name="check_connections",
        description="检查 MySQL 实例的连接状态，包括活跃连接数、锁等待、会话详情",
        parameters={
            "instance_name": {
                "type": "string",
                "description": "实例名称",
            }
        },
        required=["instance_name"],
        handler=_check_connections,
    ),

    FunctionSchema(
        name="analyze_storage",
        description="分析 MySQL 实例的存储空间使用情况，包括表大小、索引、碎片",
        parameters={
            "instance_name": {
                "type": "string",
                "description": "实例名称",
            },
            "analyze_type": {
                "type": "string",
                "description": "分析类型: overview, tables, indexes, fragmentation",
                "enum": ["overview", "tables", "indexes", "fragmentation"],
            }
        },
        required=["instance_name"],
        handler=_analyze_storage,
    ),

    FunctionSchema(
        name="get_parameters",
        description="获取 MySQL 实例的参数配置，支持查询特定参数或全部参数",
        parameters={
            "instance_name": {
                "type": "string",
                "description": "实例名称",
            },
            "parameter_name": {
                "type": "string",
                "description": "参数名称 (可选，不提供则返回关键参数)",
            }
        },
        required=["instance_name"],
        handler=_get_parameters,
    ),

    FunctionSchema(
        name="search_knowledge",
        description="搜索 MySQL 运维知识库，获取相关文档和建议",
        parameters={
            "query": {
                "type": "string",
                "description": "搜索关键词或问题",
            },
            "top_k": {
                "type": "integer",
                "description": "返回结果数量，默认 3",
            }
        },
        required=["query"],
        handler=_search_knowledge,
    ),

    FunctionSchema(
        name="run_diagnostic",
        description="执行 MySQL 实例的自动化诊断检查，生成健康评分和建议",
        parameters={
            "instance_name": {
                "type": "string",
                "description": "实例名称",
            },
            "diagnostic_type": {
                "type": "string",
                "description": "诊断类型: quick_check (快速), full_inspection (完整), performance_diag (性能)",
                "enum": ["quick_check", "full_inspection", "performance_diag"],
            }
        },
        required=["instance_name"],
        handler=_run_diagnostic,
    ),
]


# ============================================================
# 工具注册函数
# ============================================================

def register_rds_tools(registry: ToolRegistry) -> None:
    """
    注册所有 RDS 工具到指定的 ToolRegistry

    Args:
        registry: ToolRegistry 实例
    """
    for schema in RDS_TOOL_SCHEMAS:
        registry.register(schema)
        logger.info(f"Registered RDS tool: {schema.name}")

    logger.info(f"Total RDS tools registered: {registry.count()}")


def get_rds_tool_registry() -> ToolRegistry:
    """
    获取包含所有 RDS 工具的 ToolRegistry

    Returns:
        初始化了 RDS 工具的 ToolRegistry
    """
    registry = ToolRegistry()
    register_rds_tools(registry)
    return registry


def register_tools_to_global() -> None:
    """注册工具到全局注册中心"""
    registry = get_global_registry()
    register_rds_tools(registry)