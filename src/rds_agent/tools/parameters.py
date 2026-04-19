"""参数查询工具。"""

import json
from typing import Optional

from langchain_core.tools import tool

from rds_agent.data import get_platform_client
from rds_agent.data.mysql_client import MySQLClient
from rds_agent.utils.logger import get_logger

logger = get_logger("tools.parameters")


# MySQL关键参数推荐配置
PARAMETER_RECOMMENDATIONS = {
    "innodb_buffer_pool_size": {
        "description": "InnoDB缓冲池大小",
        "recommend_rule": "建议设置为总内存的70-80%",
        "unit": "字节",
    },
    "max_connections": {
        "description": "最大连接数",
        "recommend_rule": "根据应用并发需求设置，一般500-1000",
        "unit": "个",
    },
    "innodb_log_file_size": {
        "description": "InnoDB日志文件大小",
        "recommend_rule": "建议设置为buffer_pool_size的25%",
        "unit": "字节",
    },
    "innodb_flush_log_at_trx_commit": {
        "description": "事务日志刷新策略",
        "recommend_rule": "高安全场景设为1，高性能场景可设为2",
        "values": {"1": "最安全，每次事务都刷新", "2": "每秒刷新", "0": "依赖操作系统"},
    },
    "sync_binlog": {
        "description": "Binlog同步策略",
        "recommend_rule": "高安全场景设为1，高性能场景可设为0",
        "values": {"1": "每次事务都同步", "0": "依赖操作系统"},
    },
    "slow_query_log": {
        "description": "慢查询日志开关",
        "recommend_rule": "建议开启",
        "values": {"ON": "开启", "OFF": "关闭"},
    },
    "long_query_time": {
        "description": "慢查询阈值时间",
        "recommend_rule": "建议设置为1-3秒",
        "unit": "秒",
    },
    "innodb_lock_wait_timeout": {
        "description": "锁等待超时时间",
        "recommend_rule": "默认50秒，可根据业务调整",
        "unit": "秒",
    },
    "max_allowed_packet": {
        "description": "最大数据包大小",
        "recommend_rule": "建议设置为16M或更大",
        "unit": "字节",
    },
    "query_cache_size": {
        "description": "查询缓存大小（MySQL 8.0已废弃）",
        "recommend_rule": "MySQL 5.7可设置，8.0建议关闭",
        "unit": "字节",
    },
    "tmp_table_size": {
        "description": "临时表大小",
        "recommend_rule": "建议与max_heap_table_size一致",
        "unit": "字节",
    },
    "max_heap_table_size": {
        "description": "MEMORY表最大大小",
        "recommend_rule": "根据临时表需求设置",
        "unit": "字节",
    },
    "wait_timeout": {
        "description": "非交互连接超时时间",
        "recommend_rule": "默认8小时，可适当降低",
        "unit": "秒",
    },
    "interactive_timeout": {
        "description": "交互连接超时时间",
        "recommend_rule": "与wait_timeout保持一致",
        "unit": "秒",
    },
}


def _get_mysql_client(instance_name: str) -> tuple[Optional[MySQLClient], str]:
    """获取MySQL客户端的辅助函数"""
    platform_client = get_platform_client()
    instance = platform_client.search_instance_by_name(instance_name)

    if not instance:
        platform_client.close()
        return None, f"错误: 未找到实例 '{instance_name}'"

    conn_config = platform_client.get_instance_connection(instance.id)
    platform_client.close()

    if not conn_config:
        return None, f"错误: 无法获取实例 '{instance_name}' 的连接配置"

    return MySQLClient(conn_config), ""


