"""工具层模块 - 各种诊断和查询工具。"""

# 实例信息工具
from rds_agent.tools.instance import (
    get_instance_list,
    get_instance_info,
    get_mysql_version,
)

# 性能监控工具
from rds_agent.tools.performance import (
    get_performance_metrics,
    get_innodb_status,
)

# SQL诊断工具
from rds_agent.tools.sql import (
    get_slow_queries,
    analyze_processlist,
)

# 连接诊断工具
from rds_agent.tools.connection import (
    get_connection_status,
    get_lock_info,
)

# 存储分析工具
from rds_agent.tools.storage import (
    get_storage_usage,
    get_table_stats,
    get_index_usage,
)

# 参数查询工具
from rds_agent.tools.parameters import (
    get_parameters,
    get_all_variables,
)

# 知识库检索工具
from rds_agent.tools.knowledge import (
    search_knowledge,
    search_mysql_performance_knowledge,
    search_mysql_troubleshooting_knowledge,
    search_mysql_parameter_knowledge,
)

# 诊断Agent工具
from rds_agent.tools.diagnostic import (
    run_full_inspection,
    run_quick_check,
    run_performance_diagnosis,
    run_connection_diagnosis,
    run_storage_diagnosis,
    get_health_score,
    generate_diagnostic_report,
)

# 工具基类
from rds_agent.tools.base import (
    ToolResult,
    BaseRDSTool,
    register_tool,
    get_tool,
    list_tools,
    get_all_tools,
)

__all__ = [
    # 实例工具
    "get_instance_list",
    "get_instance_info",
    "get_mysql_version",
    # 性能工具
    "get_performance_metrics",
    "get_innodb_status",
    # SQL工具
    "get_slow_queries",
    "analyze_processlist",
    # 连接工具
    "get_connection_status",
    "get_lock_info",
    # 存储工具
    "get_storage_usage",
    "get_table_stats",
    "get_index_usage",
    # 参数工具
    "get_parameters",
    "get_all_variables",
    # 知识库工具
    "search_knowledge",
    "search_mysql_performance_knowledge",
    "search_mysql_troubleshooting_knowledge",
    "search_mysql_parameter_knowledge",
    # 诊断工具
    "run_full_inspection",
    "run_quick_check",
    "run_performance_diagnosis",
    "run_connection_diagnosis",
    "run_storage_diagnosis",
    "get_health_score",
    "generate_diagnostic_report",
    # 基类
    "ToolResult",
    "BaseRDSTool",
    "register_tool",
    "get_tool",
    "list_tools",
    "get_all_tools",
]


def get_all_langchain_tools() -> list:
    """获取所有LangChain工具列表"""
    from langchain_core.tools import Tool

    tools = [
        # Phase 1: 智能问答工具
        get_instance_list,
        get_instance_info,
        get_mysql_version,
        get_performance_metrics,
        get_innodb_status,
        get_slow_queries,
        analyze_processlist,
        get_connection_status,
        get_lock_info,
        get_storage_usage,
        get_table_stats,
        get_index_usage,
        get_parameters,
        get_all_variables,
        search_knowledge,
        search_mysql_performance_knowledge,
        search_mysql_troubleshooting_knowledge,
        search_mysql_parameter_knowledge,
        # Phase 2: 诊断工具
        run_full_inspection,
        run_quick_check,
        run_performance_diagnosis,
        run_connection_diagnosis,
        run_storage_diagnosis,
        get_health_score,
        generate_diagnostic_report,
    ]
    return tools