@tool
def get_parameters(instance_name: str, param_names: Optional[str] = None) -> str:
    """获取MySQL实例的关键参数配置。

    Args:
        instance_name: 实例名称或实例ID
        param_names: 参数名列表（可选，逗号分隔，如"max_connections,innodb_buffer_pool_size"）

    Returns:
        参数配置的JSON字符串，包含当前值和推荐值
    """
    try:
        mysql_client, error = _get_mysql_client(instance_name)
        if error:
            return error

        names = None
        if param_names:
            names = [n.strip() for n in param_names.split(",")]

        parameters = mysql_client.get_parameters(names)
        mysql_client.close()

        result = {
            "instance": instance_name,
            "parameters": [
                {
                    "name": p.name,
                    "current_value": p.value,
                    "description": PARAMETER_RECOMMENDATIONS.get(p.name, {}).get("description", ""),
                    "recommend_rule": PARAMETER_RECOMMENDATIONS.get(p.name, {}).get("recommend_rule", ""),
                    "unit": PARAMETER_RECOMMENDATIONS.get(p.name, {}).get("unit", ""),
                    "analysis": _analyze_parameter(p.name, p.value),
                }
                for p in parameters
            ],
        }

        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"获取参数配置失败: {instance_name} - {e}")
        return f"错误: 获取参数配置失败 - {str(e)}"


def _analyze_parameter(name: str, value: str) -> dict:
    """分析参数配置"""
    analysis = {
        "status": "正常",
        "suggestions": [],
    }

    # 特定参数分析
    if name == "innodb_buffer_pool_size":
        # 转换为GB
        try:
            size_bytes = int(value)
            size_gb = size_bytes / (1024**3)
            if size_gb < 1:
                analysis["status"] = "需优化"
                analysis["suggestions"].append(
                    f"Buffer Pool过小({size_gb:.2f}GB)，建议增大到内存的70-80%"
                )
        except ValueError:
            pass

    elif name == "max_connections":
        try:
            max_conn = int(value)
            if max_conn < 100:
                analysis["status"] = "需优化"
                analysis["suggestions"].append(
                    f"最大连接数较小({max_conn})，建议适当增加"
                )
            elif max_conn > 5000:
                analysis["warnings"] = ["最大连接数过大，注意资源消耗"]
        except ValueError:
            pass

    elif name == "slow_query_log":
        if value.upper() != "ON":
            analysis["status"] = "需优化"
            analysis["suggestions"].append(
                "建议开启慢查询日志以便监控性能问题"
            )

    elif name == "long_query_time":
        try:
            threshold = float(value)
            if threshold > 5:
                analysis["suggestions"].append(
                    f"慢查询阈值较高({threshold}秒)，可能遗漏部分慢查询"
                )
            elif threshold < 0.1:
                analysis["suggestions"].append(
                    "慢查询阈值很低，可能产生大量日志"
                )
        except ValueError:
            pass

    elif name == "innodb_flush_log_at_trx_commit":
        if value == "0":
            analysis["warnings"] = ["设置为0可能丢失最近1秒的事务数据"]
        elif value == "2":
            analysis["notes"] = ["设置为2，操作系统崩溃可能丢失最近1秒数据"]

    return analysis


@tool
def get_all_variables(instance_name: str, variable_type: str = "global") -> str:
    """获取MySQL实例的所有变量（状态变量或系统变量）。

    Args:
        instance_name: 实例名称或实例ID
        variable_type: 变量类型，"status"表示状态变量，"global"表示系统变量

    Returns:
        变量列表的JSON字符串
    """
    try:
        mysql_client, error = _get_mysql_client(instance_name)
        if error:
            return error

        if variable_type == "status":
            variables = mysql_client.get_status_variables()
        else:
            variables = mysql_client.get_system_variables()

        mysql_client.close()

        # 只返回关键变量
        key_variables = {
            "status": [
                "Uptime", "Questions", "Threads_connected", "Threads_running",
                "Innodb_buffer_pool_read_requests", "Innodb_buffer_pool_reads",
                "Com_select", "Com_insert", "Com_update", "Com_delete",
                "Connections", "Aborted_connects",
            ],
            "global": [
                "version", "innodb_buffer_pool_size", "max_connections",
                "slow_query_log", "long_query_time",
            ],
        }

        keys = key_variables.get(variable_type, key_variables["global"])

        result = {
            "instance": instance_name,
            "type": variable_type,
            "total_variables": len(variables),
            "key_variables": {
                k: variables.get(k, "N/A")
                for k in keys
                if k in variables
            },
        }

        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"获取变量失败: {instance_name} - {e}")
        return f"错误: 获取变量失败 - {str(e)}"